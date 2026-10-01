"""Filter and provenance controls for supplementary verse exports."""

import json
from pathlib import Path
import tempfile
import unittest

from controlled_ntvmr import (connect, edition_inventory_report,
                              import_edition_inventory, record_coverage_review)
from export_attestation import build_exports, main


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
