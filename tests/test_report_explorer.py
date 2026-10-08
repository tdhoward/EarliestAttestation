"""Full-corpus display adaptation; no collection or manuscript examination."""

import copy
import json
from pathlib import Path
import subprocess
import unittest

from report_explorer import (build_explorer_data, pack_explorer_data, pack_explorer_data_phase1,
                             pack_explorer_data_phase2, pack_explorer_data_phase3, expand_explorer_data,
                             PHASE1_FORMAT_VERSION, PHASE2_FORMAT_VERSION, PHASE3_FORMAT_VERSION)
from build_collection import DATA, prepare_collection, read_json
from controlled_ntvmr import connect
from source_reports import import_batch, build_report_exports
from collection_fixture import pilot_collection, pilot_discovery
from contextlib import closing
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def sparse_fixture():
    """Extend the independent fictional oracle with repeated storage cases.

    These cloned assertions are synthetic codec values, not collected reports.
    Keep this expected-data construction in sync with explorer-fixtures.js.
    """
    expected = read_json(FIXTURES / "explorer-normalized.v1.json")

    def add(ref, row):
        expected["coordinates"].append([ref, "main"])
        expected["observations"][ref] = row

    for verse in range(1, 13):
        add(f"Gal.2.{verse}", copy.deepcopy(expected["observations"]["Gal.1.1"]))
    for verse in range(1, 9):
        row = copy.deepcopy(expected["observations"]["Gal.1.1"])
        row["reported_coverage"][:2] = reversed(row["reported_coverage"][:2])
        add(f"Gal.3.{verse}", row)
    for verse in range(1, 7):
        row = copy.deepcopy(expected["observations"]["Gal.1.4"])
        pairs = copy.deepcopy(expected["observations"]["Gal.1.1"]["reported_coverage"])
        if verse == 1:
            pairs = []
        elif verse == 2:
            pairs = [pairs[0], copy.deepcopy(pairs[0])]
        elif verse == 3:
            pairs = [pairs[0]]
            del pairs[0]["witness_id"]
        elif verse == 4:
            pairs = pairs[:3]
        elif verse == 5:
            for pair in pairs:
                pair["extra_storage_case"] = [True, 1, None]
        else:
            pairs[0]["date_assessments"] = ["2"]
        row["reported_coverage"] = pairs
        add(f"Gal.4.{verse}", row)
    return expected


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
            for version in (1, 2, 3):
                with self.subTest(fixture=name, version=version):
                    retained = read_json(FIXTURES / f"{name}.v{version}.json")
                    self.assertEqual(retained["format_version"], version)
                    self.assert_json_equal(expand_explorer_data(retained), expected)

    def test_production_version3_snapshots_match_fresh_packing_and_independent_oracles(self):
        for name in ("explorer-normalized", "explorer-empty", "explorer-sparse"):
            expected = sparse_fixture() if name == "explorer-sparse" else read_json(FIXTURES / f"{name}.v1.json")
            with self.subTest(fixture=name):
                packed = pack_explorer_data(expected)
                self.assertEqual(packed["format_version"], 3)
                self.assert_json_equal(packed, read_json(FIXTURES / f"{name}.v3.json"))
                self.assert_json_equal(expand_explorer_data(packed), expected)
                candidate = pack_explorer_data_phase3(expected)
                self.assert_json_equal(packed, {**candidate, "format_version": 3})
                if name == "explorer-sparse":
                    size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                    self.assertLess(size(packed), size(expected) * 0.4)

    def test_current_packer_preserves_the_oracle_and_is_deterministic(self):
        for name in ("explorer-normalized", "explorer-empty"):
            with self.subTest(fixture=name):
                expected = read_json(FIXTURES / f"{name}.v1.json")
                original = copy.deepcopy(expected)
                for packer in (pack_explorer_data, pack_explorer_data_phase1, pack_explorer_data_phase2, pack_explorer_data_phase3):
                    packed = packer(expected)
                    self.assert_json_equal(expand_explorer_data(packed), original)
                    self.assertEqual(json.dumps(packed), json.dumps(packer(expected)))
                    self.assert_json_equal(expected, original)

    def test_node_decodes_python_packing_against_the_independent_oracle(self):
        script = """
          const assert = require('node:assert/strict');
          const {readFileSync} = require('node:fs');
          const {expandData, createDataStore} = require('./web/attestation-explorer/explorer.js');
          const expected = JSON.parse(readFileSync(process.argv[1], 'utf8'));
          const packed = JSON.parse(readFileSync(0, 'utf8'));
          assert.deepStrictEqual(expandData(packed), expected);
          const store = createDataStore(packed);
          for (const [ref, row] of Object.entries(expected.observations)) assert.deepStrictEqual(store.observation(ref), row);
          for (const [id, claim] of Object.entries(expected.claims)) assert.deepStrictEqual(store.claim(id), claim);
          for (const [id, date] of Object.entries(expected.dates)) assert.deepStrictEqual(store.date(id), date);
        """
        for name in ("explorer-normalized", "explorer-empty"):
            with self.subTest(fixture=name):
                path = FIXTURES / f"{name}.v1.json"
                for packer in (pack_explorer_data, pack_explorer_data_phase1, pack_explorer_data_phase2, pack_explorer_data_phase3):
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
          const {expandData, createDataStore} = require('./web/attestation-explorer/explorer.js');
          const {packed, expected} = JSON.parse(readFileSync(0, 'utf8'));
          assert.deepStrictEqual(expandData(packed), expected);
          const store = createDataStore(packed);
          for (const [ref, row] of Object.entries(expected.observations)) assert.deepStrictEqual(store.observation(ref), row);
          for (const [id, claim] of Object.entries(expected.claims)) assert.deepStrictEqual(store.claim(id), claim);
          for (const [id, date] of Object.entries(expected.dates)) assert.deepStrictEqual(store.date(id), date);
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


class Phase2CodecTests(unittest.TestCase):
    # Reuse the type-sensitive oracle assertions without rerunning inherited tests.
    assert_json_equal = CompatibilityOracleTests.assert_json_equal

    def test_phase2_snapshots_preserve_compact_and_literal_claims_and_shared_coverage(self):
        for name in ("explorer-normalized", "explorer-empty"):
            expected = read_json(FIXTURES / f"{name}.v1.json")
            packed = read_json(FIXTURES / f"{name}.phase2.json")
            self.assertEqual(packed["format_version"], PHASE2_FORMAT_VERSION)
            self.assert_json_equal(packed, pack_explorer_data_phase2(expected))
            self.assert_json_equal(expand_explorer_data(packed), expected)
        packed = pack_explorer_data_phase2(read_json(FIXTURES / "explorer-normalized.v1.json"))
        self.assertEqual(packed["claims"]["101"][0], "ntvmr_index_v1")
        self.assertEqual(packed["claims"]["102"][0], "literal")
        a, b = [packed["observations"][ref][1][1][0] for ref in ("Gal.1.1", "Gal.1.2")]
        self.assertNotEqual(a, b)
        self.assertEqual(packed["coverage_records"][a][0], packed["coverage_records"][b][0])
        self.assertEqual(packed["coverage_records"][a][1], ["102", "101"])
        self.assertLess(len(packed["coverage_contexts"]), len(packed["coverage_records"]))
        encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        expected = read_json(FIXTURES / "explorer-normalized.v1.json")
        self.assertLess(len(encode(packed)), len(encode(pack_explorer_data_phase1(expected))))

    def test_phase2_eligibility_falls_back_losslessly_in_both_languages(self):
        cases = []
        variants = ("details_extra", "reported_extra", "missing_details", "missing_reported", "reported_literal",
                    "key_leading_zero", "key_plus", "key_negative_zero", "key_mismatch", "key_nonnumeric",
                    "claim_string", "claim_boolean", "claim_null", "claim_unsafe", "claim_float",
                    "ref_mismatch", "ref_type", "page_mismatch", "page_type", "doc_mismatch", "doc_type",
                    "page_string", "page_boolean", "page_null", "page_unsafe", "doc_string", "doc_unsafe",
                    "missing_doc", "locator_leading_zero", "locator_alternate", "locator_negative",
                    "locator_unsafe", "locator_null")
        for variant in variants:
            expected = read_json(FIXTURES / "explorer-normalized.v1.json")
            # An unused claim exercises arbitrary identifiers without changing
            # valid ranking-event references in the independent oracle.
            claim = copy.deepcopy(expected["claims"]["101"])
            claim["claim_id"] = 501
            identifier = "501"
            if variant == "details_extra": claim["extra"] = {"values": [True, 1, None, 'résumé "quoted"']}
            elif variant == "reported_extra": claim["reported"]["extra"] = None
            elif variant == "missing_details": del claim["page_id"]
            elif variant == "missing_reported": del claim["reported"]["pageID"]
            elif variant == "reported_literal": claim["reported"] = 'Fictional publication: résumé "quoted"'
            elif variant.startswith("key_"):
                identifier = {"key_leading_zero": "0501", "key_plus": "+501", "key_negative_zero": "-0",
                              "key_mismatch": "502", "key_nonnumeric": "publication"}[variant]
            elif variant.startswith("claim_"):
                claim["claim_id"] = {"claim_string": "501", "claim_boolean": True, "claim_null": None,
                                     "claim_unsafe": 2**53, "claim_float": 501.0}[variant]
                if variant == "claim_unsafe": identifier = str(2**53)
            elif variant == "ref_mismatch": claim["source_ref"] = "Gal.1.2"
            elif variant == "ref_type": claim["source_ref"], claim["reported"]["osisID"] = True, 1
            elif variant == "page_mismatch": claim["page_id"] = 11
            elif variant == "page_type": claim["page_id"], claim["reported"]["pageID"] = True, 1
            elif variant == "doc_mismatch": claim["doc_id"] = 2
            elif variant == "doc_type": claim["doc_id"], claim["reported"]["docID"] = True, 1
            elif variant.startswith("page_"):
                value = {"page_string": "10", "page_boolean": True, "page_null": None, "page_unsafe": 2**53}[variant]
                claim["page_id"] = claim["reported"]["pageID"] = value
            elif variant.startswith("doc_"):
                claim["doc_id"] = claim["reported"]["docID"] = "1" if variant == "doc_string" else 2**53
            elif variant == "missing_doc": del claim["doc_id"]
            else:
                claim["source_locator"] = {"locator_leading_zero": "data.indexContents.indexContent[00]",
                    "locator_alternate": "data.indexContents.indexContent[0] ",
                    "locator_negative": "data.indexContents.indexContent[-1]",
                    "locator_unsafe": f"data.indexContents.indexContent[{2**53}]", "locator_null": None}[variant]
            expected["claims"][identifier] = claim
            packed = pack_explorer_data_phase2(expected)
            with self.subTest(variant=variant):
                self.assertEqual(packed["claims"][identifier][0], "literal")
                self.assert_json_equal(expand_explorer_data(packed), expected)
            cases.append({"packed": packed, "expected": expected})
        # Safe integer boundaries and structured/null reported contents survive
        # compact storage too; no content is interpreted or reconstructed.
        for identifier, content in (("-9007199254740991", None), ("9007199254740991", [True, 1, 'résumé "quoted"'])):
            expected = read_json(FIXTURES / "explorer-normalized.v1.json")
            claim = copy.deepcopy(expected["claims"]["101"])
            claim.update(claim_id=int(identifier), source_locator="data.indexContents.indexContent[9007199254740991]")
            claim["reported"]["indexContent"] = content
            expected["claims"][identifier] = claim
            packed = pack_explorer_data_phase2(expected)
            self.assertEqual(packed["claims"][identifier][0], "ntvmr_index_v1")
            self.assert_json_equal(expand_explorer_data(packed), expected)
            cases.append({"packed": packed, "expected": expected})
        script = """
          const assert = require('node:assert/strict');
          const {readFileSync} = require('node:fs');
          const {expandData, createDataStore} = require('./web/attestation-explorer/explorer.js');
          for (const {packed, expected} of JSON.parse(readFileSync(0, 'utf8'))) {
            assert.deepStrictEqual(expandData(packed), expected);
            const store = createDataStore(packed);
            for (const [ref, row] of Object.entries(expected.observations)) assert.deepStrictEqual(store.observation(ref), row);
            for (const [id, claim] of Object.entries(expected.claims)) assert.deepStrictEqual(store.claim(id), claim);
            for (const [id, date] of Object.entries(expected.dates)) assert.deepStrictEqual(store.date(id), date);
          }
        """
        result = subprocess.run(["node", "-e", script], cwd=ROOT,
            input=json.dumps(cases, ensure_ascii=False), text=True, encoding="utf-8", capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_phase2_preserves_complete_coverage_values_and_mutation_isolation(self):
        for variant in ("missing_vs_null", "different_unknown_reason", "date_order", "witness_type"):
            expected = read_json(FIXTURES / "explorer-normalized.v1.json")
            first, second = [expected["observations"][ref]["reported_coverage"][4] for ref in ("Gal.1.1", "Gal.1.2")]
            if variant == "missing_vs_null": second["extra"] = None
            elif variant == "different_unknown_reason": second["unknown_reason"] = "unresolved_reference_mapping"
            elif variant == "date_order": first["date_assessments"], second["date_assessments"] = ["1", "2"], ["2", "1"]
            else: first["witness_id"], second["witness_id"] = True, 1
            packed = pack_explorer_data_phase2(expected)
            a, b = [packed["coverage_records"][packed["observations"][ref][1][1][4]][0]
                    for ref in ("Gal.1.1", "Gal.1.2")]
            with self.subTest(variant=variant):
                self.assertNotEqual(a, b)
                self.assert_json_equal(expand_explorer_data(packed), expected)
        expected = read_json(FIXTURES / "explorer-normalized.v1.json")
        first, second = [expected["observations"][ref]["reported_coverage"][0] for ref in ("Gal.1.1", "Gal.1.2")]
        first["extra"], second["extra"] = {"values": [True, None]}, {"values": [1, None]}
        packed = pack_explorer_data_phase2(expected)
        a, b = [packed["coverage_records"][packed["observations"][ref][1][1][0]][0]
                for ref in ("Gal.1.1", "Gal.1.2")]
        self.assertNotEqual(a, b)
        restored = expand_explorer_data(packed)
        self.assert_json_equal(restored, expected)
        pair = restored["observations"]["Gal.1.1"]["reported_coverage"][0]
        self.assertEqual(pair["date_assessments"], ["1", "2"])
        pair["date_assessments"].append("changed")
        pair["claims"].append("changed")
        pair["extra"]["values"].append("changed")
        restored["claims"]["101"]["reported"]["indexContent"] = "changed"
        restored["claims"]["102"]["reported_extra"]["values"].append("changed")
        self.assert_json_equal(restored["observations"]["Gal.1.2"], expected["observations"]["Gal.1.2"])
        self.assert_json_equal(expand_explorer_data(packed), expected)
        # Complete record interning preserves repeated occurrence and array order.
        expected["observations"]["Gal.1.5"]["reported_coverage"] *= 2
        self.assert_json_equal(expand_explorer_data(pack_explorer_data_phase2(expected)), expected)

    def test_phase2_rejects_missing_tables_and_invalid_indices(self):
        packed = read_json(FIXTURES / "explorer-normalized.phase2.json")
        for name in ("claim_contexts", "coverage_contexts", "coverage_records", "discovery_records",
                     "ranking_templates", "observation_contexts"):
            broken = copy.deepcopy(packed)
            del broken[name]
            with self.subTest(table=name), self.assertRaisesRegex(ValueError, "Missing .* record tables"):
                expand_explorer_data(broken)
            for index in (-1, len(packed[name]), 0.5, "0", True, None):
                broken = copy.deepcopy(packed)
                if name == "claim_contexts": broken["claims"]["101"][1] = index
                elif name == "coverage_contexts": broken["coverage_records"][0][0] = index
                elif name == "coverage_records": broken["observations"]["Gal.1.1"][1][1][0] = index
                elif name == "observation_contexts": broken["observations"]["Gal.1.1"][0] = index
                else: broken["observation_contexts"][0]["discovery" if name == "discovery_records" else "dating_alternatives"] = index
                with self.subTest(table=name, index=index), self.assertRaisesRegex(ValueError, "Invalid .* reference"):
                    expand_explorer_data(broken)

    def test_phase2_rejects_bad_claim_tuples_and_context_collisions(self):
        packed = read_json(FIXTURES / "explorer-normalized.phase2.json")
        for value in (None, [], ["literal", 0], ["literal", 0, {}, None], ["unknown", 0, {}],
                      ["literal", 0, []], ["ntvmr_index_v1", 0, []], ["ntvmr_index_v1", 0, ["x", "ref", 1, 0, None]]):
            broken = copy.deepcopy(packed)
            broken["claims"]["101"] = value
            with self.subTest(value=value), self.assertRaises(ValueError): expand_explorer_data(broken)
        for value in (-1, 0.5, True, "0", None, 2**53):
            broken = copy.deepcopy(packed)
            broken["claims"]["101"][2][3] = value
            with self.subTest(locator=value), self.assertRaises(ValueError): expand_explorer_data(broken)
        for identifier in ("0101", "+101", "-0", "9007199254740992", "publication"):
            broken = copy.deepcopy(packed)
            broken["claims"][identifier] = copy.deepcopy(broken["claims"]["101"])
            with self.subTest(identifier=identifier), self.assertRaises(ValueError): expand_explorer_data(broken)
        for value in (0.5, True, "1", None, 2**53):
            for field in ("doc", "page"):
                broken = copy.deepcopy(packed)
                if field == "doc": broken["claim_contexts"][broken["claims"]["101"][1]]["doc_id"] = value
                else: broken["claims"]["101"][2][2] = value
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "Invalid compact index claim"):
                    expand_explorer_data(broken)
        for compact in (True, False):
            broken = copy.deepcopy(packed)
            identifier = "101" if compact else "102"
            context = broken["claim_contexts"][broken["claims"][identifier][1]]
            context["source_ref"] = "Conflicting fictional field"
            with self.subTest(compact=compact), self.assertRaisesRegex(ValueError, "overrides its context"):
                expand_explorer_data(broken)

    def test_phase2_rejects_bad_coverage_records_and_dangling_claims(self):
        packed = read_json(FIXTURES / "explorer-normalized.phase2.json")
        for value in (None, [], [0], [0, [], None], [0, None], [0, [102]], [0, ["missing"]]):
            broken = copy.deepcopy(packed)
            broken["coverage_records"][0] = value
            with self.subTest(value=value), self.assertRaises(ValueError): expand_explorer_data(broken)
        broken = copy.deepcopy(packed)
        broken["coverage_contexts"][broken["coverage_records"][0][0]]["claims"] = []
        with self.assertRaisesRegex(ValueError, "Coverage context contains claims"): expand_explorer_data(broken)
        broken = copy.deepcopy(packed)
        # Even unreferenced coverage records must not hide dangling claims.
        broken["coverage_records"].append([0, ["missing"]])
        with self.assertRaisesRegex(ValueError, "Dangling coverage claim reference"): expand_explorer_data(broken)


class Phase3CodecTests(unittest.TestCase):
    assert_json_equal = CompatibilityOracleTests.assert_json_equal

    def test_phase3_snapshots_match_independent_oracles_and_fresh_packing(self):
        cases = [(name, read_json(FIXTURES / f"{name}.v1.json"))
                 for name in ("explorer-normalized", "explorer-empty")]
        cases.append(("explorer-sparse", sparse_fixture()))
        script = """
          const assert = require('node:assert/strict');
          const {readFileSync} = require('node:fs');
          const {expandData, createDataStore} = require('./web/attestation-explorer/explorer.js');
          const {packed, expected} = JSON.parse(readFileSync(0, 'utf8'));
          assert.deepStrictEqual(expandData(packed), expected);
          const store = createDataStore(packed);
          for (const [ref, row] of Object.entries(expected.observations)) assert.deepStrictEqual(store.observation(ref), row);
          for (const [id, claim] of Object.entries(expected.claims)) assert.deepStrictEqual(store.claim(id), claim);
          for (const [id, date] of Object.entries(expected.dates)) assert.deepStrictEqual(store.date(id), date);
        """
        for name, expected in cases:
            with self.subTest(fixture=name):
                packed = pack_explorer_data_phase3(expected)
                self.assertEqual(packed["format_version"], PHASE3_FORMAT_VERSION)
                self.assert_json_equal(packed, read_json(FIXTURES / f"{name}.phase3.json"))
                self.assert_json_equal(expand_explorer_data(packed), expected)
                self.assertEqual(json.dumps(packed), json.dumps(pack_explorer_data_phase3(expected)))
                result = subprocess.run(["node", "-e", script], cwd=ROOT,
                    input=json.dumps({"packed": packed, "expected": expected}, ensure_ascii=False),
                    text=True, encoding="utf-8", capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_phase3_shares_exact_defaults_and_retains_dense_fallbacks(self):
        expected = sparse_fixture()
        packed = pack_explorer_data_phase3(expected)
        self.assertEqual(len(packed["coverage_defaults"]), 2)
        first = packed["observations"]["Gal.1.1"][1]
        self.assertEqual(first, ["sparse", 0, []])
        self.assertEqual(packed["observations"]["Gal.2.1"][1], first)
        self.assertEqual(packed["observations"]["Gal.3.1"][1], ["sparse", 1, []])
        self.assertEqual(packed["observations"]["Gal.4.6"][1][0], "sparse")
        for ref in ("Gal.1.2", "Gal.1.5", *(f"Gal.4.{i}" for i in range(1, 6))):
            self.assertEqual(packed["observations"][ref][1][0], "dense", ref)
        self.assertEqual(packed["observations"]["Gal.4.1"][1], ["dense", []])
        self.assertNotIn("Gal.1.7", packed["observations"])
        restored = expand_explorer_data(packed)
        self.assert_json_equal(restored, expected)
        self.assertEqual(restored["observations"]["Gal.1.1"]["reported_coverage"][3]["claims"], ["106"])
        self.assertEqual(restored["observations"]["Gal.4.6"]["reported_coverage"][0]["date_assessments"], ["2"])
        # On this stable fixture, sparse storage must save bytes even after all
        # table/tag overhead. Legitimate collection growth has no byte cap.
        size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        self.assertLess(size(packed), size(pack_explorer_data_phase2(expected)))

    def test_phase3_counts_default_overhead_before_selecting_sparse_rows(self):
        expected = read_json(FIXTURES / "explorer-normalized.v1.json")
        row = expected["observations"]["Gal.1.1"]
        expected["observations"] = {"Gal.1.1": row, "Gal.1.2": copy.deepcopy(row)}
        packed = pack_explorer_data_phase3(expected)
        # Sparse would save bytes on each row separately, but not enough to
        # pay for its default vector and field/table syntax.
        self.assertEqual(packed["coverage_defaults"], [])
        self.assertTrue(all(row[1][0] == "dense" for row in packed["observations"].values()))
        self.assert_json_equal(expand_explorer_data(packed), expected)

    def test_phase3_ties_use_first_record_and_witness_grouping_preserves_types(self):
        expected = read_json(FIXTURES / "explorer-normalized.v1.json")
        first, second = [expected["observations"][ref] for ref in ("Gal.1.2", "Gal.1.1")]
        expected["observations"] = {f"Gal.2.{i}": copy.deepcopy(first if i <= 12 else second)
                                    for i in range(1, 25)}
        dense = pack_explorer_data_phase2(expected)
        packed = pack_explorer_data_phase3(expected)
        self.assertEqual(packed["coverage_defaults"][0], dense["observations"]["Gal.2.1"][1][1])
        self.assertEqual(json.dumps(packed), json.dumps(pack_explorer_data_phase3(expected)))
        self.assert_json_equal(expand_explorer_data(packed), expected)
        # True and 1 are distinct JSON identities and must not share a group.
        for i, row in enumerate(expected["observations"].values()):
            row["reported_coverage"][0]["witness_id"] = True if i < 12 else 1
        packed = pack_explorer_data_phase3(expected)
        self.assertEqual(len(packed["coverage_defaults"]), 2)
        self.assertNotEqual(packed["observations"]["Gal.2.1"][1][1],
                            packed["observations"]["Gal.2.13"][1][1])
        self.assert_json_equal(expand_explorer_data(packed), expected)

    def test_phase3_dense_and_sparse_expansion_are_independent_mutable_views(self):
        expected = sparse_fixture()
        packed = pack_explorer_data_phase3(expected)
        dense = copy.deepcopy(packed)
        phase2 = pack_explorer_data_phase2(expected)
        for ref, row in dense["observations"].items():
            row[1] = phase2["observations"][ref][1]
        self.assert_json_equal(expand_explorer_data(dense), expected)
        restored = expand_explorer_data(packed)
        first = restored["observations"]["Gal.1.1"]
        first["reported_coverage"][0]["claims"].append("changed")
        first["reported_coverage"][0]["date_assessments"].append("changed")
        first["reported_coverage"][3]["unknown_reason"] = "changed"
        first["dating_alternatives"]["combinations"][0]["scenarios"]["optimistic"][0]["coverage_claim_ids"].append(999)
        self.assert_json_equal(restored["observations"]["Gal.2.1"], expected["observations"]["Gal.2.1"])
        self.assert_json_equal(expand_explorer_data(packed), expected)

    def test_phase3_rejects_malformed_defaults_and_overrides(self):
        self.check_malformed_sparse(pack_explorer_data_phase3(sparse_fixture()))

    def test_production_version3_rejects_malformed_defaults_and_overrides(self):
        self.check_malformed_sparse(pack_explorer_data(sparse_fixture()))

    def check_malformed_sparse(self, original):
        missing = copy.deepcopy(original)
        del missing["coverage_defaults"]
        with self.assertRaisesRegex(ValueError, "Missing .* record tables"):
            expand_explorer_data(missing)
        for index in (-1, len(original["coverage_defaults"]), 0.5, "0", True, None):
            broken = copy.deepcopy(original)
            broken["observations"]["Gal.1.1"][1][1] = index
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "Invalid coverage_defaults reference"):
                expand_explorer_data(broken)
        for vector in (None, {}, "vector", [-1], [len(original["coverage_records"])], [True], ["0"], [0.5]):
            broken = copy.deepcopy(original)
            broken["coverage_defaults"].append(vector)
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                expand_explorer_data(broken)
        for encoding in ([], ["sparse"], ["sparse", 0], ["sparse", 0, [], None],
                         ["sparse", 0, None], ["other", 0, []], ["dense", None]):
            broken = copy.deepcopy(original)
            broken["observations"]["Gal.1.1"][1] = encoding
            with self.subTest(encoding=encoding), self.assertRaisesRegex(ValueError, "Invalid coverage encoding"):
                expand_explorer_data(broken)
        overrides = [None, [], [0], [0, 0, 0], [True, 0], [-1, 0], [7, 0], [0.5, 0], ["0", 0],
                     [0, -1], [0, len(original["coverage_records"])], [0, True], [0, "0"], [0, 0.5]]
        for override in overrides:
            broken = copy.deepcopy(original)
            broken["observations"]["Gal.1.1"][1][2] = [override]
            with self.subTest(override=override), self.assertRaises(ValueError):
                expand_explorer_data(broken)
        for overrides in ([[0, 0], [0, 0]], [[1, 0], [0, 0]]):
            broken = copy.deepcopy(original)
            broken["observations"]["Gal.1.1"][1][2] = overrides
            with self.assertRaisesRegex(ValueError, "Invalid coverage override position"):
                expand_explorer_data(broken)


class ExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest, _ = prepare_collection(pilot_collection(), discovery_records=pilot_discovery())
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
        self.assertEqual(len(data["dates"]), 25)
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
        self.assertEqual(packed["format_version"], 3)
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
        packed = pack_explorer_data(sparse_fixture())
        ref = next(iter(packed["observations"]))
        for name in ("coverage_records", "discovery_records", "claim_contexts", "coverage_contexts",
                     "observation_contexts", "ranking_templates", "coverage_defaults"):
            for index in (-1, len(packed[name]), 0.5, "0", True, None):
                broken = copy.deepcopy(packed)
                if name == "coverage_records":
                    broken["coverage_defaults"][0][0] = index
                elif name == "coverage_defaults":
                    broken["observations"][ref][1][1] = index
                elif name == "coverage_contexts":
                    broken["coverage_records"][0][0] = index
                elif name == "observation_contexts":
                    broken["observations"][ref][0] = index
                elif name == "discovery_records":
                    broken["observation_contexts"][0]["discovery"] = index
                elif name == "ranking_templates":
                    broken["observation_contexts"][0]["dating_alternatives"] = index
                else:
                    next(iter(broken["claims"].values()))[1] = index
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
