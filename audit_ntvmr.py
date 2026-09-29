#!/usr/bin/env python3
"""Read-only, offline structural audit of the legacy NTVMR SQLite database.

Passing these checks does not establish historical accuracy or corpus completeness.
This module deliberately does not import the sync client or make HTTP requests.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys


REQUIRED_COLUMNS = {
    "verse": {"osis_ref"},
    "manuscript": {"doc_id", "ga_num", "date_min", "date_max"},
    "manuscript_verse": {"doc_id", "osis_ref"},
    "verse_earliest": {
        "osis_ref", "earliest_doc_id", "earliest_date_min", "earliest_date_max"
    },
    "api_cache": {"url", "params_json", "status_code", "response_text"},
}


def audit_database(db_path: str | Path) -> dict:
    """Inspect an existing database without creating it or changing its schema."""
    con = sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        # Keep all checks on the same read snapshot if a writer is active.
        con.execute("BEGIN")
        for table, expected in REQUIRED_COLUMNS.items():
            actual = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
            if expected - actual:
                raise ValueError(f"Unsupported schema: {table} missing {sorted(expected - actual)}")

        report = {
            "scope": "Legacy schema; structural checks only, not historical validation",
            "counts": {
                table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in REQUIRED_COLUMNS
            },
            "issues": [],
        }

        def issue(code: str, count: int, message: str, examples=()) -> None:
            if count:
                report["issues"].append({
                    "code": code, "count": count, "message": message,
                    "examples": [list(row) for row in examples][:5],
                })

        integrity = [row[0] for row in con.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            issue("sqlite_integrity", len(integrity), "SQLite integrity check failed.",
                  [(item,) for item in integrity])

        checks = [
            ("invalid_manuscript_dates", "Both date bounds must be positive integer CE years, with min <= max.",
             "SELECT doc_id, date_min, date_max FROM manuscript WHERE "
             "typeof(date_min) != 'integer' OR typeof(date_max) != 'integer' "
             "OR date_min <= 0 OR date_max <= 0 OR date_min > date_max"),
            ("invalid_earliest_dates", "Stored earliest results have unusable date bounds.",
             "SELECT osis_ref, earliest_date_min, earliest_date_max FROM verse_earliest WHERE "
             "typeof(earliest_date_min) != 'integer' OR typeof(earliest_date_max) != 'integer' "
             "OR earliest_date_min <= 0 OR earliest_date_max <= 0 "
             "OR earliest_date_min > earliest_date_max"),
            ("orphan_earliest", "Earliest results refer to a missing verse or manuscript.",
             "SELECT e.osis_ref, e.earliest_doc_id FROM verse_earliest e "
             "LEFT JOIN verse v ON v.osis_ref=e.osis_ref "
             "LEFT JOIN manuscript m ON m.doc_id=e.earliest_doc_id "
             "WHERE v.osis_ref IS NULL OR m.doc_id IS NULL"),
            ("orphan_coverage", "Coverage refers to a missing verse or manuscript.",
             "SELECT mv.osis_ref, mv.doc_id FROM manuscript_verse mv "
             "LEFT JOIN verse v ON v.osis_ref=mv.osis_ref "
             "LEFT JOIN manuscript m ON m.doc_id=mv.doc_id "
             "WHERE v.osis_ref IS NULL OR m.doc_id IS NULL"),
            ("stale_earliest_dates", "Stored earliest dates differ from manuscript dates.",
             "SELECT e.osis_ref, e.earliest_doc_id FROM verse_earliest e "
             "JOIN manuscript m ON m.doc_id=e.earliest_doc_id "
             "WHERE e.earliest_date_min IS NOT m.date_min OR e.earliest_date_max IS NOT m.date_max"),
            ("earliest_without_coverage", "Earliest results lack a matching stored coverage row; evidence is unverified.",
             "SELECT e.osis_ref, e.earliest_doc_id FROM verse_earliest e WHERE NOT EXISTS "
             "(SELECT 1 FROM manuscript_verse mv WHERE mv.osis_ref=e.osis_ref AND mv.doc_id=e.earliest_doc_id)"),
            ("verses_without_result", "Seeded verses lack a result; this does not establish absence of evidence.",
             "SELECT v.osis_ref FROM verse v WHERE NOT EXISTS "
             "(SELECT 1 FROM verse_earliest e WHERE e.osis_ref=v.osis_ref)"),
        ]
        for code, message, sql in checks:
            rows = con.execute(sql).fetchall()
            issue(code, len(rows), message, rows)

        report["earliest_by_manuscript"] = [
            {"doc_id": row[0], "name": row[1], "date_min": row[2], "date_max": row[3], "verses": row[4]}
            for row in con.execute(
                "SELECT m.doc_id, m.ga_num, m.date_min, m.date_max, COUNT(*) "
                "FROM verse_earliest e JOIN manuscript m ON m.doc_id=e.earliest_doc_id "
                "GROUP BY m.doc_id ORDER BY COUNT(*) DESC, m.doc_id"
            )
        ]

        bad_http, bad_json, bad_search, legacy_lang, kjv = [], [], [], [], []
        candidates, empty_searches = {}, []
        for url, params_text, status, body in con.execute(
            "SELECT url, params_json, status_code, response_text FROM api_cache ORDER BY url, params_json"
        ):
            if not isinstance(status, int) or not 200 <= status < 300:
                bad_http.append((url, status))
                continue
            try:
                params = json.loads(params_text)
                if not isinstance(params, dict):
                    raise ValueError("Parameters must be an object")
                if "/v11n/get" in url and params.get("v11nid") == "KJV":
                    kjv.append((params.get("subset"),))
                if params.get("format") != "json":
                    continue
                payload = json.loads(body)
                if not isinstance(payload, dict) or payload.get("status") != "success":
                    raise ValueError("Expected a successful API envelope")
            except (ValueError, TypeError):
                bad_json.append((url, params_text))
                continue
            if "/liste/search" not in url:
                continue
            if params.get("lang") == "gr":
                legacy_lang.append((params.get("indexContent"), params.get("gaNum")))
            try:
                container = payload["data"]["manuscripts"]
                rows = container.get("manuscript", [])
                if isinstance(rows, dict):
                    rows = [rows]
                if not isinstance(rows, list) or type(container.get("count")) is not int:
                    raise ValueError("Unknown list shape")
                if container["count"] != len(rows):
                    raise ValueError("Count mismatch")
                for row in rows:
                    if not isinstance(row, dict) or type(row.get("docID")) is not int:
                        raise ValueError("Invalid candidate")
                for row in rows:
                    candidates[row["docID"]] = str(row.get("gaNum", row.get("primaryName", "")))
                if not rows:
                    empty_searches.append(params.get("indexContent"))
            except (KeyError, TypeError, ValueError, AttributeError):
                bad_search.append((url, params_text))

        issue("cached_http_errors", len(bad_http), "Cached requests failed at the HTTP layer.", bad_http)
        issue("cached_payload_errors", len(bad_json), "Invalid cached JSON, parameters, or API status.", bad_json)
        issue("search_contract_errors", len(bad_search), "Search shape/count cannot be validated; do not treat it as no evidence.", bad_search)
        issue("legacy_language_filter", len(legacy_lang), "lang=gr excludes P52 in the recorded probe; these searches need revalidation.", legacy_lang)
        issue("kjv_verse_seed", len(kjv), "KJV seed responses do not define NA28 edition membership.", kjv)
        report["cached_candidates"] = {"count": len(candidates), "names": sorted(set(candidates.values()))}
        report["cached_empty_searches"] = empty_searches
        return report
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="ntvmr.sqlite", help="Existing SQLite database (opened read-only)")
    parser.add_argument("--json", action="store_true", help="Print the complete report as JSON")
    args = parser.parse_args(argv)
    try:
        report = audit_database(args.db)
    except (sqlite3.Error, ValueError, OSError) as exc:
        print(f"Audit could not run: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(report["scope"])
        for table, count in report["counts"].items():
            print(f"{table}: {count}")
        for finding in report["issues"]:
            print(f"{finding['code']}: {finding['count']} - {finding['message']}")
        if not report["issues"]:
            print("No structural issues detected. Historical validation is still required.")
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
