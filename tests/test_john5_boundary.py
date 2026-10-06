"""A verse crossing two real writing layers still counts as one physical witness."""

from contextlib import closing
import hashlib
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from audit_reviewed import audit_database, load_benchmark
from controlled_ntvmr import connect, record_coverage_review, record_physical_absence_review
from export_attestation import build_exports
from render_attestation import render
from replay_john5_boundary import (
    ORIGINAL, REFS, REVIEW, ROOT, SUPPLEMENT, apply, checked_transcription,
    load_inputs, main, read_json,
)

BENCHMARK = ROOT / "benchmarks/john5-boundary-evidence-benchmark-v1.json"


class John5BoundaryTests(unittest.TestCase):
    def test_offline_replay_preserves_both_layers_and_deduplicates_boundary_verse(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "boundary.sqlite"
            with patch("controlled_ntvmr.urlopen", side_effect=AssertionError("Offline replay")):
                summary = apply(path)
            self.assertEqual(summary["network_attempts"], 0)
            self.assertEqual(summary["positive_witness_verse_pairs"], 4)
            audit = audit_database(path, BENCHMARK)
            self.assertEqual(audit["findings"], [])
            self.assertEqual(audit["benchmark"]["passed"], 5)
            self.assertFalse(audit["historical_validation_complete"])
            with closing(sqlite3.connect(path)) as con:
                complete, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
                self.assertEqual(con.execute("SELECT count(*) FROM physical_witness").fetchone()[0], 1)
                self.assertEqual(con.execute("SELECT count(*) FROM coverage_review").fetchone()[0], 6)
                self.assertEqual(con.execute("SELECT count(*) FROM coverage_unit_assignment").fetchone()[0], 5)
                self.assertEqual(con.execute("SELECT count(*) FROM physical_absence_review").fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT count(*) FROM date_selection WHERE assessment_id IS NOT NULL")
                                 .fetchone()[0], 0)
                self.assertEqual(con.execute("SELECT unit_id,date_min,date_max FROM date_assessment ORDER BY id")
                                 .fetchall(), [(SUPPLEMENT, 601, 800), (ORIGINAL, 400, 499)])
            self.assertEqual(complete["counts"]["positive_witness_verse_pairs"], 4)
            self.assertEqual(graph["counts"]["absent_witness_verse_pairs"], 0)
            self.assertEqual([verse["osis_ref"] for verse in graph["verses"]], REFS)
            for verse in graph["verses"]:
                ref = verse["osis_ref"]
                alternatives = verse["dating_alternatives"]
                if ref == "John.5.12":
                    self.assertEqual(verse["evidence"]["positive_witness_ids"], [])
                    self.assertEqual(verse["evidence"]["absent_witness_ids"], [])
                    self.assertEqual(verse["evidence"]["coverage_reviews"][0]["status"], "uncertain")
                    self.assertEqual(alternatives["state"], "no_rankable_dates")
                    self.assertEqual(alternatives["combinations"], [])
                    continue
                self.assertEqual(len(verse["evidence"]["positive_witness_ids"]), 1)
                self.assertEqual(alternatives["eligible_witness_count"], 1)
                self.assertEqual(len(alternatives["combinations"]), 1)
                combo = alternatives["combinations"][0]
                if ref == "John.5.11":
                    self.assertEqual(alternatives["unit_count"], 2)
                    self.assertEqual(len(verse["evidence"]["coverage_reviews"]), 2)
                    self.assertEqual({a["unit_id"] for a in combo["assessments"]}, {ORIGINAL, SUPPLEMENT})
                expected_unit = SUPPLEMENT if ref in REFS[:2] else ORIGINAL
                for scenario, expected_year in (("optimistic", 601 if ref in REFS[:2] else 400),
                                                ("pessimistic", 800 if ref in REFS[:2] else 499)):
                    entries = combo["scenarios"][scenario]
                    self.assertEqual(len(entries), 1)
                    self.assertEqual(entries[0]["witness_id"], "032-washingtonianus")
                    self.assertEqual(entries[0]["unit_id"], expected_unit)
                    self.assertEqual(entries[0]["event_year"], expected_year)
            html = render(graph)
            for expected in ("Prototype: incomplete discovery and validation", "uncertain",
                             "64v", "65r", "NT_GRC_032S_John.xml", "NT_GRC_032_John.xml",
                             "601–800", "400–499", "perhaps", "empty ab element"):
                self.assertIn(expected, html)

    def test_withdrawal_falls_back_to_surviving_supplement_then_removes_witness(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "withdraw.sqlite"
            summary = apply(path)
            with closing(connect(path)) as con:
                response = con.execute("SELECT index_response_id FROM coverage_review LIMIT 1").fetchone()[0]
                for page, expected_pairs, years in [(1290, 4, [601, 800]), (1280, 3, None)]:
                    record_coverage_review(con, summary["inventory_id"], "John.5.11", "John.5.11",
                                           20032, page, response, "withdrawn", "reviewed_transcription",
                                           "Synthetic withdrawal", "test", "tester")
                    _, graph = build_exports(con, summary["inventory_id"], summary["policy_id"])
                    self.assertEqual(graph["counts"]["positive_witness_verse_pairs"], expected_pairs)
                    verse = next(v for v in graph["verses"] if v["osis_ref"] == "John.5.11")
                    if years:
                        scenarios = verse["dating_alternatives"]["combinations"][0]["scenarios"]
                        self.assertEqual([scenarios[s][0]["event_year"] for s in
                                          ("optimistic", "pessimistic")], years)
                        self.assertEqual({e["unit_id"] for entries in scenarios.values()
                                          for e in entries}, {SUPPLEMENT})
                    else:
                        self.assertEqual(verse["dating_alternatives"]["combinations"], [])
                        self.assertEqual(verse["evidence"]["positive_witness_ids"], [])
                    self.assertEqual([len(v["evidence"]["positive_witness_ids"])
                                      for v in graph["verses"] if v["osis_ref"] != "John.5.11"],
                                     [1, 1, 0, 1])

    def test_uncertain_benchmark_rejects_later_positive_or_absence_inference(self):
        for change in ("positive", "absent"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "uncertain.sqlite"
                summary = apply(path)
                with closing(connect(path)) as con:
                    if change == "positive":
                        response = con.execute("SELECT index_response_id FROM coverage_review LIMIT 1").fetchone()[0]
                        record_coverage_review(con, summary["inventory_id"], "John.5.12", "John.5.12",
                                               20032, 1290, response, "partial", "reviewed_transcription",
                                               "Synthetic positive", "test", "tester")
                    else:
                        record_physical_absence_review(con, summary["inventory_id"], "John.5.12",
                                                       "032-washingtonianus", "absent", "checked_image",
                                                       "Synthetic image", "Synthetic absence", "test", "tester")
                audit = audit_database(path, BENCHMARK)
                self.assertEqual(audit["benchmark"]["passed"], 4)
                self.assertTrue(any(f["code"] == "benchmark_coverage_mismatch" for f in audit["findings"]))

    def test_changed_survival_identity_line_or_boundary_requires_new_source_review(self):
        changes = [
            ("032S", "excerpt", "<w>απεκρινατο</w>", f"<w><{tag}>απεκρινατο</{tag}></w>")
            for tag in ("supplied", "unclear", "ex")
        ] + [
            ("032S", "excerpt", '<w>απεκρινατο</w>', '<w hand="corrector">απεκρινατο</w>'),
            ("032S", "excerpt", 'reason="witnessEnd"', 'reason="lacuna"'),
            ("032S", "excerpt", 'P64vC1L30-032S', 'P64vC1L32-032S'),
            ("032", "excerpt", '<ab n="John.5.12"></ab>', '<ab n="John.5.12"><w>τις</w></ab>'),
            ("032", "excerpt", 'extent="rest"', 'extent="all"'),
            ("032", "excerpt", 'n="65r"', 'n="64v"'),
            ("032", "excerpt", 'type="book" n="John"', 'type="book" n="John" hand="corrector"'),
            ("032", "header", 'n="032"', 'n="032S"'),
        ]
        review, _, _, _ = load_inputs()
        for siglum, part, before, after in changes:
            with self.subTest(siglum=siglum, after=after):
                unit = next(u for u in review["units"] if u["siglum"] == siglum)
                fixture = read_json(ROOT / unit["transcription_fixture"])
                self.assertIn(before, fixture[f"raw_{part}"])
                fixture[f"raw_{part}"] = fixture[f"raw_{part}"].replace(before, after)
                fixture[f"{part}_sha256"] = hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest()
                with self.assertRaises(ValueError):
                    checked_transcription(fixture, siglum)

    def test_swapped_dates_layers_page_links_or_human_status_fail_before_database_creation(self):
        for change in ("supplement_date", "original_date", "cross_layer", "human_status", "index", "folio"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "bad.sqlite"

                def changed_read(source):
                    fixture = read_json(source)
                    if Path(source).name == REVIEW.name:
                        if change == "supplement_date":
                            fixture["units"][0]["assessments"][0].update(date_min=400, date_max=499)
                        elif change == "original_date":
                            fixture["units"][1]["assessments"][0].update(date_min=601, date_max=800)
                        elif change == "cross_layer":
                            fixture["coverage_reviews"][3]["unit_id"] = SUPPLEMENT
                        elif change == "human_status":
                            fixture["independent_human_validation"] = True
                        elif change == "index":
                            fixture["coverage_reviews"][0]["page_id"] = 1290
                        else:
                            fixture["coverage_reviews"][3]["folio"] = "64v"
                    return fixture

                with patch("replay_john5_boundary.read_json", side_effect=changed_read):
                    with self.assertRaises(ValueError):
                        apply(path)
                self.assertFalse(path.exists())

    def test_uncertain_benchmark_cannot_assert_numeric_date_or_positive_status(self):
        for change in ("date", "status"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as folder:
                fixture = read_json(BENCHMARK)
                case = next(c for c in fixture["cases"] if c["expected_coverage"] == "uncertain")
                if change == "date":
                    case.update(expected_date=[400, 499], date_citation="test")
                else:
                    case["expected_status"] = "partial"
                from controlled_ntvmr import encoded
                path = Path(folder) / "invalid.json"
                path.write_text(encoded(fixture), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_benchmark(path)

    def test_dry_run_and_existing_destination_are_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "boundary.sqlite"
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(main(["--db", str(path), "--dry-run"]), 0)
            self.assertFalse(path.exists())
            path.write_bytes(b"existing research")
            with self.assertRaisesRegex(ValueError, "fresh database"):
                apply(path)
            self.assertEqual(path.read_bytes(), b"existing research")


if __name__ == "__main__":
    unittest.main()
