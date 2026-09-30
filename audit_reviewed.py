#!/usr/bin/env python3
"""Read-only structural and cited-benchmark audit of a reviewed NTVMR database."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from controlled_ntvmr import (coverage_review_report, encoded, inventory_ref_parts,
                              parse_search, rank_candidates, ranking_input, ranking_report)


def load_benchmark(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(manifest, dict) and manifest.get("format_version") == 2:
        if set(manifest) != {"format_version", "benchmark_id", "inventory_id",
                             "policy_id", "coverage_citation", "reviewed_on", "cases"}:
            raise ValueError("Benchmark v2 has missing or extra fields")
        if (not isinstance(manifest["coverage_citation"], str) or
                not manifest["coverage_citation"].strip() or
                not isinstance(manifest["reviewed_on"], str)):
            raise ValueError("Benchmark v2 requires citation and review date")
        if not isinstance(manifest["cases"], list):
            raise ValueError("Benchmark v2 requires cases")
        for case in manifest["cases"]:
            if not isinstance(case, dict) or set(case) != {
                    "osis_ref", "witness_id", "expected_coverage", "expected_date",
                    "date_citation", "expected_status"}:
                raise ValueError("Benchmark v2 case has missing or extra fields")
        manifest = {"format_version": 1, "benchmark_id": manifest["benchmark_id"],
                    "inventory_id": manifest["inventory_id"],
                    "policy_id": manifest["policy_id"],
                    "cases": [{**case, "coverage_citation": manifest["coverage_citation"],
                               "reviewed_on": manifest["reviewed_on"]}
                              for case in manifest["cases"]]}
    if not isinstance(manifest, dict) or set(manifest) != {
            "format_version", "benchmark_id", "inventory_id", "policy_id", "cases"}:
        raise ValueError("Benchmark needs format_version, benchmark_id, inventory_id, policy_id, cases")
    if type(manifest["format_version"]) is not int or manifest["format_version"] != 1:
        raise ValueError("Unsupported benchmark format version")
    for key in ("benchmark_id", "inventory_id", "policy_id"):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError(f"Benchmark {key} must be nonempty")
    if not isinstance(manifest["cases"], list) or not manifest["cases"]:
        raise ValueError("Benchmark requires at least one case")
    seen = set()
    for case in manifest["cases"]:
        fields = {"osis_ref", "witness_id", "expected_coverage", "expected_date",
                  "coverage_citation", "date_citation", "reviewed_on"}
        if not isinstance(case, dict) or set(case) not in (fields, fields | {"expected_status"}):
            raise ValueError("Benchmark case has missing or extra fields")
        for key in ("osis_ref", "witness_id", "coverage_citation", "reviewed_on"):
            if not isinstance(case[key], str) or not case[key].strip():
                raise ValueError(f"Benchmark {key} must be nonempty")
        try:
            date.fromisoformat(case["reviewed_on"])
        except ValueError as error:
            raise ValueError("Benchmark reviewed_on must be YYYY-MM-DD") from error
        if case["expected_coverage"] not in ("positive", "rejected"):
            raise ValueError("Expected coverage must be positive or rejected")
        expected_status = case.get("expected_status")
        if expected_status is not None and expected_status not in (
                ("partial", "full") if case["expected_coverage"] == "positive"
                else ("rejected",)):
            raise ValueError("Expected status conflicts with coverage expectation")
        interval = case["expected_date"]
        if interval is not None:
            if (not isinstance(interval, list) or len(interval) != 2 or
                    any(type(year) is not int or year <= 0 for year in interval) or
                    interval[0] > interval[1] or case["expected_coverage"] != "positive" or
                    not isinstance(case["date_citation"], str) or
                    not case["date_citation"].strip()):
                raise ValueError("Expected date needs positive ordered CE bounds and a citation")
        elif case["date_citation"] is not None:
            raise ValueError("Date citation requires expected_date")
        identity = (case["osis_ref"], case["witness_id"])
        if identity in seen:
            raise ValueError(f"Duplicate benchmark case: {identity}")
        seen.add(identity)
    return manifest


def _finding(code, details):
    return {"code": code, "details": details}


def load_source_controls(path):
    controls = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"format_version", "benchmark_id", "doc_id", "witness_label",
                "source_citation", "source_consulted_on", "index_citation",
                "index_source_url", "index_response_sha256",
                "indexed_refs_expected", "neighbor_refs_not_indexed", "scope_note"}
    if not isinstance(controls, dict) or set(controls) != required:
        raise ValueError("Source controls have missing or extra fields")
    if type(controls["format_version"]) is not int or controls["format_version"] != 1:
        raise ValueError("Unsupported source-control format version")
    if type(controls["doc_id"]) is not int or controls["doc_id"] <= 0:
        raise ValueError("Source-control document ID must be positive")
    for key in ("benchmark_id", "witness_label", "source_citation", "source_consulted_on",
                "index_citation", "index_source_url", "index_response_sha256", "scope_note"):
        if not isinstance(controls[key], str) or not controls[key].strip():
            raise ValueError(f"Source-control {key} must be nonempty")
    if (len(controls["index_response_sha256"]) != 64 or
            any(char not in "0123456789abcdef" for char in controls["index_response_sha256"])):
        raise ValueError("Source-control response SHA-256 must be lowercase hex")
    try:
        date.fromisoformat(controls["source_consulted_on"])
    except ValueError as error:
        raise ValueError("Source-control consultation date must be YYYY-MM-DD") from error
    indexed = controls["indexed_refs_expected"]
    neighbors = controls["neighbor_refs_not_indexed"]
    if not isinstance(indexed, list) or not indexed or not isinstance(neighbors, list) or not neighbors:
        raise ValueError("Source controls require expected and neighbor references")
    pairs = []
    for item in indexed:
        if not isinstance(item, dict) or set(item) != {"osis_ref", "page_id"} or \
                type(item["page_id"]) is not int or item["page_id"] <= 0:
            raise ValueError("Expected indexed entry needs one ref and positive page ID")
        inventory_ref_parts(item["osis_ref"])
        pairs.append((item["osis_ref"], item["page_id"]))
    if len(pairs) != len(set(pairs)) or len({ref for ref, _ in pairs}) != len(pairs):
        raise ValueError("Duplicate expected indexed reference")
    for ref in neighbors:
        inventory_ref_parts(ref)
    if len(neighbors) != len(set(neighbors)) or set(neighbors) & {ref for ref, _ in pairs}:
        raise ValueError("Neighbor references must be distinct from expected entries")
    return controls


def source_control_report(con, controls):
    doc_id = controls["doc_id"]
    job_row = con.execute("""SELECT run_id,state,response_id,updated_at FROM collection_job
        WHERE doc_id=? AND stage='coverage' ORDER BY updated_at DESC,rowid DESC LIMIT 1""",
        (doc_id,)).fetchone()
    current_job = dict(zip(("run_id", "state", "response_id", "updated_at"), job_row)) \
        if job_row else None
    index_rows = list(con.execute(
        "SELECT osis_ref,page_id,response_id FROM coverage_index WHERE doc_id=?", (doc_id,)))
    actual = {(ref, page) for ref, page, _ in index_rows}
    expected = {(item["osis_ref"], item["page_id"])
                for item in controls["indexed_refs_expected"]}
    neighbors = set(controls["neighbor_refs_not_indexed"])
    findings = []
    if not current_job or current_job["state"] != "success":
        findings.append(_finding("source_control_collection_not_current", {
            "doc_id": doc_id, "latest_job": current_job}))
    else:
        response = con.execute("""SELECT endpoint,url,status_code,body_sha256,body FROM source_response
            WHERE id=?""", (current_job["response_id"],)).fetchone()
        if (response is None or response[:4] != ("biblicalcontent/get",
                controls["index_source_url"], 200, controls["index_response_sha256"]) or
                hashlib.sha256(response[4].encode("utf-8")).hexdigest() !=
                controls["index_response_sha256"]):
            findings.append(_finding("source_control_source_changed", {"doc_id": doc_id,
                                                                         "response_id": current_job["response_id"]}))
        if any(response_id != current_job["response_id"] for _, _, response_id in index_rows):
            findings.append(_finding("source_control_index_response_mismatch", {"doc_id": doc_id}))
    if actual != expected:
        findings.append(_finding("source_control_index_mismatch", {
            "doc_id": doc_id, "missing": sorted(expected - actual),
            "unexpected": sorted(actual - expected)}))
    indexed_neighbors = sorted((ref, page) for ref, page in actual if ref in neighbors)
    if indexed_neighbors:
        findings.append(_finding("source_control_neighbor_indexed", {
            "doc_id": doc_id, "entries": indexed_neighbors}))
    return {"benchmark_id": controls["benchmark_id"], "doc_id": doc_id,
            "state": "pass" if not findings else "finding",
            "checked_index_entries": len(actual), "latest_coverage_job": current_job,
            "scope": "candidate index alignment only; physical text and date unverified",
            "findings": findings}


def load_date_source(path):
    control = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"format_version", "control_id", "doc_id", "source_url",
                "source_citation", "captured_on", "search_params", "response_sha256",
                "observed", "dating_caveat_citation", "dating_caveat", "usage"}
    if not isinstance(control, dict) or set(control) != required:
        raise ValueError("Date-source control has missing or extra fields")
    if control["format_version"] != 1 or type(control["format_version"]) is not int:
        raise ValueError("Unsupported date-source format version")
    if type(control["doc_id"]) is not int or control["doc_id"] <= 0:
        raise ValueError("Date-source document ID must be positive")
    for key in ("control_id", "source_url", "source_citation", "captured_on",
                "response_sha256", "dating_caveat_citation", "dating_caveat"):
        if not isinstance(control[key], str) or not control[key].strip():
            raise ValueError(f"Date-source {key} must be nonempty")
    date.fromisoformat(control["captured_on"])
    if (len(control["response_sha256"]) != 64 or
            any(char not in "0123456789abcdef" for char in control["response_sha256"])):
        raise ValueError("Date-source response SHA-256 must be lowercase hex")
    if control["usage"] != "catalogue_observation_only":
        raise ValueError("Date-source controls cannot select a ranking date")
    params = control["search_params"]
    if (not isinstance(params, dict) or set(params) !=
            {"gaNum", "indexContent", "detail", "format", "limit", "lang"} or
            any(not isinstance(value, str) or not value for value in params.values()) or
            params["format"] != "json"):
        raise ValueError("Date-source search parameters are invalid")
    inventory_ref_parts(params["indexContent"])
    observed = control["observed"]
    if (not isinstance(observed, dict) or set(observed) !=
            {"original_notation", "date_min", "date_max", "source_language"} or
            any(not isinstance(observed[key], str) or not observed[key].strip()
                for key in ("original_notation", "source_language")) or
            type(observed["date_min"]) is not int or type(observed["date_max"]) is not int or
            not 0 < observed["date_min"] <= observed["date_max"]):
        raise ValueError("Date-source observation is invalid")
    return control


def date_source_report(con, control):
    row = con.execute("""SELECT id,url,status_code,body,body_sha256 FROM source_response
        WHERE endpoint='metadata/liste/search' AND params_json=?
        ORDER BY id DESC LIMIT 1""", (encoded(control["search_params"]),)).fetchone()
    findings = []
    if row is None:
        findings.append(_finding("date_source_missing", {"doc_id": control["doc_id"]}))
    else:
        response_id, url, status_code, body, digest = row
        if (url != control["source_url"] or status_code != 200 or
                digest != control["response_sha256"] or
                hashlib.sha256(body.encode("utf-8")).hexdigest() != digest):
            findings.append(_finding("date_source_changed", {"response_id": response_id}))
        else:
            try:
                records, reported = parse_search(json.loads(body))
                manuscript = records[0] if len(records) == reported == 1 else None
            except (ValueError, TypeError):
                manuscript = None
            expected = control["observed"]
            if (not manuscript or manuscript.get("docID") != control["doc_id"] or
                    manuscript.get("orig") != expected["original_notation"] or
                    manuscript.get("origEarly") != expected["date_min"] or
                    manuscript.get("origLate") != expected["date_max"] or
                    manuscript.get("lang") != expected["source_language"]):
                findings.append(_finding("date_source_observation_mismatch", {
                    "response_id": response_id}))
    return {"control_id": control["control_id"],
            "state": "pass" if not findings else "finding",
            "scope": "catalogue date observation only; no selected scholarly date",
            "findings": findings}


def audit_database(db_path, benchmark=None, source_controls=None, date_source=None):
    path = Path(db_path).resolve()
    con = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        con.execute("BEGIN")
        required = {"edition_inventory", "edition_verse", "coverage_review", "ranking_snapshot",
                    "ranking_entry", "date_assessment", "date_selection", "physical_witness"}
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if required - tables:
            version = con.execute("PRAGMA user_version").fetchone()[0]
            raise ValueError(f"Unsupported reviewed database (schema version {version}): "
                             f"missing {sorted(required - tables)}. "
                             "Open it with sync_ntvmr.py first to add the reviewed schema")
        findings = []
        for row in con.execute("PRAGMA integrity_check"):
            if row[0] != "ok":
                findings.append(_finding("sqlite_integrity", row[0]))
        for row in con.execute("PRAGMA foreign_key_check"):
            findings.append(_finding("foreign_key", list(row)))
        counts = {table: con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in sorted(required)}
        books = [dict(zip(("inventory_id", "book", "verses"), row)) for row in con.execute(
            "SELECT inventory_id,book,count(*) FROM edition_verse "
            "GROUP BY inventory_id,book ORDER BY inventory_id,book_order")]
        review_counts = [dict(zip(("status", "count"), row)) for row in con.execute(
            "SELECT status,count(*) FROM coverage_review GROUP BY status ORDER BY status")]
        job_counts = [dict(zip(("stage", "state", "count"), row)) for row in con.execute(
            "SELECT stage,state,count(*) FROM collection_job "
            "GROUP BY stage,state ORDER BY stage,state")]
        for inventory_id, osis_ref, policy_id in con.execute(
                "SELECT inventory_id,osis_ref,policy_id FROM ranking_snapshot ORDER BY 1,2,3"):
            key = {"inventory_id": inventory_id, "osis_ref": osis_ref, "policy_id": policy_id}
            try:
                report = ranking_report(con, inventory_id, osis_ref, policy_id)
            except ValueError as error:
                findings.append(_finding("ranking_unreadable", {**key, "error": str(error)}))
                continue
            if report["state"] not in ("success", "empty"):
                findings.append(_finding("ranking_not_current", {**key, "state": report["state"]}))
                continue
            _, candidates, _, _ = ranking_input(con, inventory_id, osis_ref, policy_id)
            for scenario in ("optimistic", "pessimistic"):
                expected = rank_candidates(candidates, scenario)[:5]
                actual = report["scenarios"][scenario]
                fields = ("rank", "witness_id", "unit_id", "assessment_id", "selection_id",
                          "coverage_review_id", "date_min", "date_max", "event_year")
                if ([tuple(row[field] for field in fields) for row in expected] !=
                        [tuple(row[field] for field in fields) for row in actual]):
                    findings.append(_finding("ranking_entry_mismatch", {**key, "scenario": scenario}))
        benchmark_result = None
        if benchmark is not None:
            manifest = load_benchmark(benchmark)
            benchmark_result = {"benchmark_id": manifest["benchmark_id"],
                                "case_count": len(manifest["cases"]), "passed": 0}
            for case in manifest["cases"]:
                key = {"osis_ref": case["osis_ref"], "witness_id": case["witness_id"]}
                try:
                    reviews = coverage_review_report(con, manifest["inventory_id"],
                                                     case["osis_ref"])["reviews"]
                except ValueError as error:
                    findings.append(_finding("benchmark_missing_verse", {**key, "error": str(error)}))
                    continue
                matching = [row for row in reviews if row["witness_id"] == case["witness_id"]]
                positive = any(row["status"] in ("partial", "full") and
                               (case.get("expected_status") is None or
                                row["status"] == case["expected_status"]) and
                               row["citation"] == case["coverage_citation"] and
                               not row["review_needed"] for row in matching)
                rejected = any(row["status"] == "rejected" and
                               (case.get("expected_status") is None or
                                row["status"] == case["expected_status"]) and
                               row["citation"] == case["coverage_citation"] and
                               not row["review_needed"] for row in matching)
                any_positive = any(row["status"] in ("partial", "full") and
                                   not row["review_needed"] for row in matching)
                if not (positive if case["expected_coverage"] == "positive" else rejected and not any_positive):
                    findings.append(_finding("benchmark_coverage_mismatch", key))
                    continue
                expected_date = case["expected_date"]
                if expected_date is not None:
                    _, candidates, _, _ = ranking_input(con, manifest["inventory_id"],
                                                          case["osis_ref"], manifest["policy_id"])
                    dates = {(row["date_min"], row["date_max"]) for row in candidates
                             if row["witness_id"] == case["witness_id"] and
                             con.execute("SELECT citation FROM date_assessment WHERE id=?",
                                         (row["assessment_id"],)).fetchone()[0] ==
                             case["date_citation"]}
                    if tuple(expected_date) not in dates:
                        findings.append(_finding("benchmark_date_mismatch", {**key,
                                                                              "actual_intervals": sorted(dates)}))
                        continue
                benchmark_result["passed"] += 1
        source_result = None
        if source_controls is not None:
            source_result = source_control_report(con, load_source_controls(source_controls))
            findings.extend(source_result["findings"])
        date_result = None
        if date_source is not None:
            date_result = date_source_report(con, load_date_source(date_source))
            findings.extend(date_result["findings"])
        return {"scope": "reviewed database; structural and declared benchmark checks",
                "counts": counts, "verses_by_book": books,
                "coverage_reviews_by_status": review_counts, "collection_jobs": job_counts,
                "index_entries_by_state": [dict(zip(("state", "count"), row)) for row in
                    con.execute("SELECT state,count(*) FROM coverage_index GROUP BY state ORDER BY state")],
                "documents_by_latest_source_type": [dict(zip(("source_type", "count"), row))
                    for row in con.execute("""SELECT r.source_type,count(*) FROM candidate_review r
                        WHERE r.id=(SELECT max(x.id) FROM candidate_review x WHERE x.doc_id=r.doc_id)
                        GROUP BY r.source_type ORDER BY r.source_type""")],
                "valid_assessments_by_start_century": [dict(zip(("century", "count"), row))
                    for row in con.execute("""SELECT CAST((date_min-1)/100 AS INTEGER)+1 AS century,
                        count(*) FROM date_assessment WHERE status='valid'
                        GROUP BY century ORDER BY century""")],
                "benchmark": benchmark_result, "source_controls": source_result,
                "date_source": date_result,
                "findings": findings,
                "historical_validation_complete": False}
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--source-controls", type=Path)
    parser.add_argument("--date-source", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = audit_database(args.db, args.benchmark, args.source_controls,
                                args.date_source)
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        print(f"Audit could not run: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Reviewed audit: {len(report['findings'])} findings")
        print(f"Counts: {report['counts']}")
        if report["benchmark"]:
            result = report["benchmark"]
            print(f"Benchmark {result['benchmark_id']}: {result['passed']}/{result['case_count']} passed")
        if report["source_controls"]:
            result = report["source_controls"]
            print(f"Source controls {result['benchmark_id']}: {result['state']}")
        if report["date_source"]:
            result = report["date_source"]
            print(f"Date source {result['control_id']}: {result['state']}")
        for finding in report["findings"]:
            print(f"{finding['code']}: {finding['details']}")
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
