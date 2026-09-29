"""Offline checks for the audit, using isolated databases rather than ntvmr.sqlite."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit_ntvmr import audit_database, main


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sample.sqlite"
        with contextlib.closing(sqlite3.connect(self.path)) as con:
            con.executescript("""
                CREATE TABLE verse (osis_ref TEXT PRIMARY KEY);
                CREATE TABLE manuscript (doc_id INTEGER PRIMARY KEY, ga_num TEXT, date_min INTEGER, date_max INTEGER);
                CREATE TABLE manuscript_verse (doc_id INTEGER, osis_ref TEXT);
                CREATE TABLE verse_earliest (osis_ref TEXT, earliest_doc_id INTEGER, earliest_date_min INTEGER, earliest_date_max INTEGER);
                CREATE TABLE api_cache (url TEXT, params_json TEXT, status_code INTEGER, response_text TEXT);
                INSERT INTO verse VALUES ('John.18.31');
                INSERT INTO manuscript VALUES (10052, 'P52', 125, 175);
                INSERT INTO manuscript_verse VALUES (10052, 'John.18.31');
                INSERT INTO verse_earliest VALUES ('John.18.31', 10052, 125, 175);
            """)

    def execute(self, sql, params=()):
        with contextlib.closing(sqlite3.connect(self.path)) as con:
            with con:
                con.execute(sql, params)

    def issues(self):
        return {issue["code"]: issue["count"] for issue in audit_database(self.path)["issues"]}

    def cache(self, payload, params=None, status=200):
        self.execute("INSERT INTO api_cache VALUES (?,?,?,?)", (
            "https://example.invalid/metadata/liste/search/",
            json.dumps(params or {"format": "json", "indexContent": "John.18.31"}),
            status, json.dumps(payload),
        ))

    def test_valid_structure_and_no_writes(self):
        before = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(self.issues(), {})
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_missing_database_is_not_created(self):
        missing = self.path.with_name("missing.sqlite")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["--db", str(missing)]), 2)
        self.assertFalse(missing.exists())

    def test_unsupported_schema_is_explicit(self):
        self.execute("DROP TABLE manuscript_verse")
        with self.assertRaisesRegex(ValueError, "Unsupported schema"):
            audit_database(self.path)

    def test_missing_evidence_is_not_a_confirmed_attestation(self):
        self.execute("DELETE FROM manuscript_verse")
        self.assertEqual(self.issues()["earliest_without_coverage"], 1)

    def test_missing_result_is_reported_as_unknown(self):
        self.execute("INSERT INTO verse VALUES ('John.18.32')")
        self.assertEqual(self.issues()["verses_without_result"], 1)

    def test_invalid_date_intervals(self):
        for lower, upper in [(None, 175), (0, 175), (175, 125), (125, None), (125, 0), ("II", 175), (125.5, 175)]:
            with self.subTest(lower=lower, upper=upper):
                self.execute("UPDATE manuscript SET date_min=?, date_max=?", (lower, upper))
                self.assertEqual(self.issues()["invalid_manuscript_dates"], 1)

    def test_orphans_detected_without_foreign_key_declarations(self):
        self.execute("DELETE FROM manuscript")
        self.assertEqual(self.issues()["orphan_earliest"], 1)
        self.assertEqual(self.issues()["orphan_coverage"], 1)

    def test_stale_materialized_dates(self):
        self.execute("UPDATE manuscript SET date_max=200")
        self.assertEqual(self.issues()["stale_earliest_dates"], 1)

    def test_http_and_application_errors(self):
        self.cache({}, status=429)
        self.cache({"status": "error", "message": "failed"})
        self.assertEqual(self.issues()["cached_http_errors"], 1)
        self.assertEqual(self.issues()["cached_payload_errors"], 1)

    def test_unrecognized_and_incomplete_search_results(self):
        self.cache({"status": "success", "data": {"unexpected": []}})
        self.cache({"status": "success", "data": {"manuscripts": {"count": 2, "manuscript": [{"docID": 10052}]}}})
        self.assertEqual(self.issues()["search_contract_errors"], 2)

    def test_recorded_language_probe_singletons_and_zero_results(self):
        fixture_path = Path(__file__).parent / "fixtures" / "p52_language_probe.json"
        probe = json.loads(fixture_path.read_text(encoding="utf-8"))
        for case in probe["cases"]:
            params = dict(probe["common_params"])
            if case["lang"] is not None:
                params["lang"] = case["lang"]
            self.cache(case["response"], params=params)
        report = audit_database(self.path)
        self.assertEqual(report["cached_candidates"], {"count": 1, "names": ["P52"]})
        self.assertEqual(report["cached_empty_searches"], ["John.18.31"])
        self.assertEqual(self.issues(), {"legacy_language_filter": 1})

    def test_cli_exit_status_and_json(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--db", str(self.path), "--json"]), 0)
        self.assertEqual(json.loads(output.getvalue())["counts"]["verse"], 1)
        self.execute("DELETE FROM manuscript_verse")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--db", str(self.path)]), 1)


if __name__ == "__main__":
    unittest.main()
