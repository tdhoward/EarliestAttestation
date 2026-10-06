"""Full-corpus display adaptation; no collection or manuscript examination."""

import copy
import json
from pathlib import Path
import unittest

from report_explorer import build_explorer_data, pack_explorer_data, expand_explorer_data
from build_collection import DATA, prepare_collection, read_json
from controlled_ntvmr import connect
from source_reports import import_batch, build_report_exports
from contextlib import closing
import tempfile


ROOT = Path(__file__).resolve().parents[1]


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest, _ = prepare_collection(read_json(DATA / "collection.json"))
        with tempfile.TemporaryDirectory() as tmp, closing(connect(Path(tmp) / "test.sqlite")) as con:
            import_batch(con, manifest, DATA)
            _, cls.graph = build_report_exports(con, "collection")

    def test_full_axis_does_not_expand_collected_coverage(self):
        data = build_explorer_data(self.graph)
        self.assertEqual(len(data["coordinates"]), 7957)
        self.assertEqual(data["coordinates"][0][0], "Matt.1.1")
        self.assertEqual(data["coordinates"][-1][0], "Rev.22.21")
        self.assertEqual(len({ref.split('.')[0] for ref, _ in data["coordinates"]}), 27)
        self.assertEqual(len(data["observations"]), 7941)
        self.assertNotIn("Rom.16.24", data["observations"])
        self.assertEqual(len(data["dates"]), 17)
        self.assertEqual(data["metadata"]["counts"], self.graph["counts"])

    def test_rankings_and_provenance_survive_compaction(self):
        data = build_explorer_data(self.graph)
        for verse in self.graph["verses"]:
            row = data["observations"][verse["osis_ref"]]
            for original, pair in zip(verse["reported_coverage"], row["reported_coverage"]):
                self.assertEqual(pair["state"], original["state"])
                self.assertEqual([data["claims"][key] for key in pair["claims"]], original["claims"])
                self.assertEqual([data["dates"][key] for key in pair["date_assessments"]], original["date_assessments"])
            for original, combo in zip(verse["dating_alternatives"]["combinations"], row["dating_alternatives"]["combinations"]):
                self.assertEqual([data["dates"][key] for key in combo["assessments"]], original["assessments"])
                for side in ("optimistic", "pessimistic"):
                    restored = [{**data["dates"][str(event["assessment_id"])], **event} for event in combo["scenarios"][side]]
                    self.assertEqual(restored, original["scenarios"][side])

    def test_transfer_format_is_lossless_and_reduces_repeated_records(self):
        data = build_explorer_data(self.graph)
        packed = pack_explorer_data(data)
        self.assertEqual(expand_explorer_data(packed), data)
        self.assertEqual(expand_explorer_data(data), data)
        self.assertEqual(pack_explorer_data(expand_explorer_data(packed)), packed)
        size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        self.assertLess(size(packed), size(data) * 0.4)
        self.assertLess(len(packed["claim_contexts"]), len(data["claims"]))
        self.assertLess(len(packed["coverage_records"]),
                        sum(len(row["reported_coverage"]) for row in data["observations"].values()))
        self.assertLess(len(packed["discovery_records"]), len(data["observations"]))
        # Storage sharing does not couple independent observations after loading.
        restored = expand_explorer_data(packed)
        ref, row = next(iter(restored["observations"].items()))
        row["reported_coverage"][0]["claims"].append("synthetic")
        row["discovery"]["state"] = "synthetic"
        self.assertEqual(expand_explorer_data(packed), data)
        self.assertTrue(all(other["discovery"]["state"] != "synthetic"
                            for other_ref, other in restored["observations"].items() if other_ref != ref))

    def test_invalid_transfer_references_fail_instead_of_losing_evidence(self):
        packed = pack_explorer_data(build_explorer_data(self.graph))
        ref = next(iter(packed["observations"]))
        for name in ("coverage_records", "discovery_records", "claim_contexts"):
            for index in (-1, len(packed[name]), "0", True):
                broken = copy.deepcopy(packed)
                if name == "coverage_records":
                    broken["observations"][ref]["reported_coverage"][0] = index
                elif name == "discovery_records":
                    broken["observations"][ref]["discovery"] = index
                else:
                    next(iter(broken["claims"].values()))[0] = index
                with self.assertRaisesRegex(ValueError, "Invalid .* reference"):
                    expand_explorer_data(broken)

    def test_entire_corpus_input_has_no_two_hundred_verse_limit(self):
        graph = copy.deepcopy(self.graph)
        coordinates = build_explorer_data(graph)["coordinates"]
        # Synthetic display fixture, explicitly empty: no invented source report.
        graph["verses"] = [{"osis_ref": ref, "editorial_status": status,
                            "reported_coverage": [], "ranking_state": "no_rankable_dates",
                            "dating_alternatives": {"state": "complete", "combinations": [],
                                                    "combination_count": 0, "max_combinations": 256}}
                           for ref, status in coordinates]
        graph["counts"]["verse_count"] = len(coordinates)
        data = build_explorer_data(graph)
        self.assertEqual(len(data["observations"]), 7957)
        self.assertFalse(data["claims"])
        self.assertFalse(data["dates"])

    def test_source_text_stays_in_json_and_never_changes_the_app(self):
        graph = copy.deepcopy(self.graph)
        text = '</script><script>alert("source")</script>& EXPLORER_DATA'
        graph["collection_scope"] = text
        data = json.loads(json.dumps(build_explorer_data(graph)))
        self.assertEqual(data["metadata"]["collection_scope"], text)
        html = (ROOT / "web/attestation-explorer/index.html").read_text(encoding="utf-8")
        self.assertNotIn(text, html)
        self.assertNotIn('<script id="attestation-data"', html)
        self.assertIn('src="./app.js"', html)
        self.assertIn('href="./explorer.css"', html)

    def test_bad_coordinates_and_inconsistent_identifiers_fail_loudly(self):
        graph = copy.deepcopy(self.graph)
        graph["verses"][1]["osis_ref"] = graph["verses"][0]["osis_ref"]
        with self.assertRaisesRegex(ValueError, "duplicate graph coordinate"):
            build_explorer_data(graph)
        graph["verses"][1]["osis_ref"] = "Other.1.1"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            build_explorer_data(graph)
        graph = copy.deepcopy(self.graph)
        pair = graph["verses"][1]["reported_coverage"][0]
        pair["date_assessments"] = [{**pair["date_assessments"][0], "date_min": 1}]
        with self.assertRaisesRegex(ValueError, "Conflicting assessment_id"):
            build_explorer_data(graph)


if __name__ == "__main__":
    unittest.main()
