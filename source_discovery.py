"""Bounded book-index discovery; search matches never become contents claims."""

import hashlib
import json
from datetime import datetime
from urllib.parse import urlencode

from controlled_ntvmr import (API_BASE, NT_BOOKS, AccessBlocked, ContractError,
                              JobFailure, RunStopped, collect_search_pages, encoded,
                              parse_search, search_continuation)


SCHEMA = """
CREATE TABLE IF NOT EXISTS scholarly_discovery_run (
 run_id TEXT PRIMARY KEY, definition_json TEXT NOT NULL, state TEXT NOT NULL,
 error TEXT, terminal_response_id INTEGER REFERENCES source_response(id));
"""
LIMITATION = ("The book-index query covers only its declared document-ID range and source snapshot. "
              "Unindexed or differently indexed witnesses and other catalogue ranges may be missed. "
              "Rankings describe the collected witnesses; exhaustive earliest-witness discovery is not established.")


def sha(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def range_params(definition):
    if definition.get("format_version") != 1 or definition.get("book") not in NT_BOOKS:
        raise ValueError("Discovery requires format 1 and one New Testament book code")
    for field in ("scope_id", "catalogue_citation", "access_expectations"):
        if not isinstance(definition.get(field), str) or not definition[field].strip():
            raise ValueError(f"Discovery requires {field}")
    if definition.get("transport_base_url"):
        if not isinstance(definition.get("transport_qualification"), str) or not definition["transport_qualification"].strip():
            raise ValueError("A configured relay requires an explicit transport qualification")
    low, high, limit = (definition.get(k) for k in ("doc_id_min", "doc_id_max", "page_limit"))
    if type(low) is not int or type(high) is not int or not 0 < low < high or high-low >= 50000:
        raise ValueError("Discovery requires a positive finite range of at most 50,000 IDs")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("Discovery page limit must be between 1 and 200")
    budget = definition.get("request_budget")
    interval = definition.get("minimum_interval_seconds")
    duration = definition.get("maximum_run_seconds")
    if type(budget) is not int or not 1 <= budget <= 50:
        raise ValueError("Discovery requires a budget of 1 to 50 attempts, including document collection")
    if type(interval) not in (int, float) or interval < 5:
        raise ValueError("Discovery minimum interval must be at least five seconds")
    if type(duration) not in (int, float) or not 0 < duration <= 600:
        raise ValueError("Discovery requires a run duration of at most 600 seconds")
    return {"docID": f"{low}-{high}", "indexContent": definition["book"],
            "detail": "document", "format": "json", "limit": str(limit)}


def response_capture(con, response_id):
    row = con.execute("""SELECT url,params_json,status_code,headers_json,body,body_sha256,retrieved_at
                         FROM source_response WHERE id=?""", (response_id,)).fetchone()
    if row is None:
        raise ValueError("Discovery source response is missing")
    # Session credentials are not source evidence. Continuation headers are retained.
    headers = {k: v for k, v in json.loads(row[3]).items()
               if k.lower() not in ("set-cookie", "cookie", "authorization")}
    return {"source_url": row[0], "params": json.loads(row[1]), "http_status": row[2],
            "headers": headers, "raw_body": row[4], "body_sha256": row[5], "retrieved_at": row[6]}


def captured_chain(con, definition, base_url=API_BASE, *, offline=True):
    """Read the same advancing cache chain as the collector, without making requests."""
    params, captures, first_id = range_params(definition), [], 0
    while True:
        row = con.execute("""SELECT id FROM source_response WHERE endpoint='metadata/liste/search'
          AND url=? AND params_json=? AND status_code=200 AND id>=? AND (origin='http' OR ?)
          ORDER BY id DESC LIMIT 1""", (base_url + "/metadata/liste/search/", encoded(params), first_id, offline)).fetchone()
        if row is None:
            return captures
        capture = response_capture(con, row[0])
        try:
            payload = json.loads(capture["raw_body"])
            rows, _ = parse_search(payload)
            cursor = search_continuation(payload, rows, capture["headers"], int(params.get("afterDocID", 0)))
        except (ValueError, KeyError):
            return captures
        captures.append(capture)
        if cursor is None:
            return captures
        first_id = first_id or row[0]
        params["afterDocID"] = str(cursor)


def collect_book_range(client, definition):
    params = range_params(definition)
    con = client.con
    con.executescript(SCHEMA)
    prior = con.execute("SELECT definition_json,state FROM scholarly_discovery_run WHERE run_id=?",
                        (client.run_id,)).fetchone()
    if prior and prior[0] != encoded(definition):
        raise ValueError("Run ID already belongs to a different discovery definition")
    if prior and prior[1] == "blocked":
        raise AccessBlocked("Prior discovery access block is preserved; do not automatically retry")
    if prior and prior[1] == "complete":
        return "complete"
    con.execute("""INSERT INTO scholarly_discovery_run VALUES (?,?,'pending',NULL,NULL)
      ON CONFLICT(run_id) DO UPDATE SET state='pending',error=NULL""", (client.run_id, encoded(definition)))
    con.commit()
    try:
        allowed = set(range(definition["doc_id_min"], definition["doc_id_max"]+1))
        records, _, terminal, mismatch = collect_search_pages(client, params, allowed_ids=allowed)
        if any(record["docID"] not in allowed for record, _ in records):
            raise ContractError("Terminal discovery response contains a document outside the declared range")
        state = "incomplete" if mismatch else "complete"
        con.execute("UPDATE scholarly_discovery_run SET state=?,terminal_response_id=? WHERE run_id=?",
                    (state, terminal, client.run_id))
        con.commit()
        return state
    except (ContractError, RunStopped, JobFailure) as error:
        state = "blocked" if isinstance(error, AccessBlocked) else "pending" if isinstance(error, RunStopped) else "failed"
        con.execute("UPDATE scholarly_discovery_run SET state=?,error=? WHERE run_id=?",
                    (state, str(error), client.run_id))
        con.commit()
        raise


def validate_search_capture(record, params):
    if (record.get("http_status") != 200 or record.get("params") != params
            or not isinstance(record.get("source_url"), str)
            or not record["source_url"].endswith("/metadata/liste/search/")
            or not isinstance(record.get("raw_body"), str)
            or sha(record["raw_body"]) != record.get("body_sha256")):
        raise ValueError("Invalid bounded discovery capture")
    stamp = datetime.fromisoformat(record["retrieved_at"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Discovery source timestamp must include a timezone")
    payload = json.loads(record["raw_body"])
    rows, count = parse_search(payload)
    cursor = search_continuation(payload, rows, record.get("headers", {}), int(params.get("afterDocID", 0)))
    return rows, count, cursor


def prepare_discovery(record, documents):
    """Derive completion from retained pages, never from a manifest's optimistic flag."""
    if record is None:
        return {"search_state": "not_searched", "candidate_collection_state": "not_assessed",
                "corpus_complete": False, "ranking_scope": "collected_witnesses_only",
                "limitation": LIMITATION, "candidate_ids": [], "pending_candidate_ids": []}, []
    definition = record["definition"]
    params = range_params(definition)
    captures = record["search_captures"]
    if not isinstance(captures, list):
        raise ValueError("Discovery search captures must be a list")
    candidates, snapshots, seen = [], [], set()
    terminal, mismatch = False, False
    for capture in captures:
        if terminal:
            raise ValueError("Discovery captures continue after a terminal page")
        rows, count, cursor = validate_search_capture(capture, params)
        ids = {row["docID"] for row in rows}
        if seen & ids or any(not definition["doc_id_min"] <= doc <= definition["doc_id_max"]
                            or doc <= int(params.get("afterDocID", 0)) for doc in ids):
            raise ValueError("Discovery captures repeat documents or leave the declared range")
        seen.update(ids)
        mismatch |= count != len(rows)
        snapshot_index = len(snapshots)
        candidates.extend({"doc_id": row["docID"], "reported": row, "snapshot": snapshot_index} for row in rows)
        snapshots.append({"endpoint": "metadata/liste/search", "url": capture["source_url"],
                          "params": dict(params), "body": capture["raw_body"], "headers": capture.get("headers", {}),
                          "body_sha256": capture["body_sha256"], "retrieved_at": capture["retrieved_at"],
                          "provider": "INTF / NTVMR", "citation": API_BASE + "/metadata/liste/search/?" + urlencode(params),
                          "transport_qualification": definition.get("transport_qualification", "Canonical HTTPS transport")})
        terminal = cursor is None
        if not terminal:
            params["afterDocID"] = str(cursor)
    search_state = "complete" if terminal and not mismatch else "incomplete" if captures else "not_completed"
    # A failed/blocked run cannot promote a cached terminal page into fresh completion.
    run_state = record.get("run_state", "complete")
    if run_state not in ("complete", "incomplete", "pending", "failed", "blocked"):
        raise ValueError("Invalid discovery run state")
    if run_state in ("pending", "failed", "blocked"):
        search_state = run_state
    ready = {d["doc_id"] for d in documents
             if d["metadata_state"] == "success" and d["coverage_state"] in ("success", "empty")}
    pending = sorted(seen - ready)
    summary = {"definition": definition, "scope_id": definition["scope_id"],
               "search_state": search_state,
               "candidate_collection_state": "not_assessed" if not seen and search_state != "complete"
                    else "incomplete" if pending else "complete",
               "candidate_ids": sorted(seen), "collected_candidate_ids": sorted(seen & ready),
               "pending_candidate_ids": pending, "additional_collected_doc_ids": sorted(ready-seen),
               "candidates": candidates, "corpus_complete": False,
               "ranking_scope": "collected_witnesses_only", "limitation": LIMITATION,
               "source_snapshots": snapshots,
               "source_hashes": [s["body_sha256"] for s in snapshots],
               "collection_cost": record.get("collection_cost", {}), "run_error": record.get("run_error")}
    return summary, snapshots


def verse_discovery(summary, ref):
    if "scopes" in summary:
        scopes = [verse_discovery(item, ref) for item in summary["scopes"]
                  if item.get("definition", {}).get("book") == ref.split(".")[0]]
        if not scopes:
            return {"state": "not_searched", "ranking_scope": "collected_witnesses_only"}
        # Completion applies only when every declared search for this book is ready.
        state = ("search_incomplete" if any(s["state"] == "search_incomplete" for s in scopes)
                 else "candidate_collection_incomplete" if any(s["state"] == "candidate_collection_incomplete" for s in scopes)
                 else "bounded_search_complete")
        return {"state": state, "scopes": scopes, "corpus_complete": False,
                "ranking_scope": "collected_witnesses_only"}
    if "definition" not in summary or ref.split(".")[0] != summary["definition"]["book"]:
        return {"state": "not_searched", "ranking_scope": "collected_witnesses_only"}
    state = ("bounded_search_complete" if summary["search_state"] == "complete"
             and summary["candidate_collection_state"] == "complete"
             else "candidate_collection_incomplete" if summary["search_state"] == "complete"
             else "search_incomplete")
    return {"state": state, "scope_id": summary["scope_id"],
            "search_state": summary["search_state"],
            "candidate_collection_state": summary["candidate_collection_state"],
            "book_candidate_count": len(summary["candidate_ids"]),
            "pending_candidate_ids": summary["pending_candidate_ids"],
            "corpus_complete": False, "ranking_scope": "collected_witnesses_only"}
