"""A real partial-survival boundary must not become a whole-verse absence."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database
from controlled_ntvmr import connect, record_physical_absence_review
from export_attestation import build_exports
from render_attestation import render
from replay_john6_gap import ROOT, REVIEW, apply, checked_transcription, read_json


BENCHMARK = ROOT / "benchmarks/john6-gap-evidence-benchmark-v1.json"


class John6GapTests(unittest.TestCase):
    def test_offline_replay_audit_and_varying_chart_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gap.sqlite"
            summary = apply(path)
            self.assertEqual(summary["network_attempts"], 0)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 10)
            self.assertFalse(audit["historical_validation_complete"])
            # The reused John 1 evidence still passes its independent benchmark.
            self.assertEqual(audit_database(path, ROOT / "benchmarks/john1-evidence-benchmark-v1.json")
                             ["benchmark"]["passed"], 20)
            with closing(sqlite3.connect(path)) as con:
                complete, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
            self.assertEqual(complete["counts"]["positive_witness_verse_pairs"], 7)
            self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 3)
            self.assertEqual(graph["counts"]["conflicting_witness_verse_pairs"], 0)
            for index, verse in enumerate(graph["verses"]):
                combinations = verse["dating_alternatives"]["combinations"]
                self.assertEqual(len(combinations), 1)
                scenarios = combinations[0]["scenarios"]
                self.assertEqual([r["event_year"] for r in scenarios["optimistic"]],
                                 [101, 400] if index < 2 else [101])
                self.assertEqual([r["event_year"] for r in scenarios["pessimistic"]],
                                 [300, 499] if index < 2 else [300])
                evidence = verse["evidence"]
                self.assertEqual(evidence["absent_witness_ids"],
                                 [] if index < 2 else ["02-alexandrinus"])
            # John 6:50 is positive despite its incomplete ending.
            boundary = graph["verses"][1]["evidence"]["coverage_reviews"]
            alex = next(r for r in boundary if r["witness_id"] == "02-alexandrinus")
            self.assertEqual(alex["status"], "partial")
            html = render(graph)
            self.assertIn("Prototype: incomplete discovery and validation", html)
            self.assertIn("NT_GRC_02_John.xml", html)
            self.assertIn("Reviewed physical absence", html)
            self.assertIn("P70v", html)

    def test_absence_withdrawal_is_unknown_and_fails_benchmark(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "gap.sqlite"
            summary = apply(path)
            with closing(connect(path)) as con:
                record_physical_absence_review(
                    con, summary["inventory_id"], "John.6.51", "02-alexandrinus",
                    "withdrawn", "reviewed_transcription", "Synthetic regression location",
                    "Synthetic withdrawal", "Synthetic citation", "tester")
                _, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
            self.assertEqual(audit_database(path, BENCHMARK)["benchmark"]["passed"], 9)
            verse = graph["verses"][2]
            self.assertEqual(verse["evidence"]["absent_witness_ids"], [])
            self.assertEqual(verse["evidence"]["positive_witness_ids"], ["p66-bodmer-ii"])
            self.assertIn("Physical absence review withdrawn", render(graph))

    def test_bad_review_is_rejected_before_creation_and_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "gap.sqlite"
            review = read_json(REVIEW)
            review["witnesses"][0]["positive_reviews"][2]["page_id"] = 370
            manifest = folder / "bad-review.json"
            manifest.write_text(json.dumps(review), encoding="utf-8")
            # P66 6:51 spans both pages, but this review cites only page 40.
            with self.assertRaisesRegex(ValueError, "page/folio"):
                apply(path, manifest)
            self.assertFalse(path.exists())
            path.write_bytes(b"existing work")
            with patch("replay_john6_gap.replay_john1") as replay:
                with self.assertRaisesRegex(ValueError, "fresh database"):
                    apply(path)
            replay.assert_not_called()
            self.assertEqual(path.read_bytes(), b"existing work")

    def test_missing_index_is_insufficient_without_direct_lacuna_anchor(self):
        fixture = read_json(ROOT / "tests/fixtures/alexandrinus-john6-transcription.json")
        fixture["raw_excerpt"] = fixture["raw_excerpt"].replace('reason="lacuna"', 'reason="unspecified"')
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checked_transcription(fixture, "02")
        fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "explicit transcription lacuna"):
            checked_transcription(fixture, "02")


if __name__ == "__main__":
    unittest.main()
