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

    def test_current_file_combines_all_collected_books_and_witnesses(self):
        data = self.data
        self.assertEqual(data, expand_explorer_data(read_json(DATA / "attestations.json")))
        self.assertEqual(read_json(DATA / "attestations.json")["format_version"], 3)
        self.assertEqual(len(data["coordinates"]), 7957)
        self.assertEqual(data["metadata"]["counts"]["verse_count"], 7941)
        self.assertEqual(data["metadata"]["counts"]["witness_count"], 18)
        self.assertEqual(data["metadata"]["counts"]["witness_verse_pairs"],
                         {"present": 16661, "unknown": 126277, "absent": 0, "contested": 0})
        self.assertEqual(data["metadata"]["counts"]["by_discovery_state"],
                         {"bounded_search_complete": 654, "not_searched": 7287})
        self.assertEqual(data["metadata"]["counts"]["graphable_coordinates"], 7928)
        self.assertEqual(data["metadata"]["counts"]["mapping_gaps"], 13)
        self.assertEqual(len({ref.split('.')[0] for ref in data["observations"]}), 27)
        self.assertEqual(data["metadata"]["collection_cost"]["reused_response_count"], 40)
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
                         {"ntvmr:20001", "ntvmr:20002"})
        self.assertTrue(all(p["state"] == "unknown" for p in pairs
                            if p["witness_id"] not in ("ntvmr:20001", "ntvmr:20002")))
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
        self.assertEqual(data["observations"]["1Thess.4.12"]["discovery"]["state"], "not_searched")
        self.assertFalse(scope["corpus_complete"])

    def test_2thessalonians_addition_preserves_prior_claims_dates_and_coverage(self):
        config = read_json(DATA / "collection.json")
        config["documents"] = [d for d in config["documents"] if d["doc_id"] != 10030]
        records = [r for r in read_json(DATA / "discovery.json") if r["definition"]["book"] != "2Thess"]
        with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")):
            before = build_data(config, discovery_records=records)
        for table in ("claims", "dates"):
            for key, value in before[table].items():
                self.assertEqual(self.data[table][key], value)
        added_present = 0
        for ref, old in before["observations"].items():
            new = self.data["observations"][ref]
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


if __name__ == "__main__":
    unittest.main()
