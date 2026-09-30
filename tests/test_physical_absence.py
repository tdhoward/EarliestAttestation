"""Offline checks for direct physical-absence reviews without API index rows."""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit_reviewed import audit_database
from controlled_ntvmr import (compute_ranking, connect, import_edition_inventory,
                              now, physical_absence_report,
                              record_physical_absence_review)
from replay_p52_benchmark import apply_review
from review_absence import main


ROOT = Path(__file__).resolve().parent.parent


class PhysicalAbsenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reviewed.sqlite"
        self.con = connect(self.path)
        self.addCleanup(self.con.close)
        import_edition_inventory(self.con, {
            "format_version": 1, "inventory_id": "absence-test", "edition": "TEST",
            "scope": "synthetic John 18 subset", "source_citation": "synthetic inventory",
            "reuse_terms": "test fixture", "mapping_citation": "synthetic mapping",
            "reviewer": "tester", "verses": [
                {"osis_ref": "John.18.31", "editorial_status": "main",
                 "ntvmr_refs": ["John.18.31"]},
                {"osis_ref": "John.18.34", "editorial_status": "main",
                 "ntvmr_refs": [], "mapping_note": "Unmapped test coordinate"}]})
        self.con.execute("""INSERT INTO physical_witness(witness_id,label,created_at)
            VALUES(?,?,?)""", ("synthetic-object", "Synthetic object", now()))
        self.con.commit()
        self.action = {
            "format_version": 1, "inventory_id": "absence-test", "osis_ref": "John.18.34",
            "witness_id": "synthetic-object", "decision": "absent",
            "evidence_type": "checked_image", "source_locator": "synthetic folio 1r, gap",
            "reason": "Synthetic image shows a physical gap at this coordinate",
            "citation": "synthetic image fixture, folio 1r", "reviewer": "tester"}

    def test_unmapped_absence_is_cited_reported_and_benchmarked(self):
        action_path = Path(self.temp.name) / "absence.json"
        action_path.write_text(json.dumps(self.action), encoding="utf-8")
        missing_db = Path(self.temp.name) / "dry-run-must-not-create.sqlite"
        self.assertEqual(main(["--db", str(missing_db), "--action", str(action_path),
                               "--dry-run"]), 0)
        self.assertFalse(missing_db.exists())
        self.assertEqual(main(["--db", str(self.path), "--action", str(action_path)]), 0)
        self.assertEqual(main(["--db", str(self.path), "--report", "absence-test",
                               "--ref", "John.18.34"]), 0)
        report = physical_absence_report(self.con, "absence-test", "John.18.34")
        self.assertEqual(len(report["reviews"]), 1)
        self.assertEqual(report["reviews"][0]["decision"], "absent")
        self.assertFalse(report["reviews"][0]["conflicts_with_positive"])
        self.assertEqual(self.con.execute("SELECT count(*) FROM edition_verse_map").fetchone()[0], 1)
        benchmark = {"format_version": 1, "benchmark_id": "synthetic-absence",
                     "inventory_id": "absence-test", "policy_id": "none",
                     "cases": [{"osis_ref": "John.18.34", "witness_id": "synthetic-object",
                                "expected_coverage": "absent", "expected_status": "absent",
                                "coverage_citation": self.action["citation"],
                                "reviewed_on": "2026-09-29", "expected_date": None,
                                "date_citation": None}]}
        benchmark_path = Path(self.temp.name) / "benchmark.json"
        benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")
        audit = audit_database(self.path, benchmark_path)
        self.assertEqual(audit["findings"], [])
        self.assertEqual(audit["benchmark"]["passed"], 1)
        self.assertEqual(audit["counts"]["physical_absence_review"], 1)
        self.assertFalse(audit["historical_validation_complete"])
        record_physical_absence_review(self.con, "absence-test", "John.18.34",
                                       "synthetic-object", "withdrawn", "checked_image",
                                       "synthetic folio 1r", "Decision corrected",
                                       "synthetic correction", "tester")
        self.assertEqual(physical_absence_report(self.con, "absence-test")["reviews"][0]
                         ["decision"], "withdrawn")
        self.assertEqual(audit_database(self.path, benchmark_path)["benchmark"]["passed"], 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM physical_absence_review")
                         .fetchone()[0], 2)

    def test_absence_requires_direct_evidence_existing_witness_and_inventory_verse(self):
        args = ("absence-test", "John.18.34", "synthetic-object", "absent",
                "checked_image", "synthetic folio 1r", "reason", "citation", "tester")
        with self.assertRaises(ValueError):
            record_physical_absence_review(self.con, *args[:4], "catalogue_content_statement",
                                           *args[5:])
        with self.assertRaises(ValueError):
            record_physical_absence_review(self.con, *args[:5], "", *args[6:])
        with self.assertRaises(ValueError):
            record_physical_absence_review(self.con, args[0], "John.18.35", *args[2:])
        with self.assertRaises(ValueError):
            record_physical_absence_review(self.con, args[0], args[1], "unknown", *args[3:])
        with self.assertRaises(ValueError):
            record_physical_absence_review(self.con, args[0], args[1], args[2],
                                           "withdrawn", *args[4:])
        self.assertEqual(self.con.execute("SELECT count(*) FROM physical_absence_review")
                         .fetchone()[0], 0)

    def test_conflicting_positive_review_holds_ranking_and_audit_flags_it(self):
        other_db = Path(self.temp.name) / "p52.sqlite"
        replay = apply_review(other_db)
        con = connect(other_db)
        try:
            record_physical_absence_review(
                con, replay["inventory_id"], "John.18.31", replay["witness_id"],
                "absent", "checked_image", "synthetic folio", "conflict fixture",
                "synthetic contradiction", "tester")
            absence = physical_absence_report(con, replay["inventory_id"], "John.18.31")
            self.assertTrue(absence["reviews"][0]["conflicts_with_positive"])
            ranking = compute_ranking(con, replay["inventory_id"], "John.18.31",
                                      "p52-cautious-source-v1")
            self.assertEqual(ranking["state"], "incomplete")
            self.assertIn("conflicting_absence",
                          [item["reason"] for item in ranking["excluded_reviews"]])
            findings = audit_database(other_db, ROOT / "benchmarks" /
                                      "p52-evidence-benchmark-v1.json")["findings"]
            codes = [item["code"] for item in findings]
            self.assertIn("absence_positive_conflict", codes)
            self.assertIn("benchmark_coverage_mismatch", codes)
            record_physical_absence_review(
                con, replay["inventory_id"], "John.18.31", replay["witness_id"],
                "withdrawn", "checked_image", "synthetic folio", "conflict corrected",
                "synthetic correction", "tester")
            self.assertEqual(audit_database(other_db)["findings"], [])
        finally:
            con.close()

    def test_v11_database_adds_absence_table_without_losing_reviews(self):
        self.con.execute("DROP TABLE physical_absence_review")
        self.con.execute("PRAGMA user_version=11")
        self.con.commit()
        self.con.close()
        con = connect(self.path)
        try:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 12)
            self.assertEqual(con.execute("SELECT count(*) FROM edition_verse").fetchone()[0], 2)
            self.assertEqual(con.execute("SELECT count(*) FROM physical_absence_review")
                             .fetchone()[0], 0)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
