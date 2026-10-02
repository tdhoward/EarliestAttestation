import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database
from export_attestation import build_exports
from render_attestation import render
from replay_gal1_prototype import (
    ANCHORS, REVIEW, ROOT, apply, checked_transcription, main, read_json,
)

BENCHMARK = ROOT / "benchmarks/gal1-overlap-evidence-benchmark-v1.json"
TRANSCRIPTION = ROOT / "tests/fixtures/alexandrinus-gal1-transcription.json"


class Gal1PrototypeTests(unittest.TestCase):
    def test_offline_replay_benchmark_export_and_chart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "overlap.sqlite"
            with patch("urllib.request.urlopen", side_effect=AssertionError("Offline replay")):
                summary = apply(path)
            self.assertEqual(summary["network_attempts"], 0)
            self.assertEqual(summary["positive_witness_verse_pairs"], 10)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 10)
            self.assertFalse(audit["historical_validation_complete"])
            with closing(sqlite3.connect(path)) as con:
                complete, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
                for table, expected in (("physical_witness", 2), ("writing_unit", 2),
                                        ("coverage_unit_assignment", 10), ("date_assessment", 3)):
                    self.assertEqual(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], expected)
                self.assertEqual(con.execute(
                    "SELECT count(*) FROM date_selection WHERE assessment_id IS NOT NULL").fetchone()[0], 0)
            self.assertEqual(complete["counts"]["positive_witness_verse_pairs"], 10)
            self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 0)
            self.assertEqual(len(graph["verses"]), 5)
            for verse in graph["verses"]:
                self.assertEqual(set(verse["evidence"]["positive_witness_ids"]),
                                 {"p46-chester-beatty-michigan", "02-alexandrinus"})
                combinations = verse["dating_alternatives"]["combinations"]
                self.assertEqual(len(combinations), 2)
                endpoints = set()
                for combination in combinations:
                    scenarios = combination["scenarios"]
                    endpoints.add(tuple(tuple(e["event_year"] for e in scenarios[side])
                                        for side in ("optimistic", "pessimistic")))
                    for entries in scenarios.values():
                        self.assertEqual([e["witness_id"] for e in entries],
                                         ["p46-chester-beatty-michigan", "02-alexandrinus"])
                self.assertEqual(endpoints, {((200, 400), (225, 499)), ((201, 400), (300, 499))})
                self.assertIsNone(verse["scenarios"])
            html = render(graph)
            for expected in ("Prototype: incomplete discovery and validation", "127v",
                             "NT_GRC_02_Gal.xml", "NT_GRC_P46_Gal.xml", "third century AD"):
                self.assertIn(expected, html)

    def test_supplied_unclear_corrected_or_expanded_anchor_cannot_count(self):
        anchor = ANCHORS["Gal.1.5"]
        for tag in ("supplied", "unclear", "app", "ex"):
            with self.subTest(tag=tag):
                fixture = read_json(TRANSCRIPTION)
                fixture["raw_excerpt"] = fixture["raw_excerpt"].replace(
                    f"<w>{anchor}</w>", f"<w><{tag}>{anchor}</{tag}></w>")
                fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, "surviving base-text anchor"):
                    checked_transcription(fixture)

    def test_changed_layer_line_or_source_is_rejected(self):
        changes = [("<w>ω</w>", "<app><w>ω</w></app>", "Writing-layer"),
                   ("<w>ω</w>", "<lb/><w>ω</w>", "relative line"),
                   ('n="127v"', 'n="127r"', "page/column"),
                   ('<cb n="2"', '<cb n="1"', "page/column")]
        for before, after, error in changes:
            with self.subTest(after=after):
                fixture = read_json(TRANSCRIPTION)
                fixture["raw_excerpt"] = fixture["raw_excerpt"].replace(before, after)
                fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, error):
                    checked_transcription(fixture)
        fixture = read_json(TRANSCRIPTION)
        fixture["raw_excerpt"] += " "
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checked_transcription(fixture)

    def test_wrong_metadata_index_or_date_rejected_before_database_creation(self):
        for changed in ("identity", "folio", "date", "index", "human_status"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.sqlite"

                def changed_read(source):
                    fixture = read_json(source)
                    if Path(source).name == "alexandrinus_metadata_probe.json":
                        payload = json.loads(fixture["raw_body"])
                        manuscript = payload["data"]["manuscript"]
                        if changed == "identity":
                            manuscript["docID"] = 20001
                        elif changed == "folio":
                            next(p for p in manuscript["pages"]["page"] if p["pageID"] == 1081)["folio"] = "127r"
                        elif changed == "date":
                            manuscript["originYear"]["early"] = 401
                        fixture["raw_body"] = json.dumps(payload)
                        fixture["body_sha256"] = hashlib.sha256(fixture["raw_body"].encode()).hexdigest()
                    elif Path(source).name == REVIEW.name:
                        if changed == "index":
                            fixture["positive_reviews"][0]["page_id"] = 1090
                        elif changed == "human_status":
                            fixture["independent_human_validation"] = True
                    return fixture

                with patch("replay_gal1_prototype.read_json", side_effect=changed_read):
                    with self.assertRaises(ValueError):
                        apply(path)
                self.assertFalse(path.exists())

    def test_altered_assessment_cannot_silently_replace_source_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            review = read_json(REVIEW)
            review["assessments"][0]["date_min"] = 401
            manifest, db = Path(folder) / "review.json", Path(folder) / "bad.sqlite"
            manifest.write_text(json.dumps(review), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source bounds"):
                apply(db, manifest)
            self.assertFalse(db.exists())

    def test_dry_run_and_existing_destination_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "overlap.sqlite"
            self.assertEqual(main(["--db", str(path), "--dry-run"]), 0)
            self.assertFalse(path.exists())
            path.write_bytes(b"existing research")
            with self.assertRaisesRegex(ValueError, "fresh database"):
                apply(path)
            self.assertEqual(path.read_bytes(), b"existing research")


if __name__ == "__main__":
    unittest.main()
