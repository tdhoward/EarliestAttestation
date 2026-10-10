"""Faithful report extraction and offline report-to-chart acceptance checks."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from pipeline.controlled_ntvmr import connect, rank_candidates
from export_attestation import main as export_main
from pipeline.report_explorer import build_explorer_data
from pipeline.source_reports import (CONTRACT, build_report_exports, coverage_state, digest,
                            import_batch, prepare_batch)


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
        dataset, graph = build_report_exports(self.con, self.manifest["batch_id"])
        rows = []
        streamed_dataset, streamed_graph = build_report_exports(
            self.con, self.manifest["batch_id"], consume_verse=rows.append)
        self.assertIsNone(streamed_dataset)
        self.assertEqual(streamed_graph["verses"], [])
        self.assertEqual({**streamed_graph, "verses": rows}, graph)
        return dataset, graph

    def test_empty_string_report_retains_sources_and_leaves_every_verse_unknown(self):
        self.capture("contents-10046.json", 10046, "coverage", {"indexContents": {
            "docID": 10046, "indexContent": ""}})
        dataset, graph = self.export()
        self.assertEqual(graph["counts"]["witness_verse_pairs"],
                         {"present": 0, "absent": 0, "unknown": 3, "contested": 0})
        self.assertEqual(dataset["source_claims"], [])
        self.assertEqual(dataset["documents"][0]["coverage_state"], "empty")
        self.assertEqual(self.con.execute("SELECT count(*) FROM source_response").fetchone()[0], 2)
        body = self.con.execute("SELECT body FROM source_response WHERE endpoint='biblicalcontent/get'").fetchone()[0]
        self.assertEqual(json.loads(body)["data"]["indexContents"]["indexContent"], "")
        self.assertFalse(any(combo["scenarios"]["optimistic"] for row in graph["verses"]
                             for combo in row["dating_alternatives"]["combinations"]))

    def test_multilingual_metadata_and_mixed_contents_preserve_exact_claims_and_dates(self):
        self.capture("meta-10046.json", 10046, "metadata", {"manuscript": {
            "docID": 10046, "gaNum": "Synthetic 10046", "lang": "g-l",
            "originYear": {"early": 100, "late": 300, "content": 200}}})
        entries = [
            {"docID": 10046, "pageID": 10, "osisID": "Gen", "indexContent": 1001000000},
            {"docID": 10046, "pageID": 10, "osisID": "Gen.1.1"},
            {"docID": 10046, "pageID": 20, "osisID": "Gal.1.1"},
            {"docID": 10046, "pageID": 30, "osisID": "3Macc", "indexContent": 1023000000}]
        self.capture("contents-10046.json", 10046, "coverage", {"indexContents": {
            "docID": 10046, "indexContent": ["Summary supplies no adjacent coverage", *entries]}})
        dataset, graph = self.export()
        self.assertEqual(graph["counts"]["witness_verse_pairs"],
                         {"present": 1, "absent": 0, "unknown": 2, "contested": 0})
        claim, = dataset["source_claims"]
        self.assertEqual(claim["reported"], entries[2])
        self.assertEqual(claim["source_locator"], "data.indexContents.indexContent[3]")
        self.assertEqual(dataset["documents"][0]["reported_language"], "g-l")
        date, = dataset["date_assessments"]
        self.assertEqual(date["reported"], {"early": 100, "late": 300, "content": 200})
        self.assertIs(type(date["original_notation"]), int)
        events = graph["verses"][0]["dating_alternatives"]["combinations"][0]["scenarios"]
        self.assertEqual((events["optimistic"][0]["event_year"], events["pessimistic"][0]["event_year"]), (100, 300))

    def test_observed_multilingual_codes_are_retained_but_other_languages_stay_unsupported(self):
        for language in ("g-k", "g-l", "g-arb", "g-arm", "g-l-arb", "g-sl", "g-t", "lat", "g-unknown"):
            with self.subTest(language=language):
                self.capture("meta-10046.json", 10046, "metadata", {"manuscript": {
                    "docID": 10046, "gaNum": "Synthetic 10046", "lang": language,
                    "originYear": {"early": 100, "late": 300, "content": "Synthetic estimate"}}})
                if language in ("lat", "g-unknown"):
                    with self.assertRaisesRegex(ValueError, "Greek language"):
                        prepare_batch(self.manifest, self.root)
                else:
                    _, _, _, _, documents = prepare_batch(self.manifest, self.root)
                    self.assertEqual(documents[0]["reported_language"], language)

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
        data = build_explorer_data(graph)
        self.assertEqual(data["observations"]["Gal.1.1"]["reported_coverage"][0]["state"], "contested")
        self.assertTrue(any(c["reported"] == "A portion of the verse survives." for c in data["claims"].values()))

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

    def test_scoped_index_limitation_admits_absence_and_promotes_replacements(self):
        for i in range(6):
            self.add_document(10047+i, ["Gal.1.1"], 200+i, 400+i)
        self.report(coverage=[{"witness_id": "ntvmr:10046", "source_ref": "Gal.1.1", "assertion": "absent",
                              "source_locator": "Fictional omission report", "statement": "Verse one is absent."}])
        report = self.manifest["additional_reports"][-1]
        report.update(source_url="https://example.org/omission", body_sha256=digest(report["raw_body"]))
        self.write("omission.json", report)
        doc = self.manifest["documents"][0]
        doc["index_limitations"] = [{"limitation_id": "fictional-range-ambiguity", "verses": ["Gal.1.1"],
            "metadata_sha256": json.loads((self.root / doc["metadata_fixture"]).read_text())["body_sha256"],
            "coverage_sha256": json.loads((self.root / doc["coverage_fixture"]).read_text())["body_sha256"],
            "reason": "Fictional exact index contribution is ambiguous.", "evidence": [
                {"capture_file": "omission.json", "body_sha256": report["body_sha256"],
                 "source_locator": "Fictional omission report", "statement": "Verse one is absent."}]}]
        dataset, graph = self.export()
        pair = next(p for p in graph["verses"][0]["reported_coverage"] if p["witness_id"] == "ntvmr:10046")
        self.assertEqual(pair["state"], "absent")
        self.assertEqual({c["assertion"] for c in pair["claims"]}, {"unknown", "absent"})
        self.assertTrue(all(c["reported"]["osisID"] == "Gal.1.1" for c in pair["claims"] if "index_limitation" in c))
        neighbor = next(p for p in graph["verses"][1]["reported_coverage"] if p["witness_id"] == "ntvmr:10046")
        self.assertEqual(neighbor["state"], "present")
        for side in ("optimistic", "pessimistic"):
            events = graph["verses"][0]["dating_alternatives"]["combinations"][0]["scenarios"][side]
            self.assertEqual([e["witness_id"] for e in events], [f"ntvmr:{d}" for d in range(10047, 10052)])
        self.assertEqual(graph["counts"]["witness_verse_pairs"]["contested"], 0)
        from pipeline.browser_format import pack_browser_data, unpack_browser_data
        from pipeline.report_explorer import expand_explorer_data
        restored = expand_explorer_data(unpack_browser_data(pack_browser_data(build_explorer_data(graph))))
        claim = next(c for c in restored["claims"].values() if "index_limitation" in c)
        self.assertEqual(claim["index_limitation"]["evidence"][0]["source_url"], "https://example.org/omission")
        doc["index_limitations"][0]["coverage_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source changed"):
            prepare_batch(self.manifest, self.root)

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
        self.assertEqual(build_explorer_data(graph)["observations"]["Gal.1.1"]["dating_alternatives"]["state"], "too_many_combinations")



if __name__ == "__main__":
    unittest.main()
