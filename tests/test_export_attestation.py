"""Filter and provenance controls for supplementary verse exports."""

import json
from pathlib import Path
import tempfile
import unittest

from controlled_ntvmr import (connect, edition_inventory_report,
                              import_edition_inventory, now, record_coverage_review,
                              record_physical_absence_review)
from export_attestation import build_exports, main
from render_attestation import render


class AttestationExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "reviewed.sqlite"
        self.con = connect(self.path)
        self.addCleanup(self.con.close)
        self.manifest = {
            "format_version": 1, "inventory_id": "filter-test", "edition": "NA28",
            "scope": "synthetic", "source_citation": "fixture", "reuse_terms": "test",
            "mapping_citation": "fixture mappings", "reviewer": "tester",
            "verses": [
                {"osis_ref": "Matt.17.20", "editorial_status": "main",
                 "ntvmr_refs": ["Matt.17.20"]},
                {"osis_ref": "Matt.17.21", "editorial_status": "omitted",
                 "editorial_note": "NA28 skips number", "ntvmr_refs": ["Matt.17.21"]},
                {"osis_ref": "Mark.16.9", "editorial_status": "bracketed",
                 "editorial_note": "Bracketed passage", "ntvmr_refs": ["Mark.16.9"]},
                {"osis_ref": "Luke.1.1", "editorial_status": "uncertain",
                 "editorial_note": "Editorial check pending", "ntvmr_refs": [],
                 "mapping_note": "Unmapped"}]}
        import_edition_inventory(self.con, self.manifest)

    def test_complete_dataset_and_independent_graph_filters(self):
        dataset, graph = build_exports(self.con, "filter-test", "policy")
        self.assertEqual(dataset["format_version"], 2)
        self.assertEqual(graph["format_version"], 2)
        self.assertEqual(dataset["counts"]["verse_count"], 4)
        self.assertEqual(graph["counts"]["verse_count"], 3)
        self.assertEqual(graph["filters"], {"include_omitted": False,
                                              "include_bracketed": True})
        self.assertNotIn("Matt.17.21", [v["osis_ref"] for v in graph["verses"]])
        self.assertEqual(graph["counts"]["by_ranking_state"]["uncomputed"], 3)
        self.assertIsNone(graph["verses"][0]["scenarios"])
        self.assertEqual(dataset["verses"][1]["editorial_status"], "omitted")
        self.assertEqual(self.con.execute("SELECT count(*) FROM edition_verse").fetchone()[0], 4)

        _, included = build_exports(self.con, "filter-test", "policy",
                                    include_omitted=True, include_bracketed=False)
        self.assertEqual(included["counts"]["verse_count"], 3)
        self.assertIn("Matt.17.21", [v["osis_ref"] for v in included["verses"]])
        self.assertNotIn("Mark.16.9", [v["osis_ref"] for v in included["verses"]])
        self.assertEqual(included["counts"]["by_editorial_status"]["omitted"], 1)

    def test_omitted_positive_review_requires_cited_identification(self):
        args = (self.con, "filter-test", "Matt.17.21", "Matt.17.21",
                100, 10, 1, "partial", "reviewed_transcription", "reason",
                "source", "tester")
        with self.assertRaisesRegex(ValueError, "cited traditional passage"):
            record_coverage_review(*args)
        revised = json.loads(json.dumps(self.manifest))
        revised["inventory_id"] = "filter-test-cited"
        revised["verses"][1]["passage_citation"] = "Reviewed traditional passage source"
        import_edition_inventory(self.con, revised)
        self.assertEqual(edition_inventory_report(self.con, "filter-test-cited")
                         ["verses"][1]["passage_citation"],
                         "Reviewed traditional passage source")
        with self.assertRaisesRegex(ValueError, "current|index|witness|identity"):
            record_coverage_review(self.con, "filter-test-cited", *args[2:])

    def test_absence_only_unmapped_and_filtered_coordinates_keep_evidence(self):
        self.con.execute("INSERT INTO physical_witness VALUES (?,?,?)",
                         ("synthetic-object", "Synthetic object", now()))
        self.con.commit()
        for ref in ("Matt.17.21", "Luke.1.1"):
            record_physical_absence_review(
                self.con, "filter-test", ref, "synthetic-object", "absent",
                "checked_image", "Synthetic folio <1r>", "Synthetic physical gap",
                "Synthetic source https://example.org/folio", "Test reviewer")
        changes = self.con.total_changes
        dataset, graph = build_exports(self.con, "filter-test", "policy")
        self.assertEqual(self.con.total_changes, changes)
        self.assertEqual(dataset["counts"]["absent_witness_verse_pairs"], 2)
        self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 1)
        self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], 0)
        verse = graph["verses"][-1]
        self.assertEqual(verse["osis_ref"], "Luke.1.1")
        self.assertEqual(verse["ntvmr_refs"], [])
        self.assertIsNone(verse["dating_alternatives"])
        self.assertIsNone(verse["scenarios"])
        self.assertEqual(verse["ranking_state"], "uncomputed")
        self.assertEqual(verse["evidence"]["absent_witness_ids"], ["synthetic-object"])
        self.assertEqual(verse["evidence"]["coverage_reviews"], [])
        html = render(graph)
        self.assertIn("Reviewed physical absence", html)
        self.assertIn("Synthetic folio &lt;1r&gt;", html)
        self.assertIn('href="https://example.org/folio"', html)
        self.assertIn("Test reviewer", html)
        self.assertIn("No physical coverage review recorded", html)
        _, included = build_exports(self.con, "filter-test", "policy", include_omitted=True)
        self.assertEqual(included["counts"]["absent_witness_verse_pairs"], 2)

    def test_uncertain_and_withdrawn_absence_are_not_counted_as_absent(self):
        self.con.execute("INSERT INTO physical_witness VALUES (?,?,?)",
                         ("synthetic-object", "Synthetic object", now()))
        self.con.commit()
        for decision, label in (("absent", "Reviewed physical absence"),
                                ("uncertain", "Physical absence uncertain"),
                                ("withdrawn", "Physical absence review withdrawn")):
            with self.subTest(decision=decision):
                record_physical_absence_review(
                    self.con, "filter-test", "Luke.1.1", "synthetic-object", decision,
                    "checked_image", "Synthetic folio", "Synthetic revised decision",
                    "Synthetic source", "tester")
                _, graph = build_exports(self.con, "filter-test", "policy")
                self.assertEqual(graph["counts"]["absent_witness_verse_pairs"],
                                 int(decision == "absent"))
                reviews = graph["verses"][-1]["evidence"]["physical_absence_reviews"]
                self.assertEqual(len(reviews), 1)
                self.assertEqual(reviews[0]["decision"], decision)
                self.assertIn(label, render(graph))
        self.assertEqual(self.con.execute("SELECT count(*) FROM physical_absence_review")
                         .fetchone()[0], 3)

    def test_stale_snapshot_has_no_graph_events(self):
        self.con.execute("""INSERT INTO ranking_snapshot
            (inventory_id,osis_ref,policy_id,input_sha256,state,candidate_count,computed_at)
            VALUES ('filter-test','Matt.17.20','policy','obsolete','success',1,
                    '2026-09-30T00:00:00+00:00')""")
        self.con.commit()
        dataset, graph = build_exports(self.con, "filter-test", "policy")
        self.assertEqual(dataset["verses"][0]["ranking_state"], "stale")
        self.assertIsNone(graph["verses"][0]["scenarios"])

    def test_cli_exports_offline_without_database_changes(self):
        dataset_path = Path(self.temp.name) / "dataset.json"
        graph_path = Path(self.temp.name) / "graph.json"
        self.assertEqual(main(["--db", str(self.path), "--inventory", "filter-test",
                               "--policy", "policy", "--dataset-output", str(dataset_path),
                               "--graph-output", str(graph_path), "--include-omitted",
                               "--exclude-bracketed"]), 0)
        self.assertEqual(json.loads(graph_path.read_text(encoding="utf-8"))
                         ["counts"]["verse_count"], 3)
        self.assertEqual(json.loads(dataset_path.read_text(encoding="utf-8"))
                         ["counts"]["verse_count"], 4)
        self.assertEqual(self.con.execute("SELECT count(*) FROM ranking_snapshot").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
