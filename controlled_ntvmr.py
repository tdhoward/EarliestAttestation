#!/usr/bin/env python3
"""Budgeted, resumable NTVMR document collector and offline P52 sample."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
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
SCHEMA = """
PRAGMA foreign_keys=ON;
PRAGMA user_version=3;
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


def parse_coverage(payload, doc_id):
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ContractError("Coverage response lacks success status")
    data = payload.get("data")
    contents = data.get("indexContents") if isinstance(data, dict) else None
    if not isinstance(contents, dict) or contents.get("docID") != doc_id:
        raise ContractError("Coverage response has missing or wrong docID")
    entries = contents.get("indexContent")
    if not isinstance(entries, list):
        raise ContractError("Coverage indexContent is not a list")
    result = []
    for index, entry in enumerate(entries):
        if index == 0 and isinstance(entry, str):
            continue  # The summary range is not verse evidence.
        if not isinstance(entry, dict) or entry.get("docID") != doc_id:
            raise ContractError("Malformed coverage entry")
        ref, page = entry.get("osisID"), entry.get("pageID")
        if not isinstance(ref, str) or not OSIS.fullmatch(ref):
            raise ContractError(f"Invalid OSIS reference: {ref!r}")
        if type(page) is not int or page <= 0:
            raise ContractError(f"Invalid page ID: {page!r}")
        result.append((ref, page))
    return list(dict.fromkeys(result))


def parse_metadata(payload):
    if not isinstance(payload, dict) or payload.get("status") != "success" or not isinstance(payload.get("data"), dict):
        raise ContractError("Metadata response lacks recognized success data")


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
        if self.attempts >= self.budget:
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

    def get_json(self, endpoint, params, *, refresh=False):
        if not refresh:
            row = self.con.execute("""SELECT id,body FROM source_response WHERE endpoint=?
              AND url=? AND params_json=? AND status_code BETWEEN 200 AND 299
              AND (origin='http' OR ?) ORDER BY id DESC LIMIT 1""",
              (endpoint, self.base_url + "/" + endpoint.strip("/") + "/", encoded(params), self.offline)).fetchone()
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


def collect_stage(client, doc_id, stage, *, refresh=False):
    con = client.con
    row = con.execute("SELECT state FROM collection_job WHERE run_id=? AND doc_id=? AND stage=?",
                      (client.run_id, doc_id, stage)).fetchone()
    if row and row[0] in ("success", "empty") and not refresh:
        return row[0]
    set_job(con, client.run_id, doc_id, stage, "pending")
    endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
    params = {"docID": str(doc_id), "detail": "10" if stage == "metadata" else "long", "format": "json"}
    before = client.attempts
    try:
        payload, response_id = client.get_json(endpoint, params, refresh=refresh)
        if stage == "metadata":
            parse_metadata(payload)
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
    params = search_params(ref, ga_num, lang)
    con.execute("""INSERT INTO discovery_job(run_id,osis_ref,ga_num,lang_filter,state,updated_at)
        VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,osis_ref,ga_num,lang_filter)
        DO UPDATE SET state='pending', error=NULL, updated_at=excluded.updated_at""",
        (*key, "pending", now()))
    con.commit()
    try:
        payload, response_id = client.get_json("metadata/liste/search", params, refresh=refresh)
        rows, reported = parse_search(payload)
        state = "incomplete" if reported != len(rows) else "success" if rows else "empty"
        with con:
            con.execute("""DELETE FROM discovery_candidate WHERE run_id=? AND osis_ref=?
                AND ga_num_query=? AND lang_filter=?""", key)
            con.executemany("""INSERT INTO discovery_candidate(run_id,osis_ref,ga_num_query,
                lang_filter,doc_id,response_id,ga_num,primary_name,source_lang,raw_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", [
                (*key, row["docID"], response_id,
                 str(row["gaNum"]) if "gaNum" in row else None,
                 str(row["primaryName"]) if "primaryName" in row else None,
                 row.get("lang"), encoded(row)) for row in rows])
            con.execute("""UPDATE discovery_job SET state=?,response_id=?,reported_count=?,
                returned_count=?,error=?,updated_at=? WHERE run_id=? AND osis_ref=?
                AND ga_num=? AND lang_filter=?""",
                (state, response_id, reported, len(rows),
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


def discovery_report(con, run_id):
    jobs = [dict(zip(("osis_ref", "ga_num", "lang_filter", "state", "reported_count",
                      "returned_count"), row)) for row in con.execute("""SELECT osis_ref,ga_num,
        lang_filter,state,reported_count,returned_count FROM discovery_job
        WHERE run_id=? ORDER BY osis_ref,ga_num,lang_filter""", (run_id,))]
    candidates = [dict(zip(("osis_ref", "query_ga_num", "lang_filter", "doc_id",
                            "ga_num", "primary_name", "source_lang", "review_state",
                            "review_reason"), row)) for row in con.execute("""SELECT osis_ref,
        ga_num_query,lang_filter,doc_id,ga_num,primary_name,source_lang,review_state,
        review_reason FROM discovery_candidate WHERE run_id=?
        ORDER BY osis_ref,ga_num_query,lang_filter,doc_id""", (run_id,))]
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
            "reason": "The API page limit and search indexing have no verified exhaustive contract",
            "jobs": jobs, "candidates": candidates,
            "indexed_coverage_search_omissions": omissions}


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
    ap.add_argument("--export-p52", type=Path)
    args = ap.parse_args(argv)
    if min(args.request_budget, args.max_run_seconds, args.min_interval, args.jitter) < 0:
        ap.error("Budgets and intervals must be nonnegative")
    if any(doc <= 0 for doc in args.doc_id):
        ap.error("Document IDs must be positive")
    if not args.offline and (args.doc_id or args.search_ga_num) and args.request_budget == 0:
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
    try:
        if args.archive_legacy and args.dry_run:
            print(f"Would archive {args.archive_legacy} to {args.archive_to}")
        elif args.archive_legacy:
            archive_legacy(args.archive_legacy, args.archive_to)
            print(f"Archived legacy database to {args.archive_to}")
        with closing(connect(args.db)) as con:
            if args.fixture_p52 and not args.dry_run:
                import_p52(con, Path(__file__).parent / "tests/fixtures/p52_coverage_probe.json")
            if args.fixture_language_probe and not args.dry_run:
                import_language_probe(con, Path(__file__).parent / "tests/fixtures/p52_language_probe.json")
            jobs = [(doc, stage) for doc in sorted(set(args.doc_id)) for stage in ("metadata", "coverage")]
            pending = []
            blocked = []
            for doc, stage in jobs:
                row = con.execute("SELECT state FROM collection_job WHERE run_id=? AND doc_id=? AND stage=?",
                                  (args.run_id, doc, stage)).fetchone()
                if row and row[0] == "blocked" and args.refresh_stage not in (stage, "both"):
                    blocked.append((doc, stage))
                    continue
                if args.refresh_stage in (stage, "both") or not row or row[0] not in ("success", "empty"):
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
            print(json.dumps({"run_id": args.run_id, "planned_jobs": pending,
                "cached_jobs": cached, "blocked_jobs": blocked, "fixture_p52": args.fixture_p52,
                "search_scope": "named gaNum and single OSIS verse lookups",
                "search_jobs": search_pending, "cached_searches": search_cached,
                "blocked_searches": search_blocked,
                "prior_network_attempts": prior_attempts,
                "maximum_network_attempts": 0 if args.offline else min(max(0, args.request_budget - prior_attempts), planned_network_jobs * 3),
                "offline": args.offline, "refresh_stage": args.refresh_stage}))
            if args.dry_run:
                return 0
            if blocked or search_blocked:
                raise RunStopped("Prior access block requires explicit refresh")
            client = Client(con, args.run_id, base_url=args.base_url, offline=args.offline,
                budget=args.request_budget, interval=args.min_interval,
                jitter=args.jitter, duration=args.max_run_seconds)
            try:
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
            if searches and any(job["state"] not in ("success", "empty") for job in report["jobs"]):
                raise RunStopped("Search results are incomplete")
            if args.export_p52:
                export_p52(con, args.export_p52)
        return 0
    except (OSError, sqlite3.Error, ValueError, RunStopped, JobFailure) as error:
        print(f"Collection incomplete: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
