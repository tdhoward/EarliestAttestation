"""Offline integration checks for the cited P52 benchmark replay."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database, load_benchmark
from controlled_ntvmr import (assign_coverage_unit, compute_ranking, connect,
                              dating_alternatives_report,
                              record_coverage_review, select_date_assessment,
                              writing_unit_report)
from export_attestation import build_exports
import replay_p52_benchmark
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
        self.assertEqual(report["counts"]["date_assessment"], 4)
        self.assertEqual(report["counts"]["date_selection"], 1)
        self.assertEqual(report["counts"]["ranking_snapshot"], 0)
        with closing(sqlite3.connect(self.path)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM writing_unit").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
            mapped = [row[0] for row in con.execute("""SELECT osis_ref FROM edition_verse_map
                WHERE inventory_id='na28-john18-p52-subset-v1' ORDER BY osis_ref""")]
            self.assertEqual(mapped, first["reviewed_verses"])
            dates = con.execute("""SELECT status,date_min,date_max,original_notation
                FROM date_assessment ORDER BY id""").fetchall()
            self.assertEqual(dates, [("valid", 125, 175, "II (M)"),
                                     ("unknown", None, None, "2nd Century"),
                                     ("unknown", None, None,
                                      "extends into the third century"),
                                     ("valid", 101, 300, "II or III")])
            selection = con.execute("""SELECT policy_id,assessment_id
                FROM date_selection""").fetchone()
            self.assertEqual(selection, ("p52-cautious-source-v1", None))
            unit = writing_unit_report(con, first["witness_id"])["units"][0]
            self.assertEqual(unit["kind"], "original")
            self.assertFalse(unit["selected_by_policy"]["p52-cautious-source-v1"]["rankable"])
            self.assertEqual(unit["coverage_links"], [])

    def test_v2_replay_appends_to_v1_review_without_changing_its_history(self):
        old_manifest = ROOT / "benchmarks" / "p52-dating-review-v1.json"
        with patch.object(replay_p52_benchmark, "DATING_REVIEW", old_manifest):
            apply_review(self.path)
        with closing(sqlite3.connect(self.path)) as con:
            original_assessments = con.execute("""SELECT id,status,date_min,date_max,
                original_notation,citation FROM date_assessment ORDER BY id""").fetchall()
            original_selection = con.execute("""SELECT id,policy_id,assessment_id,reason
                FROM date_selection ORDER BY id""").fetchall()
        self.assertEqual(len(original_assessments), 3)
        self.assertEqual(len(original_selection), 1)
        apply_review(self.path)
        apply_review(self.path)
        with closing(sqlite3.connect(self.path)) as con:
            assessments = con.execute("""SELECT id,status,date_min,date_max,
                original_notation,citation FROM date_assessment ORDER BY id""").fetchall()
            selections = con.execute("""SELECT id,policy_id,assessment_id,reason
                FROM date_selection ORDER BY id""").fetchall()
        self.assertEqual(assessments[:3], original_assessments)
        self.assertEqual(len(assessments), 4)
        self.assertEqual(selections[:1], original_selection)
        self.assertEqual(len(selections), 2)
        self.assertIsNone(selections[-1][2])
        self.assertEqual(audit_database(self.path)["counts"]["ranking_snapshot"], 0)

    def test_test_only_p52_dating_scenario_ranks_five_verses_and_audits(self):
        replay = apply_review(self.path)
        self.assertFalse(replay["selected_date"])
        manifest = json.loads((ROOT / "benchmarks" / "p52-dating-review-v2.json").read_text(
            encoding="utf-8"))
        barker = manifest["assessments"][3]
        policy = "p52-barker-what-if-test"
        unit = manifest["unit"]["unit_id"]
        con = connect(self.path)
        try:
            reviews = con.execute("""SELECT id,osis_ref FROM coverage_review
                ORDER BY osis_ref""").fetchall()
            self.assertEqual([ref for _, ref in reviews], replay["reviewed_verses"])
            assessment_id = con.execute("""SELECT id FROM date_assessment
                WHERE unit_id=? AND original_notation='II or III'""", (unit,)).fetchone()[0]
            for review_id, _ in reviews:
                assign_coverage_unit(con, review_id, unit,
                                     "Test-only original-unit link",
                                     manifest["unit"]["citation"], "offline test")
            alternatives = dating_alternatives_report(
                con, replay["inventory_id"], reviews[0][1], "p52-cautious-source-v1")
            self.assertEqual(alternatives["state"], "complete")
            self.assertEqual(alternatives["combination_count"], 2)
            self.assertEqual({(case["scenarios"]["optimistic"][0]["event_year"],
                               case["scenarios"]["pessimistic"][0]["event_year"])
                              for case in alternatives["combinations"]},
                             {(125, 175), (101, 300)})
            self.assertEqual(con.execute("SELECT count(*) FROM ranking_snapshot").fetchone()[0], 0)
            _, graph = build_exports(con, replay["inventory_id"], "p52-cautious-source-v1")
            graph_verse = next(verse for verse in graph["verses"]
                               if verse["osis_ref"] == reviews[0][1])
            self.assertEqual(graph_verse["ranking_state"], "uncomputed")
            self.assertEqual(graph_verse["dating_alternatives"]["combination_count"], 2)
            self.assertIsNone(graph_verse["scenarios"])
            select_date_assessment(con, unit, assessment_id, policy,
                                   "Test-only Barker scenario", "offline test")
            for _, ref in reviews:
                report = compute_ranking(con, replay["inventory_id"], ref, policy)
                self.assertEqual(report["state"], "success")
                self.assertEqual(report["current_eligible_witness_count"], 1)
                for scenario, year in (("optimistic", 101), ("pessimistic", 300)):
                    self.assertEqual(len(report["scenarios"][scenario]), 1)
                    entry = report["scenarios"][scenario][0]
                    self.assertEqual(entry["event_year"], year)
                    self.assertEqual(entry["date_citation"], barker["citation"])
                    self.assertEqual(entry["coverage_status"], "partial")
                    self.assertEqual(entry["witness_id"], replay["witness_id"])
            self.assertEqual(con.execute("""SELECT assessment_id FROM date_selection
                WHERE policy_id='p52-cautious-source-v1' ORDER BY id DESC LIMIT 1""").fetchone(),
                             (None,))
        finally:
            con.close()
        benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
        benchmark["benchmark_id"] = "p52-barker-what-if-test"
        benchmark["policy_id"] = policy
        for case in benchmark["cases"]:
            case["expected_date"] = [101, 300]
            case["date_citation"] = barker["citation"]
        test_benchmark = Path(self.temp.name) / "p52-what-if.json"
        test_benchmark.write_text(json.dumps(benchmark), encoding="utf-8")
        audit = audit_database(self.path, test_benchmark, SOURCE_CONTROLS, DATE_SOURCE)
        self.assertEqual(audit["findings"], [])
        self.assertEqual(audit["benchmark"]["passed"], 5)
        self.assertFalse(audit["historical_validation_complete"])
        con = connect(self.path)
        try:
            con.execute("""UPDATE ranking_entry SET event_year=999
                WHERE osis_ref='John.18.31' AND scenario='optimistic' AND policy_id=?""",
                (policy,))
            con.commit()
        finally:
            con.close()
        findings = audit_database(self.path, test_benchmark)["findings"]
        self.assertIn("ranking_entry_mismatch", [finding["code"] for finding in findings])

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

    def test_replay_preserves_a_later_manual_date_selection(self):
        old_manifest = ROOT / "benchmarks" / "p52-dating-review-v1.json"
        with patch.object(replay_p52_benchmark, "DATING_REVIEW", old_manifest):
            apply_review(self.path)
        con = connect(self.path)
        try:
            assessment_id = con.execute("""SELECT id FROM date_assessment
                WHERE original_notation='II (M)'""").fetchone()[0]
            select_date_assessment(con, "p52-rylands-gk-457-original",
                                   assessment_id, "p52-cautious-source-v1",
                                   "manual choice for conflict test", "tester")
        finally:
            con.close()
        with self.assertRaisesRegex(ValueError, "date selection differs"):
            apply_review(self.path)
        with closing(sqlite3.connect(self.path)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM date_assessment").fetchone()[0], 3)


if __name__ == "__main__":
    unittest.main()
