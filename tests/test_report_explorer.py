"""Full-corpus display adaptation; no collection or manuscript examination."""

import copy
import json
from pathlib import Path
import re
import unittest

from report_explorer import build_explorer_data, render_report_explorer


ROOT = Path(__file__).resolve().parents[1]


def embedded_data(html):
    return json.loads(re.search(r'<script id="attestation-data" type="application/json">(.*?)</script>',
                               html, re.S).group(1))


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((ROOT / "examples/galatians-source-reports-graph-input.json").read_text(encoding="utf-8"))

    def test_full_axis_does_not_expand_collected_coverage(self):
        data = build_explorer_data(self.graph)
        self.assertEqual(len(data["coordinates"]), 7957)
        self.assertEqual(data["coordinates"][0][0], "Matt.1.1")
        self.assertEqual(data["coordinates"][-1][0], "Rev.22.21")
        self.assertEqual(len({ref.split('.')[0] for ref, _ in data["coordinates"]}), 27)
        self.assertEqual(len(data["observations"]), 149)
        self.assertNotIn("John.3.16", data["observations"])
        self.assertEqual(len(data["dates"]), 3)
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
        data = embedded_data(render_report_explorer(graph))
        self.assertEqual(len(data["observations"]), 7957)
        self.assertFalse(data["claims"])
        self.assertFalse(data["dates"])

    def test_offline_html_safely_embeds_source_text(self):
        graph = copy.deepcopy(self.graph)
        text = '</script><script>alert("source")</script>& EXPLORER_DATA'
        graph["collection_scope"] = text
        html = render_report_explorer(graph)
        self.assertNotIn(text, html)
        self.assertEqual(embedded_data(html)["metadata"]["collection_scope"], text)
        self.assertEqual(html.count('<canvas '), 1)
        self.assertNotRegex(html, r'<(?:script|link)[^>]+(?:src|href)=')
        self.assertIn('name="scenario" value="pessimistic"', html)

    def test_bad_coordinates_and_inconsistent_identifiers_fail_loudly(self):
        graph = copy.deepcopy(self.graph)
        graph["verses"][1]["osis_ref"] = graph["verses"][0]["osis_ref"]
        with self.assertRaisesRegex(ValueError, "duplicate graph coordinate"):
            build_explorer_data(graph)
        graph["verses"][1]["osis_ref"] = "Other.1.1"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            build_explorer_data(graph)
        graph = copy.deepcopy(self.graph)
        graph["verses"][1]["reported_coverage"][0]["date_assessments"][0]["date_min"] = 1
        with self.assertRaisesRegex(ValueError, "Conflicting assessment_id"):
            build_explorer_data(graph)


if __name__ == "__main__":
    unittest.main()
