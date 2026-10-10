"""Production browser projection, relational references, and offline compatibility."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pipeline.browser_format import (pack_browser_data, pack_integers, project_browser_data,
                            unpack_browser_data, unpack_integers)
from build_collection import refresh
from pipeline.report_explorer import expand_explorer_data, pack_explorer_data

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class BrowserFormatTests(unittest.TestCase):
    def fixture(self, name="explorer-normalized"):
        return json.loads((FIXTURES / f"{name}.v3.json").read_text(encoding="utf-8"))

    def node(self, packed, expected, original=None):
        script = r"""
          const assert = require('node:assert/strict');
          const {createDataStore, createModel, expandData} = require('./web/attestation-explorer/explorer.js');
          const {packed, expected, original} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
          assert.deepStrictEqual(expandData(packed), expected);
          const store = createDataStore(packed), old = createDataStore(expected);
          assert.equal(store.diagnostics().observationDecodes, 0);
          for (const [ref, row] of Object.entries(expected.observations)) {
            assert.deepStrictEqual(store.summary(ref), old.summary(ref));
            assert.deepStrictEqual(store.chartAlternatives(ref), old.chartAlternatives(ref));
            assert.deepStrictEqual(store.observation(ref), row);
          }
          for (const [id, claim] of Object.entries(expected.claims)) assert.deepStrictEqual(store.claim(id), claim);
          for (const [id, date] of Object.entries(expected.dates)) assert.deepStrictEqual(store.date(id), date);
          const model = createModel(store), previous = createModel(old), legacy = createModel(original || expected);
          for (let i=0;i<expected.coordinates.length;i++) assert.deepStrictEqual(model.discovery(i), legacy.discovery(i));
          for (const scenario of ['optimistic','pessimistic']) for (let i=0;i<expected.coordinates.length;i++)
            assert.deepStrictEqual(model.cell(i,scenario), previous.cell(i,scenario));
          const {mount} = require('./web/attestation-explorer/explorer.js');
          const {explorerDOM} = require('./tests/explorer-dom-fixture.js');
          const snapshots = [];
          for (const input of [packed, original || expected]) {
            const raw = structuredClone(input);
            raw.metadata.counts ||= {verse_count: Object.keys(expected.observations).length,
              witness_count: raw.documents.length, graphable_coordinates: 0, mapping_gaps: 0, witness_verse_pairs: {}};
            const dom = explorerDOM(), mounted = mount(dom.root, raw);
            dom.draw();
            const details = dom.nodes.get('source-details'); details.open = true; details.dispatch('toggle');
            snapshots.push(['witnesses','claims','summary','discovery-summary'].map(name => dom.snapshot(dom.nodes.get(name))));
            mounted.destroy();
          }
          assert.deepStrictEqual(snapshots[0], snapshots[1]);
          for (const [witness, choices] of model.choices) for (const date of choices) {
            model.selection.set(witness,String(date.assessment_id)); previous.selection.set(witness,String(date.assessment_id));
            for (let i=0;i<expected.coordinates.length;i++) assert.deepStrictEqual(model.cell(i,'optimistic'), previous.cell(i,'optimistic'));
          }
          assert.equal(store.hasObservation('Not.1.1'), false);
          assert.equal(store.observation('Not.1.1'), null);
          assert.equal(store.claim('missing'), undefined);
          assert.equal(store.date('missing'), undefined);
          assert(Object.isFrozen(store.claim(Object.keys(expected.claims)[0]) || {} ) || !Object.keys(expected.claims).length);
          // Exercise the ordinary browser globals as well as CommonJS imports.
          const fs = require('node:fs'), vm = require('node:vm'), realm = vm.createContext({});
          const html = fs.readFileSync('web/attestation-explorer/index.html','utf8');
          assert(html.indexOf('./collection-format.js') < html.indexOf('./explorer.js'));
          for (const file of ['collection-format.js','explorer.js'])
            vm.runInContext(fs.readFileSync('web/attestation-explorer/'+file,'utf8'),realm);
          const browser = realm.AttestationExplorer.createDataStore(packed);
          for (const [ref, row] of Object.entries(expected.observations))
            assert.deepStrictEqual(JSON.parse(JSON.stringify(browser.observation(ref))), row);
          packed.observations = {}; packed.dates = {}; packed.claim_contexts = [];
          for (const [ref, row] of Object.entries(expected.observations)) assert.deepStrictEqual(store.observation(ref), row);
        """
        result = subprocess.run(["node", "-e", script], input=json.dumps({"packed": packed, "expected": expected, "original": original}),
                                text=True, capture_output=True, cwd=ROOT, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_python_and_browser_preserve_reports_states_rankings_and_alternatives(self):
        for name in ("explorer-normalized", "explorer-empty", "explorer-sparse"):
            with self.subTest(name=name):
                original = self.fixture(name)
                before = deepcopy(original)
                packed = pack_browser_data(original)
                projected = project_browser_data(original)
                self.assertEqual(expand_explorer_data(unpack_browser_data(packed)), expand_explorer_data(projected))
                expected = expand_explorer_data(projected)
                self.assertEqual(expand_explorer_data(packed), expected)
                self.assertEqual(pack_browser_data(original), packed)
                self.assertEqual(original, before)
                self.node(packed, expected, expand_explorer_data(original))

    def test_rebuild_writes_format5_deterministically_and_checks_same_format(self):
        normalized = expand_explorer_data(self.fixture())
        with tempfile.TemporaryDirectory() as tmp, patch("build_collection.build_data", return_value=normalized):
            directory = Path(tmp)
            refresh(directory)
            output = directory / "attestations.json"
            first = output.read_bytes()
            self.assertEqual(json.loads(first)["format_version"], 5)
            self.assertEqual(json.loads(first), pack_browser_data(pack_explorer_data(normalized)))
            refresh(directory)
            refresh(directory, check=True)
            self.assertEqual(output.read_bytes(), first)

    def test_numeric_columns_preserve_order_and_values_and_save_space(self):
        for values in ([], [3], [5, 1, 8, 2], list(range(1000)), [7]*1000,
                       [0, 1, 4, 7, 10, 12]*20, ["001", "claim-a", 2],
                       [1000000 + i*i for i in range(1000)]):
            self.assertEqual(unpack_integers(pack_integers(values)), values)
        self.assertLess(len(json.dumps(pack_integers(range(10000)))), 50)
        self.assertEqual(unpack_integers({"deltas": {"runs": [1, 1, 4]}}), [1, 3, 6, 10])
        for value in ({"runs": [0, 1]}, {"runs": [0, 1, -1]}, {"runs": [0, 1, True]},
                      {"runs": [2**53-1, 1, 2]}, {"deltas": [2**53-1, 1]},
                      {"deltas": {"deltas": [1, 2]}}, {"deltas": [True]}):
            with self.assertRaises(ValueError): unpack_integers(value)

    def test_browser_rejects_corrupt_or_dangling_relations(self):
        base = pack_browser_data(self.fixture())
        mutations = [
            lambda d: d["index_claims"].update(ids={"runs": [1, 1, -1]}),
            lambda d: d["index_claims"].update(pages=[]),
            lambda d: d["claim_references"][0].__setitem__(0, 999999),
            lambda d: d["coverage_records"].update(claims=[99999999]),
            lambda d: d["claim_contexts"][0].update(provider_id=999999),
            lambda d: d["observations"].update({"999999": [0, 0, []]}),
            lambda d: d["coverage_defaults"].append([99999999]),
            lambda d: d["coverage_contexts"][0].update(date_assessments=["missing"]),
            lambda d: d["ranking_events"].append({"witness_id": "unused", "assessment_id": "missing", "event_year": 100}),
            lambda d: d["ranking_templates"][0]["combinations"][0]["scenarios"].update(optimistic=[999999]),
            lambda d: d["index_claims"].update(ids={"deltas": [2**53-1, 1]}),
            lambda d: d["coordinate_statuses"].update({"999999": "bracketed"}),
            lambda d: d.pop("observation_defaults"),
            lambda d: d["coverage_records"].update(claims={"context_deltas": [2**53-1]*100}),
        ]
        cases = []
        for mutate in mutations:
            value = deepcopy(base); mutate(value); cases.append(value)
        script = """
          const assert = require('node:assert/strict');
          const {createDataStore} = require('./web/attestation-explorer/explorer.js');
          for (const value of JSON.parse(require('fs').readFileSync(0,'utf8'))) assert.throws(()=>createDataStore(value));
        """
        result = subprocess.run(["node", "-e", script], input=json.dumps(cases), text=True,
                                capture_output=True, cwd=ROOT, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_projection_removes_only_app_unused_fields(self):
        data = self.fixture()
        data["documents"] = [{"witness_id": "w", "label": "Example", "identity": {"provider": "Provider"}}]
        data["sources"] = [{"source_response_id": 1, "canonical_url": "https://example.org", "url": "local proxy",
                            "body_sha256": "hash", "retrieved_at": "2026-10-07", "params": {}, "capture_file": "raw.json"}]
        projected = project_browser_data(data)
        self.assertEqual(projected["documents"], [{"witness_id": "w", "label": "Example"}])
        self.assertNotIn("url", projected["sources"][0])
        self.assertNotIn("capture_file", projected["sources"][0])
        for field in ("claims", "dates", "observations", "coverage_contexts"):
            self.assertEqual(projected[field], data[field])

    def test_contextual_claim_deltas_preserve_order_empty_pairs_and_repeated_contexts(self):
        original = self.fixture()
        packed = pack_browser_data(original)
        coverage = packed["coverage_records"]
        contexts, lengths = (unpack_integers(coverage[k]) for k in ("contexts", "lengths"))
        values = [int(v) for record in original["coverage_records"] for v in record[1]]
        previous, deltas, offset = {}, [], 0
        for context, length in zip(contexts, lengths):
            for value in values[offset:offset + length]:
                deltas.append(value - previous.get(context, 0))
                previous[context] = value
            offset += length
        coverage["claims"] = {"context_deltas": pack_integers(deltas)}
        expected = expand_explorer_data(project_browser_data(original))
        self.assertEqual(expand_explorer_data(packed), expected)
        self.node(packed, expected, expand_explorer_data(original))

    def test_defaults_and_projection_keep_exceptions_and_real_date_choices(self):
        data = self.fixture()
        packed = pack_browser_data(data)
        self.assertTrue(all(isinstance(ref, str) for ref in packed["coordinates"]))
        self.assertEqual(packed["coordinate_statuses"], {"5": "bracketed"})
        projected = project_browser_data(data)
        self.assertEqual(projected["dates"], data["dates"])
        self.assertEqual(projected["ranking_templates"][0]["combinations"][0]["assessments"], ["1"])
        self.assertEqual(projected["ranking_templates"][0]["combinations"][1]["assessments"], ["2"])
        self.assertNotIn("discovery", projected["metadata"])
        self.assertTrue(all("scopes" not in r for r in projected["discovery_records"]))

    def test_discovery_counts_union_overlapping_scopes_and_preserve_date_limits(self):
        data = self.fixture()
        scope = {"definition": {"books": ["Gal"], "scope_type": "catalogue_range", "earliest_date_before": 1000},
                 "candidate_ids": [1, 2, 3], "eligible_candidate_ids": [1, 2], "pending_candidate_ids": [2],
                 "date_excluded_candidate_ids": [3], "search_state": "complete", "candidate_collection_state": "incomplete"}
        data["metadata"]["discovery"] = {"scopes": [scope, deepcopy(scope)]}
        summary = project_browser_data(data)["metadata"]["discovery_summary"]["Gal"]
        self.assertEqual(summary, {"state": "candidate_collection_incomplete", "search_state": "complete",
            "candidate_count": 3, "eligible_count": 2, "pending_count": 1, "excluded_count": 1,
            "cutoffs": [1000], "catalogue": True})
        scope["search_state"] = "blocked"
        self.assertEqual(project_browser_data(data)["metadata"]["discovery_summary"]["Gal"]["state"], "search_incomplete")

    def test_varints_and_typed_columns_preserve_boundaries_and_reject_damage(self):
        import base64
        import random
        rng = random.Random(41)
        values = [rng.randrange(-2**31, 2**31) for _ in range(300)]
        packed = pack_integers(values)
        self.assertIn("varints", packed)
        self.assertEqual(unpack_integers(packed), values)
        invalid = [{"varints": [1, "AA=="]}, {"varints": [1, "AB=="]}]
        # The first is valid zero; the others are bad padding, truncation,
        # overlong, out-of-range, or mismatched integer counts.
        valid_zero = invalid.pop(0)
        for body in (b"\x80", b"\x80\x00", b"\xff\xff\xff\xff\x10", b"\x00\x00"):
            invalid.append({"varints": [1, base64.b64encode(body).decode()]})
        invalid.extend([{"varints": [-1, ""]}, {"varints": [1, "!"]}, {"varints": [True, "AA=="]}])
        for value in invalid:
            with self.assertRaises(ValueError): unpack_integers(value)
        script = r"""
          const assert=require('node:assert/strict'), {column}=require('./web/attestation-explorer/collection-format.js');
          const {packed, values, invalid, valid_zero}=JSON.parse(require('fs').readFileSync(0,'utf8'));
          assert.deepEqual(Array.from(column(packed)),values);
          assert.deepEqual(Array.from(column(valid_zero)),[0]);
          for(const value of invalid)assert.throws(()=>column(value));
          for(const [value, Type, expected] of [
            [[0,255],Uint8Array,[0,255]], [[256,65535],Uint16Array,[256,65535]],
            [[65536,4294967295],Uint32Array,[65536,4294967295]],
            [[4294967296],Float64Array,[4294967296]], [[-2147483648],Int32Array,[-2147483648]],
            [{deltas:[255,1]},Uint16Array,[255,256]], [{deltas:[4294967295,1]},Float64Array,[4294967295,4294967296]]]) {
            const actual=column(value); assert(actual instanceof Type); assert.deepEqual(Array.from(actual),expected);
          }
        """
        result = subprocess.run(["node", "-e", script], input=json.dumps({
            "packed": packed, "values": values, "invalid": invalid, "valid_zero": valid_zero}),
            text=True, capture_output=True, cwd=ROOT, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
