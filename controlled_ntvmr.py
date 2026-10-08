#!/usr/bin/env python3
"""Budgeted, resumable NTVMR document collector and offline P52 sample."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://ntvmr.uni-muenster.de/community/vmr/api"
OSIS = re.compile(r"^[1-3]?[A-Za-z][A-Za-z0-9]*\.[1-9][0-9]*\.[1-9][0-9]*$")
OSIS_CHAPTER = re.compile(r"^[1-3]?[A-Za-z][A-Za-z0-9]*\.[1-9][0-9]*$")
NT_BOOKS = ("Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor",
            "Gal", "Eph", "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim",
            "Titus", "Phlm", "Heb", "Jas", "1Pet", "2Pet", "1John", "2John",
            "3John", "Jude", "Rev")
BOOK_ORDER = {book: position for position, book in enumerate(NT_BOOKS, 1)}
# Additional book markers observed in retained catalogue contents reports.
# Markers remain source metadata and never establish verse presence.
CONTENTS_BOOK_MARKERS = frozenset(NT_BOOKS) | {"Gen", "Exod", "Num", "Deut", "Ps", "3Macc"}
SCHEMA = """
PRAGMA foreign_keys=ON;
PRAGMA user_version=12;
CREATE TABLE IF NOT EXISTS source_response (
 id INTEGER PRIMARY KEY, endpoint TEXT NOT NULL, url TEXT NOT NULL,
 params_json TEXT NOT NULL, status_code INTEGER NOT NULL, headers_json TEXT NOT NULL,
 body TEXT NOT NULL, body_sha256 TEXT NOT NULL, retrieved_at TEXT NOT NULL,
 origin TEXT NOT NULL CHECK(origin IN ('http','fixture')));
CREATE INDEX IF NOT EXISTS response_lookup ON source_response(endpoint,params_json,id);
CREATE TABLE IF NOT EXISTS request_attempt (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, endpoint TEXT NOT NULL,
 params_json TEXT NOT NULL, attempted_at TEXT NOT NULL,
 response_id INTEGER REFERENCES source_response(id), failure TEXT);
CREATE TABLE IF NOT EXISTS collection_job (
 run_id TEXT NOT NULL, doc_id INTEGER NOT NULL,
 stage TEXT NOT NULL CHECK(stage IN ('metadata','coverage')),
 state TEXT NOT NULL CHECK(state IN ('pending','success','empty','failed','blocked')),
 response_id INTEGER REFERENCES source_response(id), attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, updated_at TEXT NOT NULL, PRIMARY KEY(run_id,doc_id,stage));
CREATE TABLE IF NOT EXISTS document_metadata (
 doc_id INTEGER PRIMARY KEY, response_id INTEGER NOT NULL REFERENCES source_response(id),
 ga_num TEXT, primary_name TEXT, source_lang TEXT NOT NULL,
 origin_date_json TEXT, origin_notation TEXT,
 date_status TEXT NOT NULL CHECK(date_status IN ('valid','unknown','invalid')),
 date_min INTEGER, date_max INTEGER,
 CHECK((date_status='valid' AND date_min IS NOT NULL AND date_max IS NOT NULL
        AND date_min>0 AND date_max>=date_min) OR
       (date_status!='valid' AND date_min IS NULL AND date_max IS NULL)));
CREATE TABLE IF NOT EXISTS coverage_index (
 doc_id INTEGER NOT NULL, osis_ref TEXT NOT NULL, page_id INTEGER NOT NULL,
 response_id INTEGER NOT NULL REFERENCES source_response(id),
 state TEXT NOT NULL DEFAULT 'candidate' CHECK(state IN ('candidate','reviewed')),
 PRIMARY KEY(doc_id,osis_ref,page_id));
CREATE TABLE IF NOT EXISTS discovery_job (
 run_id TEXT NOT NULL, osis_ref TEXT NOT NULL, ga_num TEXT NOT NULL,
 lang_filter TEXT NOT NULL, state TEXT NOT NULL
 CHECK(state IN ('pending','success','empty','incomplete','failed','blocked')),
 response_id INTEGER REFERENCES source_response(id), reported_count INTEGER,
 returned_count INTEGER, error TEXT, updated_at TEXT NOT NULL,
 PRIMARY KEY(run_id,osis_ref,ga_num,lang_filter));
CREATE TABLE IF NOT EXISTS discovery_candidate (
 run_id TEXT NOT NULL, osis_ref TEXT NOT NULL, ga_num_query TEXT NOT NULL,
 lang_filter TEXT NOT NULL, doc_id INTEGER NOT NULL, response_id INTEGER NOT NULL
 REFERENCES source_response(id), ga_num TEXT, primary_name TEXT, source_lang TEXT,
 review_state TEXT NOT NULL DEFAULT 'unreviewed'
 CHECK(review_state IN ('unreviewed','eligible','excluded','uncertain')),
 review_reason TEXT, raw_json TEXT NOT NULL,
 PRIMARY KEY(run_id,osis_ref,ga_num_query,lang_filter,doc_id),
 FOREIGN KEY(run_id,osis_ref,ga_num_query,lang_filter)
 REFERENCES discovery_job(run_id,osis_ref,ga_num,lang_filter));
CREATE TABLE IF NOT EXISTS catalogue_scope (
 run_id TEXT PRIMARY KEY, requested_ids_json TEXT NOT NULL,
 index_ref TEXT, page_limit INTEGER NOT NULL CHECK(page_limit>0),
 state TEXT NOT NULL CHECK(state IN ('pending','success','empty','incomplete','failed','blocked')),
 response_id INTEGER REFERENCES source_response(id), reported_count INTEGER,
 returned_count INTEGER, error TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalogue_candidate (
 run_id TEXT NOT NULL REFERENCES catalogue_scope(run_id),
 doc_id INTEGER NOT NULL, response_id INTEGER NOT NULL REFERENCES source_response(id),
 ga_num TEXT, primary_name TEXT, source_lang TEXT, raw_json TEXT NOT NULL,
 PRIMARY KEY(run_id,doc_id));
CREATE TABLE IF NOT EXISTS candidate_review (
 id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL,
 source_response_id INTEGER NOT NULL REFERENCES source_response(id),
 decision TEXT NOT NULL CHECK(decision IN ('retain','exclude','uncertain')),
 source_type TEXT NOT NULL CHECK(source_type IN
 ('greek_manuscript','printed_edition','other','uncertain')),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0),
 reviewed_at TEXT NOT NULL,
 CHECK((decision='retain' AND source_type='greek_manuscript') OR
       (decision='exclude' AND source_type IN ('printed_edition','other')) OR
       (decision='uncertain' AND source_type='uncertain')));
CREATE INDEX IF NOT EXISTS candidate_review_latest ON candidate_review(doc_id,id);
CREATE TABLE IF NOT EXISTS physical_witness (
 witness_id TEXT PRIMARY KEY CHECK(length(trim(witness_id))>0),
 label TEXT NOT NULL CHECK(length(trim(label))>0), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS witness_assignment (
 id INTEGER PRIMARY KEY, doc_id INTEGER NOT NULL,
 witness_id TEXT REFERENCES physical_witness(witness_id),
 source_response_id INTEGER NOT NULL REFERENCES source_response(id),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0), assigned_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS witness_assignment_latest ON witness_assignment(doc_id,id);
CREATE TABLE IF NOT EXISTS edition_inventory (
 inventory_id TEXT PRIMARY KEY CHECK(length(trim(inventory_id))>0),
 edition TEXT NOT NULL CHECK(length(trim(edition))>0),
 scope TEXT NOT NULL CHECK(length(trim(scope))>0),
 source_citation TEXT NOT NULL CHECK(length(trim(source_citation))>0),
 reuse_terms TEXT NOT NULL CHECK(length(trim(reuse_terms))>0),
 mapping_citation TEXT, reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0),
 manifest_sha256 TEXT NOT NULL, manifest_json TEXT NOT NULL,
 imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS edition_verse (
 inventory_id TEXT NOT NULL REFERENCES edition_inventory(inventory_id),
 osis_ref TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>0),
 book TEXT NOT NULL, book_order INTEGER NOT NULL CHECK(book_order BETWEEN 1 AND 27),
 chapter INTEGER NOT NULL CHECK(chapter>0), verse INTEGER NOT NULL CHECK(verse>0),
 editorial_status TEXT NOT NULL CHECK(editorial_status IN
 ('main','bracketed','omitted','uncertain')),
 editorial_note TEXT, mapping_note TEXT,
 PRIMARY KEY(inventory_id,osis_ref), UNIQUE(inventory_id,ordinal),
 UNIQUE(inventory_id,book,chapter,verse));
CREATE TABLE IF NOT EXISTS edition_verse_map (
 inventory_id TEXT NOT NULL, osis_ref TEXT NOT NULL,
 ntvmr_ref TEXT NOT NULL,
 PRIMARY KEY(inventory_id,osis_ref,ntvmr_ref),
 FOREIGN KEY(inventory_id,osis_ref) REFERENCES edition_verse(inventory_id,osis_ref));
CREATE TABLE IF NOT EXISTS coverage_review (
 id INTEGER PRIMARY KEY, inventory_id TEXT NOT NULL, osis_ref TEXT NOT NULL,
 ntvmr_ref TEXT NOT NULL, doc_id INTEGER NOT NULL, page_id INTEGER NOT NULL,
 witness_id TEXT NOT NULL REFERENCES physical_witness(witness_id),
 identity_assignment_id INTEGER NOT NULL REFERENCES witness_assignment(id),
 index_response_id INTEGER NOT NULL REFERENCES source_response(id),
 status TEXT NOT NULL CHECK(status IN ('partial','full','uncertain','rejected','withdrawn')),
 evidence_type TEXT NOT NULL CHECK(evidence_type IN
 ('checked_image','reviewed_transcription','catalogue_content_statement')),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0), reviewed_at TEXT NOT NULL,
 FOREIGN KEY(inventory_id,osis_ref,ntvmr_ref)
 REFERENCES edition_verse_map(inventory_id,osis_ref,ntvmr_ref));
CREATE INDEX IF NOT EXISTS coverage_review_latest ON coverage_review
 (inventory_id,osis_ref,doc_id,page_id,ntvmr_ref,id);
CREATE TABLE IF NOT EXISTS physical_absence_review (
 id INTEGER PRIMARY KEY, inventory_id TEXT NOT NULL, osis_ref TEXT NOT NULL,
 witness_id TEXT NOT NULL REFERENCES physical_witness(witness_id),
 decision TEXT NOT NULL CHECK(decision IN ('absent','uncertain','withdrawn')),
 evidence_type TEXT NOT NULL CHECK(evidence_type IN
 ('checked_image','reviewed_transcription')),
 source_locator TEXT NOT NULL CHECK(length(trim(source_locator))>0),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0), reviewed_at TEXT NOT NULL,
 FOREIGN KEY(inventory_id,osis_ref) REFERENCES edition_verse(inventory_id,osis_ref));
CREATE INDEX IF NOT EXISTS physical_absence_latest ON physical_absence_review
 (inventory_id,osis_ref,witness_id,id);
CREATE TABLE IF NOT EXISTS writing_unit (
 unit_id TEXT PRIMARY KEY CHECK(length(trim(unit_id))>0),
 witness_id TEXT NOT NULL REFERENCES physical_witness(witness_id),
 label TEXT NOT NULL CHECK(length(trim(label))>0),
 kind TEXT NOT NULL CHECK(kind IN ('original','correction','supplement','uncertain')),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0), created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS coverage_unit_assignment (
 id INTEGER PRIMARY KEY, coverage_review_id INTEGER NOT NULL REFERENCES coverage_review(id),
 unit_id TEXT REFERENCES writing_unit(unit_id),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0), assigned_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS coverage_unit_latest ON coverage_unit_assignment(coverage_review_id,id);
CREATE TABLE IF NOT EXISTS date_assessment (
 id INTEGER PRIMARY KEY, unit_id TEXT NOT NULL REFERENCES writing_unit(unit_id),
 status TEXT NOT NULL CHECK(status IN ('valid','unknown','invalid')),
 date_min INTEGER, date_max INTEGER, original_notation TEXT NOT NULL
 CHECK(length(trim(original_notation))>0),
 citation TEXT NOT NULL CHECK(length(trim(citation))>0),
 consulted_on TEXT NOT NULL, reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0),
 recorded_at TEXT NOT NULL,
 UNIQUE(unit_id,id),
 CHECK((status='valid' AND date_min IS NOT NULL AND date_max IS NOT NULL
        AND date_min>0 AND date_max>=date_min) OR
       (status!='valid' AND date_min IS NULL AND date_max IS NULL)));
CREATE INDEX IF NOT EXISTS date_assessment_unit ON date_assessment(unit_id,id);
CREATE TABLE IF NOT EXISTS date_selection (
 id INTEGER PRIMARY KEY, unit_id TEXT NOT NULL REFERENCES writing_unit(unit_id),
 policy_id TEXT NOT NULL CHECK(length(trim(policy_id))>0), assessment_id INTEGER,
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0), selected_at TEXT NOT NULL,
 FOREIGN KEY(unit_id,assessment_id) REFERENCES date_assessment(unit_id,id));
CREATE INDEX IF NOT EXISTS date_selection_latest ON date_selection(unit_id,policy_id,id);
CREATE TABLE IF NOT EXISTS ranking_snapshot (
 inventory_id TEXT NOT NULL, osis_ref TEXT NOT NULL, policy_id TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('success','empty')),
 candidate_count INTEGER NOT NULL CHECK(candidate_count>=0), computed_at TEXT NOT NULL,
 PRIMARY KEY(inventory_id,osis_ref,policy_id),
 FOREIGN KEY(inventory_id,osis_ref) REFERENCES edition_verse(inventory_id,osis_ref));
CREATE TABLE IF NOT EXISTS ranking_entry (
 inventory_id TEXT NOT NULL, osis_ref TEXT NOT NULL, policy_id TEXT NOT NULL,
 scenario TEXT NOT NULL CHECK(scenario IN ('optimistic','pessimistic')),
 rank INTEGER NOT NULL CHECK(rank>0), witness_id TEXT NOT NULL REFERENCES physical_witness(witness_id),
 unit_id TEXT NOT NULL REFERENCES writing_unit(unit_id),
 assessment_id INTEGER NOT NULL REFERENCES date_assessment(id),
 selection_id INTEGER NOT NULL REFERENCES date_selection(id),
 coverage_review_id INTEGER NOT NULL REFERENCES coverage_review(id),
 date_min INTEGER NOT NULL, date_max INTEGER NOT NULL, event_year INTEGER NOT NULL,
 PRIMARY KEY(inventory_id,osis_ref,policy_id,scenario,rank),
 UNIQUE(inventory_id,osis_ref,policy_id,scenario,witness_id),
 FOREIGN KEY(inventory_id,osis_ref,policy_id)
 REFERENCES ranking_snapshot(inventory_id,osis_ref,policy_id));
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def encoded(params):
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys=ON")
    if con.execute("SELECT 1 FROM sqlite_master WHERE name='verse_earliest'").fetchone():
        con.close()
        raise ValueError("Use a separate versioned database, not the legacy snapshot")
    con.executescript(SCHEMA)
    return con


def archive_legacy(source, target):
    if target.exists():
        raise ValueError(f"Archive already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source.resolve().as_posix()}?mode=ro", uri=True) as original:
        with sqlite3.connect(target) as backup:
            original.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Backup integrity check failed")
            tables = [row[0] for row in original.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for table in tables:
                # Table names come from SQLite's own schema, not user input.
                query = 'SELECT count(*) FROM "' + table.replace('"', '""') + '"'
                if original.execute(query).fetchone()[0] != backup.execute(query).fetchone()[0]:
                    raise ValueError(f"Backup row-count mismatch in {table}")


class ContractError(ValueError):
    pass


class RunStopped(RuntimeError):
    pass


class AccessBlocked(RunStopped):
    pass


class JobFailure(RuntimeError):
    pass


def parse_coverage(payload, doc_id, *, books=None):
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ContractError("Coverage response lacks success status")
    data = payload.get("data")
    contents = data.get("indexContents") if isinstance(data, dict) else None
    if not isinstance(contents, dict) or contents.get("docID") != doc_id:
        raise ContractError("Coverage response has missing or wrong docID")
    entries = contents.get("indexContent")
    if entries == "":
        return []  # Captured empty report shape; no presence or absence assertion.
    if not isinstance(entries, list):
        raise ContractError("Coverage indexContent is not a list")
    result = []
    for index, entry in enumerate(entries):
        if index == 0 and isinstance(entry, str):
            continue  # The summary range is not verse evidence.
        if not isinstance(entry, dict) or entry.get("docID") != doc_id:
            raise ContractError("Malformed coverage entry")
        ref, page = entry.get("osisID"), entry.get("pageID")
        book_marker = (isinstance(ref, str) and ref in CONTENTS_BOOK_MARKERS and
                       type(entry.get("indexContent")) is int and
                       entry["indexContent"] % 1000000 == 0)
        if not isinstance(ref, str) or not (OSIS.fullmatch(ref) or
                                            OSIS_CHAPTER.fullmatch(ref) or
                                            book_marker):
            raise ContractError(f"Invalid OSIS reference: {ref!r}")
        if type(page) is not int or page <= 0:
            raise ContractError(f"Invalid page ID: {page!r}")
        if book_marker or OSIS_CHAPTER.fullmatch(ref):
            # Book and chapter markers remain in the raw response; never infer verses.
            continue
        if books is not None and ref.split(".")[0] not in books:
            continue  # Preserve other books in the raw response, outside this scope.
        result.append((ref, page))
    return list(dict.fromkeys(result))


def parse_metadata(payload, doc_id):
    """Validate the observed manuscript/get shape without treating its date as selected."""
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ContractError("Metadata response lacks success status")
    data = payload.get("data")
    manuscript = data.get("manuscript") if isinstance(data, dict) else None
    if not isinstance(manuscript, dict) or type(manuscript.get("docID")) is not int or manuscript["docID"] != doc_id:
        raise ContractError("Metadata response has missing or wrong manuscript docID")
    for field in ("gaNum", "primaryName"):
        if field in manuscript and type(manuscript[field]) not in (str, int):
            raise ContractError(f"Metadata manuscript has invalid {field}")
    if not any(manuscript.get(field) not in (None, "") for field in ("gaNum", "primaryName")):
        raise ContractError("Metadata manuscript has no catalogue name")
    if not isinstance(manuscript.get("lang"), str):
        raise ContractError("Metadata manuscript has no language string")
    origin = manuscript.get("originYear")
    notation = origin.get("content") if isinstance(origin, dict) else None
    if notation is not None and type(notation) not in (str, int):
        raise ContractError("Metadata originYear content is not a string or integer")
    early = origin.get("early") if isinstance(origin, dict) else None
    late = origin.get("late") if isinstance(origin, dict) else None
    if origin is None or (early in (None, 0) and late in (None, 0)):
        date_status = "unknown"
    elif type(early) is int and type(late) is int and 0 < early <= late:
        date_status = "valid"
    else:
        date_status = "invalid"
    return {
        "ga_num": str(manuscript["gaNum"]) if "gaNum" in manuscript else None,
        "primary_name": str(manuscript["primaryName"]) if "primaryName" in manuscript else None,
        "source_lang": manuscript["lang"],
        "origin_date_json": encoded(origin) if origin is not None else None,
        "origin_notation": notation,
        "date_status": date_status,
        "date_min": early if date_status == "valid" else None,
        "date_max": late if date_status == "valid" else None,
    }


def parse_search(payload):
    """Return document rows and the reported count; never assert exhaustiveness."""
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ContractError("Search response lacks success status")
    data = payload.get("data")
    manuscripts = data.get("manuscripts") if isinstance(data, dict) else None
    if not isinstance(manuscripts, dict):
        raise ContractError("Search response lacks manuscripts container")
    count, pagecount = manuscripts.get("count"), manuscripts.get("pagecount")
    if type(count) is not int or count < 0 or type(pagecount) is not int or pagecount < 0:
        raise ContractError("Search count or pagecount is invalid")
    rows = manuscripts.get("manuscript", [] if count == 0 else None)
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ContractError("Search manuscript is not a list or singleton")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get("docID")) is not int or row["docID"] <= 0:
            raise ContractError("Search candidate has invalid docID")
        if row["docID"] in seen:
            raise ContractError("Search contains duplicate docID")
        seen.add(row["docID"])
        for field in ("gaNum", "primaryName"):
            if field in row and type(row[field]) not in (str, int):
                raise ContractError(f"Search candidate has invalid {field}")
        if "lang" in row and not isinstance(row["lang"], str):
            raise ContractError("Search candidate has invalid lang")
    return rows, count


def search_continuation(payload, rows, headers=None, after_doc_id=0):
    """Read the documented root attributes or equivalent response headers."""
    root = payload["data"]["manuscripts"]
    if headers is not None and not isinstance(headers, dict):
        raise ContractError("Search response headers are invalid")
    headers = {key.lower(): value for key, value in (headers or {}).items()}

    def partial_value(value):
        if type(value) is bool:
            return value
        if value in ("true", "false"):
            return value == "true"
        raise ContractError("Search partial flag is invalid")

    flags = [partial_value(container[key]) for container, key in
             ((root, "partial"), (headers, "x-vmr-partial")) if key in container]
    if len(set(flags)) > 1:
        raise ContractError("Search partial attributes and headers disagree")
    partial = flags[0] if flags else False
    cursors = []
    for container, key in ((root, "nextAfterDocID"), (headers, "x-vmr-next-afterdocid")):
        if key not in container:
            continue
        value = container[key]
        if type(value) is int and value > 0:
            cursors.append(value)
        elif isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value):
            cursors.append(int(value))
        else:
            raise ContractError("Search continuation cursor is invalid")
    if len(set(cursors)) > 1:
        raise ContractError("Search continuation attributes and headers disagree")
    if not partial:
        if cursors:
            raise ContractError("Terminal search response has a continuation cursor")
        return None
    if not rows or not cursors:
        raise ContractError("Partial search response lacks rows or continuation cursor")
    cursor = cursors[0]
    if cursor <= after_doc_id or cursor != max(row["docID"] for row in rows):
        raise ContractError("Search continuation cursor does not advance to the last document")
    return cursor


def collect_search_pages(client, params, *, refresh=False, allowed_ids=None):
    """Replay captured pages on resume; publish candidates only after a terminal page.

    Params tracks the current request for the caller's failure checkpoint. Each
    candidate keeps its own page response ID. A refreshed first page cannot be
    combined with older cached continuation pages.
    """
    records, seen, reported, first_response_id = [], set(), 0, 0
    mismatch = False
    while True:
        payload, response_id = client.get_json("metadata/liste/search", params,
            refresh=refresh, min_response_id=first_response_id)
        rows, count = parse_search(payload)
        headers = json.loads(client.con.execute(
            "SELECT headers_json FROM source_response WHERE id=?", (response_id,)).fetchone()[0])
        after_doc_id = int(params.get("afterDocID", 0))
        cursor = search_continuation(payload, rows, headers, after_doc_id)
        ids = {row["docID"] for row in rows}
        if seen & ids or any(doc_id <= after_doc_id for doc_id in ids):
            raise ContractError("Search continuation repeats or goes backwards over document IDs")
        if cursor is not None and allowed_ids is not None and ids - allowed_ids:
            raise ContractError("Partial search returned documents outside the declared scope")
        seen.update(ids)
        records.extend((row, response_id) for row in rows)
        reported += count  # Count is per response, not a declaration of corpus size.
        mismatch = mismatch or count != len(rows)
        first_response_id = first_response_id or response_id
        if cursor is None:
            return records, reported, response_id, mismatch
        params["afterDocID"] = str(cursor)


def retry_after(value, clock=time.time):
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - clock())
        except (TypeError, ValueError, OverflowError):
            return None


def transport(url, params, timeout):
    request = Request(url + "?" + urlencode(params), headers={
        "User-Agent": "EarliestAttestation/0.2 (research collector; project repository)",
        "Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace"), dict(response.headers.items())
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace"), dict(error.headers.items())


class Client:
    def __init__(self, con, run_id, *, base_url=API_BASE, offline=False, budget=0,
                 interval=5.0, jitter=0.25, duration=0, send=transport,
                 sleep=time.sleep, clock=time.monotonic, rng=random.random):
        self.con, self.run_id, self.base_url = con, run_id, base_url.rstrip("/")
        self.offline, self.budget, self.interval, self.jitter = offline, budget, interval, jitter
        self.duration, self.send, self.sleep, self.clock, self.rng = duration, send, sleep, clock, rng
        self.started, self.last_attempt = clock(), None
        self.attempts = con.execute("SELECT count(*) FROM request_attempt WHERE run_id=?", (run_id,)).fetchone()[0]

    def wait(self, delay):
        delay = max(0, delay)
        if self.duration and self.clock() - self.started + delay > self.duration:
            raise RunStopped("Run time budget cannot accommodate wait")
        if delay:
            self.sleep(delay)

    def attempt(self, endpoint, params):
        if self.budget is not None and self.attempts >= self.budget:
            raise RunStopped("Network request budget exhausted")
        if self.last_attempt is not None:
            self.wait(self.interval + self.jitter * self.rng() - (self.clock() - self.last_attempt))
        if self.duration and self.clock() - self.started >= self.duration:
            raise RunStopped("Run time budget exhausted")
        self.last_attempt = self.clock()
        self.attempts += 1
        url = self.base_url + "/" + endpoint.strip("/") + "/"
        args = encoded(params)
        self.con.execute("INSERT INTO request_attempt(run_id,endpoint,params_json,attempted_at) VALUES(?,?,?,?)",
                         (self.run_id, endpoint, args, now()))
        attempt_id = self.con.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.con.commit()
        try:
            status, body, headers = self.send(url, params, 30)
        except (TimeoutError, URLError, OSError) as error:
            self.con.execute("UPDATE request_attempt SET failure=? WHERE id=?", (str(error), attempt_id))
            self.con.commit()
            raise
        self.con.execute("""INSERT INTO source_response(endpoint,url,params_json,status_code,
            headers_json,body,body_sha256,retrieved_at,origin) VALUES(?,?,?,?,?,?,?,?,?)""",
            (endpoint, url, args, status, json.dumps(headers), body,
             hashlib.sha256(body.encode()).hexdigest(), now(), "http"))
        response_id = self.con.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.con.execute("UPDATE request_attempt SET response_id=? WHERE id=?", (response_id, attempt_id))
        self.con.commit()
        return status, body, headers, response_id

    def get_json(self, endpoint, params, *, refresh=False, min_response_id=0):
        if not refresh:
            row = self.con.execute("""SELECT id,body FROM source_response WHERE endpoint=?
              AND url=? AND params_json=? AND status_code BETWEEN 200 AND 299
              AND (origin='http' OR ?) AND id>=? ORDER BY id DESC LIMIT 1""",
              (endpoint, self.base_url + "/" + endpoint.strip("/") + "/", encoded(params),
               self.offline, min_response_id)).fetchone()
            if row:
                if row[1].lstrip().lower().startswith(("<!doctype html", "<html")):
                    raise AccessBlocked(f"Cached HTML block/challenge, response {row[0]}")
                try:
                    return json.loads(row[1]), row[0]
                except json.JSONDecodeError as error:
                    raise ContractError(f"Cached response {row[0]} is invalid JSON") from error
        if self.offline:
            raise RunStopped(f"Offline cache miss: {endpoint} {encoded(params)}")
        for retry in range(3):
            try:
                status, body, headers, response_id = self.attempt(endpoint, params)
            except (TimeoutError, URLError, OSError) as error:
                if retry == 2:
                    raise JobFailure(f"Transport failed after three attempts: {error}") from error
                if self.budget is not None and self.attempts >= self.budget:
                    raise RunStopped(f"Network request budget exhausted after transport failure: {error}") from error
                self.wait(2 ** retry + self.rng())
                continue
            if status in (401, 403):
                raise AccessBlocked(f"Access blocked: HTTP {status}, response {response_id}")
            if status == 429:
                if retry == 2:
                    raise AccessBlocked(f"Repeated HTTP 429, response {response_id}")
                delay_header = next((value for key, value in headers.items() if key.lower() == "retry-after"), None)
                self.wait(retry_after(delay_header) or 60)
                continue
            if status >= 500:
                if retry == 2:
                    raise JobFailure(f"HTTP {status} after three attempts, response {response_id}")
                self.wait(2 ** retry + self.rng())
                continue
            if status < 200 or status >= 300:
                raise JobFailure(f"HTTP {status}, response {response_id}")
            content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "")
            if body.lstrip().lower().startswith(("<!doctype html", "<html")) or "html" in content_type.lower():
                raise AccessBlocked(f"HTML block or unexpected HTML, response {response_id}")
            try:
                return json.loads(body), response_id
            except json.JSONDecodeError as error:
                raise ContractError(f"Invalid JSON, response {response_id}") from error
        raise AssertionError("Retry loop terminated unexpectedly")


def set_job(con, run_id, doc_id, stage, state, response_id=None, error=None):
    con.execute("""INSERT INTO collection_job(run_id,doc_id,stage,state,response_id,error,updated_at)
      VALUES(?,?,?,?,?,?,?) ON CONFLICT(run_id,doc_id,stage) DO UPDATE SET
      state=excluded.state,response_id=excluded.response_id,error=excluded.error,
      updated_at=excluded.updated_at""", (run_id, doc_id, stage, state, response_id, error, now()))
    con.commit()


def metadata_checkpoint_ready(con, doc_id, response_id):
    return response_id is not None and bool(con.execute(
        "SELECT 1 FROM document_metadata WHERE doc_id=? AND response_id=?",
        (doc_id, response_id)).fetchone())


def collect_stage(client, doc_id, stage, *, refresh=False):
    con = client.con
    row = con.execute("SELECT state,response_id FROM collection_job WHERE run_id=? AND doc_id=? AND stage=?",
                      (client.run_id, doc_id, stage)).fetchone()
    metadata_ready = stage != "metadata" or (row and metadata_checkpoint_ready(con, doc_id, row[1]))
    if row and row[0] in ("success", "empty") and metadata_ready and not refresh:
        return row[0]
    blocked = con.execute("""SELECT doc_id,stage,error FROM collection_job
      WHERE run_id=? AND state='blocked' ORDER BY doc_id,stage LIMIT 1""",
      (client.run_id,)).fetchone()
    if blocked:
        raise AccessBlocked(f"Prior document access block is preserved for {blocked[0]} {blocked[1]}: "
                            f"{blocked[2]}; do not automatically retry this run")
    set_job(con, client.run_id, doc_id, stage, "pending")
    endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
    params = {"docID": str(doc_id), "detail": "10" if stage == "metadata" else "long", "format": "json"}
    before = client.attempts
    try:
        payload, response_id = client.get_json(endpoint, params, refresh=refresh)
        if stage == "metadata":
            metadata = parse_metadata(payload, doc_id)
            with con:
                con.execute("""INSERT INTO document_metadata(doc_id,response_id,ga_num,
                    primary_name,source_lang,origin_date_json,origin_notation,date_status,
                    date_min,date_max) VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(doc_id) DO UPDATE SET response_id=excluded.response_id,
                    ga_num=excluded.ga_num,primary_name=excluded.primary_name,
                    source_lang=excluded.source_lang,origin_date_json=excluded.origin_date_json,
                    origin_notation=excluded.origin_notation,date_status=excluded.date_status,
                    date_min=excluded.date_min,date_max=excluded.date_max""",
                    (doc_id, response_id, metadata["ga_num"], metadata["primary_name"],
                     metadata["source_lang"], metadata["origin_date_json"],
                     metadata["origin_notation"], metadata["date_status"],
                     metadata["date_min"], metadata["date_max"]))
            state = "success"
        else:
            entries = parse_coverage(payload, doc_id)
            with con:
                con.execute("DELETE FROM coverage_index WHERE doc_id=?", (doc_id,))
                con.executemany("INSERT INTO coverage_index(doc_id,osis_ref,page_id,response_id) VALUES(?,?,?,?)",
                                [(doc_id, ref, page, response_id) for ref, page in entries])
            state = "success" if entries else "empty"
        set_job(con, client.run_id, doc_id, stage, state, response_id)
        return state
    except (ContractError, RunStopped, JobFailure) as error:
        state = "blocked" if isinstance(error, AccessBlocked) else "pending" if isinstance(error, RunStopped) else "failed"
        latest = con.execute("""SELECT id FROM source_response WHERE endpoint=? AND url=?
           AND params_json=? ORDER BY id DESC LIMIT 1""",
           (endpoint, client.base_url + "/" + endpoint + "/", encoded(params))).fetchone()
        set_job(con, client.run_id, doc_id, stage, state,
                response_id=latest[0] if latest else None, error=str(error))
        raise
    finally:
        con.execute("UPDATE collection_job SET attempts=attempts+? WHERE run_id=? AND doc_id=? AND stage=?",
                    (client.attempts - before, client.run_id, doc_id, stage))
        con.commit()


def search_params(ref, ga_num, lang=None):
    params = {"gaNum": ga_num, "indexContent": ref, "detail": "document",
              "format": "json", "limit": "10"}
    if lang is not None:
        params["lang"] = lang
    return params


def collect_search(client, ref, ga_num, *, lang=None, refresh=False):
    """Persist a bounded named-document lookup as candidates, never verified evidence."""
    if not OSIS.fullmatch(ref) or not ga_num.strip():
        raise ValueError("Search requires one OSIS verse and a nonempty gaNum")
    con = client.con
    key = (client.run_id, ref, ga_num, lang or "")
    prior = con.execute("""SELECT state FROM discovery_job WHERE run_id=? AND osis_ref=?
        AND ga_num=? AND lang_filter=?""", key).fetchone()
    if prior and prior[0] in ("success", "empty") and not refresh:
        return prior[0]
    if prior and prior[0] == "blocked" and not refresh:
        raise AccessBlocked("Prior search access block requires explicit refresh")
    params = search_params(ref, ga_num, lang)
    con.execute("""INSERT INTO discovery_job(run_id,osis_ref,ga_num,lang_filter,state,updated_at)
        VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,osis_ref,ga_num,lang_filter)
        DO UPDATE SET state='pending', error=NULL, updated_at=excluded.updated_at""",
        (*key, "pending", now()))
    con.commit()
    try:
        records, reported, response_id, mismatch = collect_search_pages(client, params, refresh=refresh)
        state = "incomplete" if mismatch else "success" if records else "empty"
        with con:
            con.execute("""DELETE FROM discovery_candidate WHERE run_id=? AND osis_ref=?
                AND ga_num_query=? AND lang_filter=?""", key)
            con.executemany("""INSERT INTO discovery_candidate(run_id,osis_ref,ga_num_query,
                lang_filter,doc_id,response_id,ga_num,primary_name,source_lang,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [
                (*key, row["docID"], page_response_id,
                 str(row["gaNum"]) if "gaNum" in row else None,
                 str(row["primaryName"]) if "primaryName" in row else None,
                 row.get("lang"), encoded(row)) for row, page_response_id in records])
            con.execute("""UPDATE discovery_job SET state=?,response_id=?,reported_count=?,
                returned_count=?,error=?,updated_at=? WHERE run_id=? AND osis_ref=?
                AND ga_num=? AND lang_filter=?""",
                (state, response_id, reported, len(records),
                 "Returned rows differ from reported count" if state == "incomplete" else None,
                 now(), *key))
        return state
    except (ContractError, RunStopped, JobFailure) as error:
        state = "blocked" if isinstance(error, AccessBlocked) else "pending" if isinstance(error, RunStopped) else "failed"
        latest = con.execute("""SELECT id FROM source_response WHERE endpoint=? AND url=?
            AND params_json=? ORDER BY id DESC LIMIT 1""",
            ("metadata/liste/search", client.base_url + "/metadata/liste/search/",
             encoded(params))).fetchone()
        con.execute("""UPDATE discovery_job SET state=?,response_id=?,error=?,updated_at=? WHERE
            run_id=? AND osis_ref=? AND ga_num=? AND lang_filter=?""",
            (state, latest[0] if latest else None, str(error), now(), *key))
        con.commit()
        raise


def record_candidate_review(con, doc_id, source_response_id, decision, source_type,
                            reason, citation, reviewer):
    """Append a document classification; never convert it to verse evidence."""
    if type(doc_id) is not int or doc_id <= 0 or type(source_response_id) is not int or source_response_id <= 0:
        raise ValueError("Review requires positive document and source response IDs")
    allowed = {"retain": "greek_manuscript", "uncertain": "uncertain"}
    if (decision not in ("retain", "exclude", "uncertain") or
        source_type not in ("greek_manuscript", "printed_edition", "other", "uncertain") or
        (decision in allowed and source_type != allowed[decision]) or
        (decision == "exclude" and source_type not in ("printed_edition", "other"))):
        raise ValueError("Review decision and source type are inconsistent")
    if any(not isinstance(value, str) or not value.strip()
           for value in (reason, citation, reviewer)):
        raise ValueError("Review requires a reason, citation, and reviewer")
    linked = con.execute("""SELECT 1 FROM document_metadata WHERE doc_id=? AND response_id=?
        UNION SELECT 1 FROM discovery_candidate WHERE doc_id=? AND response_id=?
        UNION SELECT 1 FROM catalogue_candidate WHERE doc_id=? AND response_id=? LIMIT 1""",
        (doc_id, source_response_id) * 3).fetchone()
    if not linked:
        raise ValueError("Review source response is not linked to this document")
    with con:
        con.execute("""INSERT INTO candidate_review(doc_id,source_response_id,decision,
            source_type,reason,citation,reviewer,reviewed_at) VALUES(?,?,?,?,?,?,?,?)""",
            (doc_id, source_response_id, decision, source_type, reason.strip(),
             citation.strip(), reviewer.strip(), now()))
        review_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    return review_id


def latest_candidate_reviews(con, doc_ids):
    ids = sorted(set(doc_ids))
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = con.execute(f"""SELECT r.doc_id,r.id,r.source_response_id,r.decision,
        r.source_type,r.reason,r.citation,r.reviewer,r.reviewed_at
        FROM candidate_review r JOIN (
          SELECT doc_id,MAX(id) AS id FROM candidate_review
          WHERE doc_id IN ({placeholders}) GROUP BY doc_id
        ) latest ON latest.id=r.id""", ids)
    fields = ("doc_id", "review_id", "review_source_response_id", "review_decision",
              "source_type", "review_reason", "review_citation", "reviewer", "reviewed_at")
    reviews = {row[0]: dict(zip(fields, row)) for row in rows}
    for review in reviews.values():
        source = con.execute("""SELECT endpoint,url,params_json,body_sha256
            FROM source_response WHERE id=?""",
            (review["review_source_response_id"],)).fetchone()
        latest = con.execute("""SELECT body_sha256 FROM source_response WHERE
            endpoint=? AND url=? AND params_json=? AND status_code BETWEEN 200 AND 299
            ORDER BY id DESC LIMIT 1""", source[:3]).fetchone()
        review["review_source_changed"] = latest is not None and latest[0] != source[3]
    return reviews


def record_witness_assignment(con, doc_id, source_response_id, witness_id, label,
                              reason, citation, reviewer):
    """Append a reviewed physical identity link, or an explicit unlink."""
    if type(doc_id) is not int or doc_id <= 0 or type(source_response_id) is not int or source_response_id <= 0:
        raise ValueError("Identity assignment requires positive document and response IDs")
    if any(not isinstance(value, str) or not value.strip()
           for value in (reason, citation, reviewer)):
        raise ValueError("Identity assignment requires reason, citation, and reviewer")
    if witness_id is not None and (not isinstance(witness_id, str) or not witness_id.strip()):
        raise ValueError("Witness ID must be a nonempty string")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise ValueError("Witness label must be a nonempty string")
    if witness_id is None and label is not None:
        raise ValueError("An unlink cannot create a witness label")
    if witness_id is None and not con.execute("""SELECT 1 FROM witness_assignment
        WHERE doc_id=? AND witness_id IS NOT NULL AND id=(
            SELECT MAX(id) FROM witness_assignment WHERE doc_id=?)""",
        (doc_id, doc_id)).fetchone():
        raise ValueError("Document has no current witness link to remove")
    review = latest_candidate_reviews(con, [doc_id]).get(doc_id)
    if not review or review["review_source_response_id"] != source_response_id:
        raise ValueError("Identity assignment requires a document reviewed against this response")
    if witness_id is not None and review["review_decision"] != "retain":
        raise ValueError("A witness link requires a retained document")
    if witness_id is not None and review["review_source_changed"]:
        raise ValueError("Identity assignment requires review of the latest source response")
    if witness_id is not None:
        witness_id = witness_id.strip()
        existing = con.execute("SELECT label FROM physical_witness WHERE witness_id=?",
                               (witness_id,)).fetchone()
        if existing and label is not None and label.strip() != existing[0]:
            raise ValueError("Witness ID already has a different label")
        if not existing and label is None:
            raise ValueError("A new witness ID requires a label")
    with con:
        if witness_id is not None and not existing:
            con.execute("INSERT INTO physical_witness(witness_id,label,created_at) VALUES(?,?,?)",
                        (witness_id.strip(), label.strip(), now()))
        con.execute("""INSERT INTO witness_assignment(doc_id,witness_id,source_response_id,
            reason,citation,reviewer,assigned_at) VALUES(?,?,?,?,?,?,?)""",
            (doc_id, witness_id.strip() if witness_id is not None else None,
             source_response_id, reason.strip(), citation.strip(), reviewer.strip(), now()))
        assignment_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    return assignment_id


def latest_witness_assignments(con, doc_ids, reviews=None):
    ids = sorted(set(doc_ids))
    if not ids:
        return {}
    if reviews is None:
        reviews = latest_candidate_reviews(con, ids)
    placeholders = ",".join("?" for _ in ids)
    rows = con.execute(f"""SELECT a.doc_id,a.id,a.witness_id,w.label,
        a.source_response_id,a.reason,a.citation,a.reviewer,a.assigned_at
        FROM witness_assignment a LEFT JOIN physical_witness w ON w.witness_id=a.witness_id
        JOIN (SELECT doc_id,MAX(id) id FROM witness_assignment
              WHERE doc_id IN ({placeholders}) GROUP BY doc_id) latest ON latest.id=a.id""", ids)
    fields = ("doc_id", "identity_assignment_id", "witness_id", "witness_label",
              "identity_source_response_id", "identity_reason", "identity_citation",
              "identity_reviewer", "identity_assigned_at")
    assignments = {row[0]: dict(zip(fields, row)) for row in rows}
    for assignment in assignments.values():
        review = reviews.get(assignment["doc_id"])
        assignment["identity_review_needed"] = bool(
            not review or review["review_decision"] != "retain" or
            review["review_source_changed"] or
            review["review_source_response_id"] != assignment["identity_source_response_id"])
    return assignments


def witness_identity_report(con):
    """Show current document links, including links requiring renewed review."""
    doc_ids = [row[0] for row in con.execute(
        "SELECT DISTINCT doc_id FROM witness_assignment ORDER BY doc_id")]
    reviews = latest_candidate_reviews(con, doc_ids)
    assignments = latest_witness_assignments(con, doc_ids, reviews)
    witnesses = []
    for witness_id, label in con.execute(
            "SELECT witness_id,label FROM physical_witness ORDER BY witness_id"):
        linked = [assignment for assignment in assignments.values()
                  if assignment["witness_id"] == witness_id]
        witnesses.append({"witness_id": witness_id, "label": label,
                          "current_doc_ids": sorted(row["doc_id"] for row in linked),
                          "review_needed_doc_ids": sorted(
                              row["doc_id"] for row in linked if row["identity_review_needed"])})
    return {"scope": "manually reviewed document-to-physical-witness links",
            "evidence_verified": False,
            "witnesses": witnesses,
            "assignments": [assignments[doc_id] for doc_id in doc_ids]}


def discovery_report(con, run_id):
    jobs = [dict(zip(("osis_ref", "ga_num", "lang_filter", "state", "reported_count",
                      "returned_count"), row)) for row in con.execute("""SELECT osis_ref,ga_num,
        lang_filter,state,reported_count,returned_count FROM discovery_job
        WHERE run_id=? ORDER BY osis_ref,ga_num,lang_filter""", (run_id,))]
    candidates = [dict(zip(("osis_ref", "query_ga_num", "lang_filter", "doc_id",
                            "response_id", "ga_num", "primary_name", "source_lang"), row))
                  for row in con.execute("""SELECT osis_ref,
        ga_num_query,lang_filter,doc_id,response_id,ga_num,primary_name,source_lang
        FROM discovery_candidate WHERE run_id=?
        ORDER BY osis_ref,ga_num_query,lang_filter,doc_id""", (run_id,))]
    reviews = latest_candidate_reviews(con, (row["doc_id"] for row in candidates))
    identities = latest_witness_assignments(con, (row["doc_id"] for row in candidates), reviews)
    for candidate in candidates:
        candidate.update(reviews.get(candidate["doc_id"],
                         {"review_decision": "unreviewed"}))
        candidate.update(identities.get(candidate["doc_id"],
                         {"witness_id": None, "identity_review_needed": None}))
    omissions = [dict(zip(("osis_ref", "query_ga_num", "lang_filter", "doc_id"), row)) for row in con.execute("""
        SELECT DISTINCT j.osis_ref,j.ga_num,j.lang_filter,c.doc_id FROM discovery_job j
        JOIN coverage_index c ON c.osis_ref=j.osis_ref
        WHERE j.run_id=? AND j.ga_num IN (
            SELECT COALESCE(d.ga_num,d.primary_name) FROM discovery_candidate d
            WHERE d.run_id=j.run_id AND d.doc_id=c.doc_id
        ) AND NOT EXISTS (
            SELECT 1 FROM discovery_candidate d WHERE d.run_id=j.run_id
            AND d.osis_ref=j.osis_ref AND d.doc_id=c.doc_id
            AND d.ga_num_query=j.ga_num AND d.lang_filter=j.lang_filter)
        ORDER BY j.osis_ref,j.ga_num,j.lang_filter,c.doc_id""", (run_id,))]
    return {"run_id": run_id, "scope": "named gaNum and single OSIS verse lookups",
            "corpus_complete": False, "discovery_complete": False,
            "reason": "Named lookups remain bounded; continued search completion does not establish exhaustive manuscript discovery",
            "jobs": jobs, "candidates": candidates,
            "indexed_coverage_search_omissions": omissions}


def catalogue_params(doc_ids, index_ref=None, page_limit=200):
    if not doc_ids or any(type(doc) is not int or doc <= 0 for doc in doc_ids):
        raise ValueError("Catalogue scope requires 1 to 20 positive document IDs")
    ids = sorted(set(doc_ids))
    if len(ids) > 20:
        raise ValueError("Catalogue scope requires 1 to 20 positive document IDs")
    if index_ref is not None and not OSIS.fullmatch(index_ref):
        raise ValueError("Catalogue index filter must be one OSIS verse")
    if type(page_limit) is not int or not 1 <= page_limit <= 200:
        raise ValueError("Catalogue page limit must be between 1 and 200")
    params = {"docID": "|".join(map(str, ids)), "detail": "document",
              "format": "json", "limit": str(page_limit)}
    if index_ref is not None:
        params["indexContent"] = index_ref
    return ids, params


def collect_catalogue_scope(client, doc_ids, *, index_ref=None, page_limit=200, refresh=False):
    """Look up a declared finite ID set; preserve its records as unreviewed candidates."""
    ids, params = catalogue_params(doc_ids, index_ref, page_limit)
    con = client.con
    row = con.execute("""SELECT requested_ids_json,index_ref,page_limit,state
        FROM catalogue_scope WHERE run_id=?""", (client.run_id,)).fetchone()
    if row and row[:3] != (encoded(ids), index_ref, page_limit):
        raise ValueError("Run ID already belongs to a different catalogue scope")
    if row and row[3] in ("success", "empty") and not refresh:
        return row[3]
    if row and row[3] == "blocked" and not refresh:
        raise AccessBlocked("Prior catalogue access block requires explicit refresh")
    con.execute("""INSERT INTO catalogue_scope(run_id,requested_ids_json,index_ref,
        page_limit,state,updated_at) VALUES(?,?,?,?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET state='pending',error=NULL,
        updated_at=excluded.updated_at""",
        (client.run_id, encoded(ids), index_ref, page_limit, "pending", now()))
    con.commit()
    try:
        records, reported, response_id, mismatch = collect_search_pages(
            client, params, refresh=refresh, allowed_ids=set(ids))
        returned = {record["docID"] for record, _ in records}
        unexpected = returned - set(ids)
        missing = set(ids) - returned
        incomplete = mismatch or bool(unexpected) or (index_ref is None and bool(missing))
        state = "incomplete" if incomplete else "success" if records else "empty"
        error = None
        if incomplete:
            error = f"count mismatch={mismatch}; missing={sorted(missing)}; unexpected={sorted(unexpected)}"
        with con:
            con.execute("DELETE FROM catalogue_candidate WHERE run_id=?", (client.run_id,))
            con.executemany("""INSERT INTO catalogue_candidate(run_id,doc_id,response_id,
                ga_num,primary_name,source_lang,raw_json) VALUES(?,?,?,?,?,?,?)""", [
                (client.run_id, record["docID"], page_response_id,
                 str(record["gaNum"]) if "gaNum" in record else None,
                 str(record["primaryName"]) if "primaryName" in record else None,
                 record.get("lang"), encoded(record)) for record, page_response_id in records])
            con.execute("""UPDATE catalogue_scope SET state=?,response_id=?,
                reported_count=?,returned_count=?,error=?,updated_at=? WHERE run_id=?""",
                (state, response_id, reported, len(records), error, now(), client.run_id))
        return state
    except (ContractError, RunStopped, JobFailure) as error:
        state = "blocked" if isinstance(error, AccessBlocked) else "pending" if isinstance(error, RunStopped) else "failed"
        latest = con.execute("""SELECT id FROM source_response WHERE endpoint=? AND url=?
            AND params_json=? ORDER BY id DESC LIMIT 1""",
            ("metadata/liste/search", client.base_url + "/metadata/liste/search/",
             encoded(params))).fetchone()
        con.execute("""UPDATE catalogue_scope SET state=?,response_id=?,error=?,
            updated_at=? WHERE run_id=?""",
            (state, latest[0] if latest else None, str(error), now(), client.run_id))
        con.commit()
        raise


def catalogue_report(con, run_id):
    row = con.execute("""SELECT requested_ids_json,index_ref,page_limit,state,
        reported_count,returned_count,error FROM catalogue_scope WHERE run_id=?""",
        (run_id,)).fetchone()
    if not row:
        return None
    requested = json.loads(row[0])
    candidates = [dict(zip(("doc_id", "response_id", "ga_num", "primary_name", "source_lang"), record))
                  for record in con.execute("""SELECT doc_id,response_id,ga_num,primary_name,source_lang
                  FROM catalogue_candidate WHERE run_id=? ORDER BY doc_id""", (run_id,))]
    reviews = latest_candidate_reviews(con, (row["doc_id"] for row in candidates))
    identities = latest_witness_assignments(con, (row["doc_id"] for row in candidates), reviews)
    for candidate in candidates:
        candidate.update(reviews.get(candidate["doc_id"],
                         {"review_decision": "unreviewed"}))
        candidate.update(identities.get(candidate["doc_id"],
                         {"witness_id": None, "identity_review_needed": None}))
    returned = {candidate["doc_id"] for candidate in candidates}
    current = row[3] in ("success", "empty", "incomplete")
    return {"run_id": run_id, "scope": "explicit catalogue document IDs",
            "requested_doc_ids": requested, "index_ref": row[1], "page_limit": row[2],
            "state": row[3], "reported_count": row[4], "returned_count": row[5],
            "not_returned_doc_ids": sorted(set(requested) - returned) if current else None,
            "unexpected_doc_ids": sorted(returned - set(requested)) if current else None,
            "candidate_snapshot_stale": not current,
            "catalogue_lookup_complete": row[3] == "success" and row[1] is None
                and returned == set(requested),
            "corpus_complete": False, "evidence_verified": False,
            "error": row[6], "candidates": candidates}


def scoped_index_report(con, run_id, refs):
    """Invert completed document indexes within one declared catalogue scope."""
    if not refs or any(not OSIS.fullmatch(ref) for ref in refs):
        raise ValueError("Scope checks require individual OSIS verses")
    scope = catalogue_report(con, run_id)
    if not scope:
        raise ValueError("No catalogue scope exists for this run")
    ready, unready = [], []
    if not scope["catalogue_lookup_complete"]:
        return {"run_id": run_id, "state": "incomplete", "reason": "Catalogue ID lookup is incomplete",
                "refs": sorted(set(refs)), "ready_doc_ids": [],
                "unready_doc_ids": scope["requested_doc_ids"], "candidates": {},
                "named_search_omissions": [], "discovery_complete": False}
    for doc_id in scope["requested_doc_ids"]:
        job = con.execute("""SELECT state,response_id FROM collection_job
            WHERE run_id=? AND doc_id=? AND stage='coverage'""", (run_id, doc_id)).fetchone()
        latest = con.execute("""SELECT MAX(response_id) FROM collection_job
            WHERE doc_id=? AND stage='coverage' AND state IN ('success','empty')""",
            (doc_id,)).fetchone()[0]
        mismatched = bool(job and job[1] is not None and con.execute("""
            SELECT 1 FROM coverage_index WHERE doc_id=? AND response_id!=? LIMIT 1""",
            (doc_id, job[1])).fetchone())
        if not job or job[0] not in ("success", "empty") or job[1] != latest or mismatched:
            unready.append(doc_id)
        else:
            ready.append(doc_id)
    candidates = {}
    scope_by_doc = {row["doc_id"]: row for row in scope["candidates"]}
    for ref in sorted(set(refs)):
        candidates[ref] = []
        for doc_id in ready:
            page_ids = [page for (page,) in con.execute("""SELECT page_id FROM
                coverage_index WHERE doc_id=? AND osis_ref=? ORDER BY page_id""",
                (doc_id, ref))]
            if page_ids:
                review = scope_by_doc.get(doc_id, {})
                candidates[ref].append({"doc_id": doc_id, "page_ids": page_ids,
                    "review_decision": review.get("review_decision", "unreviewed"),
                    "review_reason": review.get("review_reason"),
                    "review_source_changed": review.get("review_source_changed")})
    omissions = []
    names = {row["doc_id"]: (row["ga_num"], row["primary_name"])
             for row in scope["candidates"]}
    for ref, records in candidates.items():
        for (query_name, lang_filter, state) in con.execute("""SELECT ga_num,
            lang_filter,state FROM discovery_job WHERE run_id=? AND osis_ref=?""",
            (run_id, ref)):
            if state not in ("success", "empty"):
                continue
            for record in records:
                aliases = names.get(record["doc_id"], ())
                if not any(alias is not None and
                           (alias == query_name or
                            (alias.isdecimal() and query_name.isdecimal()
                             and int(alias) == int(query_name))) for alias in aliases):
                    continue
                hit = con.execute("""SELECT 1 FROM discovery_candidate WHERE
                    run_id=? AND osis_ref=? AND ga_num_query=? AND lang_filter=?
                    AND doc_id=? LIMIT 1""",
                    (run_id, ref, query_name, lang_filter, record["doc_id"])).fetchone()
                if not hit:
                    omissions.append({"osis_ref": ref, "query_ga_num": query_name,
                                      "lang_filter": lang_filter, "doc_id": record["doc_id"]})
    return {"run_id": run_id, "state": "complete" if not unready and not omissions else "incomplete",
            "refs": sorted(set(refs)), "ready_doc_ids": ready,
            "unready_doc_ids": unready, "candidates": candidates,
            "named_search_omissions": omissions,
            "discovery_complete": False,
            "warning": "Index candidates are not verified physical survival; missing index rows are not proof of absence"}


def inventory_ref_parts(ref):
    if not isinstance(ref, str) or not OSIS.fullmatch(ref):
        raise ValueError(f"Inventory requires one OSIS verse, got {ref!r}")
    book, chapter, verse = ref.split(".")
    if book not in BOOK_ORDER:
        raise ValueError(f"Inventory has unknown New Testament book: {book}")
    return book, int(chapter), int(verse)


def validate_inventory(manifest):
    """Validate a cited coordinate list without inferring edition membership."""
    required = {"format_version", "inventory_id", "edition", "scope",
                "source_citation", "reuse_terms", "mapping_citation", "reviewer", "verses"}
    if not isinstance(manifest, dict) or set(manifest) != required or \
            type(manifest.get("format_version")) is not int or manifest["format_version"] != 1:
        raise ValueError("Inventory manifest has an unsupported shape or format version")
    for field in ("inventory_id", "edition", "scope", "source_citation",
                  "reuse_terms", "reviewer"):
        if not isinstance(manifest[field], str) or not manifest[field].strip():
            raise ValueError(f"Inventory requires {field}")
    mapping_citation = manifest["mapping_citation"]
    if mapping_citation is not None and (not isinstance(mapping_citation, str) or
                                         not mapping_citation.strip()):
        raise ValueError("Inventory mapping citation must be nonempty or null")
    verses = manifest["verses"]
    if not isinstance(verses, list) or not verses:
        raise ValueError("Inventory requires a nonempty explicit verse list")
    validated = []
    prior = None
    seen = set()
    for row in verses:
        if not isinstance(row, dict) or not {"osis_ref", "editorial_status", "ntvmr_refs"} <= set(row) or \
                set(row) - {"osis_ref", "editorial_status", "ntvmr_refs", "editorial_note", "mapping_note", "passage_citation"}:
            raise ValueError("Inventory verse has an unsupported shape")
        ref = row["osis_ref"]
        book, chapter, verse = inventory_ref_parts(ref)
        key = (BOOK_ORDER[book], chapter, verse)
        if ref in seen or (prior is not None and key <= prior):
            raise ValueError("Inventory verses must be unique and in numeric canonical order")
        seen.add(ref)
        prior = key
        status = row["editorial_status"]
        if status not in ("main", "bracketed", "omitted", "uncertain"):
            raise ValueError(f"Invalid editorial status at {ref}")
        editorial_note = row.get("editorial_note")
        if editorial_note is not None and (not isinstance(editorial_note, str) or
                                           not editorial_note.strip()):
            raise ValueError(f"Invalid editorial note at {ref}")
        if status != "main" and editorial_note is None:
            raise ValueError(f"Non-main verse requires an editorial note: {ref}")
        passage_citation = row.get("passage_citation")
        if passage_citation is not None and (status != "omitted" or
                not isinstance(passage_citation, str) or not passage_citation.strip()):
            raise ValueError(f"Passage citation must identify an omitted coordinate: {ref}")
        refs = row["ntvmr_refs"]
        if not isinstance(refs, list) or len(refs) != len(set(
                item for item in refs if isinstance(item, str))):
            raise ValueError(f"NTVMR mappings must be a distinct list at {ref}")
        for mapped_ref in refs:
            inventory_ref_parts(mapped_ref)
        mapping_note = row.get("mapping_note")
        if mapping_note is not None and (not isinstance(mapping_note, str) or
                                         not mapping_note.strip()):
            raise ValueError(f"Invalid mapping note at {ref}")
        if refs and mapping_citation is None:
            raise ValueError("Mapped verses require a mapping citation")
        if refs != [ref] and mapping_note is None:
            raise ValueError(f"Unresolved or changed mapping requires a note: {ref}")
        validated.append((ref, book, BOOK_ORDER[book], chapter, verse, status,
                          editorial_note, mapping_note, refs))
    return validated


def import_edition_inventory(con, manifest):
    """Insert an immutable inventory snapshot; corrections use a new ID."""
    rows = validate_inventory(manifest)
    body = encoded(manifest)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    inventory_id = manifest["inventory_id"]
    existing = con.execute("SELECT manifest_sha256 FROM edition_inventory WHERE inventory_id=?",
                           (inventory_id,)).fetchone()
    if existing:
        if existing[0] != digest:
            raise ValueError("Inventory ID already exists with different content; use a new ID")
        return len(rows)
    with con:
        con.execute("""INSERT INTO edition_inventory(inventory_id,edition,scope,
            source_citation,reuse_terms,mapping_citation,reviewer,manifest_sha256,
            manifest_json,imported_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (inventory_id, manifest["edition"], manifest["scope"],
             manifest["source_citation"], manifest["reuse_terms"],
             manifest["mapping_citation"], manifest["reviewer"], digest, body, now()))
        for ordinal, (ref, book, book_order, chapter, verse, status,
                      editorial_note, mapping_note, refs) in enumerate(rows, 1):
            con.execute("""INSERT INTO edition_verse(inventory_id,osis_ref,ordinal,
                book,book_order,chapter,verse,editorial_status,editorial_note,mapping_note)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (inventory_id, ref, ordinal, book, book_order, chapter, verse,
                 status, editorial_note, mapping_note))
            con.executemany("""INSERT INTO edition_verse_map(inventory_id,osis_ref,ntvmr_ref)
                VALUES(?,?,?)""", [(inventory_id, ref, mapped) for mapped in refs])
    return len(rows)


def edition_inventory_report(con, inventory_id, books=None, limit=None):
    row = con.execute("""SELECT edition,scope,source_citation,reuse_terms,
        mapping_citation,reviewer,manifest_sha256 FROM edition_inventory
        WHERE inventory_id=?""", (inventory_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown inventory ID: {inventory_id}")
    if books is not None and (not books or any(book not in BOOK_ORDER for book in books)):
        raise ValueError("Inventory book filter requires New Testament OSIS book names")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("Inventory limit must be positive")
    query = """SELECT osis_ref,ordinal,book,chapter,verse,editorial_status,
        editorial_note,mapping_note FROM edition_verse WHERE inventory_id=?"""
    params = [inventory_id]
    if books is not None:
        query += " AND book IN (" + ",".join("?" for _ in books) + ")"
        params.extend(books)
    query += " ORDER BY ordinal"
    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)
    fields = ("osis_ref", "ordinal", "book", "chapter", "verse",
              "editorial_status", "editorial_note", "mapping_note")
    verses = [dict(zip(fields, record)) for record in con.execute(query, params)]
    manifest = json.loads(con.execute("SELECT manifest_json FROM edition_inventory WHERE inventory_id=?",
                                      (inventory_id,)).fetchone()[0])
    passage_citations = {item["osis_ref"]: item.get("passage_citation")
                         for item in manifest["verses"]}
    for verse in verses:
        verse["passage_citation"] = passage_citations.get(verse["osis_ref"])
        verse["ntvmr_refs"] = [mapped for (mapped,) in con.execute("""SELECT ntvmr_ref
            FROM edition_verse_map WHERE inventory_id=? AND osis_ref=? ORDER BY ntvmr_ref""",
            (inventory_id, verse["osis_ref"]))]
    return {"inventory_id": inventory_id, "edition": row[0], "scope": row[1],
            "source_citation": row[2], "reuse_terms": row[3],
            "mapping_citation": row[4], "reviewer": row[5],
            "manifest_sha256": row[6], "whole_nt_complete": False,
            "verses": verses}


def record_coverage_review(con, inventory_id, osis_ref, ntvmr_ref, doc_id, page_id,
                           index_response_id, status, evidence_type, reason, citation,
                           reviewer):
    """Review one indexed page/verse pair; keep corrections as new decisions."""
    if status not in ("partial", "full", "uncertain", "rejected", "withdrawn"):
        raise ValueError("Unknown coverage review status")
    if evidence_type not in ("checked_image", "reviewed_transcription",
                             "catalogue_content_statement"):
        raise ValueError("Unknown coverage evidence type")
    if any(not isinstance(value, str) or not value.strip()
           for value in (reason, citation, reviewer)):
        raise ValueError("Coverage review requires reason, citation, and reviewer")
    if any(type(value) is not int or value <= 0
           for value in (doc_id, page_id, index_response_id)):
        raise ValueError("Document, page, and response IDs must be positive integers")
    if not con.execute("""SELECT 1 FROM edition_verse_map WHERE inventory_id=?
        AND osis_ref=? AND ntvmr_ref=?""", (inventory_id, osis_ref, ntvmr_ref)).fetchone():
        raise ValueError("Verse requires an explicit mapping in the selected inventory")
    if status in ("partial", "full"):
        inventory = con.execute("SELECT manifest_json FROM edition_inventory WHERE inventory_id=?",
                                (inventory_id,)).fetchone()
        verse = next((item for item in json.loads(inventory[0])["verses"]
                      if item["osis_ref"] == osis_ref), None)
        if verse["editorial_status"] == "omitted" and not verse.get("passage_citation"):
            raise ValueError("Positive coverage of an omitted coordinate requires a cited traditional passage in a new inventory snapshot")
    if status == "withdrawn":
        prior = con.execute("""SELECT witness_id,identity_assignment_id,index_response_id
            FROM coverage_review WHERE inventory_id=? AND osis_ref=? AND ntvmr_ref=?
            AND doc_id=? AND page_id=? ORDER BY id DESC LIMIT 1""",
            (inventory_id, osis_ref, ntvmr_ref, doc_id, page_id)).fetchone()
        if not prior or prior[2] != index_response_id:
            raise ValueError("Withdrawal requires a prior review of this indexed page")
        witness_id, assignment_id = prior[:2]
    else:
        assignment = latest_witness_assignments(con, [doc_id]).get(doc_id)
        if not assignment or not assignment["witness_id"] or assignment["identity_review_needed"]:
            raise ValueError("Coverage review requires a current retained physical witness link")
        index = con.execute("""SELECT response_id FROM coverage_index WHERE
            doc_id=? AND osis_ref=? AND page_id=?""", (doc_id, ntvmr_ref, page_id)).fetchone()
        if not index or index[0] != index_response_id:
            raise ValueError("Coverage review requires the current indexed page and response")
        witness_id = assignment["witness_id"]
        assignment_id = assignment["identity_assignment_id"]
    with con:
        con.execute("""INSERT INTO coverage_review(inventory_id,osis_ref,ntvmr_ref,
            doc_id,page_id,witness_id,identity_assignment_id,index_response_id,
            status,evidence_type,reason,citation,reviewer,reviewed_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (inventory_id, osis_ref, ntvmr_ref, doc_id, page_id,
             witness_id, assignment_id,
             index_response_id, status, evidence_type, reason.strip(),
             citation.strip(), reviewer.strip(), now()))
        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def coverage_review_report(con, inventory_id, osis_ref=None):
    if not con.execute("SELECT 1 FROM edition_inventory WHERE inventory_id=?",
                       (inventory_id,)).fetchone():
        raise ValueError(f"Unknown inventory ID: {inventory_id}")
    if osis_ref is not None and not con.execute("""SELECT 1 FROM edition_verse
        WHERE inventory_id=? AND osis_ref=?""", (inventory_id, osis_ref)).fetchone():
        raise ValueError("Verse is not in the selected inventory")
    query = """SELECT r.id,r.osis_ref,r.ntvmr_ref,r.doc_id,r.page_id,r.witness_id,
        r.identity_assignment_id,r.index_response_id,r.status,r.evidence_type,
        r.reason,r.citation,r.reviewer,r.reviewed_at,s.body_sha256,s.url,s.retrieved_at
        FROM coverage_review r JOIN source_response s ON s.id=r.index_response_id
        WHERE r.inventory_id=? AND r.id=(SELECT MAX(x.id) FROM coverage_review x
        WHERE x.inventory_id=r.inventory_id AND x.osis_ref=r.osis_ref
        AND x.ntvmr_ref=r.ntvmr_ref AND x.doc_id=r.doc_id AND x.page_id=r.page_id)"""
    params = [inventory_id]
    if osis_ref is not None:
        query += " AND r.osis_ref=?"
        params.append(osis_ref)
    query += " ORDER BY r.osis_ref,r.doc_id,r.page_id,r.ntvmr_ref"
    fields = ("review_id", "osis_ref", "ntvmr_ref", "doc_id", "page_id", "witness_id",
              "identity_assignment_id", "index_response_id", "status", "evidence_type",
              "reason", "citation", "reviewer", "reviewed_at", "index_body_sha256",
              "index_source_url", "index_retrieved_at")
    rows = [dict(zip(fields, row)) for row in con.execute(query, params)]
    assignments = latest_witness_assignments(con, [row["doc_id"] for row in rows])
    verified = {}
    for row in rows:
        assignment = assignments.get(row["doc_id"])
        index = con.execute("""SELECT response_id FROM coverage_index WHERE
            doc_id=? AND osis_ref=? AND page_id=?""",
            (row["doc_id"], row["ntvmr_ref"], row["page_id"])).fetchone()
        row["review_needed"] = bool(
            not assignment or assignment["identity_review_needed"] or
            assignment["identity_assignment_id"] != row["identity_assignment_id"] or
            index is None or index[0] != row["index_response_id"])
        if row["status"] in ("partial", "full") and not row["review_needed"]:
            verified.setdefault(row["osis_ref"], set()).add(row["witness_id"])
    return {"inventory_id": inventory_id, "osis_ref": osis_ref,
            "whole_nt_complete": False, "reviews": rows,
            "verified_witnesses": {ref: sorted(ids) for ref, ids in sorted(verified.items())}}


def record_physical_absence_review(con, inventory_id, osis_ref, witness_id, decision,
                                   evidence_type, source_locator, reason, citation,
                                   reviewer):
    """Record a cited physical-text check without requiring an API index row."""
    if decision not in ("absent", "uncertain", "withdrawn"):
        raise ValueError("Unknown physical absence decision")
    if evidence_type not in ("checked_image", "reviewed_transcription"):
        raise ValueError("Physical absence needs a checked image or reviewed transcription")
    if any(not isinstance(value, str) or not value.strip() for value in
           (inventory_id, osis_ref, witness_id, source_locator, reason,
            citation, reviewer)):
        raise ValueError("Physical absence review requires identity, location, reason, citation, and reviewer")
    if not con.execute("""SELECT 1 FROM edition_verse WHERE inventory_id=? AND osis_ref=?""",
                       (inventory_id, osis_ref)).fetchone():
        raise ValueError("Physical absence requires a verse in the selected inventory")
    if not con.execute("SELECT 1 FROM physical_witness WHERE witness_id=?",
                       (witness_id,)).fetchone():
        raise ValueError("Physical absence requires an existing physical witness")
    previous = con.execute("""SELECT decision FROM physical_absence_review
        WHERE inventory_id=? AND osis_ref=? AND witness_id=? ORDER BY id DESC LIMIT 1""",
        (inventory_id, osis_ref, witness_id)).fetchone()
    if decision == "withdrawn" and (not previous or previous[0] == "withdrawn"):
        raise ValueError("Withdrawal requires a current physical absence review")
    with con:
        con.execute("""INSERT INTO physical_absence_review(inventory_id,osis_ref,
            witness_id,decision,evidence_type,source_locator,reason,citation,
            reviewer,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (inventory_id, osis_ref, witness_id, decision, evidence_type,
             source_locator.strip(), reason.strip(), citation.strip(),
             reviewer.strip(), now()))
        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def physical_absence_report(con, inventory_id, osis_ref=None):
    """Show current direct absence decisions and contradictions with positive reviews."""
    coverage = coverage_review_report(con, inventory_id, osis_ref)
    query = """SELECT r.id,r.osis_ref,r.witness_id,r.decision,r.evidence_type,
        r.source_locator,r.reason,r.citation,r.reviewer,r.reviewed_at
        FROM physical_absence_review r WHERE r.inventory_id=? AND r.id=(
        SELECT MAX(x.id) FROM physical_absence_review x WHERE x.inventory_id=r.inventory_id
        AND x.osis_ref=r.osis_ref AND x.witness_id=r.witness_id)"""
    params = [inventory_id]
    if osis_ref is not None:
        query += " AND r.osis_ref=?"
        params.append(osis_ref)
    query += " ORDER BY r.osis_ref,r.witness_id"
    fields = ("review_id", "osis_ref", "witness_id", "decision", "evidence_type",
              "source_locator", "reason", "citation", "reviewer", "reviewed_at")
    rows = [dict(zip(fields, row)) for row in con.execute(query, params)]
    for row in rows:
        row["conflicts_with_positive"] = (row["decision"] == "absent" and
            row["witness_id"] in coverage["verified_witnesses"].get(row["osis_ref"], []))
    return {"inventory_id": inventory_id, "osis_ref": osis_ref,
            "whole_nt_complete": False, "reviews": rows}


def create_writing_unit(con, unit_id, witness_id, label, kind, reason, citation, reviewer):
    if kind not in ("original", "correction", "supplement", "uncertain"):
        raise ValueError("Unknown writing-unit kind")
    if any(not isinstance(value, str) or not value.strip() for value in
           (unit_id, witness_id, label, reason, citation, reviewer)):
        raise ValueError("Writing unit requires ID, witness, label, reason, citation, and reviewer")
    if not con.execute("SELECT 1 FROM physical_witness WHERE witness_id=?",
                       (witness_id,)).fetchone():
        raise ValueError("Writing unit requires an existing physical witness")
    with con:
        con.execute("""INSERT INTO writing_unit(unit_id,witness_id,label,kind,reason,
            citation,reviewer,created_at) VALUES(?,?,?,?,?,?,?,?)""",
            (unit_id.strip(), witness_id, label.strip(), kind, reason.strip(),
             citation.strip(), reviewer.strip(), now()))
    return unit_id.strip()


def assign_coverage_unit(con, coverage_review_id, unit_id, reason, citation, reviewer):
    if type(coverage_review_id) is not int or coverage_review_id <= 0:
        raise ValueError("Coverage review ID must be positive")
    if any(not isinstance(value, str) or not value.strip()
           for value in (reason, citation, reviewer)):
        raise ValueError("Unit assignment requires reason, citation, and reviewer")
    review = con.execute("""SELECT inventory_id,osis_ref,ntvmr_ref,doc_id,page_id,
        witness_id,status FROM coverage_review WHERE id=?""",
        (coverage_review_id,)).fetchone()
    if not review:
        raise ValueError("Unknown coverage review ID")
    if unit_id is None:
        previous = con.execute("""SELECT unit_id FROM coverage_unit_assignment
            WHERE coverage_review_id=? ORDER BY id DESC LIMIT 1""",
            (coverage_review_id,)).fetchone()
        if not previous or previous[0] is None:
            raise ValueError("Coverage review has no current unit link to remove")
    else:
        unit = con.execute("SELECT witness_id FROM writing_unit WHERE unit_id=?",
                           (unit_id,)).fetchone()
        if not unit or unit[0] != review[5]:
            raise ValueError("Writing unit must belong to the reviewed physical witness")
        if review[6] not in ("partial", "full"):
            raise ValueError("Only positive coverage reviews can be assigned a writing unit")
        current = next((row for row in coverage_review_report(con, review[0], review[1])["reviews"]
                        if row["review_id"] == coverage_review_id), None)
        if not current or current["review_needed"]:
            raise ValueError("Unit assignment requires a current positive coverage review")
    with con:
        con.execute("""INSERT INTO coverage_unit_assignment(coverage_review_id,unit_id,
            reason,citation,reviewer,assigned_at) VALUES(?,?,?,?,?,?)""",
            (coverage_review_id, unit_id, reason.strip(), citation.strip(),
             reviewer.strip(), now()))
        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def record_date_assessment(con, unit_id, status, date_min, date_max,
                           original_notation, citation, consulted_on, reviewer):
    if status not in ("valid", "unknown", "invalid"):
        raise ValueError("Unknown date assessment status")
    if any(not isinstance(value, str) or not value.strip() for value in
           (unit_id, original_notation, citation, consulted_on, reviewer)):
        raise ValueError("Date assessment requires unit, notation, citation, consultation date, and reviewer")
    try:
        datetime.fromisoformat(consulted_on).date()
    except ValueError as error:
        raise ValueError("Consultation date must be ISO formatted") from error
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", consulted_on):
        raise ValueError("Consultation date must be YYYY-MM-DD")
    if status == "valid":
        if (type(date_min) is not int or type(date_max) is not int or
                date_min <= 0 or date_max < date_min):
            raise ValueError("Valid date assessment requires an inclusive CE interval")
    elif date_min is not None or date_max is not None:
        raise ValueError("Unknown or invalid dates cannot have numeric bounds")
    if not con.execute("SELECT 1 FROM writing_unit WHERE unit_id=?", (unit_id,)).fetchone():
        raise ValueError("Date assessment requires an existing writing unit")
    with con:
        con.execute("""INSERT INTO date_assessment(unit_id,status,date_min,date_max,
            original_notation,citation,consulted_on,reviewer,recorded_at)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (unit_id, status, date_min, date_max, original_notation.strip(),
             citation.strip(), consulted_on, reviewer.strip(), now()))
        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def select_date_assessment(con, unit_id, assessment_id, policy_id, reason, reviewer):
    if any(not isinstance(value, str) or not value.strip()
           for value in (unit_id, policy_id, reason, reviewer)):
        raise ValueError("Date selection requires unit, policy ID, reason, and reviewer")
    if not con.execute("SELECT 1 FROM writing_unit WHERE unit_id=?", (unit_id,)).fetchone():
        raise ValueError("Unknown writing unit")
    if assessment_id is not None:
        if type(assessment_id) is not int or assessment_id <= 0 or not con.execute(
                "SELECT 1 FROM date_assessment WHERE id=? AND unit_id=?",
                (assessment_id, unit_id)).fetchone():
            raise ValueError("Selected assessment must belong to the writing unit")
    with con:
        con.execute("""INSERT INTO date_selection(unit_id,policy_id,assessment_id,
            reason,reviewer,selected_at) VALUES(?,?,?,?,?,?)""",
            (unit_id, policy_id.strip(), assessment_id, reason.strip(),
             reviewer.strip(), now()))
        return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def writing_unit_report(con, witness_id):
    if not con.execute("SELECT 1 FROM physical_witness WHERE witness_id=?",
                       (witness_id,)).fetchone():
        raise ValueError("Unknown physical witness")
    units = []
    review_reports = {}
    for unit_id, label, kind, reason, citation, reviewer, created_at in con.execute(
            """SELECT unit_id,label,kind,reason,citation,reviewer,created_at
            FROM writing_unit WHERE witness_id=? ORDER BY unit_id""", (witness_id,)):
        assessments = [dict(zip(("assessment_id", "status", "date_min", "date_max",
                                 "original_notation", "citation", "consulted_on", "reviewer",
                                 "recorded_at"), row)) for row in con.execute(
            """SELECT id,status,date_min,date_max,original_notation,citation,
            consulted_on,reviewer,recorded_at FROM date_assessment
            WHERE unit_id=? ORDER BY id""", (unit_id,))]
        selections = [dict(zip(("selection_id", "policy_id", "assessment_id", "reason", "reviewer",
                                "selected_at"), row)) for row in con.execute(
            """SELECT id,policy_id,assessment_id,reason,reviewer,selected_at FROM date_selection
            WHERE unit_id=? ORDER BY id""", (unit_id,))]
        links = [dict(zip(("assignment_id", "coverage_review_id", "reason", "citation",
                           "reviewer", "assigned_at", "current_assignment"), row))
                 for row in con.execute("""SELECT a.id,a.coverage_review_id,a.reason,
            a.citation,a.reviewer,a.assigned_at,a.id=(SELECT MAX(x.id)
            FROM coverage_unit_assignment x WHERE x.coverage_review_id=a.coverage_review_id)
            FROM coverage_unit_assignment a WHERE a.unit_id=? ORDER BY a.id""", (unit_id,))]
        for link in links:
            link["current_assignment"] = bool(link["current_assignment"])
            inventory_id = con.execute("SELECT inventory_id FROM coverage_review WHERE id=?",
                                       (link["coverage_review_id"],)).fetchone()[0]
            if inventory_id not in review_reports:
                review_reports[inventory_id] = {
                    row["review_id"]: row for row in
                    coverage_review_report(con, inventory_id)["reviews"]}
            current = review_reports[inventory_id].get(link["coverage_review_id"])
            link["current_positive"] = bool(link["current_assignment"] and current and
                current["status"] in ("partial", "full") and not current["review_needed"])
        by_policy = {}
        for selection in selections:
            selected = next((a for a in assessments
                             if a["assessment_id"] == selection["assessment_id"]), None)
            by_policy[selection["policy_id"]] = {
                "selection_id": selection["selection_id"],
                "assessment_id": selection["assessment_id"],
                "assessment": selected,
                "rankable": bool(selected and selected["status"] == "valid")}
        units.append({"unit_id": unit_id, "label": label, "kind": kind,
                      "reason": reason, "citation": citation, "reviewer": reviewer,
                      "created_at": created_at, "assessments": assessments,
                      "selection_history": selections,
                      "selected_by_policy": by_policy,
                      "coverage_links": links})
    return {"witness_id": witness_id, "units": units,
            "rankings_computed": False, "whole_nt_complete": False}


def ranking_input(con, inventory_id, osis_ref, policy_id, *, alternatives=False):
    """Resolve current evidence with selected dates or all valid unit dates."""
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise ValueError("Ranking requires a dating policy ID")
    reviews = coverage_review_report(con, inventory_id, osis_ref)["reviews"]
    absences = {row["witness_id"]: row for row in
                physical_absence_report(con, inventory_id, osis_ref)["reviews"]
                if row["decision"] == "absent"}
    inputs = []
    eligible = []
    excluded = []
    failures = []
    for review in reviews:
        doc_id = review["doc_id"]
        jobs = [dict(zip(("run_id", "state", "response_id", "error", "updated_at"), row))
                for row in con.execute("""SELECT run_id,state,response_id,error,updated_at
                    FROM collection_job WHERE doc_id=? AND stage='coverage' ORDER BY run_id""",
                    (doc_id,))]
        for job in jobs:
            if (job["state"] in ("failed", "blocked") and
                    job["updated_at"] >= review["index_retrieved_at"]):
                failures.append({"doc_id": doc_id, "run_id": job["run_id"],
                                 "state": job["state"], "error": job["error"]})
        assignment = con.execute("""SELECT id,unit_id FROM coverage_unit_assignment
            WHERE coverage_review_id=? ORDER BY id DESC LIMIT 1""",
            (review["review_id"],)).fetchone()
        unit_id = assignment[1] if assignment else None
        selection = None
        assessment = None
        assessments = []
        if unit_id is not None:
            if alternatives:
                assessments = list(con.execute("""SELECT id,date_min,date_max,
                    original_notation,citation,consulted_on FROM date_assessment
                    WHERE unit_id=? AND status='valid' ORDER BY id""", (unit_id,)))
            else:
                selection = con.execute("""SELECT id,assessment_id FROM date_selection
                    WHERE unit_id=? AND policy_id=? ORDER BY id DESC LIMIT 1""",
                    (unit_id, policy_id)).fetchone()
                if selection and selection[1] is not None:
                    assessment = con.execute("""SELECT status,date_min,date_max,
                        original_notation,citation,consulted_on FROM date_assessment
                        WHERE id=? AND unit_id=?""", (selection[1], unit_id)).fetchone()
        absence = absences.get(review["witness_id"])
        inputs.append({"review": review, "physical_absence_review": absence,
                       "unit_assignment": assignment,
                       "date_selection": selection, "date_assessment": assessment,
                       **({"valid_alternatives": assessments} if alternatives else {}),
                       "coverage_jobs": jobs})
        if review["status"] not in ("partial", "full"):
            reason = "nonpositive_review"
        elif review["review_needed"]:
            reason = "review_needed"
        elif absence is not None:
            reason = "conflicting_absence"
        elif unit_id is None:
            reason = "missing_writing_unit"
        elif alternatives and not assessments:
            reason = "no_valid_date_alternative"
        elif not alternatives and (not selection or selection[1] is None):
            reason = "missing_selected_date"
        elif not alternatives and (not assessment or assessment[0] != "valid"):
            reason = "invalid_or_unknown_date"
        else:
            reason = None
        if reason:
            excluded.append({"coverage_review_id": review["review_id"],
                             "witness_id": review["witness_id"], "reason": reason})
            continue
        if alternatives:
            for item in assessments:
                eligible.append({"witness_id": review["witness_id"], "unit_id": unit_id,
                                 "assessment_id": item[0], "selection_id": None,
                                 "coverage_review_id": review["review_id"],
                                 "date_min": item[1], "date_max": item[2]})
        else:
            eligible.append({"witness_id": review["witness_id"], "unit_id": unit_id,
                             "assessment_id": selection[1], "selection_id": selection[0],
                             "coverage_review_id": review["review_id"],
                             "date_min": assessment[1], "date_max": assessment[2]})
    digest = hashlib.sha256(encoded(inputs).encode("utf-8")).hexdigest()
    return digest, eligible, excluded, failures


def rank_candidates(candidates, scenario):
    if scenario == "optimistic":
        key = lambda row: (row["date_min"], row["date_max"], row["witness_id"],
                           row.get("unit_id", ""), row.get("coverage_review_id", 0))
        event = "date_min"
    elif scenario == "pessimistic":
        key = lambda row: (row["date_max"], row["date_min"], row["witness_id"],
                           row.get("unit_id", ""), row.get("coverage_review_id", 0))
        event = "date_max"
    else:
        raise ValueError("Unknown ranking scenario")
    # The first qualifying event for each physical object is selected independently.
    per_witness = {}
    for row in sorted(candidates, key=key):
        per_witness.setdefault(row["witness_id"], row)
    return [{**row, "rank": rank, "event_year": row[event]}
            for rank, row in enumerate(sorted(per_witness.values(), key=key), 1)]


def dating_alternatives_report(con, inventory_id, osis_ref, policy_id,
                               *, max_combinations=256):
    """Calculate conditional rankings for every combination of valid unit dates.

    This does not pick a preferred assessment or alter stored policy snapshots.
    The cap prevents a partial list from masquerading as complete alternatives.
    """
    if type(max_combinations) is not int or max_combinations < 1:
        raise ValueError("Alternative combination cap must be a positive integer")
    _, candidates, excluded, failures = ranking_input(
        con, inventory_id, osis_ref, policy_id, alternatives=True)
    units = sorted({row["unit_id"] for row in candidates})
    review_ids = sorted({row["coverage_review_id"] for row in candidates} |
                        {row["coverage_review_id"] for row in excluded})
    assigned_units = set(units)
    for review_id in review_ids:
        assignment = con.execute("""SELECT unit_id FROM coverage_unit_assignment
            WHERE coverage_review_id=? ORDER BY id DESC LIMIT 1""",
            (review_id,)).fetchone()
        if assignment and assignment[0]:
            assigned_units.add(assignment[0])
    unrankable = []
    for unit_id in sorted(assigned_units):
        unrankable.extend(dict(zip(("unit_id", "assessment_id", "status",
                                    "original_notation", "citation", "consulted_on",
                                    "reviewer", "reason"), (*row, "not_valid_for_ranking")))
            for row in con.execute("""SELECT unit_id,id,status,original_notation,
                citation,consulted_on,reviewer FROM date_assessment
                WHERE unit_id=? AND status!='valid' ORDER BY id""", (unit_id,)))
    choices = {unit: sorted({row["assessment_id"] for row in candidates
                            if row["unit_id"] == unit}) for unit in units}
    count = 1
    for unit in units:
        count *= len(choices[unit])
    unresolved = any(row["reason"] in ("review_needed", "conflicting_absence")
                     for row in excluded)
    state = ("failed" if failures else "incomplete" if unresolved else
             "no_rankable_dates" if not units else
             "too_many_combinations" if count > max_combinations else "complete")
    report = {"inventory_id": inventory_id, "osis_ref": osis_ref,
              "policy_id": policy_id, "state": state,
              "combination_count": count if units else 0,
              "max_combinations": max_combinations, "unit_count": len(units),
              "eligible_witness_count": len({row["witness_id"] for row in candidates}),
              "unrankable_assessments": unrankable,
              "excluded_reviews": excluded, "failed_coverage_jobs": failures,
              "combinations": []}
    if state != "complete":
        return report
    review_provenance = {row[0]: row[1:] for row in con.execute("""SELECT
        r.id,r.status,r.evidence_type,r.citation,s.url,r.reviewer
        FROM coverage_review r JOIN source_response s ON s.id=r.index_response_id
        WHERE r.id IN (""" + ",".join("?" for _ in
            {item["coverage_review_id"] for item in candidates}) + ")",
        sorted({item["coverage_review_id"] for item in candidates}))}
    for selected in product(*(choices[unit] for unit in units)):
        by_unit = dict(zip(units, selected))
        rows = [row for row in candidates
                if row["assessment_id"] == by_unit[row["unit_id"]]]
        provenance = [dict(zip(("unit_id", "assessment_id", "date_min", "date_max",
                                "original_notation", "citation", "consulted_on",
                                "reviewer"), item))
                      for item in con.execute("""SELECT unit_id,id,date_min,date_max,
                          original_notation,citation,consulted_on,reviewer FROM date_assessment
                          WHERE id IN (""" + ",".join("?" for _ in selected) + ") ORDER BY unit_id",
                          selected)]
        scenarios = {scenario: rank_candidates(rows, scenario)[:5]
                     for scenario in ("optimistic", "pessimistic")}
        for entries in scenarios.values():
            for entry in entries:
                (entry["coverage_status"], entry["evidence_type"],
                 entry["coverage_citation"], entry["index_source_url"],
                 entry["coverage_reviewer"]) = \
                    review_provenance[entry["coverage_review_id"]]
        report["combinations"].append({
            "assessments": provenance,
            "scenarios": scenarios})
    return report


def ranking_report(con, inventory_id, osis_ref, policy_id):
    digest, candidates, excluded, failures = ranking_input(
        con, inventory_id, osis_ref, policy_id)
    unresolved = any(row["reason"] in ("review_needed", "conflicting_absence")
                     for row in excluded)
    snapshot = con.execute("""SELECT input_sha256,state,candidate_count,computed_at
        FROM ranking_snapshot WHERE inventory_id=? AND osis_ref=? AND policy_id=?""",
        (inventory_id, osis_ref, policy_id)).fetchone()
    if failures:
        state = "failed"
    elif unresolved:
        state = "stale" if snapshot else "incomplete"
    elif not snapshot:
        state = "uncomputed"
    else:
        state = "stale" if snapshot[0] != digest else snapshot[1]
    entries = {}
    for scenario in ("optimistic", "pessimistic"):
        fields = ("rank", "witness_id", "unit_id", "assessment_id", "selection_id",
                  "coverage_review_id", "date_min", "date_max", "event_year",
                  "coverage_status", "evidence_type", "coverage_citation",
                  "index_response_id", "index_source_url", "date_citation",
                  "original_notation", "consulted_on")
        entries[scenario] = [dict(zip(fields, row)) for row in con.execute("""SELECT
            e.rank,e.witness_id,e.unit_id,e.assessment_id,e.selection_id,
            e.coverage_review_id,e.date_min,e.date_max,e.event_year,
            r.status,r.evidence_type,r.citation,r.index_response_id,s.url,
            a.citation,a.original_notation,a.consulted_on
            FROM ranking_entry e JOIN coverage_review r ON r.id=e.coverage_review_id
            JOIN source_response s ON s.id=r.index_response_id
            JOIN date_assessment a ON a.id=e.assessment_id
            WHERE e.inventory_id=? AND e.osis_ref=? AND e.policy_id=?
            AND e.scenario=? ORDER BY e.rank LIMIT 5""",
            (inventory_id, osis_ref, policy_id, scenario))]
    return {"inventory_id": inventory_id, "osis_ref": osis_ref,
            "policy_id": policy_id, "state": state,
            "computed_at": snapshot[3] if snapshot else None,
            "candidate_count": snapshot[2] if snapshot else None,
            "current_eligible_witness_count": len({r["witness_id"] for r in candidates}),
            "excluded_reviews": excluded, "failed_coverage_jobs": failures,
            "scenarios": entries, "scope": "reviewed evidence in selected inventory",
            "whole_nt_complete": False}


def compute_ranking(con, inventory_id, osis_ref, policy_id):
    """Atomically replace both scenarios; retain an earlier snapshot on failure."""
    digest, candidates, excluded, failures = ranking_input(
        con, inventory_id, osis_ref, policy_id)
    if failures or any(row["reason"] in ("review_needed", "conflicting_absence")
                       for row in excluded):
        return ranking_report(con, inventory_id, osis_ref, policy_id)
    ranked = {scenario: rank_candidates(candidates, scenario)
              for scenario in ("optimistic", "pessimistic")}
    witness_count = len(ranked["optimistic"])
    with con:
        con.execute("""DELETE FROM ranking_entry WHERE inventory_id=? AND osis_ref=?
            AND policy_id=?""", (inventory_id, osis_ref, policy_id))
        con.execute("""INSERT INTO ranking_snapshot(inventory_id,osis_ref,policy_id,
            input_sha256,state,candidate_count,computed_at) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(inventory_id,osis_ref,policy_id) DO UPDATE SET
            input_sha256=excluded.input_sha256,state=excluded.state,
            candidate_count=excluded.candidate_count,computed_at=excluded.computed_at""",
            (inventory_id, osis_ref, policy_id, digest,
             "success" if witness_count else "empty", witness_count, now()))
        for scenario, rows in ranked.items():
            for row in rows[:5]:
                con.execute("""INSERT INTO ranking_entry(inventory_id,osis_ref,
                    policy_id,scenario,rank,witness_id,unit_id,assessment_id,
                    selection_id,coverage_review_id,date_min,date_max,event_year)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (inventory_id, osis_ref, policy_id, scenario, row["rank"],
                     row["witness_id"], row["unit_id"], row["assessment_id"],
                     row["selection_id"], row["coverage_review_id"],
                     row["date_min"], row["date_max"], row["event_year"]))
    return ranking_report(con, inventory_id, osis_ref, policy_id)


def validate_dating_action(action):
    fields = {
        "create_unit": {"unit_id", "witness_id", "label", "kind", "reason",
                        "citation", "reviewer"},
        "assign_coverage": {"coverage_review_id", "unit_id", "reason",
                            "citation", "reviewer"},
        "assess_date": {"unit_id", "status", "date_min", "date_max",
                        "original_notation", "citation", "consulted_on", "reviewer"},
        "select_date": {"unit_id", "assessment_id", "policy_id", "reason", "reviewer"},
    }
    if not isinstance(action, dict) or action.get("action") not in fields:
        raise ValueError("Unknown dating action")
    kind = action["action"]
    if set(action) != fields[kind] | {"action"}:
        raise ValueError("Dating action has missing or unexpected fields")
    return kind, fields[kind]


def apply_dating_action(con, action):
    """Apply exactly one explicit, offline writing-unit or dating decision."""
    kind, field_names = validate_dating_action(action)
    if kind == "create_unit":
        result = create_writing_unit(con, **{key: action[key] for key in field_names})
        return {"unit_id": result}
    if kind == "assign_coverage":
        result = assign_coverage_unit(con, **{key: action[key] for key in field_names})
        return {"coverage_unit_assignment_id": result}
    if kind == "assess_date":
        result = record_date_assessment(con, **{key: action[key] for key in field_names})
        return {"date_assessment_id": result}
    result = select_date_assessment(con, **{key: action[key] for key in field_names})
    return {"date_selection_id": result}


def import_p52(con, fixture):
    record = json.loads(fixture.read_text(encoding="utf-8"))
    body = json.dumps(record["response"], separators=(",", ":"))
    digest = hashlib.sha256(body.encode()).hexdigest()
    params = encoded(record["params"])
    row = con.execute("""SELECT id FROM source_response WHERE origin='fixture' AND url=?
       AND params_json=? AND body_sha256=?""", (record["source_url"], params, digest)).fetchone()
    if row:
        return row[0]
    con.execute("""INSERT INTO source_response(endpoint,url,params_json,status_code,headers_json,
       body,body_sha256,retrieved_at,origin) VALUES(?,?,?,?,?,?,?,?,?)""",
       ("biblicalcontent/get", record["source_url"], params, record["http_status"], "{}",
        body, digest, record["review_date"] + "T00:00:00+00:00", "fixture"))
    con.commit()
    return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def import_language_probe(con, fixture):
    record = json.loads(fixture.read_text(encoding="utf-8"))
    ids = []
    for case in record["cases"]:
        params = dict(record["common_params"])
        if case["lang"] is not None:
            params["lang"] = case["lang"]
        body = encoded(case["response"])
        digest = hashlib.sha256(body.encode()).hexdigest()
        args = encoded(params)
        row = con.execute("""SELECT id FROM source_response WHERE origin='fixture'
            AND url=? AND params_json=? AND body_sha256=?""",
            (record["source_url"], args, digest)).fetchone()
        if row:
            ids.append(row[0])
            continue
        con.execute("""INSERT INTO source_response(endpoint,url,params_json,status_code,
            headers_json,body,body_sha256,retrieved_at,origin)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            ("metadata/liste/search", record["source_url"], args, 200, "{}", body,
             digest, record["review_date"] + "T00:00:00+00:00", "fixture"))
        ids.append(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    con.commit()
    return ids


def import_search_fixture(con, fixture):
    record = (json.loads(fixture.read_text(encoding="utf-8"))
              if isinstance(fixture, Path) else fixture)
    body = record["raw_body"]
    digest = hashlib.sha256(body.encode()).hexdigest()
    if digest != record["body_sha256"]:
        raise ValueError("Search fixture body hash mismatch")
    args = encoded(record["params"])
    headers = encoded(record.get("headers", {}))
    row = con.execute("""SELECT id FROM source_response WHERE origin='fixture'
        AND url=? AND params_json=? AND body_sha256=? AND headers_json=?""",
        (record["source_url"], args, digest, headers)).fetchone()
    if row:
        return row[0]
    con.execute("""INSERT INTO source_response(endpoint,url,params_json,status_code,
        headers_json,body,body_sha256,retrieved_at,origin)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        ("metadata/liste/search", record["source_url"], args,
         record["http_status"], headers, body, digest, record["retrieved_at"], "fixture"))
    con.commit()
    return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def import_coverage_fixture(con, fixture):
    """Store a captured complete coverage response for offline replay."""
    record = (json.loads(fixture.read_text(encoding="utf-8"))
              if isinstance(fixture, Path) else fixture)
    if (not isinstance(record, dict) or
            not {"source_url", "params", "http_status", "raw_body",
                 "body_sha256", "retrieved_at"} <= set(record) or
            not isinstance(record["source_url"], str) or
            not record["source_url"].endswith("/biblicalcontent/get/") or
            record["http_status"] != 200 or
            not isinstance(record["params"], dict)):
        raise ValueError("Coverage fixture has an unsupported shape")
    params = record["params"]
    try:
        doc_id = int(params["docID"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Coverage fixture requires a document ID") from error
    if params != {"docID": str(doc_id), "detail": "long", "format": "json"}:
        raise ValueError("Coverage fixture has unexpected request parameters")
    body = record["raw_body"]
    if not isinstance(body, str) or hashlib.sha256(body.encode("utf-8")).hexdigest() != record["body_sha256"]:
        raise ValueError("Coverage fixture body hash mismatch")
    parse_coverage(json.loads(body), doc_id)
    datetime.fromisoformat(record["retrieved_at"])
    args = encoded(params)
    row = con.execute("""SELECT id FROM source_response WHERE origin='fixture'
        AND url=? AND params_json=? AND body_sha256=?""",
        (record["source_url"], args, record["body_sha256"])).fetchone()
    if row:
        return row[0]
    con.execute("""INSERT INTO source_response(endpoint,url,params_json,status_code,
        headers_json,body,body_sha256,retrieved_at,origin)
        VALUES(?,?,?,?,?,?,?,?,?)""",
        ("biblicalcontent/get", record["source_url"], args, 200, "{}", body,
         record["body_sha256"], record["retrieved_at"], "fixture"))
    con.commit()
    return con.execute("SELECT last_insert_rowid()").fetchone()[0]


def export_p52(con, path):
    rows = con.execute("""SELECT c.osis_ref,c.page_id,c.state,r.id,r.body_sha256,
       r.url,r.params_json,r.retrieved_at,r.origin
       FROM coverage_index c JOIN source_response r ON r.id=c.response_id
       WHERE c.doc_id=10052 ORDER BY c.osis_ref,c.page_id""").fetchall()
    if len(rows) != 5:
        raise ValueError("P52 sample requires exactly five indexed verse/page pairs")
    sample = {"dataset": "offline P52 single-witness sample", "corpus_complete": False,
      "edition_mapping": "unresolved; traditional OSIS coordinates only",
      "evidence_state": "index candidates; see docs/DATA_REVIEW.md for independent source check",
      "doc_id": 10052, "witness": "P52", "partial_coverage": True,
      "verses": [{"osis_ref": ref, "page_id": page, "index_state": state,
         "response_id": response, "body_sha256": digest,
         "source_url": url + "?" + urlencode(json.loads(params)),
         "retrieved_at": retrieved, "response_origin": origin}
         for ref, page, state, response, digest, url, params, retrieved, origin in rows]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sample, indent=2) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=Path("ntvmr-v2.sqlite"))
    ap.add_argument("--archive-legacy", type=Path)
    ap.add_argument("--archive-to", type=Path, default=Path("data/ntvmr-legacy-backup.sqlite"))
    ap.add_argument("--base-url", default=API_BASE)
    ap.add_argument("--run-id", default="manual")
    ap.add_argument("--doc-id", type=int, action="append", default=[])
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--request-budget", type=int, default=0)
    ap.add_argument("--max-run-seconds", type=float, default=0)
    ap.add_argument("--min-interval", type=float, default=5)
    ap.add_argument("--jitter", type=float, default=0.25)
    ap.add_argument("--refresh-stage", choices=["metadata", "coverage", "both"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fixture-p52", action="store_true")
    ap.add_argument("--fixture-language-probe", action="store_true")
    ap.add_argument("--search-ref", help="One OSIS verse for bounded named-witness discovery")
    ap.add_argument("--search-ga-num", action="append", default=[])
    ap.add_argument("--search-lang", help="Optional literal API language filter")
    ap.add_argument("--refresh-search", action="store_true")
    ap.add_argument("--catalogue-doc-id", type=int, action="append", default=[])
    ap.add_argument("--catalogue-index-ref", help="Optional passage filter for the ID set")
    ap.add_argument("--catalogue-limit", type=int, default=200,
                    help="Approximate API page cap for the bounded catalogue lookup")
    ap.add_argument("--refresh-catalogue", action="store_true")
    ap.add_argument("--fixture-john-list", action="store_true")
    ap.add_argument("--scope-check-ref", action="append", default=[],
                    help="Invert completed coverage for this verse within the catalogue ID scope")
    ap.add_argument("--review-doc-id", type=int,
                    help="Record a manual document classification without network requests")
    ap.add_argument("--review-response-id", type=int,
                    help="Source response ID shown in a candidate report")
    ap.add_argument("--review-decision", choices=["retain", "exclude", "uncertain"])
    ap.add_argument("--review-source-type",
                    choices=["greek_manuscript", "printed_edition", "other", "uncertain"])
    ap.add_argument("--review-reason")
    ap.add_argument("--review-citation")
    ap.add_argument("--reviewer")
    ap.add_argument("--identity-doc-id", type=int,
                    help="Assign or unlink a document from a physical witness")
    ap.add_argument("--identity-response-id", type=int)
    ap.add_argument("--witness-id", help="Stable, manually chosen physical witness ID")
    ap.add_argument("--witness-label", help="Label required when creating a witness ID")
    ap.add_argument("--identity-unlink", action="store_true")
    ap.add_argument("--identity-reason")
    ap.add_argument("--identity-citation")
    ap.add_argument("--identity-reviewer")
    ap.add_argument("--identity-report", action="store_true")
    ap.add_argument("--import-inventory", type=Path,
                    help="Import a cited, reviewed verse-inventory JSON manifest")
    ap.add_argument("--inventory-report", help="Report a stored inventory ID")
    ap.add_argument("--inventory-book", action="append", default=[],
                    help="Filter inventory report by OSIS book before applying a limit")
    ap.add_argument("--inventory-limit", type=int)
    ap.add_argument("--coverage-review-inventory")
    ap.add_argument("--coverage-review-ref", help="Edition OSIS coordinate")
    ap.add_argument("--coverage-review-ntvmr-ref", help="Mapped NTVMR coordinate")
    ap.add_argument("--coverage-review-doc-id", type=int)
    ap.add_argument("--coverage-review-page-id", type=int)
    ap.add_argument("--coverage-review-response-id", type=int)
    ap.add_argument("--coverage-review-status",
                    choices=["partial", "full", "uncertain", "rejected", "withdrawn"])
    ap.add_argument("--coverage-review-evidence-type",
                    choices=["checked_image", "reviewed_transcription",
                             "catalogue_content_statement"])
    ap.add_argument("--coverage-review-reason")
    ap.add_argument("--coverage-review-citation")
    ap.add_argument("--coverage-review-reviewer")
    ap.add_argument("--coverage-report", help="Inventory ID for reviewed evidence report")
    ap.add_argument("--coverage-report-ref", help="Optional edition verse filter")
    ap.add_argument("--dating-action", type=Path,
                    help="Apply one sourced writing-unit or date decision from JSON")
    ap.add_argument("--dating-report", help="Report writing units and date history for a witness ID")
    ap.add_argument("--ranking-inventory", help="Inventory ID for one verse ranking")
    ap.add_argument("--ranking-ref", help="Edition OSIS verse to rank")
    ap.add_argument("--ranking-policy", help="Selected dating policy ID")
    ap.add_argument("--compute-ranking", action="store_true",
                    help="Atomically refresh both ranking scenarios offline")
    ap.add_argument("--export-p52", type=Path)
    args = ap.parse_args(argv)
    if min(args.request_budget, args.max_run_seconds, args.min_interval, args.jitter) < 0:
        ap.error("Budgets and intervals must be nonnegative")
    if any(doc <= 0 for doc in args.doc_id):
        ap.error("Document IDs must be positive")
    if not args.offline and (args.doc_id or args.search_ga_num or args.catalogue_doc_id) and args.request_budget == 0:
        ap.error("Network collection requires a positive --request-budget")
    if args.fixture_p52 and args.refresh_stage:
        ap.error("Fixture replay cannot refresh a network stage")
    if args.fixture_p52 and not args.offline:
        ap.error("Fixture replay requires --offline")
    if args.fixture_language_probe and not args.offline:
        ap.error("Fixture replay requires --offline")
    if args.search_ref and not OSIS.fullmatch(args.search_ref):
        ap.error("--search-ref must be one OSIS verse")
    if bool(args.search_ref) != bool(args.search_ga_num):
        ap.error("--search-ref and --search-ga-num must be supplied together")
    if args.search_lang and not args.search_ref:
        ap.error("--search-lang requires a search")
    if args.offline and args.refresh_search:
        ap.error("--refresh-search requires live mode")
    if args.catalogue_index_ref and not args.catalogue_doc_id:
        ap.error("--catalogue-index-ref requires --catalogue-doc-id")
    if args.catalogue_doc_id:
        try:
            catalogue_params(args.catalogue_doc_id, args.catalogue_index_ref, args.catalogue_limit)
        except ValueError as error:
            ap.error(str(error))
    if args.refresh_catalogue and (args.offline or not args.catalogue_doc_id):
        ap.error("--refresh-catalogue requires a live catalogue scope")
    if args.fixture_john_list and not args.offline:
        ap.error("Fixture replay requires --offline")
    if args.scope_check_ref and not args.catalogue_doc_id:
        ap.error("--scope-check-ref requires a catalogue ID scope")
    if any(not OSIS.fullmatch(ref) for ref in args.scope_check_ref):
        ap.error("--scope-check-ref requires individual OSIS verses")
    review_fields = (args.review_response_id, args.review_decision,
                     args.review_source_type, args.review_reason,
                     args.review_citation, args.reviewer)
    if args.review_doc_id is not None:
        if any(value is None for value in review_fields):
            ap.error("Document review requires response ID, decision, source type, reason, citation, and reviewer")
        if (args.doc_id or args.search_ga_num or args.catalogue_doc_id or args.scope_check_ref or
            args.fixture_p52 or args.fixture_language_probe or args.fixture_john_list or
            args.archive_legacy or args.export_p52 or args.identity_report):
            ap.error("Record a document review in a separate invocation")
    elif any(value is not None for value in review_fields):
        ap.error("Review fields require --review-doc-id")
    identity_fields = (args.identity_response_id, args.identity_reason,
                       args.identity_citation, args.identity_reviewer)
    if args.identity_doc_id is not None:
        if any(value is None for value in identity_fields):
            ap.error("Identity assignment requires response ID, reason, citation, and reviewer")
        if args.identity_unlink == bool(args.witness_id) or (args.identity_unlink and args.witness_label):
            ap.error("Supply either --identity-unlink or --witness-id, with a label only for a link")
        if (args.review_doc_id is not None or args.doc_id or args.search_ga_num or
            args.catalogue_doc_id or args.scope_check_ref or args.fixture_p52 or
            args.fixture_language_probe or args.fixture_john_list or args.archive_legacy or
            args.export_p52 or args.identity_report):
            ap.error("Record an identity assignment in a separate invocation")
    elif (any(value is not None for value in identity_fields) or args.witness_id is not None or
          args.witness_label is not None or args.identity_unlink):
        ap.error("Identity fields require --identity-doc-id")
    if args.identity_report and (args.review_doc_id is not None or args.doc_id or
        args.search_ga_num or args.catalogue_doc_id or args.scope_check_ref or
        args.fixture_p52 or args.fixture_language_probe or args.fixture_john_list or
        args.archive_legacy or args.export_p52):
        ap.error("Request the identity report in a separate invocation")
    coverage_fields = (args.coverage_review_inventory, args.coverage_review_ref,
                       args.coverage_review_ntvmr_ref, args.coverage_review_doc_id,
                       args.coverage_review_page_id, args.coverage_review_response_id,
                       args.coverage_review_status, args.coverage_review_evidence_type,
                       args.coverage_review_reason, args.coverage_review_citation,
                       args.coverage_review_reviewer)
    if any(value is not None for value in coverage_fields):
        if any(value is None for value in coverage_fields):
            ap.error("Coverage review requires all coverage-review fields")
    if args.coverage_report_ref and not args.coverage_report:
        ap.error("--coverage-report-ref requires --coverage-report")
    coverage_action = any(value is not None for value in coverage_fields) or args.coverage_report is not None
    if coverage_action and (args.review_doc_id is not None or args.identity_doc_id is not None or
        args.identity_report or args.doc_id or args.search_ga_num or args.catalogue_doc_id or
        args.scope_check_ref or args.fixture_p52 or args.fixture_language_probe or
        args.fixture_john_list or args.archive_legacy or args.export_p52 or
        args.import_inventory is not None or args.inventory_report is not None):
        ap.error("Review or report coverage in a separate invocation")
    if args.coverage_report is not None and any(value is not None for value in coverage_fields):
        ap.error("Review and report coverage in separate invocations")
    dating_action = args.dating_action is not None or args.dating_report is not None
    if args.dating_action is not None and args.dating_report is not None:
        ap.error("Apply a dating action and report in separate invocations")
    if dating_action and (coverage_action or args.review_doc_id is not None or
        args.identity_doc_id is not None or args.identity_report or args.doc_id or
        args.search_ga_num or args.catalogue_doc_id or args.scope_check_ref or
        args.fixture_p52 or args.fixture_language_probe or args.fixture_john_list or
        args.archive_legacy or args.export_p52 or args.import_inventory is not None or
        args.inventory_report is not None):
        ap.error("Apply or report dating in a separate invocation")
    ranking_action = any((args.ranking_inventory, args.ranking_ref,
                          args.ranking_policy, args.compute_ranking))
    if ranking_action:
        if not all((args.ranking_inventory, args.ranking_ref, args.ranking_policy)):
            ap.error("Ranking requires inventory, verse, and dating policy")
        if not OSIS.fullmatch(args.ranking_ref):
            ap.error("--ranking-ref must be one OSIS verse")
        if (dating_action or coverage_action or args.review_doc_id is not None or
            args.identity_doc_id is not None or args.identity_report or args.doc_id or
            args.search_ga_num or args.catalogue_doc_id or args.scope_check_ref or
            args.fixture_p52 or args.fixture_language_probe or args.fixture_john_list or
            args.archive_legacy or args.export_p52 or args.import_inventory is not None or
            args.inventory_report is not None):
            ap.error("Compute or report a ranking in a separate invocation")
    inventory_action = args.import_inventory is not None or args.inventory_report is not None
    if args.import_inventory is not None and args.inventory_report is not None:
        ap.error("Import and report an inventory in separate invocations")
    if (args.inventory_book or args.inventory_limit is not None) and args.inventory_report is None:
        ap.error("Inventory book and limit options require --inventory-report")
    if inventory_action and (args.review_doc_id is not None or args.identity_doc_id is not None or
        args.identity_report or args.doc_id or args.search_ga_num or args.catalogue_doc_id or
        args.scope_check_ref or args.fixture_p52 or args.fixture_language_probe or
        args.fixture_john_list or args.archive_legacy or args.export_p52):
        ap.error("Import or report an inventory in a separate invocation")
    try:
        if args.archive_legacy and args.dry_run:
            print(f"Would archive {args.archive_legacy} to {args.archive_to}")
        elif args.archive_legacy:
            archive_legacy(args.archive_legacy, args.archive_to)
            print(f"Archived legacy database to {args.archive_to}")
        with closing(connect(args.db)) as con:
            if ranking_action:
                if args.dry_run:
                    digest, candidates, excluded, failures = ranking_input(
                        con, args.ranking_inventory, args.ranking_ref,
                        args.ranking_policy)
                    print(json.dumps({"planned_ranking": args.ranking_ref,
                                      "eligible_records": len(candidates),
                                      "excluded_reviews": len(excluded),
                                      "failed_coverage_jobs": failures,
                                      "input_sha256": digest, "network_attempts": 0}))
                    return 0
                report = (compute_ranking if args.compute_ranking else ranking_report)(
                    con, args.ranking_inventory, args.ranking_ref, args.ranking_policy)
                print(json.dumps(report))
                return 0 if report["state"] in ("success", "empty") else 1
            if args.dating_action is not None:
                action = json.loads(args.dating_action.read_text(encoding="utf-8"))
                if args.dry_run:
                    kind, _ = validate_dating_action(action)
                    print(json.dumps({"planned_dating_action": kind,
                                      "network_attempts": 0}))
                    return 0
                print(json.dumps({**apply_dating_action(con, action), "network_attempts": 0}))
                return 0
            if args.dating_report is not None:
                print(json.dumps(writing_unit_report(con, args.dating_report)))
                return 0
            if args.coverage_review_inventory is not None:
                if args.dry_run:
                    print(json.dumps({"planned_coverage_review": {
                        "inventory_id": args.coverage_review_inventory,
                        "osis_ref": args.coverage_review_ref,
                        "doc_id": args.coverage_review_doc_id,
                        "page_id": args.coverage_review_page_id}, "network_attempts": 0}))
                    return 0
                review_id = record_coverage_review(
                    con, args.coverage_review_inventory, args.coverage_review_ref,
                    args.coverage_review_ntvmr_ref, args.coverage_review_doc_id,
                    args.coverage_review_page_id, args.coverage_review_response_id,
                    args.coverage_review_status, args.coverage_review_evidence_type,
                    args.coverage_review_reason, args.coverage_review_citation,
                    args.coverage_review_reviewer)
                print(json.dumps({"coverage_review_id": review_id, "network_attempts": 0}))
                return 0
            if args.coverage_report is not None:
                print(json.dumps(coverage_review_report(
                    con, args.coverage_report, args.coverage_report_ref)))
                return 0
            if args.import_inventory is not None:
                manifest = json.loads(args.import_inventory.read_text(encoding="utf-8"))
                if args.dry_run:
                    rows = validate_inventory(manifest)
                    print(json.dumps({"planned_inventory_id": manifest["inventory_id"],
                                      "verse_count": len(rows), "network_attempts": 0}))
                    return 0
                count = import_edition_inventory(con, manifest)
                print(json.dumps({"inventory_id": manifest["inventory_id"],
                                  "verse_count": count, "network_attempts": 0}))
                return 0
            if args.inventory_report is not None:
                print(json.dumps(edition_inventory_report(
                    con, args.inventory_report,
                    books=args.inventory_book or None, limit=args.inventory_limit)))
                return 0
            if args.identity_doc_id is not None:
                if args.dry_run:
                    print(json.dumps({"planned_identity_doc_id": args.identity_doc_id,
                                      "witness_id": args.witness_id, "unlink": args.identity_unlink,
                                      "network_attempts": 0}))
                    return 0
                assignment_id = record_witness_assignment(
                    con, args.identity_doc_id, args.identity_response_id,
                    None if args.identity_unlink else args.witness_id,
                    args.witness_label, args.identity_reason, args.identity_citation,
                    args.identity_reviewer)
                print(json.dumps({"identity_assignment_id": assignment_id,
                                  "doc_id": args.identity_doc_id,
                                  "witness_id": None if args.identity_unlink else args.witness_id}))
                return 0
            if args.identity_report:
                print(json.dumps(witness_identity_report(con)))
                return 0
            if args.review_doc_id is not None:
                if args.dry_run:
                    print(json.dumps({"planned_review_doc_id": args.review_doc_id,
                                      "source_response_id": args.review_response_id,
                                      "decision": args.review_decision,
                                      "source_type": args.review_source_type,
                                      "network_attempts": 0}))
                    return 0
                review_id = record_candidate_review(
                    con, args.review_doc_id, args.review_response_id,
                    args.review_decision, args.review_source_type,
                    args.review_reason, args.review_citation, args.reviewer)
                print(json.dumps({"review_id": review_id, "doc_id": args.review_doc_id,
                                  "decision": args.review_decision,
                                  "source_type": args.review_source_type}))
                return 0
            if args.fixture_p52 and not args.dry_run:
                import_p52(con, Path(__file__).parent / "tests/fixtures/p52_coverage_probe.json")
            if args.fixture_language_probe and not args.dry_run:
                import_language_probe(con, Path(__file__).parent / "tests/fixtures/p52_language_probe.json")
            if args.fixture_john_list and not args.dry_run:
                import_search_fixture(con, Path(__file__).parent / "tests/fixtures/john_list_probe.json")
            jobs = [(doc, stage) for doc in sorted(set(args.doc_id)) for stage in ("metadata", "coverage")]
            pending = []
            blocked = []
            for doc, stage in jobs:
                row = con.execute("SELECT state,response_id FROM collection_job WHERE run_id=? AND doc_id=? AND stage=?",
                                  (args.run_id, doc, stage)).fetchone()
                if row and row[0] == "blocked" and args.refresh_stage not in (stage, "both"):
                    blocked.append((doc, stage))
                    continue
                if (args.refresh_stage in (stage, "both") or not row or
                    row[0] not in ("success", "empty") or
                    (stage == "metadata" and not metadata_checkpoint_ready(con, doc, row[1]))):
                    pending.append((doc, stage))
            cached = []
            for doc, stage in pending:
                endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
                params = {"docID": str(doc), "detail": "10" if stage == "metadata" else "long", "format": "json"}
                url = args.base_url.rstrip("/") + "/" + endpoint + "/"
                hit = con.execute("""SELECT 1 FROM source_response WHERE endpoint=? AND url=?
                  AND params_json=? AND status_code BETWEEN 200 AND 299
                  AND (origin='http' OR ?) LIMIT 1""",
                  (endpoint, url, encoded(params), args.offline)).fetchone()
                if hit and args.refresh_stage not in (stage, "both"):
                    cached.append((doc, stage))
            planned_network_jobs = len(pending) - len(cached)
            prior_attempts = con.execute("SELECT count(*) FROM request_attempt WHERE run_id=?",
                                         (args.run_id,)).fetchone()[0]
            searches = [(args.search_ref, name) for name in sorted(set(args.search_ga_num))]
            search_pending = []
            search_blocked = []
            for ref, name in searches:
                row = con.execute("""SELECT state FROM discovery_job WHERE run_id=?
                    AND osis_ref=? AND ga_num=? AND lang_filter=?""",
                    (args.run_id, ref, name, args.search_lang or "")).fetchone()
                if row and row[0] == "blocked" and not args.refresh_search:
                    search_blocked.append((ref, name))
                elif args.refresh_search or not row or row[0] not in ("success", "empty"):
                    search_pending.append((ref, name))
            search_cached = []
            for ref, name in search_pending:
                params = search_params(ref, name, args.search_lang)
                hit = con.execute("""SELECT 1 FROM source_response WHERE endpoint=? AND url=?
                    AND params_json=? AND status_code BETWEEN 200 AND 299
                    AND (origin='http' OR ?) LIMIT 1""",
                    ("metadata/liste/search", args.base_url.rstrip("/") + "/metadata/liste/search/",
                     encoded(params), args.offline)).fetchone()
                if hit and not args.refresh_search:
                    search_cached.append((ref, name))
            planned_network_jobs += len(search_pending) - len(search_cached)
            catalogue_requested = bool(args.catalogue_doc_id)
            catalogue_pending = False
            catalogue_blocked = False
            catalogue_cached = False
            if catalogue_requested:
                catalogue_ids, catalogue_query = catalogue_params(
                    args.catalogue_doc_id, args.catalogue_index_ref, args.catalogue_limit)
                prior = con.execute("""SELECT requested_ids_json,index_ref,page_limit,state
                    FROM catalogue_scope WHERE run_id=?""", (args.run_id,)).fetchone()
                if prior and prior[:3] != (encoded(catalogue_ids), args.catalogue_index_ref, args.catalogue_limit):
                    raise ValueError("Run ID already belongs to a different catalogue scope")
                catalogue_blocked = bool(prior and prior[3] == "blocked" and not args.refresh_catalogue)
                catalogue_pending = not catalogue_blocked and (
                    args.refresh_catalogue or not prior or prior[3] not in ("success", "empty"))
                if catalogue_pending and not args.refresh_catalogue:
                    catalogue_cached = bool(con.execute("""SELECT 1 FROM source_response
                        WHERE endpoint=? AND url=? AND params_json=?
                        AND status_code BETWEEN 200 AND 299
                        AND (origin='http' OR ?) LIMIT 1""",
                        ("metadata/liste/search", args.base_url.rstrip("/") + "/metadata/liste/search/",
                         encoded(catalogue_query), args.offline)).fetchone())
                planned_network_jobs += int(catalogue_pending and not catalogue_cached)
            print(json.dumps({"run_id": args.run_id, "planned_jobs": pending,
                "cached_jobs": cached, "blocked_jobs": blocked, "fixture_p52": args.fixture_p52,
                "search_scope": "named gaNum and single OSIS verse lookups",
                "search_jobs": search_pending, "cached_searches": search_cached,
                "search_cache_scope": "initial pages only; continuations may require requests",
                "blocked_searches": search_blocked,
                "catalogue_doc_ids": sorted(set(args.catalogue_doc_id)),
                "catalogue_pending": catalogue_pending,
                "catalogue_cached": catalogue_cached,
                "catalogue_blocked": catalogue_blocked,
                "prior_network_attempts": prior_attempts,
                "maximum_network_attempts": 0 if args.offline else min(
                    max(0, args.request_budget - prior_attempts),
                    args.request_budget if search_pending or catalogue_pending else planned_network_jobs * 3),
                "offline": args.offline, "refresh_stage": args.refresh_stage}))
            if args.dry_run:
                return 0
            if blocked or search_blocked or catalogue_blocked:
                raise RunStopped("Prior access block requires explicit refresh")
            client = Client(con, args.run_id, base_url=args.base_url, offline=args.offline,
                budget=args.request_budget, interval=args.min_interval,
                jitter=args.jitter, duration=args.max_run_seconds)
            try:
                if catalogue_pending:
                    state = collect_catalogue_scope(client, args.catalogue_doc_id,
                        index_ref=args.catalogue_index_ref, page_limit=args.catalogue_limit,
                        refresh=args.refresh_catalogue)
                    if state not in ("success", "empty"):
                        raise RunStopped("Catalogue scope is incomplete")
                if args.scope_check_ref and not catalogue_report(con, args.run_id)["catalogue_lookup_complete"]:
                    raise RunStopped("Scoped index comparison requires a complete unfiltered ID lookup")
                if args.fixture_p52:
                    collect_stage(client, 10052, "coverage")
                for doc, stage in pending:
                    collect_stage(client, doc, stage, refresh=args.refresh_stage in (stage, "both"))
                for ref, name in search_pending:
                    collect_search(client, ref, name, lang=args.search_lang, refresh=args.refresh_search)
            finally:
                if searches:
                    report = discovery_report(con, args.run_id)
                    print(json.dumps(report))
                if catalogue_requested:
                    scope_report = catalogue_report(con, args.run_id)
                    if scope_report:
                        print(json.dumps(scope_report))
                if args.scope_check_ref and scope_report:
                    index_report = scoped_index_report(con, args.run_id, args.scope_check_ref)
                    print(json.dumps(index_report))
            if searches and any(job["state"] not in ("success", "empty") for job in report["jobs"]):
                raise RunStopped("Search results are incomplete")
            if catalogue_requested and scope_report["state"] not in ("success", "empty"):
                raise RunStopped("Catalogue scope is incomplete")
            if args.scope_check_ref and (index_report["state"] != "complete" or
                                         index_report["named_search_omissions"]):
                raise RunStopped("Scoped index comparison is incomplete or inconsistent")
            if args.export_p52:
                export_p52(con, args.export_p52)
        return 0
    except (OSError, sqlite3.Error, ValueError, RunStopped, JobFailure) as error:
        print(f"Collection incomplete: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
