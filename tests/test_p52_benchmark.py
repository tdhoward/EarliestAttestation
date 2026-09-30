"""Offline integration checks for the cited P52 benchmark replay."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit_reviewed import audit_database, load_benchmark
from controlled_ntvmr import connect, record_coverage_review
from replay_p52_benchmark import apply_review, main


ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "p52-evidence-benchmark-v1.json"
SOURCE_CONTROLS = ROOT / "benchmarks" / "p52-source-controls-v1.json"
DATE_SOURCE = ROOT / "benchmarks" / "p52-date-source-v1.json"


class P52BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reviewed.sqlite"

    def test_replay_is_offline_idempotent_and_auditable(self):
        self.assertEqual(main(["--db", str(self.path), "--dry-run"]), 0)
        self.assertFalse(self.path.exists())
        first = apply_review(self.path)
        second = apply_review(self.path)
        self.assertEqual(first, second)
        self.assertEqual(first["network_attempts"], 0)
        self.assertFalse(first["selected_date"])
        self.assertEqual(len(first["reviewed_verses"]), 5)
        report = audit_database(self.path, BENCHMARK, SOURCE_CONTROLS, DATE_SOURCE)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["benchmark"]["passed"], 5)
        self.assertFalse(report["historical_validation_complete"])
        self.assertEqual(report["counts"]["edition_verse"], 10)
        self.assertEqual(report["counts"]["coverage_review"], 5)
        self.assertEqual(report["counts"]["date_assessment"], 0)
        self.assertEqual(report["counts"]["date_selection"], 0)
        with closing(sqlite3.connect(self.path)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
            mapped = [row[0] for row in con.execute("""SELECT osis_ref FROM edition_verse_map
                WHERE inventory_id='na28-john18-p52-subset-v1' ORDER BY osis_ref""")]
            self.assertEqual(mapped, first["reviewed_verses"])

    def test_withdrawal_breaks_benchmark_without_erasing_history(self):
        apply_review(self.path)
        con = connect(self.path)
        try:
            row = con.execute("""SELECT inventory_id,osis_ref,ntvmr_ref,doc_id,page_id,
                index_response_id FROM coverage_review WHERE osis_ref='John.18.32'""").fetchone()
            record_coverage_review(con, *row, "withdrawn", "catalogue_content_statement",
                                   "Review withdrawn for test", "test correction", "tester")
        finally:
            con.close()
        report = audit_database(self.path, BENCHMARK)
        self.assertIn("benchmark_coverage_mismatch",
                      [finding["code"] for finding in report["findings"]])
        self.assertEqual(report["benchmark"]["passed"], 4)
        self.assertEqual(report["counts"]["coverage_review"], 6)
        with self.assertRaisesRegex(ValueError, "Existing P52 review differs"):
            apply_review(self.path)
        self.assertEqual(audit_database(self.path)["counts"]["coverage_review"], 6)
        config = json.loads((ROOT / "benchmarks" / "p52-reviewed-v1.json").read_text(
            encoding="utf-8"))
        con = connect(self.path)
        try:
            record_coverage_review(con, *row, "full", "catalogue_content_statement",
                                   config["coverage_reason"], config["coverage_citation"],
                                   "tester correction")
        finally:
            con.close()
        report = audit_database(self.path, BENCHMARK)
        self.assertIn("benchmark_coverage_mismatch",
                      [finding["code"] for finding in report["findings"]])

    def test_benchmark_v2_requires_source_citation(self):
        manifest = json.loads(BENCHMARK.read_text(encoding="utf-8"))
        manifest["coverage_citation"] = ""
        invalid = Path(self.temp.name) / "invalid.json"
        invalid.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_benchmark(invalid)


if __name__ == "__main__":
    unittest.main()
