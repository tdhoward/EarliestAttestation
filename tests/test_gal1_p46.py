"""Source fidelity and the offline path for the first Pauline papyrus increment."""

from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database
from export_attestation import build_exports
from render_attestation import render
from replay_gal1_p46 import (
    ANCHORS, ROOT, REVIEW, apply, checked_transcription, main, read_json,
)

BENCHMARK = ROOT / "benchmarks/gal1-p46-evidence-benchmark-v1.json"


class Gal1P46Tests(unittest.TestCase):
    def test_offline_replay_audit_and_equal_date_alternatives(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p46.sqlite"
            with patch("urllib.request.urlopen", side_effect=AssertionError("Offline replay")):
                summary = apply(path)
            self.assertEqual(summary["network_attempts"], 0)
            self.assertEqual(summary["positive_witness_verse_pairs"], 5)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 5)
            self.assertFalse(audit["historical_validation_complete"])
            with closing(sqlite3.connect(path)) as con:
                complete, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
                self.assertEqual(con.execute("SELECT count(*) FROM physical_witness").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT count(*) FROM coverage_unit_assignment").fetchone()[0], 5)
            self.assertEqual(complete["counts"]["positive_witness_verse_pairs"], 5)
            self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 0)
            for verse in graph["verses"]:
                self.assertEqual(verse["evidence"]["positive_witness_ids"],
                                 ["p46-chester-beatty-michigan"])
                combos = verse["dating_alternatives"]["combinations"]
                endpoints = {(c["scenarios"]["optimistic"][0]["event_year"],
                              c["scenarios"]["pessimistic"][0]["event_year"]) for c in combos}
                self.assertEqual(endpoints, {(200, 225), (201, 300)})
                self.assertEqual(len(combos), 2)
                for combination in combos:
                    for side in ("optimistic", "pessimistic"):
                        self.assertEqual(len(combination["scenarios"][side]), 1)
                self.assertIsNone(verse["scenarios"])
            html = render(graph)
            for expected in ("Prototype: incomplete discovery and validation", "81r",
                             "NT_GRC_P46_Gal.xml", "III (A)", "third century AD"):
                self.assertIn(expected, html)

    def test_reconstructed_uncertain_or_corrected_anchor_is_not_base_text(self):
        anchor = ANCHORS["Gal.1.5"]
        for tag in ("supplied", "unclear", "app"):
            with self.subTest(tag=tag):
                fixture = read_json(ROOT / "tests/fixtures/p46-gal1-transcription.json")
                fixture["raw_excerpt"] = fixture["raw_excerpt"].replace(
                    f"<w>{anchor}</w>", f"<{tag}><w>{anchor}</w></{tag}>")
                fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, "surviving base-text anchor"):
                    checked_transcription(fixture)

    def test_source_identity_page_index_and_dates_checked_before_creation(self):
        for changed in ("identity", "folio", "index", "date", "transcription_page"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.sqlite"

                def changed_read(source):
                    fixture = read_json(source)
                    if Path(source).name == "p46_metadata_probe.json":
                        payload = json.loads(fixture["raw_body"])
                        manuscript = payload["data"]["manuscript"]
                        if changed == "identity":
                            manuscript["docID"] = 10066
                        elif changed == "folio":
                            next(p for p in manuscript["pages"]["page"]
                                 if p["pageID"] == 1421)["folio"] = "081v"
                        elif changed == "date":
                            manuscript["originYear"]["late"] = 250
                        fixture["raw_body"] = json.dumps(payload)
                        fixture["body_sha256"] = hashlib.sha256(fixture["raw_body"].encode()).hexdigest()
                    elif Path(source).name == REVIEW.name and changed == "index":
                        fixture["positive_reviews"][0]["page_id"] = 1440
                    elif Path(source).name == "p46-gal1-transcription.json" and changed == "transcription_page":
                        fixture["raw_excerpt"] = fixture["raw_excerpt"].replace('n="81r"', 'n="081v"')
                        fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
                    return fixture

                with patch("replay_gal1_p46.read_json", side_effect=changed_read):
                    with self.assertRaises(ValueError):
                        apply(path)
                self.assertFalse(path.exists())

    def test_bad_source_hash_and_changed_assessment_are_rejected(self):
        fixture = read_json(ROOT / "tests/fixtures/p46-gal1-transcription.json")
        fixture["raw_excerpt"] += " "
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checked_transcription(fixture)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.sqlite"
            review = read_json(REVIEW)
            review["assessments"][0]["date_max"] = 300
            manifest = Path(folder) / "review.json"
            manifest.write_text(json.dumps(review), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source bounds"):
                apply(path, manifest)
            self.assertFalse(path.exists())

    def test_dry_run_and_existing_destination_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "p46.sqlite"
            self.assertEqual(main(["--db", str(path), "--dry-run"]), 0)
            self.assertFalse(path.exists())
            path.write_bytes(b"existing research")
            with self.assertRaisesRegex(ValueError, "fresh database"):
                apply(path)
            self.assertEqual(path.read_bytes(), b"existing research")


if __name__ == "__main__":
    unittest.main()
