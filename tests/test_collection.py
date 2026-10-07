"""One current collection, source attribution, and data-only updates. Entirely offline."""

from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from build_collection import DATA, ROOT, build_data, prepare_collection, read_json, refresh, write_json
from source_reports import capture
from report_explorer import expand_explorer_data, pack_explorer_data


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")):
            cls.data = build_data()
            config = read_json(DATA / "collection.json")
            config["documents"] = [d for d in config["documents"] if d["doc_id"] != 10133]
            records = [r for r in read_json(DATA / "discovery.json") if r["definition"]["book"] not in ("1Tim", "2Tim")]
            cls.before_timothy = build_data(config, discovery_records=records)
            config["documents"] = [d for d in config["documents"] if d["doc_id"] != 10032]
            records = [r for r in records if r["definition"]["book"] != "Titus"]
            cls.before_titus = build_data(config, discovery_records=records)
            config["documents"] = [d for d in config["documents"] if d["doc_id"] not in (10087, 10139)]
            records = [r for r in records if r["definition"]["book"] != "Phlm"]
            cls.before_phlm = build_data(config, discovery_records=records)
            records = [r for r in records if r["definition"]["book"] != "Col"]
            cls.before_col = build_data(config, discovery_records=records)
            config["documents"] = [d for d in config["documents"] if d["doc_id"] != 10016]
            records = [r for r in records if r["definition"]["book"] != "Phil"]
            cls.before_phil = build_data(config, discovery_records=records)
            config["documents"] = [d for d in config["documents"] if d["doc_id"] not in (10061, 10065)]
            records = [r for r in records if r["definition"]["book"] != "1Thess"]
            cls.before_1thess = build_data(config, discovery_records=records)

    def test_current_file_combines_all_collected_books_and_witnesses(self):
        data = self.data
        self.assertEqual(data, expand_explorer_data(read_json(DATA / "attestations.json")))
        self.assertEqual(read_json(DATA / "attestations.json")["format_version"], 3)
        self.assertEqual(len(data["coordinates"]), 7957)
        self.assertEqual(data["metadata"]["counts"]["verse_count"], 7941)
        self.assertEqual(data["metadata"]["counts"]["witness_count"], 25)
        self.assertEqual(data["metadata"]["counts"]["witness_verse_pairs"],
                         {"present": 16783, "unknown": 181742, "absent": 0, "contested": 0})
        self.assertEqual(data["metadata"]["counts"]["by_discovery_state"],
                         {"bounded_search_complete": 1209, "not_searched": 6732})
        self.assertEqual(data["metadata"]["counts"]["graphable_coordinates"], 7928)
        self.assertEqual(data["metadata"]["counts"]["mapping_gaps"], 13)
        self.assertEqual(len({ref.split('.')[0] for ref in data["observations"]}), 27)
        self.assertEqual(data["metadata"]["collection_cost"]["reused_response_count"], 61)
        self.assertEqual(data["metadata"]["collection_cost"]["replay_network_requests"], 0)

    def test_every_presence_and_date_retains_its_actual_source_field(self):
        data = self.data
        raw, metadata, entries, tiers = {}, {}, {}, {}
        for doc in read_json(DATA / "collection.json")["documents"]:
            witness = f"ntvmr:{doc['doc_id']}"
            _, payload, _ = capture(DATA / doc["metadata_fixture"], doc["doc_id"], "metadata")
            metadata[witness] = payload["data"]["manuscript"].get("originYear")
            pages = payload["data"]["manuscript"].get("pages", {}).get("page", [])
            pages = [pages] if isinstance(pages, dict) else pages
            tiers[witness] = {page["pageID"]: page.get("indexTier") for page in pages}
            _, payload, parsed = capture(DATA / doc["coverage_fixture"], doc["doc_id"], "coverage")
            entries[witness] = {ref for ref, page in parsed
                                if type(tiers[witness].get(page)) is not int or tiers[witness][page] < 4}
            raw[witness] = payload["data"]["indexContents"]["indexContent"]
        for ref, row in data["observations"].items():
            for pair in row["reported_coverage"]:
                witness = pair["witness_id"]
                self.assertEqual(pair["state"], "present" if ref in entries[witness] else "unknown")
                for key in pair["claims"]:
                    claim = data["claims"][key]
                    index = int(claim["source_locator"].split("[")[1][:-1])
                    self.assertEqual(claim["reported"], raw[witness][index])
                    self.assertEqual(claim["source_ref"], ref)
                    self.assertEqual(claim["reported_indexing_tier"], tiers[witness].get(claim["page_id"]))
                for key in pair["date_assessments"]:
                    date = data["dates"][key]
                    self.assertEqual(date["reported"], metadata[witness])
            for combo in row["dating_alternatives"]["combinations"]:
                for side, endpoint in (("optimistic", "date_min"), ("pessimistic", "date_max")):
                    events = combo["scenarios"][side]
                    self.assertEqual(len(events), len({event["witness_id"] for event in events}))
                    self.assertEqual([e["event_year"] for e in events], sorted(e["event_year"] for e in events))
                    for event in events:
                        self.assertEqual(event["event_year"], data["dates"][str(event["assessment_id"])][endpoint])
        discovery = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Gal")
        self.assertEqual(discovery["candidate_ids"], [10046, 10051, 10135])
        self.assertFalse(discovery["pending_candidate_ids"])
        self.assertFalse(discovery["corpus_complete"])
        self.assertEqual(discovery["collection_cost"]["increment_attempts_to_date"], 15)
        for doc, low, high in ((10051, 400, 425), (10135, 301, 499)):
            date = next(d for d in data["dates"].values() if d["doc_id"] == doc)
            self.assertEqual((date["date_min"], date["date_max"]), (low, high))
            self.assertTrue(date["citation"].startswith("https://ntvmr.uni-muenster.de/"))
            self.assertNotIn("TLS", date["qualifications"])

    def test_node_restores_production_data_against_the_independent_fresh_build(self):
        script = """
          const assert = require('node:assert/strict');
          const {readFileSync} = require('node:fs');
          const {expandData} = require('./web/attestation-explorer/explorer.js');
          const expected = JSON.parse(readFileSync(process.argv[1], 'utf8'));
          const packed = JSON.parse(readFileSync(process.argv[2], 'utf8'));
          assert.equal(packed.format_version, 3);
          assert.deepStrictEqual(expandData(packed), expected);
        """
        with tempfile.TemporaryDirectory() as tmp:
            expected = Path(tmp) / "normalized.json"
            write_json(expected, self.data, compact=True)
            result = subprocess.run(["node", "-e", script, str(expected), str(DATA / "attestations.json")],
                                    cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_updates_replace_one_data_file_without_changing_app_or_losing_books(self):
        assets = {p: p.read_bytes() for p in (ROOT / "web/attestation-explorer").iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for name in ("sources", "reference"):
                shutil.copytree(DATA / name, directory / name)
            shutil.copyfile(DATA / "discovery.json", directory / "discovery.json")
            config = read_json(DATA / "collection.json")
            smaller = deepcopy(config)
            smaller["documents"] = config["documents"][:3]
            write_json(directory / "collection.json", smaller)
            with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")):
                previous = refresh(directory)
                self.assertEqual(previous["metadata"]["counts"]["witness_verse_pairs"]["present"], 16401)
                write_json(directory / "collection.json", config)
                updated = refresh(directory)
                self.assertEqual(updated, self.data)
                body = (directory / "attestations.json").read_bytes()
                self.assertEqual(read_json(directory / "attestations.json"), pack_explorer_data(updated))
                self.assertEqual(refresh(directory), updated)
                self.assertEqual((directory / "attestations.json").read_bytes(), body)
                self.assertEqual(refresh(directory, check=True), updated)
                self.assertEqual((directory / "attestations.json").read_bytes(), body)
                self.assertEqual(set(p.name for p in directory.iterdir()),
                                 {"collection.json", "discovery.json", "attestations.json", "sources", "reference"})
                config["books"] = ["Gal"]
                write_json(directory / "collection.json", config)
                with self.assertRaisesRegex(ValueError, "out of date"):
                    refresh(directory, check=True)
                self.assertEqual((directory / "attestations.json").read_bytes(), body)
                config["books"] = ["Unknown"]
                write_json(directory / "collection.json", config)
                with self.assertRaisesRegex(ValueError, "distinct book codes"):
                    refresh(directory)
                self.assertEqual((directory / "attestations.json").read_bytes(), body)
        self.assertTrue(all(p.read_bytes() == body for p, body in assets.items()))

    def test_failed_atomic_replacement_preserves_previous_file_and_cleans_temporary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "attestations.json"
            output.write_bytes(b"previous data\n")
            with patch.object(Path, "replace", side_effect=OSError("Synthetic replacement failure")):
                with self.assertRaisesRegex(OSError, "replacement failure"):
                    write_json(output, {"format_version": 3}, compact=True)
            self.assertEqual(output.read_bytes(), b"previous data\n")
            self.assertEqual(list(Path(tmp).iterdir()), [output])

    def test_multiple_discovery_scopes_do_not_erase_each_other_or_expand_contents(self):
        config = read_json(DATA / "collection.json")
        records = read_json(DATA / "discovery.json")
        synthetic = deepcopy(records[0])
        synthetic.update(search_captures=[], run_state="pending", run_error="Synthetic offline case")
        synthetic["definition"].update(scope_id="synthetic-hebrews", book="Heb")
        data = build_data(config, discovery_records=[*records, synthetic])
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertEqual(data["observations"]["Heb.1.1"]["discovery"]["state"], "search_incomplete")
        self.assertEqual(data["observations"]["Rom.1.1"]["discovery"]["state"], "not_searched")
        self.assertEqual(data["claims"], self.data["claims"])
        self.assertEqual(len(data["metadata"]["discovery"]["scopes"]), len(records) + 1)
        synthetic["definition"].update(scope_id="synthetic-other-range", book="Gal", doc_id_min=20000, doc_id_max=29999)
        data = build_data(config, discovery_records=[*records, synthetic])
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "search_incomplete")
        self.assertFalse(data["metadata"]["discovery"]["corpus_complete"])

    def test_reference_mapping_and_supplementary_data_remain_separate_from_filters(self):
        config = read_json(DATA / "collection.json")
        config["include_omitted"] = True
        data = build_data(config)
        self.assertEqual(len(data["observations"]), 7957)
        self.assertEqual(data["observations"]["Rom.16.24"]["editorial_status"], "omitted")
        pairs = data["observations"]["Rom.16.24"]["reported_coverage"]
        self.assertEqual({p["witness_id"] for p in pairs if p["state"] == "present"},
                         {"ntvmr:20001", "ntvmr:20002", "ntvmr:10061"})
        self.assertTrue(all(p["state"] == "unknown" for p in pairs
                            if p["witness_id"] not in ("ntvmr:20001", "ntvmr:20002", "ntvmr:10061")))
        for books in ([], ["Gal", "Gal"], ["Unknown"]):
            with self.assertRaisesRegex(ValueError, "distinct book codes"):
                prepare_collection({**config, "books": books})
        config["documents"][0]["metadata_fixture"] = "../outside.json"
        with self.assertRaisesRegex(ValueError, "central data directory"):
            prepare_collection(config)

    def test_full_book_scope_reuses_reports_without_changing_prior_results(self):
        config = read_json(DATA / "collection.json")
        config["books"] = ["Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "Heb"]
        with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")):
            previous_scope = build_data(config)
        self.assertEqual(previous_scope["metadata"]["counts"]["verse_count"], 2020)
        for ref, row in previous_scope["observations"].items():
            self.assertEqual(row, self.data["observations"][ref])
        for key, claim in previous_scope["claims"].items():
            self.assertEqual(claim, self.data["claims"][key])
        self.assertEqual(previous_scope["dates"], self.data["dates"])
        self.assertEqual(previous_scope["sources"], self.data["sources"])
        self.assertEqual(self.data["observations"]["John.3.16"]["discovery"]["state"], "not_searched")
        self.assertFalse(self.data["metadata"]["discovery"]["corpus_complete"])
        unresolved = [row for row in self.data["observations"].values()
                      if row["ranking_state"] == "no_rankable_dates"]
        self.assertEqual(len(unresolved), 13)
        self.assertTrue(all(pair["state"] == "unknown" and not pair["claims"]
                            for row in unresolved for pair in row["reported_coverage"]))

    def test_hebrews_discovery_reuses_p46_and_adds_canonical_source_reports(self):
        discovery = next(s for s in self.data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Heb")
        candidates = [10012, 10013, 10017, 10046, 10079, 10089, 10114, 10116, 10126, 10130]
        self.assertEqual(discovery["candidate_ids"], candidates)
        self.assertEqual(discovery["collected_candidate_ids"], candidates)
        self.assertEqual(discovery["pending_candidate_ids"], [])
        self.assertEqual(discovery["search_state"], "complete")
        self.assertEqual(discovery["collection_cost"]["request_attempts"], 19)
        self.assertEqual(discovery["collection_cost"]["increment_attempts_to_date"], 25)
        self.assertEqual(self.data["observations"]["Heb.1.1"]["discovery"]["state"], "bounded_search_complete")
        for source in discovery["sources"]:
            self.assertTrue(source["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        for claim in [*self.data["claims"].values(), *self.data["dates"].values()]:
            self.assertTrue(claim["citation"].startswith("https://ntvmr.uni-muenster.de/"))
            self.assertNotIn("TLS", claim["qualifications"])

    def test_ephesians_discovery_preserves_exact_reports_and_independent_scope(self):
        data = self.data
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Eph")
        self.assertEqual(scope["candidate_ids"], [10046, 10049, 10092, 10132])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["collection_cost"]["request_attempts"], 10)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 7)
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        for doc, low, high, expected in ((10049, 275, 299, {"Eph": 29}),
                                         (10092, 200, 399, {"Eph": 6, "2Thess": 4}),
                                         (10132, 200, 399, {"Eph": 6})):
            date = next(d for d in data["dates"].values() if d["doc_id"] == doc)
            self.assertEqual((date["date_min"], date["date_max"]), (low, high))
            present = {}
            for ref, row in data["observations"].items():
                pair = next(p for p in row["reported_coverage"] if p["witness_id"] == f"ntvmr:{doc}")
                if pair["state"] == "present":
                    book = ref.split(".")[0]
                    present[book] = present.get(book, 0) + 1
            self.assertEqual(present, expected)
        for ref in ("Eph.4.16", "Eph.4.30"):
            pair = next(p for p in data["observations"][ref]["reported_coverage"] if p["witness_id"] == "ntvmr:10049")
            self.assertEqual(pair["state"], "present" if ref == "Eph.4.16" else "unknown")
        self.assertEqual(data["observations"]["Eph.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertFalse(data["metadata"]["discovery"]["corpus_complete"])

    def test_2thessalonians_discovery_reuses_p92_and_preserves_sparse_p30_reports(self):
        data = self.data
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "2Thess")
        self.assertEqual(scope["candidate_ids"], [10030, 10092])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["collection_cost"]["request_attempts"], 6)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 3)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 34)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        date = next(d for d in data["dates"].values() if d["doc_id"] == 10030)
        self.assertEqual(date["reported"], {"early": 200, "late": 299, "content": "E II - A III"})
        self.assertEqual((date["date_min"], date["date_max"]), (200, 299))
        present = {}
        for ref, row in data["observations"].items():
            pair = next(p for p in row["reported_coverage"] if p["witness_id"] == "ntvmr:10030")
            if pair["state"] == "present":
                present.setdefault(ref.split(".")[0], []).append(ref)
        self.assertEqual(len(present["1Thess"]), 19)
        self.assertEqual(present["2Thess"], ["2Thess.1.1", "2Thess.1.2"])
        self.assertEqual(set(present), {"1Thess", "2Thess"})
        for ref in ("1Thess.5.10", "1Thess.5.11", "1Thess.5.12", "2Thess.1.3"):
            pair = next(p for p in data["observations"][ref]["reported_coverage"] if p["witness_id"] == "ntvmr:10030")
            self.assertEqual(pair["state"], "present" if ref in ("1Thess.5.10", "1Thess.5.12") else "unknown")
        self.assertEqual(data["observations"]["2Thess.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertEqual(self.before_1thess["observations"]["1Thess.4.12"]["discovery"]["state"], "not_searched")
        self.assertFalse(scope["corpus_complete"])

    def test_2thessalonians_addition_preserves_prior_claims_dates_and_coverage(self):
        after = self.before_1thess
        config = read_json(DATA / "collection.json")
        config["documents"] = [d for d in config["documents"] if d["doc_id"] not in (10016, 10030, 10032, 10061, 10065, 10087, 10133, 10139)]
        records = [r for r in read_json(DATA / "discovery.json") if r["definition"]["book"] not in ("Col", "Phil", "1Thess", "2Thess", "Phlm", "Titus", "1Tim", "2Tim")]
        with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")):
            before = build_data(config, discovery_records=records)
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(after[table][key], value)
        added_present = 0
        for ref, old in before["observations"].items():
            new = after["observations"][ref]
            prior_pairs = [p for p in new["reported_coverage"] if p["witness_id"] != "ntvmr:10030"]
            self.assertEqual(prior_pairs, old["reported_coverage"])
            added = next(p for p in new["reported_coverage"] if p["witness_id"] == "ntvmr:10030")
            added_present += added["state"] == "present"
            if added["state"] == "unknown":
                self.assertEqual(new["dating_alternatives"], old["dating_alternatives"])
                self.assertEqual(new["ranking_state"], old["ranking_state"])
            if not ref.startswith("2Thess."):
                self.assertEqual(new["discovery"], old["discovery"])
        self.assertEqual(added_present, 21)
        self.assertEqual(before["observations"]["2Thess.1.4"]["discovery"]["state"], "not_searched")

    def test_1thessalonians_discovery_reuses_p30_p46_and_preserves_exact_new_reports(self):
        data = self.before_phil
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "1Thess")
        self.assertEqual(scope["candidate_ids"], [10030, 10046, 10061, 10065])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["collection_cost"]["request_attempts"], 5)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 5)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 36)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        for doc, reported, expected in (
                (10061, {"early": 700, "late": 725, "content": "VIII (A)"},
                 {"Rom": 4, "1Cor": 14, "Phil": 10, "Col": 11, "1Thess": 2, "Titus": 11, "Phlm": 4}),
                (10065, {"early": 200, "late": 299, "content": "III"}, {"1Thess": 17})):
            date = next(d for d in data["dates"].values() if d["doc_id"] == doc)
            self.assertEqual(date["reported"], reported)
            self.assertEqual((date["date_min"], date["date_max"]), (reported["early"], reported["late"]))
            present = {}
            for ref, row in data["observations"].items():
                pair = next(p for p in row["reported_coverage"] if p["witness_id"] == f"ntvmr:{doc}")
                if pair["state"] == "present":
                    book = ref.split(".")[0]
                    present[book] = present.get(book, 0) + 1
            self.assertEqual(present, expected)
        for doc, present_refs, unknown_refs in (
                (10061, ("1Thess.1.2", "1Thess.1.3", "1Cor.1.2", "1Cor.1.4"),
                 ("1Thess.1.1", "1Thess.1.4", "1Cor.1.3")),
                (10065, ("1Thess.2.1", "1Thess.2.6"),
                 ("1Thess.2.2", "1Thess.2.3", "1Thess.2.4", "1Thess.2.5"))):
            for ref in (*present_refs, *unknown_refs):
                pair = next(p for p in data["observations"][ref]["reported_coverage"]
                            if p["witness_id"] == f"ntvmr:{doc}")
                self.assertEqual(pair["state"], "present" if ref in present_refs else "unknown")
                if ref in unknown_refs:
                    self.assertEqual(pair["claims"], [])
        self.assertEqual(data["observations"]["1Thess.1.1"]["discovery"]["state"], "bounded_search_complete")
        for book in ("Rom", "1Cor", "Phil", "Col", "Titus", "Phlm"):
            self.assertEqual(data["observations"][f"{book}.1.1"]["discovery"]["state"], "not_searched")
        self.assertFalse(scope["corpus_complete"])

    def test_1thessalonians_addition_preserves_prior_claims_dates_coverage_and_discovery(self):
        before, after = self.before_1thess, self.before_phil
        added_witnesses = {"ntvmr:10061", "ntvmr:10065"}
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(after[table][key], value)
        self.assertEqual(before["coordinates"], after["coordinates"])
        self.assertEqual(before["coordinate_inventory"], after["coordinate_inventory"])
        added_present = 0
        for ref, old in before["observations"].items():
            new = after["observations"][ref]
            prior_pairs = [p for p in new["reported_coverage"] if p["witness_id"] not in added_witnesses]
            self.assertEqual(prior_pairs, old["reported_coverage"])
            added = [p for p in new["reported_coverage"] if p["witness_id"] in added_witnesses]
            added_present += sum(p["state"] == "present" for p in added)
            if all(p["state"] == "unknown" for p in added):
                self.assertEqual(new["dating_alternatives"], old["dating_alternatives"])
                self.assertEqual(new["ranking_state"], old["ranking_state"])
            if not ref.startswith("1Thess."):
                self.assertEqual(new["discovery"], old["discovery"])
        self.assertEqual(added_present, 73)
        self.assertEqual(before["observations"]["1Thess.1.1"]["discovery"]["state"], "not_searched")

    def test_philippians_discovery_reuses_p46_p61_and_copies_p16_fields_exactly(self):
        data = self.before_col
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Phil")
        self.assertEqual(scope["candidate_ids"], [10016, 10046, 10061])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["collection_cost"]["request_attempts"], 6)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 3)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 40)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        self.assertEqual(scope["definition"]["transport_base_url"], "<local proxy>/community/vmr/api")
        self.assertFalse(scope["corpus_complete"])
        date = next(d for d in data["dates"].values() if d["doc_id"] == 10016)
        # Preserve both numeric fields and notation; do not convert or reconcile them.
        self.assertEqual(date["reported"], {"early": 200, "late": 399, "content": "IV"})
        self.assertEqual((date["date_min"], date["date_max"]), (200, 399))
        self.assertTrue(date["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        present = {f"Phil.3.{v}" for v in range(10, 18)} | {f"Phil.4.{v}" for v in range(2, 9)}
        for ref, row in data["observations"].items():
            pair = next(p for p in row["reported_coverage"] if p["witness_id"] == "ntvmr:10016")
            self.assertEqual(pair["state"], "present" if ref in present else "unknown")
            if ref in present:
                self.assertTrue(pair["claims"])
                for key in pair["claims"]:
                    claim = data["claims"][key]
                    self.assertEqual(claim["reported"]["osisID"], ref)
                    self.assertEqual(claim["reported_indexing_tier"], 3)
            else:
                self.assertEqual(pair["claims"], [])
        self.assertEqual(data["observations"]["Phil.3.9"]["discovery"]["state"], "bounded_search_complete")
        self.assertEqual(data["observations"]["Col.1.1"]["discovery"]["state"], "not_searched")

    def test_philippians_addition_preserves_prior_claims_dates_coverage_and_discovery(self):
        before, after = self.before_phil, self.before_col
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(after[table][key], value)
        for table in ("coordinates", "coordinate_inventory"):
            self.assertEqual(after[table], before[table])
        self.assertEqual([d for d in after["documents"] if d["doc_id"] != 10016], before["documents"])
        old_scopes = deepcopy(before["metadata"]["discovery"]["scopes"])
        new_scopes = deepcopy(after["metadata"]["discovery"]["scopes"][:-1])
        self.assertEqual(len(new_scopes), len(old_scopes))
        for old_scope, new_scope in zip(old_scopes, new_scopes):
            self.assertEqual(new_scope.pop("additional_collected_doc_ids"),
                             sorted([*old_scope.pop("additional_collected_doc_ids"), 10016]))
            # Database IDs are temporary; compare the retained source identities.
            for scope in (old_scope, new_scope):
                hashes = {s["source_response_id"]: s["body_sha256"] for s in scope["sources"]}
                for record in [*scope["sources"], *scope["candidates"]]:
                    record["source_response_id"] = hashes[record["source_response_id"]]
            self.assertEqual(new_scope, old_scope)
        added_present = 0
        for ref, old in before["observations"].items():
            new = after["observations"][ref]
            self.assertEqual([p for p in new["reported_coverage"] if p["witness_id"] != "ntvmr:10016"],
                             old["reported_coverage"])
            added = next(p for p in new["reported_coverage"] if p["witness_id"] == "ntvmr:10016")
            added_present += added["state"] == "present"
            if added["state"] == "unknown":
                self.assertEqual(new["dating_alternatives"], old["dating_alternatives"])
                self.assertEqual(new["ranking_state"], old["ranking_state"])
            if not ref.startswith("Phil."):
                self.assertEqual(new["discovery"], old["discovery"])
        self.assertEqual(added_present, 15)
        self.assertEqual(before["observations"]["Phil.3.9"]["discovery"]["state"], "not_searched")

    def test_colossians_discovery_reuses_reports_without_changing_contents_dates_or_rankings(self):
        before, after = self.before_col, self.before_phlm
        scope = next(s for s in after["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Col")
        self.assertEqual(scope["candidate_ids"], [10046, 10061])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["candidate_collection_state"], "complete")
        self.assertFalse(scope["corpus_complete"])
        self.assertEqual(scope["collection_cost"]["request_attempts"], 4)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 1)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 42)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        self.assertEqual(scope["definition"]["transport_base_url"], "<local proxy>/community/vmr/api")
        self.assertEqual(len(scope["sources"]), 1)
        source = scope["sources"][0]
        self.assertEqual(source["params"], {"docID": "10000-19999", "indexContent": "Col",
                                           "detail": "document", "format": "json", "limit": "200"})
        self.assertTrue(source["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        for table in ("claims", "dates", "documents", "coordinates", "coordinate_inventory"):
            self.assertEqual(after[table], before[table])
        self.assertEqual(after["sources"][:-1], before["sources"])
        self.assertEqual(after["metadata"]["discovery"]["scopes"][:-1], before["metadata"]["discovery"]["scopes"])
        self.assertEqual(after["metadata"]["counts"]["witness_verse_pairs"], before["metadata"]["counts"]["witness_verse_pairs"])
        for ref, old in before["observations"].items():
            new = deepcopy(after["observations"][ref])
            if ref.startswith("Col."):
                self.assertEqual(old["discovery"]["state"], "not_searched")
                self.assertEqual(new["discovery"]["state"], "bounded_search_complete")
                new["discovery"] = old["discovery"]
            self.assertEqual(new, old, ref)

    def test_philemon_discovery_reuses_p61_and_preserves_exact_new_reports(self):
        data = self.before_titus
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Phlm")
        self.assertEqual(scope["candidate_ids"], [10061, 10087, 10139])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["candidate_collection_state"], "complete")
        self.assertFalse(scope["corpus_complete"])
        self.assertEqual(scope["collection_cost"]["request_attempts"], 5)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 5)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 42)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        self.assertEqual(scope["definition"]["transport_base_url"], "<local proxy>/community/vmr/api")
        self.assertEqual(scope["sources"][0]["params"],
                         {"docID": "10000-19999", "indexContent": "Phlm", "detail": "document", "format": "json", "limit": "200"})
        self.assertTrue(scope["sources"][0]["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        for doc, reported, verses in (
                (10087, {"early": 200, "late": 299, "content": "III"}, (13, 14, 15, 24, 25)),
                (10139, {"early": 300, "late": 399, "content": "IV"}, (6, 7, 8, 18, 19, 20))):
            date = next(d for d in data["dates"].values() if d["doc_id"] == doc)
            self.assertEqual(date["reported"], reported)
            self.assertEqual((date["date_min"], date["date_max"]), (reported["early"], reported["late"]))
            self.assertTrue(date["citation"].startswith("https://ntvmr.uni-muenster.de/"))
            present = {f"Phlm.1.{v}" for v in verses}
            for ref, row in data["observations"].items():
                pair = next(p for p in row["reported_coverage"] if p["witness_id"] == f"ntvmr:{doc}")
                self.assertEqual(pair["state"], "present" if ref in present else "unknown")
                if ref in present:
                    self.assertTrue(pair["claims"])
                    for key in pair["claims"]:
                        claim = data["claims"][key]
                        self.assertEqual(claim["reported"]["osisID"], ref)
                        self.assertEqual(claim["reported_indexing_tier"], 3)
                else:
                    self.assertEqual(pair["claims"], [])
        self.assertEqual(data["observations"]["Phlm.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertEqual(data["observations"]["Titus.1.1"]["discovery"]["state"], "not_searched")

    def test_philemon_addition_preserves_prior_claims_dates_coverage_and_discovery(self):
        before, after = self.before_phlm, self.before_titus
        added_witnesses = {"ntvmr:10087", "ntvmr:10139"}
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(after[table][key], value)
        for table in ("coordinates", "coordinate_inventory"):
            self.assertEqual(after[table], before[table])
        self.assertEqual([d for d in after["documents"] if d["witness_id"] not in added_witnesses], before["documents"])
        # Temporary database IDs may shift when new document reports precede searches.
        def source_identities(records, data):
            hashes = {s["source_response_id"]: s["body_sha256"] for s in data["sources"]}
            result = deepcopy(records)
            for record in result:
                if "source_response_id" in record:
                    record["source_response_id"] = hashes[record["source_response_id"]]
            return result
        prior_hashes = {s["body_sha256"] for s in before["sources"]}
        self.assertEqual(source_identities([s for s in after["sources"] if s["body_sha256"] in prior_hashes], after),
                         source_identities(before["sources"], before))
        old_scopes = deepcopy(before["metadata"]["discovery"]["scopes"])
        new_scopes = deepcopy(after["metadata"]["discovery"]["scopes"][:-1])
        self.assertEqual(len(new_scopes), len(old_scopes))
        for old, new in zip(old_scopes, new_scopes):
            self.assertEqual(new.pop("additional_collected_doc_ids"),
                             sorted([*old.pop("additional_collected_doc_ids"), 10087, 10139]))
            for scope, data in ((old, before), (new, after)):
                for table in ("sources", "candidates"):
                    scope[table] = source_identities(scope[table], data)
            self.assertEqual(new, old)
        added_present = 0
        for ref, old in before["observations"].items():
            new = after["observations"][ref]
            self.assertEqual([p for p in new["reported_coverage"] if p["witness_id"] not in added_witnesses],
                             old["reported_coverage"])
            added = [p for p in new["reported_coverage"] if p["witness_id"] in added_witnesses]
            added_present += sum(p["state"] == "present" for p in added)
            if all(p["state"] == "unknown" for p in added):
                self.assertEqual(new["dating_alternatives"], old["dating_alternatives"])
                self.assertEqual(new["ranking_state"], old["ranking_state"])
            if not ref.startswith("Phlm."):
                self.assertEqual(new["discovery"], old["discovery"])
        self.assertEqual(added_present, 11)
        self.assertEqual(before["observations"]["Phlm.1.1"]["discovery"]["state"], "not_searched")

    def test_titus_discovery_reuses_p61_and_preserves_exact_p32_reports(self):
        data = self.before_timothy
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "Titus")
        self.assertEqual(scope["candidate_ids"], [10032, 10061])
        self.assertEqual(scope["collected_candidate_ids"], scope["candidate_ids"])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["candidate_collection_state"], "complete")
        self.assertFalse(scope["corpus_complete"])
        self.assertEqual(scope["collection_cost"]["request_attempts"], 3)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 3)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 46)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        self.assertEqual(scope["definition"]["transport_base_url"], "<local proxy>/community/vmr/api")
        self.assertEqual(scope["sources"][0]["params"],
                         {"docID": "10000-19999", "indexContent": "Titus", "detail": "document", "format": "json", "limit": "200"})
        self.assertTrue(scope["sources"][0]["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        date = next(d for d in data["dates"].values() if d["doc_id"] == 10032)
        self.assertEqual(date["reported"], {"early": 200, "late": 225, "content": "III (A)"})
        self.assertEqual((date["date_min"], date["date_max"]), (200, 225))
        present = {f"Titus.1.{v}" for v in range(11, 16)} | {f"Titus.2.{v}" for v in range(3, 9)}
        for ref, row in data["observations"].items():
            pair = next(p for p in row["reported_coverage"] if p["witness_id"] == "ntvmr:10032")
            self.assertEqual(pair["state"], "present" if ref in present else "unknown", ref)
            if ref in present:
                self.assertTrue(pair["claims"])
                for key in pair["claims"]:
                    claim = data["claims"][key]
                    self.assertEqual(claim["reported"]["osisID"], ref)
                    self.assertEqual(claim["reported_indexing_tier"], 3)
            else:
                self.assertEqual(pair["claims"], [])
        self.assertEqual(data["observations"]["Titus.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertEqual(data["observations"]["2Tim.1.1"]["discovery"]["state"], "not_searched")

    def test_titus_addition_preserves_prior_sources_dates_coverage_and_discovery(self):
        before, after = self.before_titus, self.before_timothy
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(after[table][key], value)
        for table in ("coordinates", "coordinate_inventory"):
            self.assertEqual(after[table], before[table])
        self.assertEqual([d for d in after["documents"] if d["doc_id"] != 10032], before["documents"])

        # Compare source hashes: normalization database IDs are disposable.
        def source_identities(records, data):
            hashes = {s["source_response_id"]: s["body_sha256"] for s in data["sources"]}
            result = deepcopy(records)
            for record in result:
                if "source_response_id" in record:
                    record["source_response_id"] = hashes[record["source_response_id"]]
            return result

        prior_hashes = {s["body_sha256"] for s in before["sources"]}
        self.assertEqual(source_identities([s for s in after["sources"] if s["body_sha256"] in prior_hashes], after),
                         source_identities(before["sources"], before))
        old_scopes = deepcopy(before["metadata"]["discovery"]["scopes"])
        new_scopes = deepcopy(after["metadata"]["discovery"]["scopes"][:-1])
        self.assertEqual(len(new_scopes), len(old_scopes))
        for old, new in zip(old_scopes, new_scopes):
            self.assertEqual(new.pop("additional_collected_doc_ids"),
                             sorted([*old.pop("additional_collected_doc_ids"), 10032]))
            for scope, data in ((old, before), (new, after)):
                for table in ("sources", "candidates"):
                    scope[table] = source_identities(scope[table], data)
            self.assertEqual(new, old)
        added_present = 0
        for ref, old in before["observations"].items():
            new = after["observations"][ref]
            self.assertEqual([p for p in new["reported_coverage"] if p["witness_id"] != "ntvmr:10032"],
                             old["reported_coverage"], ref)
            added = next(p for p in new["reported_coverage"] if p["witness_id"] == "ntvmr:10032")
            added_present += added["state"] == "present"
            if added["state"] == "unknown":
                self.assertEqual(new["dating_alternatives"], old["dating_alternatives"], ref)
                self.assertEqual(new["ranking_state"], old["ranking_state"], ref)
            if not ref.startswith("Titus."):
                self.assertEqual(new["discovery"], old["discovery"], ref)
        self.assertEqual(added_present, 11)
        self.assertEqual(before["observations"]["Titus.1.1"]["discovery"]["state"], "not_searched")

    def test_2timothy_empty_index_completes_only_bounded_discovery(self):
        data = self.data
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "2Tim")
        self.assertEqual(scope["candidate_ids"], [])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["candidate_collection_state"], "complete")
        self.assertFalse(scope["corpus_complete"])
        self.assertEqual(scope["collection_cost"]["request_attempts"], 1)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 1)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        source = scope["sources"][0]
        self.assertEqual(source["params"], {"docID": "10000-19999", "indexContent": "2Tim",
                                           "detail": "document", "format": "json", "limit": "200"})
        self.assertTrue(source["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        self.assertFalse(any(c["source_ref"].startswith("2Tim.") and c["doc_id"] == 10133
                             for c in data["claims"].values()))
        rows = [row for ref, row in data["observations"].items() if ref.startswith("2Tim.")]
        self.assertEqual(len(rows), 83)
        for row in rows:
            self.assertEqual(row["discovery"]["state"], "bounded_search_complete")
            self.assertEqual(row["discovery"]["scopes"][0]["book_candidate_count"], 0)
            pair = next(p for p in row["reported_coverage"] if p["witness_id"] == "ntvmr:10133")
            self.assertEqual(pair["state"], "unknown")
            self.assertEqual(pair["claims"], [])

    def test_1timothy_retains_exact_p133_reports_and_counts_overlapping_pages_once(self):
        data = self.data
        scope = next(s for s in data["metadata"]["discovery"]["scopes"] if s["definition"]["book"] == "1Tim")
        self.assertEqual(scope["candidate_ids"], [10133])
        self.assertEqual(scope["collected_candidate_ids"], [10133])
        self.assertEqual(scope["pending_candidate_ids"], [])
        self.assertEqual(scope["search_state"], "complete")
        self.assertEqual(scope["candidate_collection_state"], "complete")
        self.assertFalse(scope["corpus_complete"])
        self.assertEqual(scope["collection_cost"]["request_attempts"], 3)
        self.assertEqual(scope["collection_cost"]["http_responses_recorded"], 3)
        self.assertEqual(scope["collection_cost"]["reused_seed_document_responses"], 48)
        self.assertEqual(scope["collection_cost"]["collection_errors"], [])
        self.assertLessEqual(scope["collection_cost"]["request_attempts"], scope["definition"]["request_budget"])
        self.assertEqual(scope["definition"]["transport_base_url"], "<local proxy>/community/vmr/api")
        self.assertEqual(scope["sources"][0]["params"]["indexContent"], "1Tim")
        date = next(d for d in data["dates"].values() if d["doc_id"] == 10133)
        self.assertEqual(date["reported"], {"early": 200, "late": 299, "content": "III"})
        self.assertEqual((date["date_min"], date["date_max"]), (200, 299))
        present = {f"1Tim.3.{v}" for v in range(13, 17)} | {f"1Tim.4.{v}" for v in range(1, 9)}
        for ref, row in data["observations"].items():
            pair = next(p for p in row["reported_coverage"] if p["witness_id"] == "ntvmr:10133")
            self.assertEqual(pair["state"], "present" if ref in present else "unknown", ref)
            if ref in present:
                self.assertTrue(pair["claims"])
                for key in pair["claims"]:
                    claim = data["claims"][key]
                    self.assertEqual(claim["reported"]["osisID"], ref)
                    self.assertEqual(claim["reported_indexing_tier"], 3)
            else:
                self.assertEqual(pair["claims"], [])
        overlap = data["observations"]["1Tim.4.3"]
        pair = next(p for p in overlap["reported_coverage"] if p["witness_id"] == "ntvmr:10133")
        self.assertEqual({data["claims"][key]["page_id"] for key in pair["claims"]}, {10, 20})
        self.assertEqual(len(pair["claims"]), 2)
        for combo in overlap["dating_alternatives"]["combinations"]:
            for side, year in (("optimistic", 200), ("pessimistic", 299)):
                events = [e for e in combo["scenarios"][side] if e["witness_id"] == "ntvmr:10133"]
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["event_year"], year)

    def test_timothy_additions_preserve_prior_claims_dates_coverage_rankings_and_scopes(self):
        before, after = self.before_timothy, self.data
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(after[table][key], value)
        for table in ("coordinates", "coordinate_inventory"):
            self.assertEqual(after[table], before[table])
        self.assertEqual([d for d in after["documents"] if d["doc_id"] != 10133], before["documents"])

        def source_identities(records, data):
            hashes = {s["source_response_id"]: s["body_sha256"] for s in data["sources"]}
            result = deepcopy(records)
            for record in result:
                if "source_response_id" in record:
                    record["source_response_id"] = hashes[record["source_response_id"]]
            return result

        prior_hashes = {s["body_sha256"] for s in before["sources"]}
        self.assertEqual(source_identities([s for s in after["sources"] if s["body_sha256"] in prior_hashes], after),
                         source_identities(before["sources"], before))
        old_scopes = deepcopy(before["metadata"]["discovery"]["scopes"])
        new_scopes = deepcopy(after["metadata"]["discovery"]["scopes"][:-2])
        self.assertEqual(len(new_scopes), len(old_scopes))
        for old, new in zip(old_scopes, new_scopes):
            self.assertEqual(new.pop("additional_collected_doc_ids"),
                             sorted([*old.pop("additional_collected_doc_ids"), 10133]))
            for scope, data in ((old, before), (new, after)):
                for table in ("sources", "candidates"):
                    scope[table] = source_identities(scope[table], data)
            self.assertEqual(new, old)
        added_present = 0
        for ref, old in before["observations"].items():
            new = after["observations"][ref]
            self.assertEqual([p for p in new["reported_coverage"] if p["witness_id"] != "ntvmr:10133"],
                             old["reported_coverage"], ref)
            added = next(p for p in new["reported_coverage"] if p["witness_id"] == "ntvmr:10133")
            added_present += added["state"] == "present"
            if added["state"] == "unknown":
                self.assertEqual(new["dating_alternatives"], old["dating_alternatives"], ref)
                self.assertEqual(new["ranking_state"], old["ranking_state"], ref)
            if ref.split(".")[0] in ("1Tim", "2Tim"):
                self.assertEqual(old["discovery"]["state"], "not_searched")
                self.assertEqual(new["discovery"]["state"], "bounded_search_complete")
            else:
                self.assertEqual(new["discovery"], old["discovery"], ref)
        self.assertEqual(added_present, 12)
        self.assertEqual(after["metadata"]["counts"]["by_discovery_state"]["bounded_search_complete"] -
                         before["metadata"]["counts"]["by_discovery_state"]["bounded_search_complete"], 196)


if __name__ == "__main__":
    unittest.main()
