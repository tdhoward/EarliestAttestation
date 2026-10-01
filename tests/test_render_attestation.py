"""The chart must preserve real P52 alternatives and unfinished neighboring verses."""

from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from export_attestation import build_exports
from render_attestation import cases_for, render
from replay_p52_benchmark import apply_review


class RenderAttestationTests(unittest.TestCase):
    def test_p52_replay_produces_two_sourced_conditional_charts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "review.sqlite"
            apply_review(path)
            with closing(sqlite3.connect(path)) as con:
                _, graph = build_exports(con, "na28-john18-p52-subset-v1",
                                         "p52-cautious-source-v1")
            cases, count = cases_for(graph)
            self.assertEqual(count, 2)
            self.assertEqual(len(cases), 2)
            self.assertEqual(graph["counts"]["verses_with_complete_date_alternatives"], 5)
            self.assertIsNone(cases[0][1][0][2])  # John 18:30 remains unresolved.
            self.assertEqual({case[1][1][2]["optimistic"][0]["event_year"]
                              for case in cases}, {101, 125})
            html = render(graph)
            self.assertIn("Conditional dating combination 2 of 2", html)
            self.assertIn("Prototype: incomplete discovery and validation", html)
            self.assertIn("John.18.34", html)
            self.assertIn("partial", html)
            self.assertIn("Unrankable assessment", html)
            self.assertIn("extends into the third century", html)
            self.assertIn("https://era.ed.ac.uk/", html)
            self.assertIn("CE year ↑ newer", html)

    def test_global_combination_overflow_does_not_choose_an_arbitrary_case(self):
        graph = {"format_version": 2, "kind": "graph_input",
                 "counts": {"verse_count": 1}, "verses": [{
                     "dating_alternatives": {"state": "complete", "combinations": [
                         {"assessments": [{"unit_id": f"unit-{i}",
                                           "assessment_id": j} for i in range(9)],
                          "scenarios": {"optimistic": [], "pessimistic": []}}
                         for j in (1, 2)]}}]}
        cases, count = cases_for(graph)
        self.assertEqual(count, 512)
        self.assertEqual(cases, [])


if __name__ == "__main__":
    unittest.main()
