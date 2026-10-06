import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database
from controlled_ntvmr import connect, record_coverage_review
from export_attestation import build_exports
from render_attestation import render
from replay_gal1_sinaiticus import (
    ANCHORS, REVIEW, ROOT, apply, checked_transcription, main, read_json,
)

BENCHMARK = ROOT / "benchmarks/gal1-three-witness-evidence-benchmark-v1.json"
TRANSCRIPTION = ROOT / "tests/fixtures/sinaiticus-gal1-transcription.json"


class Gal1SinaiticusTests(unittest.TestCase):
    def test_offline_replay_dates_layers_benchmark_and_chart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "three.sqlite"
            with patch("urllib.request.urlopen", side_effect=AssertionError("Offline replay")):
                summary = apply(path)
            self.assertEqual(summary["network_attempts"], 0)
            self.assertEqual(summary["positive_witness_verse_pairs"], 15)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 15)
            self.assertFalse(audit["historical_validation_complete"])
            with closing(sqlite3.connect(path)) as con:
                complete, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
                self.assertEqual(con.execute("SELECT count(*) FROM physical_witness").fetchone()[0], 3)
                self.assertEqual(con.execute("SELECT count(*) FROM writing_unit").fetchone()[0], 3)
                self.assertEqual(con.execute("SELECT count(*) FROM coverage_unit_assignment").fetchone()[0], 15)
                self.assertEqual(con.execute(
                    "SELECT count(*) FROM date_selection WHERE assessment_id IS NOT NULL").fetchone()[0], 0)
                dates = con.execute("SELECT status,date_min,date_max FROM date_assessment "
                                    "WHERE unit_id='01-sinaiticus-gal1-original' ORDER BY id").fetchall()
                self.assertEqual(dates, [("valid", 300, 399), ("valid", 301, 400), ("unknown", None, None)])
            self.assertEqual(complete["counts"]["positive_witness_verse_pairs"], 15)
            self.assertEqual(len(graph["verses"]), 5)
            for verse in graph["verses"]:
                self.assertEqual(set(verse["evidence"]["positive_witness_ids"]),
                                 {"p46-chester-beatty-michigan", "01-sinaiticus", "02-alexandrinus"})
                combinations = verse["dating_alternatives"]["combinations"]
                self.assertEqual(len(combinations), 4)
                endpoints = set()
                for combination in combinations:
                    scenarios = combination["scenarios"]
                    endpoints.add(tuple(tuple(e["event_year"] for e in scenarios[side])
                                        for side in ("optimistic", "pessimistic")))
                    for entries in scenarios.values():
                        self.assertEqual([e["witness_id"] for e in entries],
                                         ["p46-chester-beatty-michigan", "01-sinaiticus", "02-alexandrinus"])
                        self.assertEqual(entries[1]["unit_id"], "01-sinaiticus-gal1-original")
                self.assertEqual(endpoints, {((200, 300, 400), (225, 399, 499)),
                                             ((200, 301, 400), (225, 400, 499)),
                                             ((201, 300, 400), (300, 399, 499)),
                                             ((201, 301, 400), (300, 400, 499))})
            html = render(graph)
            for expected in ("Prototype: incomplete discovery and validation", "278v",
                             "NT_GRC_01_Gal.xml", "corrector1", "corrector2",
                             "middle of that century", "date.aspx"):
                self.assertIn(expected, html)

    def test_withdrawn_anchor_removes_only_that_witness_and_verse(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "withdraw.sqlite"
            summary = apply(path)
            with closing(connect(path)) as con:
                response_id = con.execute("SELECT index_response_id FROM coverage_review "
                                          "WHERE doc_id=20001 LIMIT 1").fetchone()[0]
                record_coverage_review(con, summary["inventory_id"], "Gal.1.4", "Gal.1.4",
                                       20001, 1580, response_id, "withdrawn", "reviewed_transcription",
                                       "Synthetic withdrawal of base-text evidence", "test", "tester")
                _, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
            self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], 14)
            for verse in graph["verses"]:
                expected = 2 if verse["osis_ref"] == "Gal.1.4" else 3
                self.assertEqual(len(verse["evidence"]["positive_witness_ids"]), expected)
                for combo in verse["dating_alternatives"]["combinations"]:
                    self.assertEqual(len(combo["scenarios"]["optimistic"]), expected)
            self.assertNotEqual(audit_database(path, BENCHMARK)["findings"], [])

    def test_corrected_supplied_or_expanded_anchor_does_not_count(self):
        anchor = ANCHORS["Gal.1.5"]
        replacements = [f"<w><{tag}>{anchor}</{tag}></w>" for tag in ("supplied", "unclear", "ex")]
        replacements += [f'<app><rdg type="corr" hand="corrector2"><w>{anchor}</w></rdg></app>',
                         f'<w hand="corrector2">{anchor}</w>']
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                fixture = read_json(TRANSCRIPTION)
                fixture["raw_excerpt"] = fixture["raw_excerpt"].replace(f"<w>{anchor}</w>", replacement)
                fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, "surviving base-text anchor"):
                    checked_transcription(fixture)

    def test_changed_corrector_original_reading_page_line_or_hash_requires_review(self):
        changes = [('hand="corrector1"', 'hand="firsthand"', "Writing-layer"),
                   ("<w>αυτων</w>", "<w>αυτον</w>", "Writing-layer"),
                   ('n="278v"', 'n="278r"', "page/column"),
                   ('<cb n="3"', '<cb n="2"', "page/column"),
                   ("<w>αδελφοι</w>", "<lb/><w>αδελφοι</w>", "relative line")]
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

    def test_changed_metadata_date_or_review_rejected_before_database_creation(self):
        for changed in ("identity", "folio", "date", "index", "human_status", "assessment", "date_source"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.sqlite"

                def changed_read(source):
                    fixture = read_json(source)
                    if Path(source).name == "sinaiticus_metadata_probe.json":
                        payload = json.loads(fixture["raw_body"])
                        manuscript = payload["data"]["manuscript"]
                        if changed == "identity":
                            manuscript["docID"] = 20002
                        elif changed == "folio":
                            next(p for p in manuscript["pages"]["page"] if p["pageID"] == 1580)["folio"] = "278r"
                        elif changed == "date":
                            manuscript["originYear"]["early"] = 301
                        fixture["raw_body"] = json.dumps(payload)
                        fixture["body_sha256"] = hashlib.sha256(fixture["raw_body"].encode()).hexdigest()
                    elif Path(source).name == REVIEW.name:
                        if changed == "index":
                            fixture["positive_reviews"][0]["page_id"] = 1590
                        elif changed == "human_status":
                            fixture["independent_human_validation"] = True
                        elif changed == "assessment":
                            fixture["assessments"][1]["date_min"] = 350
                    elif Path(source).name == "sinaiticus-date-source.json" and changed == "date_source":
                        fixture["source_text"] = "a precise date"
                    return fixture

                with patch("replay_gal1_sinaiticus.read_json", side_effect=changed_read):
                    with self.assertRaises(ValueError):
                        apply(path)
                self.assertFalse(path.exists())

    def test_dry_run_and_existing_destination_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "three.sqlite"
            self.assertEqual(main(["--db", str(path), "--dry-run"]), 0)
            self.assertFalse(path.exists())
            path.write_bytes(b"existing research")
            with self.assertRaisesRegex(ValueError, "fresh database"):
                apply(path)
            self.assertEqual(path.read_bytes(), b"existing research")


if __name__ == "__main__":
    unittest.main()
