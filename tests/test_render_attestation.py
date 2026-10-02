"""The chart must preserve real P52 alternatives and unfinished neighboring verses."""

from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
import sqlite3
import tempfile
import unittest

from export_attestation import build_exports
from controlled_ntvmr import (assign_coverage_unit, connect, record_coverage_review,
                              record_witness_assignment)
from render_attestation import cases_for, evidence_detail, render
from replay_p52_benchmark import apply_review


class RenderAttestationTests(unittest.TestCase):
    def test_undated_stale_and_rejected_coverage_stays_visible_without_false_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "review.sqlite"
            replay = apply_review(path)
            inventory, policy = replay["inventory_id"], "p52-cautious-source-v1"
            with closing(connect(path)) as con:
                review_id, response_id = con.execute("""SELECT id,index_response_id
                    FROM coverage_review WHERE osis_ref='John.18.31'""").fetchone()
                assign_coverage_unit(con, review_id, None,
                                     "Synthetic layer uncertainty", "Synthetic citation", "tester")
                _, graph = build_exports(con, inventory, policy)
                verse = graph["verses"][1]
                self.assertEqual(verse["dating_alternatives"]["state"], "no_rankable_dates")
                self.assertEqual(verse["evidence"]["positive_witness_ids"], [replay["witness_id"]])
                self.assertIn("Coverage source reviews (1)", render(graph))
                text = []
                parser = HTMLParser()
                parser.handle_data = text.append
                parser.feed(evidence_detail(verse))
                self.assertIn(verse["evidence"]["coverage_reviews"][0]["citation"],
                              ''.join(text))

                record_coverage_review(
                    con, inventory, "John.18.31", "John.18.31", 10052, 10,
                    response_id, "rejected", "checked_image", "Synthetic index rejection",
                    "Synthetic rejection citation", "tester")
                _, graph = build_exports(con, inventory, policy)
                self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], 4)
                self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 0)
                self.assertIn("Synthetic rejection citation", render(graph))

                identity = con.execute("""SELECT a.source_response_id,w.label
                    FROM witness_assignment a JOIN physical_witness w
                    ON w.witness_id=a.witness_id
                    WHERE a.doc_id=10052 ORDER BY a.id DESC LIMIT 1""").fetchone()
                record_witness_assignment(
                    con, 10052, identity[0], replay["witness_id"], identity[1],
                    "Synthetic identity recheck", "Synthetic identity citation", "tester")
                _, graph = build_exports(con, inventory, policy)
                self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], 0)
                self.assertIn("renewed review needed", render(graph))

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
            for verse in graph["verses"]:
                verse.pop("evidence")
            self.assertIn("Coverage review details unavailable in this older export", render(graph))

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
