"""Faithful report extraction and offline report-to-chart acceptance checks."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import re

from controlled_ntvmr import connect, rank_candidates
from export_attestation import main as export_main
from render_attestation import render
from report_explorer import build_explorer_data
from replay_source_reports import main as replay_main
from source_reports import (CONTRACT, build_report_exports, coverage_state, digest,
                            import_batch)


ROOT = Path(__file__).resolve().parents[1]


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "reports.sqlite"
        self.con = connect(self.db)
        self.addCleanup(self.con.close)
        self.inventory = {
            "format_version": 1, "inventory_id": "synthetic", "edition": "NA28",
            "scope": "Synthetic coordinate fixture", "source_citation": "Synthetic publisher",
            "reuse_terms": "Synthetic", "mapping_citation": "Synthetic explicit mapping",
            "reviewer": "Software test",
            "verses": [{"osis_ref": f"Gal.1.{i}", "editorial_status": "main",
                        "ntvmr_refs": [f"Gal.1.{i}"]} for i in range(1, 4)]}
        self.write("inventory.json", self.inventory)
        self.manifest = {"format_version": 1, "contract_id": CONTRACT, "batch_id": "synthetic",
                         "scope": "Fictional reports only", "inventory": "inventory.json",
                         "documents": [], "additional_reports": []}
        self.add_document(10046, ["Gal.1.1", "Gal.1.1", "Gal.1.2"], 100, 300)

    def write(self, name, record):
        (self.root / name).write_text(json.dumps(record), encoding="utf-8")

    def capture(self, name, doc_id, stage, data):
        body = json.dumps({"status": "success", "data": data})
        endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
        self.write(name, {"raw_body": body, "body_sha256": digest(body), "http_status": 200,
                          "source_url": f"https://ntvmr.uni-muenster.de/community/vmr/api/{endpoint}/",
                          "retrieved_at": "2026-10-05T12:00:00+00:00",
                          "params": {"docID": str(doc_id), "detail": "10" if stage == "metadata" else "long",
                                     "format": "json"}})

    def add_document(self, doc_id, refs, low, high):
        self.capture(f"meta-{doc_id}.json", doc_id, "metadata", {"manuscript": {
            "docID": doc_id, "gaNum": f"Synthetic {doc_id}", "lang": "grc",
            "originYear": {"early": low, "late": high, "content": "Synthetic estimate"}}})
        entries = [{"docID": doc_id, "pageID": 10+i, "osisID": ref} for i, ref in enumerate(refs)]
        self.capture(f"contents-{doc_id}.json", doc_id, "coverage", {"indexContents": {
            "docID": doc_id, "indexContent": ["Synthetic summary does not assert neighbors", *entries]}})
        self.manifest["documents"].append({"doc_id": doc_id, "corpus": "greek_nt_manuscript",
            "metadata_fixture": f"meta-{doc_id}.json", "coverage_fixture": f"contents-{doc_id}.json"})

    def report(self, *, coverage=None, dates=None):
        claims = (coverage or []) + (dates or [])
        self.manifest["additional_reports"].append({"provider": "Synthetic scholarly provider",
            "citation": "Synthetic publication https://example.org/report", "retrieved_at": "2026-10-05T12:00:00+00:00",
            "raw_body": "\n".join(c["statement"] for c in claims), "coverage": coverage or [], "dates": dates or []})

    def export(self):
        import_batch(self.con, self.manifest, self.root)
        return build_report_exports(self.con, self.manifest["batch_id"])

    def test_direct_reports_duplicates_and_missing_entries(self):
        dataset, graph = self.export()
        self.assertEqual(graph["counts"]["witness_verse_pairs"], {"present": 2, "absent": 0, "unknown": 1, "contested": 0})
        self.assertEqual(graph["counts"]["graphable_coordinates"], 2)
        events = graph["verses"][0]["dating_alternatives"]["combinations"][0]["scenarios"]
        self.assertEqual(len(events["optimistic"]), 1)
        self.assertEqual((events["optimistic"][0]["event_year"], events["pessimistic"][0]["event_year"]), (100, 300))
        for table in ("coverage_review", "candidate_review", "witness_assignment", "writing_unit", "physical_absence_review"):
            self.assertEqual(self.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
        claim = dataset["source_claims"][0]
        source = next(s for s in dataset["sources"] if s["source_response_id"] == claim["source_response_id"])
        self.assertEqual(claim["reported"], json.loads(source["raw_body"])["data"]["indexContents"]["indexContent"][1])
        self.assertIn("Indexing tier not supplied", claim["qualifications"])
        self.assertNotIn("raw_body", graph["sources"][0])

    def test_partial_full_are_presence_and_explicit_conflict_is_deferred(self):
        self.add_document(20001, ["Gal.1.1"], 200, 250)
        self.report(coverage=[{"witness_id": "ntvmr:10046", "source_ref": "Gal.1.1", "assertion": "present",
                               "extent": "partial", "source_locator": "p. 1", "statement": "A portion of the verse survives."}])
        _, graph = self.export()
        self.assertEqual(graph["verses"][0]["reported_coverage"][0]["state"], "present")
        self.manifest["batch_id"] = "disagreement"
        self.report(coverage=[{"witness_id": "ntvmr:10046", "source_ref": "Gal.1.1", "assertion": "absent",
                               "source_locator": "p. 2", "statement": "The verse is absent from this witness."}])
        _, graph = self.export()
        pairs = graph["verses"][0]["reported_coverage"]
        self.assertEqual([p["state"] for p in pairs], ["contested", "present"])
        self.assertEqual(len(pairs[0]["claims"]), 4)
        events = graph["verses"][0]["dating_alternatives"]["combinations"][0]["scenarios"]["optimistic"]
        self.assertEqual([e["witness_id"] for e in events], ["ntvmr:20001"])
        html = render(graph)
        self.assertIn("Explicit incompatible source claims retained", html)
        self.assertIn("A portion of the verse survives.", html)
        self.assertNotIn("coverage reviewed by", html)

    def test_explicit_absence_unknown_and_unmapped_stay_distinct(self):
        self.inventory["verses"][2].update(ntvmr_refs=[], mapping_note="Unresolved synthetic mapping")
        self.write("inventory.json", self.inventory)
        self.report(coverage=[{"witness_id": "ntvmr:10046", "source_ref": "Gal.1.3", "assertion": "absent",
                               "source_locator": "p. 2", "statement": "Explicit absence report."}])
        _, graph = self.export()
        self.assertEqual(graph["counts"]["mapping_gaps"], 1)
        self.assertEqual(graph["verses"][2]["reported_coverage"][0]["state"], "unknown")
        self.assertEqual(coverage_state([{"assertion": "absent"}, {"assertion": "unknown"}]), "absent")
        self.assertEqual(coverage_state([{"assertion": "present"}, {"assertion": "unknown"}]), "present")

    def test_complete_date_alternatives_preserve_interval_and_reverse_rank(self):
        self.add_document(20001, ["Gal.1.1"], 200, 250)
        self.report(dates=[{"witness_id": "ntvmr:10046", "source_locator": "Date table",
                            "statement": "Alternative estimate: 150–350 CE.", "original_notation": "150–350 CE",
                            "date_min": 150, "date_max": 350}])
        _, graph = self.export()
        combos = graph["verses"][0]["dating_alternatives"]["combinations"]
        self.assertEqual(len(combos), 2)
        for combo in combos:
            self.assertEqual(combo["scenarios"]["optimistic"][0]["witness_id"], "ntvmr:10046")
            self.assertEqual(combo["scenarios"]["pessimistic"][0]["witness_id"], "ntvmr:20001")
        self.assertEqual([(c["assessments"][0]["date_min"], c["assessments"][0]["date_max"]) for c in combos], [(100, 300), (150, 350)])
        self.assertEqual(len(build_explorer_data(graph)["observations"]["Gal.1.1"]["dating_alternatives"]["combinations"]), 2)

    def test_unknown_date_does_not_erase_presence(self):
        self.add_document(20001, ["Gal.1.3"], 0, 0)
        _, graph = self.export()
        verse = graph["verses"][2]
        self.assertEqual(verse["reported_coverage"][1]["state"], "present")
        self.assertEqual(verse["ranking_state"], "no_rankable_dates")
        self.assertEqual(verse["dating_alternatives"]["unrankable_assessments"][0]["status"], "unknown")
        self.assertEqual(build_explorer_data(graph)["dates"][str(verse["reported_coverage"][1]["date_assessments"][0]["assessment_id"])]["status"], "unknown")

    def test_explicit_provider_unconfirmed_indexing_is_unknown(self):
        path = self.root / "meta-10046.json"
        record = json.loads(path.read_text())
        payload = json.loads(record["raw_body"])
        payload["data"]["manuscript"]["pages"] = {"page": [{"pageID": 10, "indexTier": 4}]}
        record["raw_body"] = json.dumps(payload)
        record["body_sha256"] = digest(record["raw_body"])
        self.write(path.name, record)
        _, graph = self.export()
        # Another page's ordinary report still supplies presence for this same verse.
        self.assertEqual(graph["verses"][0]["reported_coverage"][0]["state"], "present")
        claim = graph["verses"][0]["reported_coverage"][0]["claims"][0]
        self.assertEqual(claim["assertion"], "unknown")
        self.assertIn("awaiting human confirmation", claim["qualifications"])

    def test_source_changes_require_new_batch_and_preserve_history(self):
        self.export()
        first_count = self.con.execute("SELECT count(*) FROM source_response").fetchone()[0]
        self.export()
        self.assertEqual(self.con.execute("SELECT count(*) FROM source_response").fetchone()[0], first_count)
        self.manifest["scope"] += " Revised."
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.export()
        self.manifest["batch_id"] = "new-version"
        self.export()
        self.assertEqual(self.con.execute("SELECT count(*) FROM scholarly_report_batch").fetchone()[0], 2)
        self.assertEqual(build_report_exports(self.con, "synthetic")[1]["collection_scope"], "Fictional reports only")

    def test_malformed_capture_is_contract_error_not_absence(self):
        path = self.root / "contents-10046.json"
        record = json.loads(path.read_text())
        record["raw_body"] = '{"status":"success","data":{}}'
        record["body_sha256"] = digest(record["raw_body"])
        self.write(path.name, record)
        with self.assertRaises(ValueError):
            self.export()
        self.assertEqual(self.con.execute("SELECT count(*) FROM source_response").fetchone()[0], 0)

    def test_stored_claim_drift_is_blocked_without_using_old_reviews(self):
        self.export()
        record = json.loads(self.con.execute("SELECT claim_json FROM scholarly_date_claim LIMIT 1").fetchone()[0])
        record["date_min"] = 1
        self.con.execute("UPDATE scholarly_date_claim SET claim_json=?", (json.dumps(record),))
        with self.assertRaisesRegex(ValueError, "claims changed"):
            build_report_exports(self.con, "synthetic")

    def test_source_hash_mismatch_is_blocked(self):
        self.export()
        self.con.execute("UPDATE source_response SET body=body || 'corrupt'")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            build_report_exports(self.con, "synthetic")

    def test_mapping_drift_is_blocked(self):
        self.export()
        self.con.execute("DELETE FROM edition_verse_map WHERE osis_ref='Gal.1.1'")
        with self.assertRaisesRegex(ValueError, "coordinates disagree"):
            build_report_exports(self.con, "synthetic")

    def test_independent_top_five_and_stable_ties(self):
        candidates = [{"witness_id": str(i), "date_min": 100+i, "date_max": 300-i} for i in range(7)]
        self.assertEqual([r["witness_id"] for r in rank_candidates(candidates, "optimistic")[:5]], list("01234"))
        self.assertEqual([r["witness_id"] for r in rank_candidates(candidates, "pessimistic")[:5]], list("65432"))
        self.assertEqual(rank_candidates(candidates, "optimistic"), rank_candidates(list(reversed(candidates)), "optimistic"))

    def test_alias_join_requires_attribution_and_counts_once(self):
        self.add_document(10047, ["Gal.1.1"], 200, 250)
        self.manifest["documents"][1]["witness_id"] = "ntvmr:10046"
        with self.assertRaisesRegex(ValueError, "provider"):
            self.export()
        self.manifest["documents"][1]["identity_report"] = {
            "provider": "Synthetic scholar", "citation": "Synthetic join catalogue",
            "consulted_on": "2026-10-05", "source_locator": "Record 1", "statement": "These IDs identify one physical witness."}
        _, graph = self.export()
        self.assertEqual(graph["counts"]["witness_count"], 1)
        for combo in graph["verses"][0]["dating_alternatives"]["combinations"]:
            self.assertEqual(len(combo["scenarios"]["optimistic"]), 1)

    def test_filters_keep_complete_reports_and_export_is_read_only(self):
        self.inventory["verses"][1].update(editorial_status="omitted", editorial_note="Synthetic edition omission")
        self.inventory["verses"][2].update(editorial_status="bracketed", editorial_note="Synthetic brackets")
        self.write("inventory.json", self.inventory)
        dataset, graph = self.export()
        self.assertEqual(dataset["counts"]["verse_count"], 3)
        self.assertEqual(graph["counts"]["verse_count"], 2)
        _, graph = build_report_exports(self.con, "synthetic", include_omitted=True, include_bracketed=False)
        self.assertEqual([v["osis_ref"] for v in graph["verses"]], ["Gal.1.1", "Gal.1.2"])
        before = self.db.read_bytes()
        with redirect_stdout(StringIO()):
            self.assertEqual(export_main(["--db", str(self.db), "--report-batch", "synthetic",
                "--dataset-output", str(self.root / "dataset.json"), "--graph-output", str(self.root / "graph.json")]), 0)
        self.assertEqual(before, self.db.read_bytes())

    def test_combination_overflow_is_visible(self):
        self.report(dates=[{"witness_id": "ntvmr:10046", "source_locator": f"Date {i}",
                            "statement": f"Synthetic alternative {i}", "original_notation": f"Alternative {i}",
                            "date_min": 100+i, "date_max": 400+i} for i in range(256)])
        _, graph = self.export()
        alt = graph["verses"][0]["dating_alternatives"]
        self.assertEqual(alt["state"], "too_many_combinations")
        self.assertEqual(alt["combination_count"], 257)
        self.assertEqual(alt["combinations"], [])
        self.assertIn("too_many_combinations", render(graph))


class BoundedReplayTests(unittest.TestCase):
    def test_whole_galatians_reuses_six_captures_in_full_gnt_explorer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = []
            for number in (1, 2):
                args = ["--manifest", str(ROOT / "benchmarks/galatians-source-reports-v1.json"),
                        "--db", str(root / f"new-{number}.sqlite"),
                        "--dataset-output", str(root / f"dataset-{number}.json"),
                        "--graph-output", str(root / f"graph-{number}.json"),
                        "--html-output", str(root / f"chart-{number}.html")]
                with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")), redirect_stdout(StringIO()):
                    self.assertEqual(replay_main(args), 0)
                artifacts.append(tuple((root / f"{name}-{number}.{suffix}").read_text(encoding="utf-8")
                                       for name, suffix in (("dataset", "json"), ("graph", "json"), ("chart", "html"))))
            self.assertEqual(artifacts[0], artifacts[1])
            graph = json.loads(artifacts[0][1])
            self.assertEqual(graph["counts"]["witness_verse_pairs"], {"present": 437, "absent": 0, "unknown": 10, "contested": 0})
            self.assertEqual(graph["counts"]["graphable_coordinates"], 149)
            self.assertEqual(graph["counts"]["mapping_gaps"], 0)
            self.assertEqual(graph["collection_cost"]["reused_response_count"], 6)
            self.assertEqual(graph["collection_cost"]["replay_network_requests"], 0)
            publisher = json.loads((ROOT / "benchmarks/na28-nt-reference-provisional-v3.json").read_text(encoding="utf-8"))
            expected = [v for v in publisher["verses"] if v["osis_ref"].startswith("Gal.")]
            self.assertEqual([v["osis_ref"] for v in graph["verses"]], [v["osis_ref"] for v in expected])
            for verse in graph["verses"]:
                pairs = verse["reported_coverage"]
                self.assertEqual([p["state"] for p in pairs[1:]], ["present", "present"])
                for pair in pairs:
                    self.assertEqual({d["status"] for d in pair["date_assessments"]}, {"valid"})
                    if pair["state"] == "unknown":
                        self.assertEqual(pair["witness_id"], "ntvmr:10046")
                        self.assertEqual(pair["claims"], [])
                        self.assertEqual(pair["unknown_reason"], "no_explicit_mapped_report")
                combo = verse["dating_alternatives"]["combinations"][0]
                present_ids = [p["witness_id"] for p in pairs if p["state"] == "present"]
                for side in ("optimistic", "pessimistic"):
                    self.assertEqual([e["witness_id"] for e in combo["scenarios"][side]], present_ids)
            html = artifacts[0][2]
            self.assertEqual(html.count('<canvas '), 1)
            payload = json.loads(re.search(r'<script id="attestation-data" type="application/json">(.*?)</script>', html, re.S).group(1))
            self.assertEqual(len(payload["coordinates"]), 7957)
            self.assertEqual(len(payload["observations"]), 149)
            self.assertEqual(payload["metadata"]["counts"], graph["counts"])
            self.assertIn('name="scenario" value="pessimistic"', html)

    def test_real_captures_replay_without_network_and_render_explorer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = ["--manifest", str(ROOT / "benchmarks/gal1-source-reports-v1.json"), "--db", str(root / "new.sqlite"),
                    "--dataset-output", str(root / "dataset.json"), "--graph-output", str(root / "graph.json"),
                    "--html-output", str(root / "chart.html")]
            with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")), redirect_stdout(StringIO()):
                self.assertEqual(replay_main(args), 0)
            graph = json.loads((root / "graph.json").read_text(encoding="utf-8"))
            self.assertEqual(graph["counts"]["witness_verse_pairs"], {"present": 29, "absent": 0, "unknown": 1, "contested": 0})
            self.assertEqual(graph["counts"]["graphable_coordinates"], 10)
            self.assertEqual(graph["collection_cost"]["replay_network_requests"], 0)
            self.assertEqual(graph["collection_cost"]["reused_response_count"], 6)
            html = (root / "chart.html").read_text(encoding="utf-8")
            self.assertEqual(html.count('<canvas '), 1)
            self.assertIn("Source snapshots", html)
            data = build_explorer_data(graph)
            combo = data["observations"]["Gal.1.1"]["dating_alternatives"]["combinations"][0]
            self.assertEqual(combo["scenarios"]["optimistic"][0]["event_year"], 200)
            self.assertEqual(combo["scenarios"]["pessimistic"][0]["event_year"], 225)
            self.assertIn("unknown", html)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                replay_main(args)


if __name__ == "__main__":
    unittest.main()
