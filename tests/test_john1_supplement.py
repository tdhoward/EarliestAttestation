"""A real replacement quire receives its own date and counts as one witness."""

from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database
from controlled_ntvmr import connect, record_coverage_review
from export_attestation import build_exports
from render_attestation import render
from replay_john1_supplement import (
    ANCHORS, REVIEW, ROOT, apply, checked_transcription, main, read_json,
)

BENCHMARK = ROOT / "benchmarks/john1-five-witness-evidence-benchmark-v1.json"
TRANSCRIPTION = ROOT / "tests/fixtures/washingtonianus-john1-transcription.json"


class John1SupplementTests(unittest.TestCase):
    def test_offline_replay_separates_supplement_date_and_reaches_five_witnesses(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "five.sqlite"
            with patch("controlled_ntvmr.urlopen", side_effect=AssertionError("Offline replay")):
                summary = apply(path)
            self.assertEqual(summary["network_attempts"], 0)
            self.assertEqual(summary["positive_witness_verse_pairs"], 25)
            self.assertEqual(summary["reviewed_witnesses"], 5)
            self.assertEqual(summary["date_assessments"], 8)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 25)
            self.assertFalse(audit["historical_validation_complete"])
            with closing(sqlite3.connect(path)) as con:
                complete, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
                self.assertEqual(con.execute("SELECT count(*) FROM physical_witness").fetchone()[0], 5)
                self.assertEqual(con.execute("SELECT count(*) FROM coverage_unit_assignment").fetchone()[0], 25)
                self.assertEqual(con.execute("SELECT kind FROM writing_unit WHERE unit_id=?",
                                 ("032-john-opening-supplement",)).fetchone()[0], "supplement")
                self.assertEqual(con.execute("SELECT date_min,date_max FROM date_assessment WHERE unit_id=?",
                                 ("032-john-opening-supplement",)).fetchall(), [(601, 800)])
                self.assertEqual(con.execute("SELECT count(*) FROM date_selection WHERE assessment_id IS NOT NULL")
                                 .fetchone()[0], 0)
                manuscript = json.loads(con.execute("SELECT body FROM source_response WHERE endpoint=? "
                                        "AND params_json LIKE '%20032%'",
                                        ("metadata/manuscript/get",)).fetchone()[0])["data"]["manuscript"]
                self.assertEqual(manuscript["originYear"], {"content": "V", "early": 400, "late": 499})
            self.assertEqual(complete["counts"]["positive_witness_verse_pairs"], 25)
            self.assertEqual(len(graph["verses"]), 5)
            for verse in graph["verses"]:
                self.assertEqual(len(verse["evidence"]["positive_witness_ids"]), 5)
                combos = verse["dating_alternatives"]["combinations"]
                self.assertEqual(len(combos), 1)
                for side, years in (("optimistic", [101, 201, 301, 400, 601]),
                                    ("pessimistic", [300, 300, 400, 499, 800])):
                    entries = combos[0]["scenarios"][side]
                    self.assertEqual([entry["event_year"] for entry in entries], years)
                    self.assertEqual(len({entry["witness_id"] for entry in entries}), 5)
                    self.assertEqual(entries[-1]["witness_id"], "032-washingtonianus")
                    self.assertEqual(entries[-1]["unit_id"], "032-john-opening-supplement")
            html = render(graph)
            for expected in ("Prototype: incomplete discovery and validation", "57r Suppl",
                             "NT_GRC_032S_John.xml", "601–800", "perhaps", "replacement quire",
                             "original manuscript catalogue date does not date this supplement"):
                self.assertIn(expected, html)

    def test_withdrawal_removes_only_supplement_witness_at_one_verse(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "withdraw.sqlite"
            summary = apply(path)
            with closing(connect(path)) as con:
                response_id = con.execute("SELECT index_response_id FROM coverage_review "
                                          "WHERE doc_id=20032 LIMIT 1").fetchone()[0]
                record_coverage_review(con, summary["inventory_id"], "John.1.2", "John.1.2",
                                       20032, 1130, response_id, "withdrawn", "reviewed_transcription",
                                       "Synthetic withdrawal", "test", "tester")
                _, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
            self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], 24)
            for verse in graph["verses"]:
                expected = 4 if verse["osis_ref"] == "John.1.2" else 5
                self.assertEqual(len(verse["evidence"]["positive_witness_ids"]), expected)
                for combo in verse["dating_alternatives"]["combinations"]:
                    for entries in combo["scenarios"].values():
                        self.assertEqual(len(entries), expected)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["benchmark"]["passed"], 24)
            self.assertTrue(audit["findings"])

    def test_supplied_unclear_expanded_or_corrected_words_cannot_supply_anchor(self):
        anchor = ANCHORS["John.1.5"]
        replacements = [f"<w><{tag}>{anchor}</{tag}></w>" for tag in ("supplied", "unclear", "ex")]
        replacements += [f'<w hand="corrector">{anchor}</w>',
                         f'<app><rdg type="corr" hand="corrector"><w>{anchor}</w></rdg></app>']
        for replacement in replacements:
            with self.subTest(replacement=replacement):
                fixture = read_json(TRANSCRIPTION)
                fixture["raw_excerpt"] = fixture["raw_excerpt"].replace(f"<w>{anchor}</w>", replacement)
                fixture["excerpt_sha256"] = hashlib.sha256(fixture["raw_excerpt"].encode()).hexdigest()
                with self.assertRaises(ValueError):
                    checked_transcription(fixture)

    def test_changed_supplement_identity_location_or_enclosing_hand_needs_review(self):
        changes = [("header", 'n="032S"', 'n="032"', "identity"),
                   ("excerpt", 'n="57r"', 'n="65r"', "page/column"),
                   ("excerpt", 'P57rC1L8-032S', 'P57rC1L9-032S', "line anchor"),
                   ("excerpt", 'type="book" n="John"', 'type="book" n="John" hand="corrector"',
                    "Writing-layer")]
        for part, before, after, error in changes:
            with self.subTest(after=after):
                fixture = read_json(TRANSCRIPTION)
                fixture[f"raw_{part}"] = fixture[f"raw_{part}"].replace(before, after)
                fixture[f"{part}_sha256"] = hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest()
                with self.assertRaisesRegex(ValueError, error):
                    checked_transcription(fixture)
        fixture = read_json(TRANSCRIPTION)
        fixture["raw_excerpt"] += " "
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            checked_transcription(fixture)

    def test_original_codex_date_layer_and_changed_sources_rejected_before_database_creation(self):
        for changed in ("original_date", "layer", "human_status", "folio", "identity", "index", "date_source"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.sqlite"

                def changed_read(source):
                    fixture = read_json(source)
                    if Path(source).name == REVIEW.name:
                        if changed == "original_date":
                            fixture["assessments"][0].update(date_min=400, date_max=499)
                        elif changed == "layer":
                            fixture["unit_kind"] = "original"
                        elif changed == "human_status":
                            fixture["independent_human_validation"] = True
                        elif changed == "index":
                            fixture["positive_reviews"][0]["page_id"] = 1140
                    elif Path(source).name == "washingtonianus_metadata_probe.json":
                        payload = json.loads(fixture["raw_body"])
                        manuscript = payload["data"]["manuscript"]
                        if changed == "folio":
                            for page in manuscript["pages"]["page"]:
                                if page["pageID"] == 1130:
                                    page["folio"] = "57r"
                        elif changed == "identity":
                            manuscript["docID"] = 20002
                        fixture["raw_body"] = json.dumps(payload)
                        fixture["body_sha256"] = hashlib.sha256(fixture["raw_body"].encode()).hexdigest()
                    elif Path(source).name == "washingtonianus-supplement-date-source.json" and changed == "date_source":
                        fixture["source_text"] = "fifth century"
                    return fixture

                with patch("replay_john1_supplement.read_json", side_effect=changed_read):
                    with self.assertRaises(ValueError):
                        apply(path)
                self.assertFalse(path.exists())

    def test_dry_run_and_existing_destination_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "five.sqlite"
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(["--db", str(path), "--dry-run"]), 0)
            self.assertFalse(path.exists())
            path.write_bytes(b"existing research")
            with self.assertRaisesRegex(ValueError, "fresh database"):
                apply(path)
            self.assertEqual(path.read_bytes(), b"existing research")


if __name__ == "__main__":
    unittest.main()
