"""Full-corpus display adaptation; no collection or manuscript examination."""

import copy
import json
from pathlib import Path
import subprocess
import unittest

from report_explorer import (build_explorer_data, pack_explorer_data, pack_explorer_data_phase1,
                             expand_explorer_data, PHASE1_FORMAT_VERSION)
from build_collection import DATA, prepare_collection, read_json
from controlled_ntvmr import connect
from source_reports import import_batch, build_report_exports
from contextlib import closing
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class CompatibilityOracleTests(unittest.TestCase):
    """Independent fictional expected data, shared with the Node tests."""

    def assert_json_equal(self, actual, expected):
        # Python object equality alone considers True == 1. Canonical JSON also
        # checks types, missing fields, nulls, and array order, ignoring key order.
        encode = lambda value: json.dumps(value, ensure_ascii=False, sort_keys=True)
        self.assertEqual(encode(actual), encode(expected))

    def test_retained_versions_match_the_independent_normalized_oracle(self):
        for name in ("explorer-normalized", "explorer-empty"):
            expected = read_json(FIXTURES / f"{name}.v1.json")
            for version in (1, 2):
                with self.subTest(fixture=name, version=version):
                    retained = read_json(FIXTURES / f"{name}.v{version}.json")
                    self.assertEqual(retained["format_version"], version)
                    self.assert_json_equal(expand_explorer_data(retained), expected)

    def test_current_packer_preserves_the_oracle_and_is_deterministic(self):
        for name in ("explorer-normalized", "explorer-empty"):
            with self.subTest(fixture=name):
                expected = read_json(FIXTURES / f"{name}.v1.json")
                original = copy.deepcopy(expected)
                for packer in (pack_explorer_data, pack_explorer_data_phase1):
                    packed = packer(expected)
                    self.assert_json_equal(expand_explorer_data(packed), original)
                    self.assertEqual(json.dumps(packed), json.dumps(packer(expected)))
                    self.assert_json_equal(expected, original)

    def test_node_decodes_python_packing_against_the_independent_oracle(self):
        script = """
          const assert = require('node:assert/strict');
          const {readFileSync} = require('node:fs');
          const {expandData} = require('./web/attestation-explorer/explorer.js');
          const expected = JSON.parse(readFileSync(process.argv[1], 'utf8'));
          const packed = JSON.parse(readFileSync(0, 'utf8'));
          assert.deepStrictEqual(expandData(packed), expected);
        """
        for name in ("explorer-normalized", "explorer-empty"):
            with self.subTest(fixture=name):
                path = FIXTURES / f"{name}.v1.json"
                for packer in (pack_explorer_data, pack_explorer_data_phase1):
                    result = subprocess.run(
                        ["node", "-e", script, str(path)], cwd=ROOT,
                        input=json.dumps(packer(read_json(path)), ensure_ascii=False),
                        text=True, encoding="utf-8", capture_output=True, timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_phase1_snapshots_share_templates_but_restore_verse_specific_ids(self):
        for name in ("explorer-normalized", "explorer-empty"):
            expected = read_json(FIXTURES / f"{name}.v1.json")
            packed = read_json(FIXTURES / f"{name}.phase1.json")
            self.assertEqual(packed["format_version"], PHASE1_FORMAT_VERSION)
            self.assert_json_equal(packed, pack_explorer_data_phase1(expected))
            self.assert_json_equal(expand_explorer_data(packed), expected)
        expected = read_json(FIXTURES / "explorer-normalized.v1.json")
        packed = pack_explorer_data_phase1(expected)
        self.assertEqual(packed["observations"]["Gal.1.1"][0], packed["observations"]["Gal.1.2"][0])
        self.assertNotEqual(packed["observations"]["Gal.1.1"][1], packed["observations"]["Gal.1.2"][1])
        template = packed["ranking_templates"][0]
        self.assertEqual(template["combinations"][0]["scenarios"]["optimistic"][0]["coverage_claim_ids"], ["pair"])
        subset_context = packed["observation_contexts"][packed["observations"]["Gal.1.3"][0]]
        subset = packed["ranking_templates"][subset_context["dating_alternatives"]]
        self.assertEqual(subset["combinations"][0]["scenarios"]["optimistic"][0]["coverage_claim_ids"], ["literal", [301]])
        restored = expand_explorer_data(packed)
        event = lambda ref: restored["observations"][ref]["dating_alternatives"]["combinations"][0]["scenarios"]["optimistic"][0]
        self.assertEqual(event("Gal.1.1")["coverage_claim_ids"], [102, 101])
        self.assertEqual(event("Gal.1.2")["coverage_claim_ids"], [202, 201])

    def test_phase1_literal_fallback_preserves_order_types_and_nonunique_pairs(self):
        script = """
          const assert = require('node:assert/strict');
          const {readFileSync} = require('node:fs');
          const {expandData} = require('./web/attestation-explorer/explorer.js');
          const {packed, expected} = JSON.parse(readFileSync(0, 'utf8'));
          assert.deepStrictEqual(expandData(packed), expected);
        """
        for variant in ("reordered", "missing_pair", "duplicate_pair", "boolean", "string"):
            with self.subTest(variant=variant):
                expected = read_json(FIXTURES / "explorer-normalized.v1.json")
                row = expected["observations"]["Gal.1.1"]
                event = row["dating_alternatives"]["combinations"][0]["scenarios"]["optimistic"][0]
                if variant == "reordered":
                    event["coverage_claim_ids"].reverse()
                elif variant == "missing_pair":
                    row["reported_coverage"].pop(0)
                elif variant == "duplicate_pair":
                    row["reported_coverage"].append(copy.deepcopy(row["reported_coverage"][0]))
                else:
                    value = True if variant == "boolean" else "1"
                    expected["claims"]["numeric-id"] = {**expected["claims"]["101"], "claim_id": 1}
                    expected["claims"]["typed-id"] = {**expected["claims"]["101"], "claim_id": value}
                    row["reported_coverage"][0]["claims"] = ["numeric-id"]
                    event["coverage_claim_ids"] = [value]
                packed = pack_explorer_data_phase1(expected)
                context = packed["observation_contexts"][packed["observations"]["Gal.1.1"][0]]
                template = packed["ranking_templates"][context["dating_alternatives"]]
                tag = template["combinations"][0]["scenarios"]["optimistic"][0]["coverage_claim_ids"]
                self.assert_json_equal(tag, ["literal", event["coverage_claim_ids"]])
                self.assert_json_equal(expand_explorer_data(packed), expected)
                result = subprocess.run(["node", "-e", script], cwd=ROOT,
                    input=json.dumps({"packed": packed, "expected": expected}),
                    text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_phase1_preserves_extra_fields_and_does_not_share_mutable_values(self):
        expected = read_json(FIXTURES / "explorer-normalized.v1.json")
        for ref in ("Gal.1.1", "Gal.1.2"):
            row = expected["observations"][ref]
            row["extra"] = {"values": [True, 1, None, "quoted résumé"]}
            row["dating_alternatives"]["extra"] = {"values": [True, 1]}
            row["dating_alternatives"]["combinations"][0]["extra"] = [None]
            row["dating_alternatives"]["combinations"][0]["scenarios"]["optimistic"][0]["extra"] = [True]
        # Missing fields and booleans must not deduplicate with nulls/numbers.
        expected["observations"]["Gal.1.3"].pop("editorial_note")
        expected["observations"]["Gal.1.3"]["extra"] = {"values": [1, 1, None, "quoted résumé"]}
        packed = pack_explorer_data_phase1(expected)
        restored = expand_explorer_data(packed)
        self.assert_json_equal(restored, expected)
        first = restored["observations"]["Gal.1.1"]
        first["extra"]["values"].append("changed")
        first["discovery"]["scopes"][0]["pending_candidate_ids"].append(999)
        first["reported_coverage"][0]["claims"].append("changed")
        alternatives = first["dating_alternatives"]
        alternatives["extra"]["values"].append("changed")
        alternatives["combinations"][0]["assessments"].append("changed")
        alternatives["combinations"][0]["scenarios"]["optimistic"][0]["coverage_claim_ids"].append(999)
        restored["claims"]["101"]["reported"]["osisID"] = "changed"
        restored["metadata"]["filters"]["include_omitted"] = True
        self.assert_json_equal(restored["observations"]["Gal.1.2"], expected["observations"]["Gal.1.2"])
        self.assert_json_equal(expand_explorer_data(packed), expected)

    def test_phase1_interns_complete_json_values_without_coercing_types_or_nulls(self):
        for variant in ("boolean_vs_number", "missing_vs_null", "ranking_extra"):
            expected = read_json(FIXTURES / "explorer-normalized.v1.json")
            first, second = [expected["observations"][ref] for ref in ("Gal.1.1", "Gal.1.2")]
            if variant == "boolean_vs_number":
                first["extra"], second["extra"] = True, 1
            elif variant == "missing_vs_null":
                second.pop("editorial_note")
            else:
                first["dating_alternatives"]["extra"] = True
                second["dating_alternatives"]["extra"] = 1
            packed = pack_explorer_data_phase1(expected)
            with self.subTest(variant=variant):
                a, b = [packed["observations"][ref][0] for ref in ("Gal.1.1", "Gal.1.2")]
                self.assertNotEqual(a, b)
                if variant == "ranking_extra":
                    self.assertNotEqual(packed["observation_contexts"][a]["dating_alternatives"],
                                        packed["observation_contexts"][b]["dating_alternatives"])
                self.assert_json_equal(expand_explorer_data(packed), expected)

    def test_phase1_rejects_missing_tables_and_invalid_indices(self):
        packed = read_json(FIXTURES / "explorer-normalized.phase1.json")
        for name in ("claim_contexts", "coverage_records", "discovery_records", "ranking_templates", "observation_contexts"):
            broken = copy.deepcopy(packed)
            del broken[name]
            with self.subTest(table=name), self.assertRaisesRegex(ValueError, "Missing .* record tables"):
                expand_explorer_data(broken)
            for index in (-1, len(packed[name]), 0.5, "0", True, None):
                broken = copy.deepcopy(packed)
                if name == "claim_contexts":
                    broken["claims"]["101"][0] = index
                elif name == "coverage_records":
                    broken["observations"]["Gal.1.1"][1][1][0] = index
                elif name == "observation_contexts":
                    broken["observations"]["Gal.1.1"][0] = index
                else:
                    field = "discovery" if name == "discovery_records" else "dating_alternatives"
                    broken["observation_contexts"][0][field] = index
                with self.subTest(table=name, index=index), self.assertRaisesRegex(ValueError, "Invalid .* reference"):
                    expand_explorer_data(broken)

    def test_phase1_rejects_bad_tags_dangling_claims_and_ambiguous_pair_recovery(self):
        original = read_json(FIXTURES / "explorer-normalized.phase1.json")
        for tag in ([], ["unknown"], ["pair", []], ["literal"], ["literal", [], []],
                    ["literal", None], ["literal", [999999]], ["literal", ["101"]]):
            broken = copy.deepcopy(original)
            broken["ranking_templates"][0]["combinations"][0]["scenarios"]["optimistic"][0]["coverage_claim_ids"] = tag
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                expand_explorer_data(broken)
        for encoding in ([], ["sparse", []], ["dense"], ["dense", [], None], ["dense", None]):
            broken = copy.deepcopy(original)
            broken["observations"]["Gal.1.1"][1] = encoding
            with self.subTest(encoding=encoding), self.assertRaisesRegex(ValueError, "Invalid coverage encoding"):
                expand_explorer_data(broken)
        for variant in ("missing_pair", "duplicate_pair", "dangling_claim", "numeric_claim_lookup", "missing_claim_id"):
            broken = copy.deepcopy(original)
            vector = broken["observations"]["Gal.1.1"][1][1]
            if variant == "missing_pair":
                vector.pop(0)
            elif variant == "duplicate_pair":
                vector.append(vector[0])
            elif variant == "dangling_claim":
                del broken["claims"]["101"]
            elif variant == "numeric_claim_lookup":
                broken["coverage_records"][0]["claims"][0] = 102
            else:
                del broken["claims"]["101"][1]["claim_id"]
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                expand_explorer_data(broken)


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest, _ = prepare_collection(read_json(DATA / "collection.json"))
        with tempfile.TemporaryDirectory() as tmp, closing(connect(Path(tmp) / "test.sqlite")) as con:
            import_batch(con, manifest, DATA)
            _, cls.graph = build_report_exports(con, "collection")

    def test_full_axis_does_not_expand_collected_coverage(self):
        data = build_explorer_data(self.graph)
        self.assertEqual(len(data["coordinates"]), 7957)
        self.assertEqual(data["coordinates"][0][0], "Matt.1.1")
        self.assertEqual(data["coordinates"][-1][0], "Rev.22.21")
        self.assertEqual(len({ref.split('.')[0] for ref, _ in data["coordinates"]}), 27)
        self.assertEqual(len(data["observations"]), 7941)
        self.assertNotIn("Rom.16.24", data["observations"])
        self.assertEqual(len(data["dates"]), 17)
        self.assertEqual(data["metadata"]["counts"], self.graph["counts"])

    def test_rankings_and_provenance_survive_compaction(self):
        data = build_explorer_data(self.graph)
        for verse in self.graph["verses"]:
            row = data["observations"][verse["osis_ref"]]
            for original, pair in zip(verse["reported_coverage"], row["reported_coverage"]):
                self.assertEqual(pair["state"], original["state"])
                self.assertEqual([data["claims"][key] for key in pair["claims"]], original["claims"])
                self.assertEqual([data["dates"][key] for key in pair["date_assessments"]], original["date_assessments"])
            for original, combo in zip(verse["dating_alternatives"]["combinations"], row["dating_alternatives"]["combinations"]):
                self.assertEqual([data["dates"][key] for key in combo["assessments"]], original["assessments"])
                for side in ("optimistic", "pessimistic"):
                    restored = [{**data["dates"][str(event["assessment_id"])], **event} for event in combo["scenarios"][side]]
                    self.assertEqual(restored, original["scenarios"][side])

    def test_transfer_format_is_lossless_and_reduces_repeated_records(self):
        data = build_explorer_data(self.graph)
        packed = pack_explorer_data(data)
        self.assertEqual(expand_explorer_data(packed), data)
        self.assertEqual(expand_explorer_data(data), data)
        self.assertEqual(pack_explorer_data(expand_explorer_data(packed)), packed)
        size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        self.assertLess(size(packed), size(data) * 0.4)
        self.assertLess(len(packed["claim_contexts"]), len(data["claims"]))
        self.assertLess(len(packed["coverage_records"]),
                        sum(len(row["reported_coverage"]) for row in data["observations"].values()))
        self.assertLess(len(packed["discovery_records"]), len(data["observations"]))
        # Storage sharing does not couple independent observations after loading.
        restored = expand_explorer_data(packed)
        ref, row = next(iter(restored["observations"].items()))
        row["reported_coverage"][0]["claims"].append("synthetic")
        row["discovery"]["state"] = "synthetic"
        self.assertEqual(expand_explorer_data(packed), data)
        self.assertTrue(all(other["discovery"]["state"] != "synthetic"
                            for other_ref, other in restored["observations"].items() if other_ref != ref))

    def test_invalid_transfer_references_fail_instead_of_losing_evidence(self):
        packed = pack_explorer_data(build_explorer_data(self.graph))
        ref = next(iter(packed["observations"]))
        for name in ("coverage_records", "discovery_records", "claim_contexts"):
            for index in (-1, len(packed[name]), "0", True):
                broken = copy.deepcopy(packed)
                if name == "coverage_records":
                    broken["observations"][ref]["reported_coverage"][0] = index
                elif name == "discovery_records":
                    broken["observations"][ref]["discovery"] = index
                else:
                    next(iter(broken["claims"].values()))[0] = index
                with self.assertRaisesRegex(ValueError, "Invalid .* reference"):
                    expand_explorer_data(broken)

    def test_entire_corpus_input_has_no_two_hundred_verse_limit(self):
        graph = copy.deepcopy(self.graph)
        coordinates = build_explorer_data(graph)["coordinates"]
        # Synthetic display fixture, explicitly empty: no invented source report.
        graph["verses"] = [{"osis_ref": ref, "editorial_status": status,
                            "reported_coverage": [], "ranking_state": "no_rankable_dates",
                            "dating_alternatives": {"state": "complete", "combinations": [],
                                                    "combination_count": 0, "max_combinations": 256}}
                           for ref, status in coordinates]
        graph["counts"]["verse_count"] = len(coordinates)
        data = build_explorer_data(graph)
        self.assertEqual(len(data["observations"]), 7957)
        self.assertFalse(data["claims"])
        self.assertFalse(data["dates"])

    def test_source_text_stays_in_json_and_never_changes_the_app(self):
        graph = copy.deepcopy(self.graph)
        text = '</script><script>alert("source")</script>& EXPLORER_DATA'
        graph["collection_scope"] = text
        data = json.loads(json.dumps(build_explorer_data(graph)))
        self.assertEqual(data["metadata"]["collection_scope"], text)
        html = (ROOT / "web/attestation-explorer/index.html").read_text(encoding="utf-8")
        self.assertNotIn(text, html)
        self.assertNotIn('<script id="attestation-data"', html)
        self.assertIn('src="./app.js"', html)
        self.assertIn('href="./explorer.css"', html)

    def test_bad_coordinates_and_inconsistent_identifiers_fail_loudly(self):
        graph = copy.deepcopy(self.graph)
        graph["verses"][1]["osis_ref"] = graph["verses"][0]["osis_ref"]
        with self.assertRaisesRegex(ValueError, "duplicate graph coordinate"):
            build_explorer_data(graph)
        graph["verses"][1]["osis_ref"] = "Other.1.1"
        with self.assertRaisesRegex(ValueError, "Unknown"):
            build_explorer_data(graph)
        graph = copy.deepcopy(self.graph)
        pair = graph["verses"][1]["reported_coverage"][0]
        pair["date_assessments"] = [{**pair["date_assessments"][0], "date_min": 1}]
        with self.assertRaisesRegex(ValueError, "Conflicting assessment_id"):
            build_explorer_data(graph)


if __name__ == "__main__":
    unittest.main()
