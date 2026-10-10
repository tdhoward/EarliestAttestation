"""Bounded fictional reports: scope, provenance, stale comparisons, and dates."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from build_collection import load_additional_reports, prepare_collection
from source_checks import METHOD, first_five_targets, prepare_checks, queue_first_five, stable_claim_id
from pipeline.source_reports import CONTRACT, digest, prepare_batch


class SourceCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory = {"format_version": 1, "inventory_id": "fictional-checks", "edition": "NA28",
                          "scope": "Fictional coordinates", "source_citation": "Fictional publisher",
                          "reuse_terms": "Fictional", "mapping_citation": "Exact coordinates",
                          "reviewer": "Software fixture", "verses": [
                              {"osis_ref": f"Gal.1.{v}", "editorial_status": "main", "ntvmr_refs": [],
                               "mapping_note": "Fictional unmapped coordinate"}
                              for v in range(1, 4)]}
        self.metadata = {"manuscript": {"docID": 10001, "gaNum": "Fictional P1", "lang": "grc",
                         "originYear": {"early": 100, "late": 300, "content": "Fictional 100-300"}}}
        self.contents = {"indexContents": {"docID": 10001, "indexContent": [
            {"docID": 10001, "pageID": 10, "osisID": "Gal.1.1"},
            {"docID": 10001, "pageID": 20, "osisID": "Gal.1.2"}]}}
        self.ntvmr_capture("metadata.json", "metadata", self.metadata)
        self.ntvmr_capture("contents.json", "coverage", self.contents)
        self.report = {"report_id": "fictional-publication", "provider": "Fictional scholar",
                       "citation": "Fictional publication https://example.org/report",
                       "retrieved_at": "2026-10-08T10:00:00Z",
                       "raw_body": "Verse one partly survives. Verse two is absent. Estimated 120-320.",
                       "coverage": [
                           {"witness_id": "ntvmr:10001", "source_ref": "Gal.1.1", "assertion": "present",
                            "extent": "partial", "source_locator": "Fictional table row 1", "statement": "Verse one partly survives."},
                           {"witness_id": "ntvmr:10001", "source_ref": "Gal.1.2", "assertion": "absent",
                            "source_locator": "Fictional table row 2", "statement": "Verse two is absent."}],
                       "dates": [{"witness_id": "ntvmr:10001", "date_min": 120, "date_max": 320,
                                  "original_notation": "Fictional 120-320", "source_locator": "Fictional date row",
                                  "statement": "Estimated 120-320.", "qualifications": "Fictional alternative estimate"}]}
        self.report["body_sha256"] = digest(self.report["raw_body"])
        self.write("publication.json", self.report)
        self.manifest = {"format_version": 1, "contract_id": CONTRACT, "batch_id": "fictional",
                         "scope": "Fictional reports only", "inventory": self.inventory,
                         "documents": [{"doc_id": 10001, "corpus": "greek_nt_manuscript",
                                        "metadata_fixture": "metadata.json", "coverage_fixture": "contents.json"}],
                         "additional_reports": [{**self.report, "capture_file": "publication.json"}]}

    def write(self, relative, value):
        (self.root / relative).write_text(json.dumps(value), encoding="utf-8")

    def ntvmr_capture(self, relative, stage, payload):
        body = json.dumps({"status": "success", "data": payload})
        endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
        record = {"raw_body": body, "body_sha256": digest(body), "http_status": 200,
                  "retrieved_at": "2026-10-08T10:00:00Z",
                  "source_url": "https://ntvmr.uni-muenster.de/community/vmr/api/"+endpoint+"/",
                  "params": {"docID": "10001", "detail": "10" if stage == "metadata" else "long", "format": "json"}}
        self.write(relative, record)
        return record

    def check(self, *, kind="content", verses=None, outcome="agreement", interpretation="explicit"):
        verses = ["Gal.1.1"] if verses is None else verses
        _, _, coverage, dates, _ = prepare_batch(self.manifest, self.root, include_pending=True)
        claims = coverage if kind == "content" else dates
        claims = [c for c in claims if kind == "date" or c["source_ref"] in verses]
        evidence = []
        for role, stage, path, meaning in [("ntvmr", "metadata", "metadata.json", "explicit" if kind == "date" else "context"),
                                            ("ntvmr", "coverage", "contents.json", interpretation if kind == "content" else "context"),
                                            ("comparison", "scholarly", "publication.json", "explicit")]:
            raw = json.loads((self.root / path).read_text())
            entry = {"role": role, "stage": stage, "capture_file": path,
                     "body_sha256": raw["body_sha256"], "source_locator": "Fictional scoped locator",
                     "claim_ids": [stable_claim_id(kind, c) for c in claims if c["source_sha256"] == raw["body_sha256"]],
                     "interpretation": meaning}
            if stage == "scholarly":
                entry.update(report_id=self.report["report_id"], admission=self.manifest["additional_reports"][0].get("admission", "active"))
            else:
                entry["doc_id"] = 10001
            evidence.append(entry)
        return {"check_id": "fictional-scoped-check", "witness_id": "ntvmr:10001", "doc_ids": [10001],
                "kind": kind, "scope": {"verses": verses} if kind == "content" else {"applicability": "catalogue_document"},
                "method": deepcopy(METHOD), "checked_on": "2026-10-08", "outcome": outcome,
                "explanation": "Fictional explicit source comparison within this scope only.", "evidence": evidence,
                "follow_up": {"state": "open", "reason": "Fictional follow-up", "evidence": []}}

    def prepare(self, *checks):
        return prepare_checks({"format_version": 1, "checks": list(checks)}, self.manifest, self.root)

    def test_partial_presence_agrees_only_within_exact_scope(self):
        check = self.check()
        result = self.prepare(check)
        self.assertEqual(result["checks"][0]["scope"], {"verses": ["Gal.1.1"]})
        self.assertEqual(result["summary"]["current_outcomes"], {"agreement": 1})
        self.assertEqual(result["checks"][0]["evidence_claim_count"], 2)
        self.assertEqual(self.prepare(self.check(verses=["Gal.1.1", "Gal.1.3"], outcome="insufficient_detail"))["checks"][0]["outcome"], "insufficient_detail")

    def test_explicit_content_conflict_is_separate_from_ambiguous_index(self):
        explicit = self.check(verses=["Gal.1.2"], outcome="disagreement")
        self.assertEqual(self.prepare(explicit)["checks"][0]["outcome"], "disagreement")
        ambiguous = self.check(verses=["Gal.1.2"], interpretation="ambiguous_index", outcome="insufficient_detail")
        self.assertEqual(self.prepare(ambiguous)["checks"][0]["outcome"], "insufficient_detail")
        ambiguous["outcome"] = "disagreement"
        with self.assertRaisesRegex(ValueError, "outcome must be insufficient_detail"):
            self.prepare(ambiguous)

    def test_other_ambiguous_evidence_does_not_mask_a_real_conflict_or_mix_identical_bodies(self):
        check = self.check(verses=["Gal.1.2"], outcome="disagreement")
        other = {**deepcopy(self.report), "report_id": "fictional-index-publication",
                 "provider": "Another fictional provider", "citation": "https://example.org/index"}
        self.write("other-publication.json", other)
        self.manifest["additional_reports"].append({**other, "capture_file": "other-publication.json"})
        _, _, claims, _, _ = prepare_batch(self.manifest, self.root)
        entry = {**deepcopy(check["evidence"][2]), "report_id": other["report_id"],
                 "capture_file": "other-publication.json", "interpretation": "ambiguous_index",
                 "claim_ids": [stable_claim_id("content", c) for c in claims
                               if c["citation"] == other["citation"] and c["source_ref"] == "Gal.1.2"]}
        check["evidence"].append(entry)
        result = self.prepare(check)
        self.assertEqual(result["checks"][0]["outcome"], "disagreement")
        self.assertEqual(result["checks"][0]["status"], "current")
        entry["claim_ids"] = check["evidence"][2]["claim_ids"]
        with self.assertRaisesRegex(ValueError, "Stable claim links"):
            self.prepare(check)

    def test_missing_index_entries_never_supply_absence_or_agreement(self):
        check = self.check(verses=["Gal.1.3"], interpretation="missing_entries", outcome="insufficient_detail")
        self.assertEqual(self.prepare(check)["summary"]["current_outcomes"], {"insufficient_detail": 1})
        check["outcome"] = "agreement"
        with self.assertRaisesRegex(ValueError, "insufficient_detail"):
            self.prepare(check)

    def test_dates_compare_complete_intervals_without_narrowing_alternatives(self):
        before = deepcopy(self.manifest)
        self.assertEqual(self.prepare(self.check(kind="date", outcome="disagreement"))["checks"][0]["kind"], "date")
        _, _, _, dates, _ = prepare_batch(self.manifest, self.root)
        self.assertEqual([(d["date_min"], d["date_max"]) for d in dates], [(100, 300), (120, 320)])
        self.assertEqual(dates[1]["original_notation"], "Fictional 120-320")
        self.assertEqual(dates[1]["qualifications"], "Fictional alternative estimate")
        self.assertEqual(self.manifest, before)

    def test_stable_ids_ignore_database_row_ids_but_include_extraction_qualifications(self):
        _, _, claims, _, _ = prepare_batch(self.manifest, self.root)
        claim = claims[0]
        identifier = stable_claim_id("content", claim)
        self.assertEqual(stable_claim_id("content", {**claim, "claim_id": 999, "snapshot": 48, "source_response_id": 77}), identifier)
        self.assertNotEqual(stable_claim_id("content", {**claim, "qualifications": "Changed rule"}), identifier)

    def test_completed_rechecks_preserve_and_validate_archived_checks(self):
        old = self.check()
        current = deepcopy(old)
        current["check_id"] = "current-recheck"
        old["superseded_by"] = current["check_id"]
        result = self.prepare(old, current)
        self.assertEqual(result["summary"]["by_status"], {"superseded": 1, "current": 1})
        self.assertEqual(result["summary"]["current_outcomes"], {"agreement": 1})
        old["evidence"][0]["body_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash"):
            self.prepare(old, current)
        old = self.check()
        old["superseded_by"] = "missing"
        with self.assertRaisesRegex(ValueError, "resolve"):
            self.prepare(old)
        old["superseded_by"] = current["check_id"]
        current["superseded_by"] = old["check_id"]
        with self.assertRaisesRegex(ValueError, "cycles"):
            self.prepare(old, current)

    def test_first_five_selection_reads_all_modes_and_alternatives_without_coverage_expansion(self):
        events = [{"witness_id": f"ntvmr:{10001+i}", "assessment_id": i+1} for i in range(10)]
        dates = {str(i+1): {"witness_id": e["witness_id"], "status": "valid", "date_min": 100+i,
                           "date_max": 200+i, "original_notation": f"Fictional {i}"} for i, e in enumerate(events)}
        dates["11"] = {**dates["1"], "date_min": 50, "date_max": 900, "original_notation": "Complete alternative"}
        events.append({"witness_id": "ntvmr:10001", "assessment_id": 11})
        data = {"format_version": 5, "coordinates": ["Gal.1.1", "Gal.1.2", "Gal.1.3", "Gal.1.4"],
            "coordinate_statuses": {"3": "omitted"},
            "dates": dates, "ranking_events": events,
            "observation_defaults": {"dating_alternatives": 0},
            "observations": {"0": [0, "coverage must not be read"], "1": [0], "2": [1]},
            "observation_contexts": [{}, {"dating_alternatives": 1}],
            "ranking_templates": [{"state": "complete", "combinations": [
                {"scenarios": {"optimistic": [0, 1, 2, 3, 4, 9], "pessimistic": [4, 5, 6, 7, 8]}},
                {"scenarios": {"optimistic": [10, 9, 1, 2, 3], "pessimistic": [4, 5, 6, 7, 8]}}]},
                {"state": "too_many_combinations", "combination_count": 512, "max_combinations": 256, "combinations": []}]}
        selection = first_five_targets(data)
        self.assertEqual(selection["summary"]["witness_count"], 10)
        self.assertEqual(selection["summary"]["witness_verse_count"], 20)
        self.assertEqual(selection["limitations"][0]["verse"], "Gal.1.3")
        self.assertEqual(selection["limitations"][1], {"verse": "Gal.1.4", "state": "filtered"})
        self.assertEqual([(d["date_min"], d["date_max"]) for d in selection["targets"][0]["date_reports"]], [(100, 200), (50, 900)])
        # The sixth lower-endpoint event is selected only through the second combination.
        self.assertEqual(selection["targets"][-1]["verses"], ["Gal.1.1", "Gal.1.2"])
        documents = [{"doc_id": 10001+i} for i in range(10)]
        queued = queue_first_five({"format_version": 1, "checks": []}, selection, documents)
        self.assertEqual(len(queued["checks"]), 20)
        self.assertEqual(queue_first_five(queued, selection, documents), queued)
        promoted = deepcopy(selection)
        promoted["targets"][0]["verses"].append("Gal.1.3")
        replacement_queue = queue_first_five(queued, promoted, documents)
        self.assertEqual(replacement_queue["checks"][0]["scope"], {"verses": ["Gal.1.1", "Gal.1.2", "Gal.1.3"]})
        self.assertEqual(len(replacement_queue["checks"]), 20)
        reduced = deepcopy(selection)
        reduced["targets"] = reduced["targets"][:-1]
        self.assertEqual(len(queue_first_five(queued, reduced, documents)["checks"]), 18)

    def test_new_reports_trigger_recheck_only_when_the_exact_scope_is_affected(self):
        check = self.check()
        extra = deepcopy(self.report)
        extra["report_id"] = "new-report"
        extra["coverage"] = [c for c in extra["coverage"] if c["source_ref"] == "Gal.1.2"]
        extra["dates"] = []
        self.manifest["additional_reports"].append(extra)
        self.assertEqual(self.prepare(check)["checks"][0]["status"], "current")
        extra["coverage"] = [self.report["coverage"][0]]
        result = self.prepare(check)
        self.assertEqual(result["checks"][0]["status"], "needs_recheck")
        self.assertIn("new-report additional scoped report added", result["checks"][0]["recheck_reasons"])

    def test_control_observations_are_checked_against_pinned_catalogue_fields(self):
        check = self.check()
        check["index_observations"] = {"expanded_entries": [deepcopy(self.contents["indexContents"]["indexContent"][0])],
                                       "metadata_pages": []}
        self.assertEqual(self.prepare(check)["checks"][0]["index_observations"], check["index_observations"])
        check["index_observations"]["expanded_entries"][0]["pageID"] = 999
        with self.assertRaisesRegex(ValueError, "exact pinned fields"):
            self.prepare(check)

    def test_new_snapshot_preserves_old_evidence_and_marks_only_its_checks_stale(self):
        check = self.check()
        old = deepcopy(check)
        payload = deepcopy(self.contents)
        payload["indexContents"]["indexContent"].append({"docID": 10001, "pageID": 30, "osisID": "Gal.1.3"})
        self.ntvmr_capture("new-contents.json", "coverage", payload)
        self.manifest["documents"][0]["coverage_fixture"] = "new-contents.json"
        result = self.prepare(check)
        self.assertEqual(result["checks"][0]["status"], "needs_recheck")
        self.assertEqual(result["summary"]["current_outcomes"], {})
        self.assertEqual(result["summary"]["recorded_outcomes"], {"agreement": 1})
        self.assertEqual(check, old)
        self.assertTrue((self.root / "contents.json").exists())
        date_check = self.check(kind="date", outcome="disagreement")
        date_check["evidence"] = [e for e in date_check["evidence"] if e["stage"] != "coverage"]
        self.assertEqual(self.prepare(date_check)["checks"][0]["status"], "current")

    def test_changed_extraction_and_admission_require_recheck_even_for_same_raw_body(self):
        check = self.check()
        self.manifest["additional_reports"][0]["coverage"][0]["qualifications"] = "New extraction qualification"
        self.assertEqual(self.prepare(check)["checks"][0]["status"], "needs_recheck")
        self.manifest["additional_reports"][0] = {**self.report, "capture_file": "publication.json", "admission": "pending_contract_review"}
        self.assertEqual(self.prepare(check)["checks"][0]["status"], "needs_recheck")

    def test_changed_method_or_contract_does_not_inherit_earlier_agreement(self):
        for field, value in [("version", 2), ("source_contract", "future-source-contract")]:
            check = self.check()
            check["method"][field] = value
            self.assertEqual(self.prepare(check)["summary"]["by_status"], {"needs_recheck": 1})

    def test_invalid_scope_identity_and_selective_claim_links_are_rejected(self):
        for mutate, message in [
            (lambda c: c["scope"].update(verses=["Gal.1.99"]), "exact distinct"),
            (lambda c: c.update(witness_id="ntvmr:10002"), "canonical witness"),
            (lambda c: c["evidence"][2].update(claim_ids=[]), "all scoped claims"),
            (lambda c: c["evidence"][2].update(claim_ids=["content:invented"]), "Stable claim links"),
        ]:
            check = self.check()
            mutate(check)
            with self.assertRaisesRegex(ValueError, message):
                self.prepare(check)
        check = self.check()
        with self.assertRaisesRegex(ValueError, "distinct"):
            self.prepare(check, deepcopy(check))

    def test_hash_tampering_and_path_escape_are_rejected(self):
        check = self.check()
        check["evidence"][2]["body_sha256"] = "0"*64
        with self.assertRaisesRegex(ValueError, "hash"):
            self.prepare(check)
        check = self.check()
        check["evidence"][2]["capture_file"] = "../outside.json"
        with self.assertRaisesRegex(ValueError, "inside"):
            self.prepare(check)

    def test_queue_access_failure_and_follow_up_remain_separate(self):
        check = self.check(outcome="not_yet_checked")
        check.update(checked_on=None, evidence=[], access_attempts=[
            {"source_url": "https://example.org/blocked", "attempted_at": "2026-10-08T12:00:00Z",
             "state": "blocked", "reason": "Fictional HTTP 403"}])
        result = self.prepare(check)
        self.assertEqual(result["summary"]["by_status"], {"not_yet_checked": 1})
        self.assertEqual(result["summary"]["current_outcomes"], {})
        check["follow_up"]["state"] = "resolved"
        with self.assertRaisesRegex(ValueError, "attributable"):
            self.prepare(check)

    def test_pending_reports_are_validated_but_supply_no_ordinary_coverage_or_dates(self):
        self.manifest["additional_reports"][0]["admission"] = "pending_contract_review"
        _, snapshots, coverage, dates, _ = prepare_batch(self.manifest, self.root)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual([c["assertion"] for c in coverage], ["present", "present"])
        self.assertEqual([(d["date_min"], d["date_max"]) for d in dates], [(100, 300)])
        self.assertEqual(self.prepare(self.check())["checks"][0]["status"], "current")
        self.manifest["additional_reports"][0]["coverage"][0]["statement"] = "Not retained"
        with self.assertRaisesRegex(ValueError, "exact reported statement"):
            prepare_batch(self.manifest, self.root)

    def test_scholarly_excerpt_references_preserve_exact_claims_without_repeating_text(self):
        _, _, before_coverage, before_dates, _ = prepare_batch(self.manifest, self.root)
        for field in ("coverage", "dates"):
            for claim in self.manifest["additional_reports"][0][field]:
                text = claim.pop("statement")
                start = self.report["raw_body"].index(text)
                claim["statement_span"] = [start, start+len(text)]
        _, _, after_coverage, after_dates, _ = prepare_batch(self.manifest, self.root)
        self.assertEqual(after_coverage, before_coverage)
        self.assertEqual(after_dates, before_dates)
        for span in ([-1, 2], [0, 999], [True, 4], [3, 3]):
            self.manifest["additional_reports"][0]["coverage"][0]["statement_span"] = span
            with self.assertRaisesRegex(ValueError, "statement span"):
                prepare_batch(self.manifest, self.root)

    def test_referenced_reports_load_without_evidence_overrides_and_build_validates_checks(self):
        self.write("inventory.json", self.inventory)
        collection = {"format_version": 1, "coordinate_inventory": "inventory.json", "books": ["Gal"],
                      "documents": self.manifest["documents"], "additional_reports": [
                          {"capture_file": "publication.json", "admission": "pending_contract_review"}],
                      "source_checks": "checks.json"}
        self.write("checks.json", {"format_version": 1, "checks": [self.check()]})
        self.assertEqual(load_additional_reports(collection, self.root)[0]["raw_body"], self.report["raw_body"])
        prepare_collection(collection, self.root)
        collection["additional_reports"][0]["provider"] = "Uncaptured override"
        with self.assertRaisesRegex(ValueError, "cannot override"):
            load_additional_reports(collection, self.root)
        collection["additional_reports"][0].pop("provider")
        self.write("checks.json", {"format_version": 99, "checks": []})
        with self.assertRaisesRegex(ValueError, "register format"):
            prepare_collection(collection, self.root)


if __name__ == "__main__":
    unittest.main()
