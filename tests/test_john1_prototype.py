"""The cited John 1 inputs rebuild a four-witness conditional graph offline."""

from __future__ import annotations

import sqlite3
import json
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from audit_reviewed import audit_database as audit_reviewed_database
from controlled_ntvmr import connect, record_coverage_review
from export_attestation import build_exports
from render_attestation import render
from replay_john1_prototype import ROOT, REVIEW, apply, load_inputs


BENCHMARK = ROOT / "benchmarks" / "john1-evidence-benchmark-v1.json"


class John1PrototypeTest(unittest.TestCase):
    def test_fresh_replay_audit_export_and_chart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "john1.sqlite"
            summary = apply(path)
            self.assertEqual(summary["reviewed_witnesses"], 4)
            self.assertEqual(summary["positive_witness_verse_pairs"], 20)
            self.assertEqual(summary["coverage_pending_candidates"], [])
            self.assertEqual(summary["network_attempts"], 0)
            audit = audit_reviewed_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 20)
            self.assertFalse(audit["historical_validation_complete"])
            with closing(sqlite3.connect(path)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT count(*) FROM coverage_unit_assignment").fetchone()[0], 20)
                self.assertEqual(con.execute("SELECT count(*) FROM date_assessment").fetchone()[0], 7)
                complete, graph = build_exports(
                    con, "na28-john1-prototype-subset-v2", "john1-conditional-source-v1")
            self.assertEqual(graph["counts"]["verse_count"], 5)
            self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], 20)
            self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 0)
            self.assertEqual(graph["counts"]["conflicting_witness_verse_pairs"], 0)
            self.assertEqual(complete["counts"]["discovered_document_count"], 4)
            self.assertEqual(graph["counts"]["verses_with_complete_date_alternatives"], 5)
            self.assertEqual([row["osis_ref"] for row in graph["verses"]],
                             [f"John.1.{number}" for number in range(1, 6)])
            for verse in graph["verses"]:
                self.assertEqual(len(verse["evidence"]["coverage_reviews"]), 4)
                self.assertEqual(len(verse["evidence"]["positive_witness_ids"]), 4)
                self.assertEqual(verse["ranking_state"], "uncomputed")
                alternatives = verse["dating_alternatives"]
                self.assertEqual(alternatives["state"], "complete")
                self.assertEqual(alternatives["combination_count"], 1)
                self.assertEqual(alternatives["eligible_witness_count"], 4)
                scenarios = alternatives["combinations"][0]["scenarios"]
                self.assertEqual([row["event_year"] for row in scenarios["optimistic"]],
                                 [101, 201, 301, 400])
                self.assertEqual([row["event_year"] for row in scenarios["pessimistic"]],
                                 [300, 300, 400, 499])
                self.assertEqual(scenarios["optimistic"][-1]["evidence_type"], "checked_image")
            candidates = {row["query_ga_num"]: row for row in
                          graph["verses"][0]["discovery_candidates"]}
            self.assertEqual(candidates["02"]["review_decision"], "retain")
            self.assertEqual(candidates["02"]["witness_id"], "02-alexandrinus")
            self.assertTrue(any(row["witness_id"] == "02-alexandrinus"
                                 for row in graph["verses"][0]["dating_alternatives"]["combinations"][0]["scenarios"]["optimistic"]))
            self.assertTrue(all(candidates[name]["review_decision"] == "retain"
                                for name in ("P66", "P75", "01", "02")))
            html = render(graph)
            self.assertIn("Prototype: incomplete discovery and validation", html)
            self.assertIn("Named search candidates:", html)
            self.assertIn("witness p75-hanna-1", html)
            self.assertIn("02-alexandrinus", html)
            self.assertIn("20002x00490XX_INTF.jpg", html)

    def test_all_checked_in_page_pairs_are_source_backed(self):
        review, inventory, fixtures = load_inputs()
        self.assertEqual(len(inventory["verses"]), 5)
        self.assertEqual(set(fixtures), {10066, 10075, 20001, 20002})
        self.assertEqual({item["consensus_status"] for item in review["witnesses"]},
                         {"unknown"})
        self.assertEqual(review["identity_only_candidates"], [])

    def test_previous_manifest_still_replays_and_existing_database_is_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "john1-v2.sqlite"
            summary = apply(path, ROOT / "benchmarks" / "john1-reviewed-v2.json")
            self.assertEqual(summary["positive_witness_verse_pairs"], 15)
            self.assertEqual(summary["coverage_pending_candidates"], ["02"])
            before = path.read_bytes()
            with patch("replay_john1_prototype.replay_candidates") as replay:
                with self.assertRaisesRegex(ValueError, "fresh database path"):
                    apply(path)
            replay.assert_not_called()
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(audit_reviewed_database(path)["findings"], [])

    def test_duplicate_witness_or_wrong_image_rejected_before_creating_database(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for defect in ("duplicate", "wrong_page", "wrong_image"):
                with self.subTest(defect=defect):
                    review = json.loads(REVIEW.read_text(encoding="utf-8"))
                    if defect == "duplicate":
                        review["witnesses"][-1] = review["witnesses"][0]
                    elif defect == "wrong_page":
                        review["witnesses"][-1]["page_id"] = 491
                    else:
                        review["witnesses"][-1]["image_check"]["source_url"] = "https://example.org/unrelated.jpg"
                    manifest = folder / "review.json"
                    manifest.write_text(json.dumps(review), encoding="utf-8")
                    path = folder / "must-not-exist.sqlite"
                    message = {"duplicate": "exactly once", "wrong_page": "verse/page pair",
                               "wrong_image": "indexed public image"}[defect]
                    with self.assertRaisesRegex(ValueError, message):
                        apply(path, manifest)
                    self.assertFalse(path.exists())

    def test_evidence_benchmark_detects_withdrawal_and_export_drops_witness(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "john1.sqlite"
            summary = apply(path)
            with closing(connect(path)) as con:
                row = con.execute("""SELECT ntvmr_ref, doc_id, page_id, index_response_id
                    FROM coverage_review WHERE doc_id=20002 AND osis_ref='John.1.3'""").fetchone()
                record_coverage_review(
                    con, summary["inventory_id"], "John.1.3", *row, "withdrawn",
                    "checked_image", "Regression test withdrawal", "Synthetic correction", "tester")
                _, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
            self.assertEqual(audit_reviewed_database(path, BENCHMARK)["benchmark"]["passed"], 19)
            verse = graph["verses"][2]
            self.assertEqual(verse["dating_alternatives"]["eligible_witness_count"], 3)
            for scenario in verse["dating_alternatives"]["combinations"][0]["scenarios"].values():
                self.assertNotIn("02-alexandrinus", [entry["witness_id"] for entry in scenario])


if __name__ == "__main__":
    unittest.main()
