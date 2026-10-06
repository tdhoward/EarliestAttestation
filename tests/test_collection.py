"""One current collection, source attribution, and data-only updates. Entirely offline."""

from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from build_collection import DATA, ROOT, build_data, prepare_collection, read_json, refresh, write_json
from source_reports import capture


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("controlled_ntvmr.transport", side_effect=AssertionError("No network")):
            cls.data = build_data()

    def test_current_file_combines_all_collected_books_and_witnesses(self):
        data = self.data
        self.assertEqual(data, read_json(DATA / "attestations.json"))
        self.assertEqual(len(data["coordinates"]), 7957)
        self.assertEqual(data["metadata"]["counts"]["verse_count"], 2020)
        self.assertEqual(data["metadata"]["counts"]["witness_count"], 5)
        self.assertEqual(data["metadata"]["counts"]["witness_verse_pairs"],
                         {"present": 5617, "unknown": 4483, "absent": 0, "contested": 0})
        self.assertEqual(data["metadata"]["counts"]["by_discovery_state"],
                         {"bounded_search_complete": 149, "not_searched": 1871})
        self.assertEqual(data["metadata"]["counts"]["mapping_gaps"], 0)
        self.assertNotIn("John.3.16", data["observations"])
        self.assertEqual(data["metadata"]["collection_cost"]["reused_response_count"], 11)
        self.assertEqual(data["metadata"]["collection_cost"]["replay_network_requests"], 0)

    def test_every_presence_and_date_retains_its_actual_source_field(self):
        data = self.data
        raw, metadata, entries = {}, {}, {}
        for doc in read_json(DATA / "collection.json")["documents"]:
            witness = f"ntvmr:{doc['doc_id']}"
            _, payload, parsed = capture(DATA / doc["coverage_fixture"], doc["doc_id"], "coverage")
            entries[witness] = {ref for ref, _ in parsed}
            raw[witness] = payload["data"]["indexContents"]["indexContent"]
            _, payload, _ = capture(DATA / doc["metadata_fixture"], doc["doc_id"], "metadata")
            metadata[witness] = payload["data"]["manuscript"]["originYear"]
        for ref, row in data["observations"].items():
            for pair in row["reported_coverage"]:
                witness = pair["witness_id"]
                self.assertEqual(pair["state"], "present" if ref in entries[witness] else "unknown")
                for key in pair["claims"]:
                    claim = data["claims"][key]
                    index = int(claim["source_locator"].split("[")[1][:-1])
                    self.assertEqual(claim["reported"], raw[witness][index])
                    self.assertEqual(claim["source_ref"], ref)
                    self.assertEqual(claim["reported_indexing_tier"], 3)
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
        discovery = data["metadata"]["discovery"]
        self.assertEqual(discovery["candidate_ids"], [10046, 10051, 10135])
        self.assertFalse(discovery["pending_candidate_ids"])
        self.assertFalse(discovery["corpus_complete"])
        self.assertEqual(discovery["collection_cost"]["increment_attempts_to_date"], 15)
        for doc, low, high in ((10051, 400, 425), (10135, 301, 499)):
            date = next(d for d in data["dates"].values() if d["doc_id"] == doc)
            self.assertEqual((date["date_min"], date["date_max"]), (low, high))
            self.assertIn("HTTP relay", date["qualifications"])

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
                self.assertEqual(previous["metadata"]["counts"]["witness_verse_pairs"]["present"], 5586)
                write_json(directory / "collection.json", config)
                updated = refresh(directory)
                self.assertEqual(updated, self.data)
                body = (directory / "attestations.json").read_bytes()
                self.assertEqual(refresh(directory, check=True), updated)
                self.assertEqual((directory / "attestations.json").read_bytes(), body)
                self.assertEqual(set(p.name for p in directory.iterdir()),
                                 {"collection.json", "discovery.json", "attestations.json", "sources", "reference"})
                config["books"] = ["Gal"]
                write_json(directory / "collection.json", config)
                with self.assertRaisesRegex(ValueError, "out of date"):
                    refresh(directory, check=True)
                self.assertEqual((directory / "attestations.json").read_bytes(), body)
        self.assertTrue(all(p.read_bytes() == body for p, body in assets.items()))

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
        self.assertEqual(len(data["metadata"]["discovery"]["scopes"]), 2)
        synthetic["definition"].update(scope_id="synthetic-other-range", book="Gal", doc_id_min=20000, doc_id_max=29999)
        data = build_data(config, discovery_records=[*records, synthetic])
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "search_incomplete")
        self.assertFalse(data["metadata"]["discovery"]["corpus_complete"])

    def test_reference_mapping_and_supplementary_data_remain_separate_from_filters(self):
        config = read_json(DATA / "collection.json")
        config["include_omitted"] = True
        data = build_data(config)
        self.assertEqual(len(data["observations"]), 2021)
        self.assertEqual(data["observations"]["Rom.16.24"]["editorial_status"], "omitted")
        self.assertEqual([p["state"] for p in data["observations"]["Rom.16.24"]["reported_coverage"]],
                         ["unknown", "unknown", "unknown", "present", "present"])
        for books in ([], ["Gal", "Gal"], ["Unknown"]):
            with self.assertRaisesRegex(ValueError, "distinct book codes"):
                prepare_collection({**config, "books": books})
        config["documents"][0]["metadata_fixture"] = "../outside.json"
        with self.assertRaisesRegex(ValueError, "central data directory"):
            prepare_collection(config)


if __name__ == "__main__":
    unittest.main()
