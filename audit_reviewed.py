#!/usr/bin/env python3
"""Read-only structural and cited-benchmark audit of a reviewed NTVMR database."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

from controlled_ntvmr import coverage_review_report, rank_candidates, ranking_input, ranking_report


def load_benchmark(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
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
        if not isinstance(case, dict) or set(case) != {
                "osis_ref", "witness_id", "expected_coverage", "expected_date",
                "coverage_citation", "date_citation", "reviewed_on"}:
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


def audit_database(db_path, benchmark=None):
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
                               row["citation"] == case["coverage_citation"] and
                               not row["review_needed"] for row in matching)
                rejected = any(row["status"] == "rejected" and
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
                "benchmark": benchmark_result, "findings": findings,
                "historical_validation_complete": False}
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = audit_database(args.db, args.benchmark)
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
        for finding in report["findings"]:
            print(f"{finding['code']}: {finding['details']}")
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
