#!/usr/bin/env python3
"""Capture the four Greek NT catalogue ranges slowly; import their reports offline."""

import argparse
from contextlib import contextmanager, nullcontext
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlsplit

from build_collection import DATA, ROOT, data_path, read_json, write_json
from collect_source_discovery import https_proxy_transport, retained_transport
from controlled_ntvmr import (API_BASE, NT_BOOKS, AccessBlocked, Client, ContractError,
                              JobFailure, RunStopped, encoded, now, transport)
from source_discovery import (catalogue_date_decision, prepare_discovery, range_params, response_capture,
                              sha, validate_date_cutoff, validate_search_capture)
from source_reports import (GREEK_LANGUAGE_CODES, additional_date_claims, capture,
                            discovery_date_overrides, metadata_date_claim)


CATEGORIES = (("papyri", 10000, 19999), ("majuscules", 20000, 29999),
              ("minuscules", 30000, 39999), ("lectionaries", 40000, 49999))
DEFAULT_DATE_CUTOFF = 1000
ENDPOINTS = {"inventory": "metadata/liste/search", "metadata": "metadata/manuscript/get",
             "coverage": "biblicalcontent/get"}
# This is a disposable collection checkpoint, never a build input. Existing
# collection.sqlite is not opened or migrated. Future schema migrations need backups.
SCHEMA = """
PRAGMA user_version=1;
CREATE TABLE source_response (
 id INTEGER PRIMARY KEY, endpoint TEXT NOT NULL, url TEXT NOT NULL,
 params_json TEXT NOT NULL, status_code INTEGER NOT NULL, headers_json TEXT NOT NULL,
 body TEXT NOT NULL, body_sha256 TEXT NOT NULL, retrieved_at TEXT NOT NULL, origin TEXT NOT NULL);
CREATE INDEX response_lookup ON source_response(endpoint,url,params_json,id);
CREATE TABLE request_attempt (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, endpoint TEXT NOT NULL, params_json TEXT NOT NULL,
 attempted_at TEXT NOT NULL, response_id INTEGER REFERENCES source_response(id), failure TEXT);
CREATE TABLE archive (response_id INTEGER PRIMARY KEY REFERENCES source_response(id), capture_file TEXT NOT NULL);
CREATE TABLE campaign (run_id TEXT PRIMARY KEY, config_json TEXT NOT NULL, state TEXT NOT NULL, error TEXT);
CREATE TABLE inventory (
 run_id TEXT NOT NULL REFERENCES campaign(run_id), category TEXT NOT NULL, after_doc_id INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'pending', error TEXT, PRIMARY KEY(run_id,category));
CREATE TABLE inventory_page (
 run_id TEXT NOT NULL, category TEXT NOT NULL, sequence INTEGER NOT NULL,
 response_id INTEGER NOT NULL REFERENCES source_response(id),
 PRIMARY KEY(run_id,category,sequence), FOREIGN KEY(run_id,category) REFERENCES inventory(run_id,category));
CREATE TABLE job (
 run_id TEXT NOT NULL REFERENCES campaign(run_id), doc_id INTEGER NOT NULL, stage TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending', capture_file TEXT, error TEXT,
 PRIMARY KEY(run_id,doc_id,stage));
CREATE TABLE pacing (id INTEGER PRIMARY KEY CHECK(id=1), next_allowed REAL NOT NULL,
 block_reason TEXT, checked_response_id INTEGER NOT NULL);
INSERT INTO pacing VALUES (1,0,NULL,0);
CREATE TABLE access_resolution (recorded_at TEXT NOT NULL, prior_block TEXT NOT NULL, reason TEXT NOT NULL);
"""


@contextmanager
def single_worker(data_dir):
    """OS releases this advisory lock after a crash, so no stale-lock deletion is needed."""
    path = data_dir / ".cache" / "catalogue.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError("Another catalogue collector or importer is already running") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def queue_connection(data_dir, *, create=False):
    path = data_dir / ".cache" / "catalogue.sqlite"
    if not path.exists() and not create:
        raise ValueError("No catalogue checkpoint exists; collect reports first")
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = not path.exists()
    con = sqlite3.connect(path)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        if fresh:
            con.executescript(SCHEMA)
        elif con.execute("PRAGMA user_version").fetchone()[0] != 1 or not con.execute(
                "SELECT 1 FROM sqlite_master WHERE name='campaign'").fetchone():
            raise ValueError("Unsupported catalogue checkpoint schema; preserve it before migrating")
        yield con
    finally:
        con.close()


def validate_config(config):
    validate_date_cutoff(config.get("earliest_date_before", DEFAULT_DATE_CUTOFF))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", config["run_id"]):
        raise ValueError("Use a short run ID containing letters, numbers, dots, underscores, or hyphens")
    if not math.isfinite(config["interval"]) or config["interval"] < 5:
        raise ValueError("The request interval must be at least five seconds")
    if not math.isfinite(config["hours"]) or config["hours"] <= 0:
        raise ValueError("The run needs a positive, finite time budget in hours")
    if config["max_requests"] is not None and config["max_requests"] <= 0:
        raise ValueError("The optional campaign request budget must be positive")
    if not 1 <= config["page_limit"] <= 200:
        raise ValueError("The catalogue page limit must be between 1 and 200")
    parts = urlsplit(config["base_url"])
    if (parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path.rstrip("/") != "/community/vmr/api"):
        raise ValueError("Use an explicit HTTP(S) API base URL ending in /community/vmr/api, without credentials")
    if config.get("https_proxy") and config["base_url"] != API_BASE:
        raise ValueError("A CONNECT proxy requires the canonical HTTPS API base URL")


def campaign_config(con, run_id):
    row = con.execute("SELECT config_json FROM campaign WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown catalogue campaign: {run_id}")
    return json.loads(row[0])


def response_is_block(status, body, headers):
    content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    return status in (401, 403) or (200 <= status < 300 and (
        body.lstrip().lower().startswith(("<!doctype html", "<html")) or "html" in content_type.lower()))


def screen_blocks(con):
    """Recover a block even if interruption preceded the JSON client's status check."""
    checked = con.execute("SELECT checked_response_id FROM pacing WHERE id=1").fetchone()[0]
    for response_id, status, body, headers, origin in con.execute(
            "SELECT id,status_code,body,headers_json,origin FROM source_response WHERE id>? ORDER BY id", (checked,)):
        recent = con.execute("SELECT status_code,origin FROM source_response WHERE id<=? ORDER BY id DESC LIMIT 3",
                             (response_id,)).fetchall() if status == 429 else []
        blocked = origin == "http" and (response_is_block(status, body, json.loads(headers)) or
                                       recent == [(429, "http")] * 3)
        with con:
            if blocked:
                con.execute("UPDATE pacing SET block_reason=coalesce(block_reason,?) WHERE id=1",
                            (f"Provider access block: HTTP {status} or challenge, response {response_id}",))
            con.execute("UPDATE pacing SET checked_response_id=? WHERE id=1", (response_id,))


def start_campaign(con, config, *, access_restored_reason=None):
    validate_config(config)
    screen_blocks(con)
    prior = con.execute("SELECT config_json FROM campaign WHERE run_id=?", (config["run_id"],)).fetchone()
    if prior:
        previous = json.loads(prior[0])
        # Explicitly changing launch time or the campaign request ceiling is fine;
        # changing source scope or route would splice different inventories together.
        fixed = ("base_url", "https_proxy", "page_limit", "interval")
        if any(config.get(key) != previous.get(key) for key in fixed):
            raise ValueError("Resume with the same API route, page limit, and interval")
        if config["max_requests"] is None and previous["max_requests"] is not None:
            config["max_requests"] = previous["max_requests"]
        # A local date filter can change without splicing different API inventories.
        # Old checkpoints adopt the default on their first resume with this version.
        config.setdefault("earliest_date_before", previous.get("earliest_date_before", DEFAULT_DATE_CUTOFF))
    else:
        config.setdefault("earliest_date_before", DEFAULT_DATE_CUTOFF)
    validate_date_cutoff(config["earliest_date_before"])
    blocked = con.execute("SELECT block_reason FROM pacing WHERE id=1").fetchone()[0]
    if blocked and not (access_restored_reason and access_restored_reason.strip()):
        raise AccessBlocked(f"Prior provider block is preserved: {blocked}")
    with con:
        if blocked:
            con.execute("INSERT INTO access_resolution VALUES (?,?,?)", (now(), blocked, access_restored_reason.strip()))
            con.execute("UPDATE pacing SET block_reason=NULL WHERE id=1")
            # An HTML challenge with HTTP 200 must remain evidence, but must not
            # be replayed as a successful cache hit after access is restored.
            for response_id, body, headers in con.execute(
                    "SELECT id,body,headers_json FROM source_response WHERE status_code BETWEEN 200 AND 299"):
                content_type = next((v for k, v in json.loads(headers).items() if k.lower() == "content-type"), "")
                if body.lstrip().lower().startswith(("<!doctype html", "<html")) or "html" in content_type.lower():
                    con.execute("UPDATE source_response SET origin='blocked' WHERE id=?", (response_id,))
            con.execute("UPDATE source_response SET origin='blocked' WHERE status_code IN (401,403,429)")
        con.execute("INSERT INTO campaign VALUES (?,?,'running',NULL) ON CONFLICT(run_id) "
                    "DO UPDATE SET config_json=excluded.config_json,state='running',error=NULL",
                    (config["run_id"], encoded(config)))
        for category, _, _ in CATEGORIES:
            con.execute("INSERT OR IGNORE INTO inventory(run_id,category) VALUES (?,?)", (config["run_id"], category))


def archive_response(con, data_dir, response_id):
    record = response_capture(con, response_id)
    endpoint = con.execute("SELECT endpoint FROM source_response WHERE id=?", (response_id,)).fetchone()[0]
    if endpoint not in ENDPOINTS.values():
        raise ValueError("Only catalogue, metadata, and verse-content reports may be archived")
    routed_url = record["source_url"]
    config_origins = []
    for (body,) in con.execute("SELECT config_json FROM campaign"):
        config = json.loads(body)
        config_origins.extend((config["base_url"] if config["base_url"] != API_BASE else None,
                               config.get("https_proxy")))
    record = retained_transport(record, *config_origins)
    record["source_url"] = API_BASE + "/" + endpoint + "/"
    if routed_url != record["source_url"]:
        record["transport_url"] = retained_transport(routed_url, *config_origins)
    stage = next(stage for stage, value in ENDPOINTS.items() if value == endpoint)
    identifier = record["params"].get("docID", "catalogue")
    target = data_dir / "sources" / f"ntvmr-{identifier}-{stage}-{sha(encoded(record))[:16]}.json"
    if target.exists() and read_json(target) != record:
        raise ValueError("Source capture filename collision; preserve both responses")
    write_json(target, record)
    relative = target.relative_to(data_dir).as_posix()
    with con:
        con.execute("INSERT OR REPLACE INTO archive VALUES (?,?)", (response_id, relative))
    return relative


def recover_archives(con, data_dir):
    # A crash after the SQLite commit but before the file write needs no re-fetch.
    for (response_id,) in con.execute("SELECT id FROM source_response"):
        row = con.execute("SELECT capture_file FROM archive WHERE response_id=?", (response_id,)).fetchone()
        if row is None or not data_path(data_dir, row[0]).exists():
            archive_response(con, data_dir, response_id)


class CatalogueClient(Client):
    """One pacer across categories, retries, launches, and campaign IDs."""

    def __init__(self, con, config, data_dir, *, send=transport, sleep=time.sleep,
                 clock=time.monotonic, wall_clock=time.time, progress=None):
        super().__init__(con, config["run_id"], base_url=config["base_url"], budget=config["max_requests"],
                         interval=config["interval"], duration=config["hours"] * 3600,
                         jitter=0, send=send, sleep=sleep, clock=clock)
        self.data_dir, self.wall_clock, self.progress = data_dir, wall_clock, progress
        due = con.execute("SELECT next_allowed FROM pacing WHERE id=1").fetchone()[0]
        self.first_network_at = clock() + self.interval if due else clock()

    def wait(self, delay):
        # In particular, preserve Retry-After if the deadline or Ctrl+C ends a wait.
        with self.con:
            self.con.execute("UPDATE pacing SET next_allowed=max(next_allowed,?) WHERE id=1",
                             (self.wall_clock() + max(0, delay),))
        super().wait(delay)

    def attempt(self, endpoint, params):
        if endpoint not in ENDPOINTS.values():
            raise ValueError("This collector does not request images or transcriptions")
        due, blocked = self.con.execute("SELECT next_allowed,block_reason FROM pacing WHERE id=1").fetchone()
        if blocked:
            raise AccessBlocked(f"Prior provider block is preserved: {blocked}")
        if self.budget is not None and self.attempts >= self.budget:
            raise RunStopped("Campaign request budget exhausted")
        self.wait(max(0, due - self.wall_clock(), self.first_network_at - self.clock()))
        with self.con:
            self.con.execute("UPDATE pacing SET next_allowed=? WHERE id=1", (self.wall_clock() + self.interval,))
        try:
            result = super().attempt(endpoint, params)
            screen_blocks(self.con)
            archive_response(self.con, self.data_dir, result[3])
            if self.progress:
                self.progress({"event": "request", "attempts": self.attempts, "endpoint": endpoint,
                               "docID": params.get("docID"), "http_status": result[0]})
            return result
        finally:
            # Waiting five seconds after response completion is conservative and
            # also protects the first request after a restart.
            with self.con:
                self.con.execute("UPDATE pacing SET next_allowed=max(next_allowed,?) WHERE id=1",
                                 (self.wall_clock() + self.interval,))


def scope_definition(config, category, low, high):
    return {"format_version": 2, "scope_type": "catalogue_range",
            "scope_id": f"catalogue-{config['run_id']}-{category}", "category": category,
            "books": list(NT_BOOKS), "doc_id_min": low, "doc_id_max": high,
            "page_limit": config["page_limit"], "catalogue_citation": API_BASE + "/metadata/liste/search/",
            "earliest_date_before": config.get("earliest_date_before"),
            "access_expectations": "Owner-authorized catalogue collection, one worker, at least five-second "
                "spacing, shared campaign budget and launch deadline, Retry-After, and persistent provider-block stops. "
                "Unfiltered inventory; the declared earliest-date cutoff screens follow-up requests locally. "
                "Metadata and reported verse contents only; no images or transcriptions.",
            "request_budget": config["max_requests"], "minimum_interval_seconds": config["interval"],
            "maximum_run_seconds": config["hours"] * 3600}


def reused_report(data_dir, documents, doc_id, stage):
    document = documents.get(doc_id)
    relative = document.get(f"{stage}_fixture") if document else None
    if relative:
        capture(data_path(data_dir, relative), doc_id, stage)
    return relative


def retained_dates(con, data_dir, collection):
    """Reuse known metadata and published alternatives, without fetching or interpreting dates."""
    documents = {d["doc_id"]: d for d in collection["documents"]}
    paths = {(doc, item["metadata_fixture"]) for doc, item in documents.items() if item.get("metadata_fixture")}
    # Include committed responses even if interruption preceded a job checkpoint.
    for params, path in con.execute("SELECT r.params_json,a.capture_file FROM source_response r "
                                   "JOIN archive a ON a.response_id=r.id WHERE r.endpoint=? AND r.status_code=200",
                                   (ENDPOINTS["metadata"],)):
        doc = json.loads(params).get("docID", "")
        if str(doc).isdigit():
            paths.add((int(doc), path))
    dates = []
    for doc, path in sorted(paths):
        try:
            snap, payload, metadata = capture(data_path(data_dir, path), doc, "metadata")
        except (ValueError, KeyError, TypeError):
            # An unusable capture cannot establish an earlier estimate.
            continue
        dates.append({**metadata_date_claim(documents.get(doc, {"doc_id": doc}), snap, payload, metadata),
                      "capture_file": path})
    witnesses = {d.get("witness_id", f"ntvmr:{doc}") for doc, d in documents.items()}
    for report in collection.get("additional_reports", []):
        dates.extend(additional_date_claims(report, witnesses))
    discovery_path = data_path(data_dir, collection.get("discovery", "discovery.json"))
    if discovery_path.exists():
        for record in read_json(discovery_path):
            dates.extend(discovery_date_overrides(record, collection["documents"]))
    by_witness = {}
    for claim in dates:
        by_witness.setdefault(claim["witness_id"], []).append(claim)
    known = {doc: {} for doc, _ in paths}
    known.update({claim["doc_id"]: {} for claim in dates if "doc_id" in claim})
    known.update(documents)
    return {doc: by_witness.get(item.get("witness_id", f"ntvmr:{doc}"), []) for doc, item in known.items()}


def apply_date_filter(con, config, date_claims):
    """Reassess unfinished jobs from retained pages; captured reports are never removed."""
    cutoff = config["earliest_date_before"]
    decisions = {}
    pages = con.execute("SELECT p.response_id FROM inventory_page p WHERE p.run_id=? ORDER BY p.category,p.sequence",
                        (config["run_id"],)).fetchall()
    for (response_id,) in pages:
        record = response_capture(con, response_id)
        rows, _, _ = validate_search_capture(record, record["params"])
        for row in rows:
            doc = row["docID"]
            decisions[doc] = catalogue_date_decision(row, cutoff, date_claims.get(doc, ()))
    with con:
        for doc, decision in decisions.items():
            for stage, state, error in con.execute("SELECT stage,state,error FROM job WHERE run_id=? AND doc_id=? "
                                                   "AND state!='captured'", (config["run_id"], doc)).fetchall():
                previous = json.loads(error) if state == "date_excluded" else {"previous_state": state, "previous_error": error}
                if decision["state"] == "date_excluded":
                    previous["reason"] = decision["reason"]
                    con.execute("UPDATE job SET state='date_excluded',error=? WHERE run_id=? AND doc_id=? AND stage=?",
                                (encoded(previous), config["run_id"], doc, stage))
                elif state == "date_excluded":
                    con.execute("UPDATE job SET state=?,error=? WHERE run_id=? AND doc_id=? AND stage=?",
                                (previous["previous_state"], previous["previous_error"], config["run_id"], doc, stage))
    return decisions


def recover_captured_jobs(con, run_id, data_dir, seed, retry_jobs=()):
    """Keep committed reports captured if interruption preceded the job update."""
    retained = {}
    for endpoint, params, path, body in con.execute("SELECT r.endpoint,r.params_json,a.capture_file,r.body FROM source_response r "
            "JOIN archive a ON a.response_id=r.id WHERE r.status_code=200 AND r.origin!='blocked' ORDER BY r.id"):
        if endpoint in (ENDPOINTS["metadata"], ENDPOINTS["coverage"]):
            try:
                json.loads(body)
                retained[endpoint, params] = path
            except ValueError:
                retained[endpoint, params] = None
    with con:
        for doc, stage in con.execute("SELECT doc_id,stage FROM job WHERE run_id=? AND state IN ('pending','date_excluded')",
                                      (run_id,)).fetchall():
            if (doc, stage) in retry_jobs:
                continue
            params = encoded({"docID": str(doc), "detail": "10" if stage == "metadata" else "long", "format": "json"})
            path = reused_report(data_dir, seed, doc, stage) or retained.get((ENDPOINTS[stage], params))
            if path:
                con.execute("UPDATE job SET state='captured',capture_file=?,error=NULL WHERE run_id=? AND doc_id=? AND stage=?",
                            (path, run_id, doc, stage))


def collect_inventory(client, config, category, low, high, seed):
    con, run_id = client.con, config["run_id"]
    after, state = con.execute("SELECT after_doc_id,state FROM inventory WHERE run_id=? AND category=?",
                              (run_id, category)).fetchone()
    if state != "pending":
        return
    definition = scope_definition(config, category, low, high)
    first = con.execute("SELECT response_id FROM inventory_page WHERE run_id=? AND category=? ORDER BY sequence LIMIT 1",
                        (run_id, category)).fetchone()
    first_id = first[0] if first else 0
    while True:
        params = range_params(definition)
        if after:
            params["afterDocID"] = str(after)
        _, response_id = client.get_json(ENDPOINTS["inventory"], params, min_response_id=first_id)
        relative = archive_response(con, client.data_dir, response_id)
        record = read_json(data_path(client.data_dir, relative))
        rows, count, cursor = validate_search_capture(record, params)
        ids = {row["docID"] for row in rows}
        if any(not low <= doc <= high or doc <= after for doc in ids):
            raise ContractError("Catalogue page leaves its range or repeats earlier document IDs")
        if any(con.execute("SELECT 1 FROM job WHERE run_id=? AND doc_id=?", (run_id, doc)).fetchone() for doc in ids):
            raise ContractError("Catalogue pagination repeats a document")
        # Validate seeds before the page checkpoint; failures cannot leave a half-page queue.
        reused = {(doc, stage): reused_report(client.data_dir, seed, doc, stage)
                  for doc in ids for stage in ("metadata", "coverage")}
        with con:
            sequence = con.execute("SELECT count(*) FROM inventory_page WHERE run_id=? AND category=?",
                                   (run_id, category)).fetchone()[0]
            con.execute("INSERT INTO inventory_page VALUES (?,?,?,?)", (run_id, category, sequence, response_id))
            for doc in sorted(ids):
                for stage in ("metadata", "coverage"):
                    path = reused[doc, stage]
                    con.execute("INSERT INTO job(run_id,doc_id,stage,state,capture_file) VALUES (?,?,?,?,?)",
                                (run_id, doc, stage, "captured" if path else "pending", path))
            failed = count != len(rows)
            state = "failed" if failed else "complete" if cursor is None else "pending"
            con.execute("UPDATE inventory SET after_doc_id=?,state=?,error=? WHERE run_id=? AND category=?",
                        (cursor or after, state, "Catalogue count disagrees with returned records" if failed else None,
                         run_id, category))
        if cursor is None or failed:
            return
        after, first_id = cursor, first_id or response_id


def summary(con, run_id):
    config = campaign_config(con, run_id)
    state, error = con.execute("SELECT state,error FROM campaign WHERE run_id=?", (run_id,)).fetchone()
    categories = []
    for category, low, high in CATEGORIES:
        item = con.execute("SELECT state,after_doc_id,error FROM inventory WHERE run_id=? AND category=?",
                           (run_id, category)).fetchone()
        counts = dict(con.execute("SELECT state,count(*) FROM job WHERE run_id=? AND doc_id BETWEEN ? AND ? GROUP BY state",
                                  (run_id, low, high)))
        categories.append({"category": category, "inventory_state": item[0], "after_doc_id": item[1],
                           "inventory_error": item[2], "documents": sum(counts.values()) // 2, "reports": counts,
                           "date_excluded_documents": con.execute("SELECT count(DISTINCT doc_id) FROM job WHERE run_id=? "
                               "AND doc_id BETWEEN ? AND ? AND state='date_excluded'", (run_id, low, high)).fetchone()[0]})
    return {"run_id": run_id, "state": state, "error": error, "categories": categories,
            "earliest_date_before": config.get("earliest_date_before"),
            "request_attempts": con.execute("SELECT count(*) FROM request_attempt WHERE run_id=?", (run_id,)).fetchone()[0],
            "provider_block": con.execute("SELECT block_reason FROM pacing WHERE id=1").fetchone()[0],
            "failed_reports": [{"doc_id": doc, "stage": stage, "error": failure} for doc, stage, failure in con.execute(
                "SELECT doc_id,stage,error FROM job WHERE run_id=? AND state='failed' ORDER BY doc_id,stage", (run_id,))],
            "date_exclusions": [{"doc_id": doc, "reason": json.loads(reason)["reason"]} for doc, reason in con.execute(
                "SELECT doc_id,min(error) FROM job WHERE run_id=? AND state='date_excluded' GROUP BY doc_id ORDER BY doc_id", (run_id,))],
            "corpus_complete": False}


def collect(con, config, data_dir, *, send=transport, sleep=time.sleep, clock=time.monotonic,
            wall_clock=time.time, progress=None, access_restored_reason=None, retry_failed=False):
    recover_archives(con, data_dir)
    start_campaign(con, config, access_restored_reason=access_restored_reason)
    collection = read_json(data_dir / "collection.json")
    seed = {d["doc_id"]: d for d in collection["documents"]}
    recover_captured_jobs(con, config["run_id"], data_dir, seed)
    known_dates = retained_dates(con, data_dir, collection)
    apply_date_filter(con, config, known_dates)
    retry_jobs = set(con.execute("SELECT doc_id,stage FROM job WHERE run_id=? AND state='failed'", (config["run_id"],))) if retry_failed else set()
    if retry_failed:
        with con:
            con.execute("UPDATE job SET state='pending',error=NULL WHERE run_id=? AND state='failed'", (config["run_id"],))
    client = CatalogueClient(con, config, data_dir, send=send, sleep=sleep, clock=clock,
                             wall_clock=wall_clock, progress=progress)
    state, error = "complete", None
    try:
        for category, low, high in CATEGORIES:
            try:
                collect_inventory(client, config, category, low, high, seed)
            except (ContractError, JobFailure, ValueError) as failure:
                with con:
                    con.execute("UPDATE inventory SET state='failed',error=? WHERE run_id=? AND category=?",
                                (str(failure), config["run_id"], category))
            finally:
                recover_captured_jobs(con, config["run_id"], data_dir, seed, retry_jobs)
                decisions = apply_date_filter(con, config, known_dates)
        jobs = con.execute("SELECT doc_id,stage FROM job WHERE run_id=? AND state='pending' "
                           "ORDER BY doc_id,CASE stage WHEN 'metadata' THEN 0 ELSE 1 END", (config["run_id"],)).fetchall()
        # Unknown inventory dates remain eligible, after the dated candidates.
        jobs.sort(key=lambda job: decisions.get(job[0], {}).get("state") == "unknown_date")
        for doc, stage in jobs:
            try:
                params = {"docID": str(doc), "detail": "10" if stage == "metadata" else "long", "format": "json"}
                _, response_id = client.get_json(ENDPOINTS[stage], params, refresh=(doc, stage) in retry_jobs)
                relative = archive_response(con, data_dir, response_id)
                with con:
                    con.execute("UPDATE job SET state='captured',capture_file=?,error=NULL WHERE run_id=? AND doc_id=? AND stage=?",
                                (relative, config["run_id"], doc, stage))
            except (ContractError, JobFailure, ValueError) as failure:
                with con:
                    con.execute("UPDATE job SET state='failed',error=? WHERE run_id=? AND doc_id=? AND stage=?",
                                (str(failure), config["run_id"], doc, stage))
        if con.execute("SELECT 1 FROM inventory WHERE run_id=? AND state!='complete'", (config["run_id"],)).fetchone() or con.execute(
                "SELECT 1 FROM job WHERE run_id=? AND state NOT IN ('captured','date_excluded')", (config["run_id"],)).fetchone():
            state = "incomplete"
    except AccessBlocked as failure:
        state, error = "blocked", str(failure)
        with con:
            con.execute("UPDATE pacing SET block_reason=? WHERE id=1", (error,))
    except RunStopped as failure:
        state, error = "paused", str(failure)
    except KeyboardInterrupt:
        blocked = con.execute("SELECT block_reason FROM pacing WHERE id=1").fetchone()[0]
        state, error = ("blocked", blocked) if blocked else ("paused", "Interrupted; committed captures and queue are retained")
    with con:
        con.execute("UPDATE campaign SET state=?,error=? WHERE run_id=?", (state, error, config["run_id"]))
    return summary(con, config["run_id"])


def import_captures(con, data_dir, run_id):
    """Validate and merge captures without a transport, a live request, or an app build."""
    config = campaign_config(con, run_id)
    campaign_state, campaign_error = con.execute("SELECT state,error FROM campaign WHERE run_id=?", (run_id,)).fetchone()
    recover_archives(con, data_dir)
    path = data_dir / "collection.json"
    original = read_json(path)
    collection = deepcopy(original)
    discovery_path = data_path(data_dir, collection.get("discovery", "discovery.json"))
    original_discovery = read_json(discovery_path) if discovery_path.exists() else []
    records = deepcopy(original_discovery)
    known = {doc["doc_id"]: doc for doc in collection["documents"]}
    errors, added, filled = [], 0, 0
    for (doc,) in con.execute("SELECT DISTINCT doc_id FROM job WHERE run_id=? ORDER BY doc_id", (run_id,)):
        item = deepcopy(known.get(doc, {"doc_id": doc, "corpus": "greek_nt_manuscript"}))
        for stage in ("metadata", "coverage"):
            if item.get(f"{stage}_fixture"):
                continue
            row = con.execute("SELECT capture_file FROM job WHERE run_id=? AND doc_id=? AND stage=? AND state='captured'",
                              (run_id, doc, stage)).fetchone()
            if not row:
                continue
            try:
                if stage == "coverage" and not item.get("metadata_fixture"):
                    raise ValueError("Contents await usable Greek NT metadata")
                _, _, parsed = capture(data_path(data_dir, row[0]), doc, stage)
                if stage == "metadata" and (parsed["source_lang"] not in GREEK_LANGUAGE_CODES
                                             or not parsed["ga_num"]):
                    raise ValueError("Metadata is outside the supported Greek GA catalogue contract")
                item[f"{stage}_fixture"] = row[0]
                filled += 1
            except (ValueError, KeyError, TypeError) as failure:
                errors.append(f"{doc} {stage}: {failure}")
        if item.get("metadata_fixture"):
            if doc in known:
                known[doc].update(item)
            else:
                collection["documents"].append(item)
                known[doc] = item
                added += 1
    ready = []
    date_claims = []
    # Existing source fidelity is checked as well, using only one report at a time.
    for item in collection["documents"]:
        metadata_state, coverage_state = "missing", "missing"
        if item.get("metadata_fixture"):
            snap, payload, metadata = capture(data_path(data_dir, item["metadata_fixture"]), item["doc_id"], "metadata")
            date_claims.append(metadata_date_claim(item, snap, payload, metadata))
            metadata_state = "success"
        if item.get("coverage_fixture"):
            _, _, entries = capture(data_path(data_dir, item["coverage_fixture"]), item["doc_id"], "coverage")
            coverage_state = "success" if entries else "empty"
        ready.append({"doc_id": item["doc_id"], "witness_id": item.get("witness_id", f"ntvmr:{item['doc_id']}"),
                      "metadata_state": metadata_state, "coverage_state": coverage_state})
    for report in collection.get("additional_reports", []):
        date_claims.extend(additional_date_claims(report, {d["witness_id"] for d in ready}))
    known_dates = retained_dates(con, data_dir, collection)
    attempts = [json.loads(row[0]) for row in con.execute("SELECT params_json FROM request_attempt WHERE run_id=?", (run_id,))]
    for category, low, high in CATEGORIES:
        definition = scope_definition(config, category, low, high)
        state, error = con.execute("SELECT state,error FROM inventory WHERE run_id=? AND category=?", (run_id, category)).fetchone()
        pages = []
        for (response_id,) in con.execute("SELECT response_id FROM inventory_page WHERE run_id=? AND category=? ORDER BY sequence",
                                          (run_id, category)):
            relative = archive_response(con, data_dir, response_id)
            pages.append(read_json(data_path(data_dir, relative)))
        cost = sum(params.get("docID") == f"{low}-{high}" or
                   (str(params.get("docID", "")).isdigit() and low <= int(params["docID"]) <= high) for params in attempts)
        record = {"format_version": 2, "definition": definition,
                  "run_state": "complete" if state == "complete" else "failed" if state == "failed"
                               else "blocked" if campaign_state == "blocked" else "pending",
                  "run_error": error or campaign_error, "search_captures": pages,
                  "collection_cost": {"request_attempts": cost, "campaign_total_request_attempts": len(attempts),
                                      "campaign_state": campaign_state, "campaign_error": campaign_error,
                                      "shared_campaign_request_budget": config["max_requests"],
                                      "collection_errors": [e for e in errors if low <= int(e.split()[0]) <= high]}}
        # Preserve the evidence for earlier estimates from nonprimary metadata.
        # These qualify collection only; they do not silently replace active date claims.
        extra = {}
        cutoff = definition["earliest_date_before"]
        if cutoff is not None:
            primary_hashes = {d["source_sha256"] for d in date_claims}
            for page in pages:
                rows, _, _ = validate_search_capture(page, page["params"])
                for row in rows:
                    if catalogue_date_decision(row, cutoff)["state"] != "date_excluded":
                        continue
                    for claim in known_dates.get(row["docID"], []):
                        if (claim.get("capture_file") and claim["status"] == "valid" and claim["date_min"] < cutoff
                                and claim["source_sha256"] not in primary_hashes):
                            extra[claim["doc_id"], claim["source_sha256"]] = {
                                "doc_id": claim["doc_id"], "capture_file": claim["capture_file"],
                                "capture": read_json(data_path(data_dir, claim["capture_file"]))}
        if extra:
            record["date_filter_metadata_captures"] = list(extra.values())
        record = retained_transport(record, config["base_url"] if config["base_url"] != API_BASE else None,
                                    config.get("https_proxy"))
        prepare_discovery(record, ready, date_claims + discovery_date_overrides(record, ready))
        records = [r for r in records if r["definition"]["scope_id"] != definition["scope_id"]]
        records.append(record)
    publisher = read_json(data_path(data_dir, collection["coordinate_inventory"]))
    collection["books"] = list(dict.fromkeys(v["osis_ref"].split(".")[0] for v in publisher["verses"]
                                             if v["osis_ref"].split(".")[0] in NT_BOOKS))
    collection["discovery"] = discovery_path.relative_to(data_dir).as_posix()
    if read_json(path) != original or (read_json(discovery_path) if discovery_path.exists() else []) != original_discovery:
        raise ValueError("Central registers changed during import; captures remain available")
    write_json(discovery_path, records)
    write_json(path, collection)
    return {"run_id": run_id, "documents_added": added, "report_fields_added": filled,
            "import_errors": errors, "network_requests": 0, "rebuild_required": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("collect", "status", "import"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument("--data-dir", type=Path, default=DATA)
        command_parser.add_argument("--run-id", default="catalogue")
        if command == "collect":
            command_parser.add_argument("--hours", type=float, default=8, help="Time budget for this launch; resume on another night")
            command_parser.add_argument("--interval", type=float, default=5, help="Minimum seconds between requests, at least 5")
            command_parser.add_argument("--max-requests", type=int, help="Optional cumulative campaign attempt ceiling, including retries; no 50-attempt cap")
            command_parser.add_argument("--page-limit", type=int, default=200)
            dates = command_parser.add_mutually_exclusive_group()
            dates.add_argument("--earliest-date-before", type=int, default=argparse.SUPPRESS,
                               help="Collect ranges starting before this CE year (default 1000; retained on resume); unknown dates remain eligible")
            dates.add_argument("--no-date-cutoff", dest="earliest_date_before", action="store_const", const=None,
                               default=argparse.SUPPRESS, help="Collect all dates; reopen jobs previously skipped by the cutoff")
            route = command_parser.add_mutually_exclusive_group()
            route.add_argument("--base-url", help="Explicit owner-configured API proxy base URL")
            route.add_argument("--use-local-proxy", action="store_true", help="Use the single proxy address documented in README.md")
            route.add_argument("--https-proxy", help="Explicit HTTPS CONNECT proxy")
            command_parser.add_argument("--access-restored-reason", help="Explicitly acknowledge resolved provider access; records the reason before resuming")
            command_parser.add_argument("--retry-failed", action="store_true", help="Explicitly retry failed document requests; successful reports and provider blocks are preserved")
    args = parser.parse_args(argv)
    try:
        data_dir = args.data_dir.resolve()
        lock = nullcontext() if args.command == "status" else single_worker(data_dir)
        with lock, queue_connection(data_dir, create=args.command == "collect") as con:
            if args.command == "collect":
                base_url = args.base_url or API_BASE
                if args.use_local_proxy:
                    match = re.search(r"The current address is `(https?://[^`]+)`", (ROOT / "README.md").read_text(encoding="utf-8"))
                    if not match:
                        raise ValueError("No current local proxy address is documented in README.md")
                    base_url = match[1].rstrip("/") + "/community/vmr/api"
                config = {"run_id": args.run_id, "hours": args.hours, "interval": args.interval,
                          "max_requests": args.max_requests, "page_limit": args.page_limit,
                          "base_url": base_url.rstrip("/"), "https_proxy": args.https_proxy}
                if hasattr(args, "earliest_date_before"):
                    config["earliest_date_before"] = args.earliest_date_before
                send = https_proxy_transport(args.https_proxy) if args.https_proxy else transport
                result = collect(con, config, data_dir, send=send,
                    access_restored_reason=args.access_restored_reason,
                    retry_failed=args.retry_failed,
                    progress=lambda event: print(json.dumps(event, sort_keys=True), flush=True))
            elif args.command == "import":
                result = import_captures(con, data_dir, args.run_id)
            else:
                result = summary(con, args.run_id)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 0 if (result.get("state") == "complete" or args.command == "status"
                     or (args.command == "import" and not result["import_errors"])) else 2
    except (ValueError, RunStopped, OSError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
