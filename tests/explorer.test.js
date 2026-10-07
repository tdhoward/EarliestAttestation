/* Run with node --test tests/explorer.test.js. Entirely offline. */
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const {join} = require("node:path");
const {expandData, createDataStore, createModel, hitIndex, segments, mount} = require("../web/attestation-explorer/explorer.js");
const {transferFixture, sparseFixture} = require("./explorer-fixtures.js");
const {explorerDOM} = require("./explorer-dom-fixture.js");
const packedCurrent = JSON.parse(readFileSync(join(__dirname, "../data/attestations.json"), "utf8"));
const current = expandData(packedCurrent);
// A smaller synthetic view keeps the three-witness model cases independent of collection growth.
const data = structuredClone(current);
const retained = new Set(["ntvmr:10046", "ntvmr:20001", "ntvmr:20002"]);
const retainedBooks = new Set(["Rom", "1Cor", "2Cor", "Gal", "Eph", "Phil", "Col", "1Thess", "Heb"]);
data.observations = Object.fromEntries(Object.entries(data.observations).filter(([ref]) => retainedBooks.has(ref.split(".")[0])));
data.documents = data.documents.filter(d => retained.has(d.witness_id));
data.dates = Object.fromEntries(Object.entries(data.dates).filter(([,d]) => retained.has(d.witness_id)));
const fixtureDateIds = new Map(Object.keys(data.dates).map((id, i) => [id, String(i + 1)]));
data.dates = Object.fromEntries(Object.entries(data.dates).map(([id, date]) =>
  [fixtureDateIds.get(id), {...date, assessment_id: Number(fixtureDateIds.get(id))}]));
for (const row of Object.values(data.observations)) {
  row.reported_coverage = row.reported_coverage.filter(p => retained.has(p.witness_id));
  for (const combo of row.dating_alternatives.combinations) {
    combo.assessments = combo.assessments.filter(id => fixtureDateIds.has(String(id))).map(id => fixtureDateIds.get(String(id)));
    for (const side of ["optimistic", "pessimistic"]) {
      combo.scenarios[side] = combo.scenarios[side].filter(e => retained.has(e.witness_id)).map((e, i) =>
        ({...e, assessment_id: Number(fixtureDateIds.get(String(e.assessment_id))), rank: i + 1}));
    }
  }
}
const copy = () => structuredClone(data);

test("retained versions and candidate codecs decode exactly to the independent fictional oracle", () => {
  for (const name of ["explorer-normalized", "explorer-empty"]) {
    const {normalized, packed, version3, phase1, phase2, phase3} = transferFixture(name);
    assert.deepEqual(expandData(normalized), normalized);
    assert.deepEqual(expandData(packed), normalized);
    assert.equal(version3.format_version, 3);
    assert.deepEqual(expandData(version3), normalized);
    assert.deepEqual(expandData(phase1), normalized);
    assert.deepEqual(expandData(phase2), normalized);
    assert.deepEqual(expandData(phase3), normalized);
  }
});

test("Phase 1 restores shared templates as independent observations and copies its packed input", () => {
  const {normalized, phase1} = transferFixture();
  assert.equal(phase1.observations["Gal.1.1"][0], phase1.observations["Gal.1.2"][0]);
  assert.deepEqual(phase1.ranking_templates[0].combinations[0].scenarios.optimistic[0].coverage_claim_ids, ["pair"]);
  const restored = expandData(phase1), first = restored.observations["Gal.1.1"];
  first.dating_alternatives.combinations[0].assessments.push("changed");
  first.dating_alternatives.combinations[0].scenarios.optimistic[0].coverage_claim_ids.push(999);
  first.dating_alternatives.combinations[0].scenarios.pessimistic[0].rank = 999;
  first.discovery.scopes[0].pending_candidate_ids.push(999);
  first.reported_coverage[0].claims.push("changed");
  restored.claims["101"].reported.osisID = "changed";
  restored.metadata.filters.include_omitted = true;
  restored.coordinates[0][0] = "changed";
  assert.deepEqual(restored.observations["Gal.1.2"], normalized.observations["Gal.1.2"]);
  assert.deepEqual(expandData(phase1), normalized);
});

test("Phase 1 rejects missing tables and negative, noninteger, boolean and dangling indices", () => {
  for (const name of ["claim_contexts", "coverage_records", "discovery_records", "ranking_templates", "observation_contexts"]) {
    const {phase1} = transferFixture();
    const missing = structuredClone(phase1);
    delete missing[name];
    assert.throws(() => expandData(missing), /Missing collection record tables/);
    assert.throws(() => createDataStore(missing), /Missing collection record tables/);
    for (const index of [-1, phase1[name].length, 0.5, "0", true, null]) {
      const broken = structuredClone(phase1);
      if (name === "claim_contexts") broken.claims["101"][0] = index;
      else if (name === "coverage_records") broken.observations["Gal.1.1"][1][1][0] = index;
      else if (name === "observation_contexts") broken.observations["Gal.1.1"][0] = index;
      else broken.observation_contexts[0][name === "discovery_records" ? "discovery" : "dating_alternatives"] = index;
      assert.throws(() => expandData(broken), /Invalid .* reference/);
      assert.throws(() => createDataStore(broken), /Invalid .* reference/);
    }
  }
});

test("Phase 1 rejects bad tuple tags, dangling claims and ambiguous pair recovery", () => {
  const {phase1} = transferFixture();
  for (const tag of [[], ["unknown"], ["pair", []], ["literal"], ["literal", [], null],
    ["literal", null], ["literal", [999999]], ["literal", ["101"]]]) {
    const broken = structuredClone(phase1);
    broken.ranking_templates[0].combinations[0].scenarios.optimistic[0].coverage_claim_ids = tag;
    assert.throws(() => expandData(broken), /Invalid event claim|Dangling event claim/);
    assert.throws(() => createDataStore(broken), /Invalid event claim|Dangling event claim/);
  }
  for (const encoding of [[], ["sparse", []], ["dense"], ["dense", [], null], ["dense", null]]) {
    const broken = structuredClone(phase1);
    broken.observations["Gal.1.1"][1] = encoding;
    assert.throws(() => expandData(broken), /Invalid coverage encoding/);
    assert.throws(() => createDataStore(broken), /Invalid coverage encoding/);
  }
  for (const row of [null, [], [0], [0, ["dense", []], null]]) {
    const broken = structuredClone(phase1);
    broken.observations["Gal.1.1"] = row;
    assert.throws(() => expandData(broken), /Invalid packed observation/);
    assert.throws(() => createDataStore(broken), /Invalid packed observation/);
  }
  for (const variant of ["missing_pair", "duplicate_pair", "dangling_claim", "numeric_claim_lookup", "missing_claim_id", "conflict"]) {
    const broken = structuredClone(phase1), vector = broken.observations["Gal.1.1"][1][1];
    if (variant === "missing_pair") vector.shift();
    else if (variant === "duplicate_pair") vector.push(vector[0]);
    else if (variant === "dangling_claim") delete broken.claims["101"];
    else if (variant === "numeric_claim_lookup") broken.coverage_records[0].claims[0] = 102;
    else if (variant === "missing_claim_id") delete broken.claims["101"][1].claim_id;
    else broken.claims["101"][1].citation = "Conflicting fictional citation";
    assert.throws(() => expandData(broken), /pair reference|claim reference|claim identifier|overrides its context/);
    assert.throws(() => createDataStore(broken), /pair reference|claim reference|claim identifier|overrides its context/);
  }
});

test("Phase 2 restores compact/literal claims and complete coverage as independent copies", () => {
  const {normalized, phase2} = transferFixture();
  assert.equal(phase2.claims["101"][0], "ntvmr_index_v1");
  assert.equal(phase2.claims["102"][0], "literal");
  const [a, b] = ["Gal.1.1", "Gal.1.2"].map(ref => phase2.observations[ref][1][1][0]);
  assert.equal(phase2.coverage_records[a][0], phase2.coverage_records[b][0]);
  assert.deepEqual(phase2.coverage_records[a][1], ["102", "101"]);
  const restored = expandData(phase2), first = restored.observations["Gal.1.1"];
  assert.deepEqual(restored, normalized);
  assert.deepEqual(first.reported_coverage[0].date_assessments, ["1", "2"]);
  first.reported_coverage[0].date_assessments.push("changed");
  first.reported_coverage[0].claims.push("changed");
  first.dating_alternatives.combinations[0].scenarios.optimistic[0].coverage_claim_ids.push(999);
  restored.claims["101"].reported.indexContent = "changed";
  restored.claims["102"].reported_extra.values.push("changed");
  restored.claims["101"].qualifications = "changed";
  assert.deepEqual(restored.observations["Gal.1.2"], normalized.observations["Gal.1.2"]);
  assert.deepEqual(restored.claims["201"], normalized.claims["201"]);
  assert.deepEqual(expandData(phase2), normalized);
});

test("Phase 2 rejects missing tables, invalid indices, and conflicting context fields", () => {
  const {phase2} = transferFixture();
  for (const name of ["claim_contexts", "coverage_contexts", "coverage_records", "discovery_records", "ranking_templates", "observation_contexts"]) {
    const missing = structuredClone(phase2);
    delete missing[name];
    assert.throws(() => expandData(missing), /Missing collection record tables/);
    assert.throws(() => createDataStore(missing), /Missing collection record tables/);
    for (const index of [-1, phase2[name].length, 0.5, "0", true, null]) {
      const broken = structuredClone(phase2);
      if (name === "claim_contexts") broken.claims["101"][1] = index;
      else if (name === "coverage_contexts") broken.coverage_records[0][0] = index;
      else if (name === "coverage_records") broken.observations["Gal.1.1"][1][1][0] = index;
      else if (name === "observation_contexts") broken.observations["Gal.1.1"][0] = index;
      else broken.observation_contexts[0][name === "discovery_records" ? "discovery" : "dating_alternatives"] = index;
      assert.throws(() => expandData(broken), /Invalid .* reference/);
      assert.throws(() => createDataStore(broken), /Invalid .* reference/);
    }
  }
  for (const id of ["101", "102"]) {
    const broken = structuredClone(phase2);
    broken.claim_contexts[broken.claims[id][1]].source_ref = "Conflicting fictional field";
    assert.throws(() => expandData(broken), /overrides its context/);
    assert.throws(() => createDataStore(broken), /overrides its context/);
  }
  const broken = structuredClone(phase2);
  broken.coverage_contexts[broken.coverage_records[0][0]].claims = [];
  assert.throws(() => expandData(broken), /Coverage context contains claims/);
  assert.throws(() => createDataStore(broken), /Coverage context contains claims/);
});

test("Phase 2 rejects malformed claims, unsafe reconstructed integers, and dangling coverage", () => {
  const {phase2} = transferFixture();
  for (const value of [null, [], ["literal", 0], ["literal", 0, {}, null], ["unknown", 0, {}],
    ["literal", 0, []], ["ntvmr_index_v1", 0, []], ["ntvmr_index_v1", 0, ["x", "ref", 1, 0, null]]]) {
    const broken = structuredClone(phase2);
    broken.claims["101"] = value;
    assert.throws(() => expandData(broken), /Invalid .*claim|Invalid claim encoding/);
    assert.throws(() => createDataStore(broken), /Invalid .*claim|Invalid claim encoding/);
  }
  for (const value of [-1, 0.5, true, "0", null, 2 ** 53]) {
    const broken = structuredClone(phase2);
    broken.claims["101"][2][3] = value;
    assert.throws(() => expandData(broken), /Invalid compact index claim/);
    assert.throws(() => createDataStore(broken), /Invalid compact index claim/);
  }
  for (const id of ["0101", "+101", "-0", "9007199254740992", "publication"]) {
    const broken = structuredClone(phase2);
    broken.claims[id] = structuredClone(broken.claims["101"]);
    assert.throws(() => expandData(broken), /Invalid compact index claim/);
    assert.throws(() => createDataStore(broken), /Invalid compact index claim/);
  }
  for (const value of [0.5, true, "1", null, 2 ** 53]) {
    for (const field of ["doc", "page"]) {
      const broken = structuredClone(phase2);
      if (field === "doc") broken.claim_contexts[broken.claims["101"][1]].doc_id = value;
      else broken.claims["101"][2][2] = value;
      assert.throws(() => expandData(broken), /Invalid compact index claim/);
      assert.throws(() => createDataStore(broken), /Invalid compact index claim/);
    }
  }
  for (const value of [null, [], [0], [0, [], null], [0, null], [0, [102]], [0, ["missing"]]]) {
    const broken = structuredClone(phase2);
    broken.coverage_records[0] = value;
    assert.throws(() => expandData(broken), /Invalid packed coverage|Dangling coverage claim/);
    assert.throws(() => createDataStore(broken), /Invalid packed coverage|Dangling coverage claim/);
  }
  const broken = structuredClone(phase2);
  broken.coverage_records.push([0, ["missing"]]);
  assert.throws(() => expandData(broken), /Dangling coverage claim/);
  assert.throws(() => createDataStore(broken), /Dangling coverage claim/);
  for (const variant of ["missing_pair", "duplicate_pair", "dangling_claim", "event_tag", "sparse"]) {
    const broken = structuredClone(phase2), vector = broken.observations["Gal.1.1"][1][1];
    if (variant === "missing_pair") vector.shift();
    else if (variant === "duplicate_pair") vector.push(vector[0]);
    else if (variant === "dangling_claim") delete broken.claims["101"];
    else if (variant === "event_tag") broken.ranking_templates[0].combinations[0].scenarios.optimistic[0].coverage_claim_ids = ["unknown"];
    else broken.observations["Gal.1.1"][1][0] = "sparse";
    assert.throws(() => expandData(broken), /pair reference|claim reference|Invalid event claim|Invalid coverage encoding/);
    assert.throws(() => createDataStore(broken), /pair reference|claim reference|Invalid event claim|Invalid coverage encoding/);
  }
});

test("Phase 3 restores sparse defaults, dense fallbacks and different witness orders exactly", () => {
  const {normalized, phase3} = sparseFixture();
  assert.equal(phase3.coverage_defaults.length, 2);
  assert.deepEqual(phase3.observations["Gal.1.1"][1], ["sparse", 0, []]);
  assert.deepEqual(phase3.observations["Gal.3.1"][1], ["sparse", 1, []]);
  assert.deepEqual(phase3.observations["Gal.4.1"][1], ["dense", []]);
  const restored = expandData(phase3);
  assert.deepEqual(restored, normalized);
  const first = restored.observations["Gal.1.1"];
  assert.equal(first.reported_coverage[0].state, "present");
  assert.deepEqual(first.reported_coverage[3].claims, ["106"]);
  assert.equal(first.reported_coverage[3].state, "unknown");
  assert.equal(first.reported_coverage[4].unknown_reason, "no_explicit_mapped_report");
  assert.equal(restored.observations["Gal.1.5"].reported_coverage[4].unknown_reason, "unresolved_reference_mapping");
  assert.deepEqual(restored.observations["Gal.4.6"].reported_coverage[0].date_assessments, ["2"]);
  assert.equal(Object.hasOwn(restored.observations, "Gal.1.7"), false);
  first.reported_coverage[0].claims.push("changed");
  first.reported_coverage[0].date_assessments.push("changed");
  first.reported_coverage[3].unknown_reason = "changed";
  first.dating_alternatives.combinations[0].scenarios.optimistic[0].coverage_claim_ids.push(999);
  assert.deepEqual(restored.observations["Gal.2.1"], normalized.observations["Gal.2.1"]);
  assert.deepEqual(expandData(phase3), normalized);

  // Independently spell out each dense vector using only its stored indices.
  const dense = structuredClone(phase3);
  for (const row of Object.values(dense.observations)) {
    if (row[1][0] !== "sparse") continue;
    const [, index, overrides] = row[1], vector = dense.coverage_defaults[index].slice();
    for (const [position, recordIndex] of overrides) vector[position] = recordIndex;
    row[1] = ["dense", vector];
  }
  assert.deepEqual(expandData(dense), normalized);
});

test("Phase 3 rejects missing defaults, dangling indices and malformed ordered overrides", () => {
  const {phase3} = sparseFixture();
  const missing = structuredClone(phase3);
  delete missing.coverage_defaults;
  assert.throws(() => expandData(missing), /Missing collection record tables/);
  assert.throws(() => createDataStore(missing), /Missing collection record tables/);
  for (const index of [-1, phase3.coverage_defaults.length, 0.5, "0", true, null]) {
    const broken = structuredClone(phase3);
    broken.observations["Gal.1.1"][1][1] = index;
    assert.throws(() => expandData(broken), /Invalid coverage_defaults reference/);
    assert.throws(() => createDataStore(broken), /Invalid coverage_defaults reference/);
  }
  for (const vector of [null, {}, "vector", [-1], [phase3.coverage_records.length], [true], ["0"], [0.5]]) {
    const broken = structuredClone(phase3);
    broken.coverage_defaults.push(vector); // Validate unused defaults as well.
    assert.throws(() => expandData(broken), /Invalid coverage/);
    assert.throws(() => createDataStore(broken), /Invalid coverage/);
  }
  for (const encoding of [[], ["sparse"], ["sparse", 0], ["sparse", 0, [], null],
    ["sparse", 0, null], ["other", 0, []], ["dense", null]]) {
    const broken = structuredClone(phase3);
    broken.observations["Gal.1.1"][1] = encoding;
    assert.throws(() => expandData(broken), /Invalid coverage encoding/);
    assert.throws(() => createDataStore(broken), /Invalid coverage encoding/);
  }
  for (const override of [null, [], [0], [0, 0, 0], [true, 0], [-1, 0], [7, 0], [0.5, 0], ["0", 0],
    [0, -1], [0, phase3.coverage_records.length], [0, true], [0, "0"], [0, 0.5]]) {
    const broken = structuredClone(phase3);
    broken.observations["Gal.1.1"][1][2] = [override];
    assert.throws(() => expandData(broken), /Invalid coverage/);
    assert.throws(() => createDataStore(broken), /Invalid coverage/);
  }
  for (const overrides of [[[0, 0], [0, 0]], [[1, 0], [0, 0]]]) {
    const broken = structuredClone(phase3);
    broken.observations["Gal.1.1"][1][2] = overrides;
    assert.throws(() => expandData(broken), /Invalid coverage override position/);
    assert.throws(() => createDataStore(broken), /Invalid coverage override position/);
  }
});

test("Phase 3 sparse chart cells, count bands and alternative selections match the independent oracle", () => {
  const {normalized, phase3} = sparseFixture();
  const expected = createModel(normalized), candidate = createModel(phase3);
  for (const selected of ["1", "2"]) {
    expected.selection.set("fictional:a", selected);
    candidate.selection.set("fictional:a", selected);
    for (let i = 0; i < normalized.coordinates.length; i++) {
      for (const side of ["optimistic", "pessimistic"]) {
        const original = expected.cell(i, side), restored = candidate.cell(i, side);
        assert.deepEqual(restored, original);
        assert.deepEqual(segments(restored.events, candidate.maximum), segments(original.events, expected.maximum));
      }
      assert.deepEqual(candidate.discovery(i), expected.discovery(i));
    }
  }
  assert.equal(candidate.minimum, expected.minimum);
  assert.equal(candidate.maximum, expected.maximum);
});

test("production version 3 preserves sparse chart behavior and independent mutable expansion", () => {
  const {normalized, version3} = sparseFixture();
  const expected = createModel(normalized), model = createModel(version3);
  for (const selected of ["1", "2"]) {
    expected.selection.set("fictional:a", selected);
    model.selection.set("fictional:a", selected);
    for (let i = 0; i < normalized.coordinates.length; i++) {
      for (const side of ["optimistic", "pessimistic"]) {
        assert.deepEqual(model.cell(i, side), expected.cell(i, side));
        assert.deepEqual(segments(model.cell(i, side).events, model.maximum),
          segments(expected.cell(i, side).events, expected.maximum));
      }
      assert.deepEqual(model.discovery(i), expected.discovery(i));
    }
  }
  const restored = expandData(version3);
  restored.observations["Gal.1.1"].reported_coverage[0].claims.push("changed");
  restored.observations["Gal.1.1"].dating_alternatives.combinations[0].scenarios.optimistic[0].coverage_claim_ids.push(999);
  restored.claims["101"].reported.indexContent = "changed";
  restored.metadata.filters.include_omitted = true;
  assert.deepEqual(restored.observations["Gal.2.1"], normalized.observations["Gal.2.1"]);
  assert.deepEqual(expandData(version3), normalized);
  assert.equal(model.minimum, expected.minimum);
  assert.equal(model.maximum, expected.maximum);
});

test("production version 3 rejects missing tables, invalid references and conflicting provenance", () => {
  const {version3} = sparseFixture();
  for (const name of ["claim_contexts", "coverage_contexts", "coverage_records", "discovery_records",
    "ranking_templates", "observation_contexts", "coverage_defaults"]) {
    const missing = structuredClone(version3);
    delete missing[name];
    assert.throws(() => expandData(missing), /Missing collection record tables/);
    assert.throws(() => createDataStore(missing), /Missing collection record tables/);
    for (const index of [-1, version3[name].length, 0.5, "0", true, null]) {
      const broken = structuredClone(version3);
      if (name === "claim_contexts") broken.claims["101"][1] = index;
      else if (name === "coverage_contexts") broken.coverage_records[0][0] = index;
      else if (name === "coverage_records") broken.coverage_defaults[0][0] = index;
      else if (name === "coverage_defaults") broken.observations["Gal.1.1"][1][1] = index;
      else if (name === "observation_contexts") broken.observations["Gal.1.1"][0] = index;
      else broken.observation_contexts[0][name === "discovery_records" ? "discovery" : "dating_alternatives"] = index;
      assert.throws(() => expandData(broken), /Invalid .* reference/);
      assert.throws(() => createDataStore(broken), /Invalid .* reference/);
    }
  }
  for (const mutate of [
    data => {data.claims["101"][0] = "unknown";},
    data => {data.claims["101"][2][3] = 2 ** 53;},
    data => {data.claim_contexts[data.claims["102"][1]].source_ref = "conflict";},
    data => {data.coverage_records.push([0, ["missing"]]);},
    data => {data.coverage_contexts[0].claims = [];},
    data => {data.observation_contexts[0].reported_coverage = [];},
    data => {data.ranking_templates[0].combinations[0].scenarios.optimistic[0].coverage_claim_ids = ["literal", [999999]];},
    data => {data.observations["Gal.1.1"][1][2] = [[0, 0], [0, 0]];},
    data => {data.coverage_defaults.push([-1]);}
  ]) {
    const broken = structuredClone(version3);
    mutate(broken);
    assert.throws(() => expandData(broken), /Invalid|Dangling|overrides|contains/);
    assert.throws(() => createDataStore(broken), /Invalid|Dangling|overrides|contains/);
  }
});

test("the fictional oracle preserves coverage assertions, claim order, unknown reasons, and omitted observations", () => {
  const {normalized, packed, version3, phase1, phase2, phase3} = transferFixture();
  for (const input of [normalized, packed, version3, phase1, phase2, phase3]) {
    const model = createModel(input);
    const first = model.cell(model.lookup("Gal 1:1"), "optimistic");
    const second = model.cell(model.lookup("Gal 1:2"), "optimistic");
    assert.equal(first.contested, true);
    assert.deepEqual(model.store.observation(first.ref).reported_coverage.map(pair => pair.state),
      ["present", "absent", "contested", "unknown", "unknown", "present", "present"]);
    assert.deepEqual(model.store.observation(first.ref).reported_coverage.map(pair => pair.claims),
      [["102", "101"], ["103"], ["104", "105"], ["106"], [], ["107"], ["108"]]);
    assert.deepEqual(model.store.observation(second.ref).reported_coverage[0].claims, ["202", "201"]);
    assert.equal(model.store.claim("103").assertion, "absent");
    assert.deepEqual(["104", "105"].map(id => model.store.claim(id).assertion), ["present", "absent"]);
    assert.equal(model.store.claim("106").assertion, "unknown");
    assert.equal(model.store.observation(first.ref).reported_coverage[4].unknown_reason, "no_explicit_mapped_report");
    const unresolved = model.cell(model.lookup("Gal 1:5"), "optimistic");
    assert.equal(unresolved.state, "no_date");
    assert.deepEqual(unresolved.events, []);
    assert.ok(model.store.observation(unresolved.ref).reported_coverage.every(pair =>
      pair.state === "unknown" && !pair.claims.length && pair.unknown_reason === "unresolved_reference_mapping"));
    assert.equal(model.store.observation(unresolved.ref).mapping_note, "Fictional unresolved mapping; no absence inference.");
    assert.equal(model.cell(model.lookup("Gal 1:6"), "optimistic").state, "filtered");
    assert.ok(model.store.observation("Gal.1.6"));
    assert.equal(model.cell(model.lookup("Gal 1:7"), "optimistic").state, "uncollected");
    assert.equal(model.store.observation("Gal.1.7"), null);
    assert.equal(model.store.hasObservation("Gal.1.7"), false);
    assert.equal(model.discovery(model.lookup("Gal 1:1")).state, "candidate_collection_incomplete");
  }
});

test("the fictional oracle keeps complete alternatives, ties, unavailable selections, and independent overflow state", () => {
  const {normalized, packed, version3, phase1, phase2, phase3} = transferFixture();
  for (const input of [normalized, packed, version3, phase1, phase2, phase3]) {
    const model = createModel(input), first = model.lookup("Gal 1:1"), second = model.lookup("Gal 1:2");
    assert.deepEqual(model.choices.get("fictional:a").map(date => [date.date_min, date.date_max]),
      [[200, 250], [300, 399]]);
    assert.equal(model.choices.has("fictional:f"), false);
    assert.equal(model.store.date("4").status, "unknown");
    assert.equal(model.store.date("4").date_min, null);
    assert.equal(model.store.date("4").date_max, null);
    assert.deepEqual(model.cell(first, "optimistic").events.map(event =>
      [event.witness_id, event.assessment_id, event.rank, event.event_year]),
      [["fictional:a", 1, 1, 200], ["fictional:g", 3, 2, 200]]);
    assert.deepEqual(model.store.observation("Gal.1.1").dating_alternatives.combinations[0].scenarios.optimistic.map(event => event.coverage_claim_ids),
      [[102, 101], [108]]);
    assert.deepEqual(model.store.observation("Gal.1.2").dating_alternatives.combinations[0].scenarios.optimistic.map(event => event.coverage_claim_ids),
      [[202, 201], [208]]);
    assert.deepEqual(model.cell(first, "pessimistic").events.map(event => event.event_year), [250, 250]);
    assert.deepEqual(segments(model.cell(first, "optimistic").events, model.maximum),
      [{from: 200, to: 450, count: 2}]);
    assert.deepEqual(model.store.observation("Gal.1.3").dating_alternatives.combinations[0].scenarios.optimistic[0].coverage_claim_ids, [301]);
    model.selection.set("fictional:a", "2");
    assert.deepEqual(model.cell(first, "optimistic").events.map(event =>
      [event.witness_id, event.assessment_id, event.rank, event.event_year]),
      [["fictional:g", 3, 1, 200], ["fictional:a", 2, 2, 300]]);
    assert.deepEqual(model.cell(first, "pessimistic").events.map(event => event.event_year), [250, 399]);
    assert.equal(model.cell(model.lookup("Gal 1:3"), "optimistic").state, "unavailable_combination");
    assert.deepEqual(model.cell(model.lookup("Gal 1:3"), "optimistic").events, []);
    const overflow = model.cell(model.lookup("Gal 1:4"), "optimistic");
    assert.equal(overflow.state, "too_many_combinations");
    assert.equal(model.store.observation(overflow.ref).ranking_state, "no_rankable_dates");
    assert.equal(model.store.observation(overflow.ref).dating_alternatives.state, "too_many_combinations");
    assert.equal(model.store.observation(overflow.ref).dating_alternatives.combination_count, 257);
    assert.equal(model.store.observation(overflow.ref).dating_alternatives.max_combinations, 256);
    assert.deepEqual(overflow.events, []);
  }
});

test("the shared empty oracle keeps a navigable axis without creating observations", () => {
  const {normalized, packed, version3, phase1, phase2, phase3} = transferFixture("explorer-empty");
  for (const input of [normalized, packed, version3, phase1, phase2, phase3]) {
    const model = createModel(input);
    assert.equal(model.hasEvents, false);
    assert.equal(model.minimum, 0); assert.equal(model.maximum, 500);
    assert.equal(model.store.hasObservation("Gal.1.1"), false);
    assert.equal(model.store.claim("101"), undefined);
    assert.deepEqual(model.store.dateIds, []);
    assert.equal(model.cell(model.lookup("Gal 1:1"), "optimistic").state, "uncollected");
  }
});

test("bounded discovery is independent of coverage, dates, and the rest of the corpus", () => {
  const discovered = structuredClone(current);
  const model = createModel(discovered);
  assert.equal(model.discovery(model.lookup("Gal 1:9")).state, "bounded_search_complete");
  assert.match(model.discovery(model.lookup("Gal 1:9")).text, /Other catalogue ranges and unindexed witnesses/);
  assert.equal(model.discovery(model.lookup("Heb 1:1")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("Eph 1:1")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("2Thess 1:4")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("1Thess 4:12")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("Phil 3:9")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("Rom 1:1")).state, "not_searched");
  assert.equal(discovered.metadata.discovery.corpus_complete, false);
  const cell = model.cell(model.lookup("Gal 1:9"), "optimistic");
  assert.equal(model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10046").state, "unknown");
  assert.equal(model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10051").state, "present");
  const pending = structuredClone(discovered);
  const pendingGal = pending.metadata.discovery.scopes.find(s => s.definition.book === "Gal");
  pendingGal.pending_candidate_ids = [10135];
  pendingGal.candidate_collection_state = "incomplete";
  pending.observations["Gal.1.9"].discovery.state = "candidate_collection_incomplete";
  const pendingModel = createModel(pending);
  assert.match(pendingModel.discovery(pendingModel.lookup("Gal 1:9")).text, /1 of 3/);
  assert.deepEqual(pendingModel.cell(pendingModel.lookup("Gal 1:9"), "optimistic").events, cell.events);
  const failed = structuredClone(pending);
  failed.metadata.discovery.scopes.find(s => s.definition.book === "Gal").search_state = "blocked";
  failed.observations["Gal.1.9"].discovery.state = "search_incomplete";
  assert.match(createModel(failed).discovery(model.lookup("Gal 1:9")).text, /blocked/);
  assert.match(readFileSync(join(__dirname, "../web/attestation-explorer/explorer.js"), "utf8"), /Earliest collected/);
});

test("full NT report expansion navigates sources, endpoints, unknowns, and supplementary filters", () => {
  const expanded = current;
  const model = createModel(expanded);
  assert.equal(model.discovery(model.lookup("Gal 1:9")).state, "bounded_search_complete");
  assert.equal(Object.keys(expanded.observations).length, 7941);
  assert.equal(model.cell(model.lookup("Rom 16:24"), "optimistic").state, "filtered");
  assert.equal(model.cell(model.lookup("John 3:16"), "optimistic").state, "dated");
  assert.equal(model.discovery(model.lookup("John 3:16")).state, "not_searched");
  assert.equal(expanded.metadata.counts.graphable_coordinates, 7928);
  const unresolved = Object.keys(expanded.observations).filter(ref => model.cell(model.indices.get(ref), "optimistic").state === "no_date");
  assert.equal(unresolved.length, 13);
  for (const ref of unresolved) {
    assert.ok(expanded.observations[ref].reported_coverage.every(pair => pair.state === "unknown" && !pair.claims.length));
    assert.deepEqual(model.cell(model.indices.get(ref), "pessimistic").events, []);
  }
  const first = model.cell(model.lookup("Rom 1:1"), "optimistic");
  assert.equal(model.store.observation(first.ref).reported_coverage[0].state, "unknown");
  assert.deepEqual(first.events.map(e => e.event_year), [300, 400]);
  for (const ref of ["2Cor 1:1", "Gal 1:1", "Eph 1:1", "Phil 1:1", "Col 1:1", "1Thess 1:1"]) {
    const optimistic = model.cell(model.lookup(ref), "optimistic");
    const pessimistic = model.cell(model.lookup(ref), "pessimistic");
    assert.deepEqual(optimistic.events.map(e => e.event_year), [200, 300, 400]);
    assert.deepEqual(pessimistic.events.map(e => e.event_year), [225, 399, 499]);
  }
  assert.deepEqual(model.cell(model.lookup("1Cor 1:1"), "optimistic").events.map(e => e.event_year), [200, 300, 400, 700]);
  assert.deepEqual(model.cell(model.lookup("1Cor 1:1"), "pessimistic").events.map(e => e.event_year), [225, 399, 499, 725]);
  const hebrews = model.cell(model.lookup("Heb 1:1"), "optimistic");
  assert.equal(model.store.observation(hebrews.ref).reported_coverage.length, 21);
  assert.equal(model.store.observation(hebrews.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10012").state, "present");
  assert.equal(model.minimum, 150); assert.equal(model.maximum, 750);
});

test("P30 source reports update chart endpoints without expanding adjacent contents", () => {
  const model = createModel(current);
  for (const ref of ["2Thess 1:1", "2Thess 1:2", "1Thess 4:12"]) {
    for (const [scenario, year] of [["optimistic", 200], ["pessimistic", 299]]) {
      const cell = model.cell(model.lookup(ref), scenario);
      const event = cell.events.find(e => e.witness_id === "ntvmr:10030");
      assert.ok(event);
      assert.equal(event.event_year, year);
      const pair = model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10030");
      assert.equal(pair.state, "present");
      assert.ok(pair.claims.every(id => model.store.claim(id).doc_id === 10030));
    }
  }
  for (const ref of ["1Thess 5:11", "2Thess 1:3"]) {
    const cell = model.cell(model.lookup(ref), "optimistic");
    assert.ok(cell.events.every(e => e.witness_id !== "ntvmr:10030"));
    const pair = model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10030");
    assert.equal(pair.state, "unknown");
    assert.deepEqual(pair.claims, []);
  }
  assert.equal(model.discovery(model.lookup("1Thess 4:12")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("2Thess 1:1")).state, "bounded_search_complete");
});

test("P61 and P65 retain chart endpoints and source gaps across independently searched books", () => {
  for (const input of [current, packedCurrent]) {
    const model = createModel(input);
    for (const [witness, refs, early, late] of [
      ["ntvmr:10061", ["1Cor 1:1", "1Thess 1:2", "Titus 3:1"], 700, 725],
      ["ntvmr:10065", ["1Thess 1:3", "1Thess 2:1", "1Thess 2:6"], 200, 299]
    ]) {
      for (const ref of refs) {
        for (const [scenario, year] of [["optimistic", early], ["pessimistic", late]]) {
          const cell = model.cell(model.lookup(ref), scenario);
          const event = cell.events.find(e => e.witness_id === witness);
          assert.ok(event, `${witness} ${ref} ${scenario}`);
          assert.equal(event.event_year, year);
          const pair = model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === witness);
          assert.equal(pair.state, "present");
          assert.ok(pair.claims.length);
          for (const id of pair.claims) {
            const claim = model.store.claim(id);
            assert.equal(claim.witness_id, witness);
            assert.equal(claim.reported.osisID, cell.ref);
            assert.match(claim.citation, /^https:\/\/ntvmr\.uni-muenster\.de\//);
          }
        }
      }
    }
    for (const [witness, refs] of [
      ["ntvmr:10061", ["1Cor 1:3", "1Thess 1:1", "1Thess 1:4"]],
      ["ntvmr:10065", ["1Thess 2:2", "1Thess 2:3", "1Thess 2:4", "1Thess 2:5"]]
    ]) {
      for (const ref of refs) {
        const cell = model.cell(model.lookup(ref), "optimistic");
        assert.ok(cell.events.every(e => e.witness_id !== witness));
        const pair = model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === witness);
        assert.equal(pair.state, "unknown");
        assert.deepEqual(pair.claims, []);
      }
    }
    assert.equal(model.discovery(model.lookup("1Thess 1:3")).state, "bounded_search_complete");
    assert.equal(model.discovery(model.lookup("Titus 3:1")).state, "not_searched");
    assert.equal(model.discovery(model.lookup("Phil 3:5")).state, "bounded_search_complete");
    assert.equal(model.cell(model.lookup("Rom 16:24"), "optimistic").state, "filtered");
  }
});

test("P16 reports retain exact chart endpoints and leave neighboring entries unknown", () => {
  for (const input of [current, packedCurrent]) {
    const model = createModel(input);
    for (const ref of ["Phil 3:10", "Phil 3:17", "Phil 4:2", "Phil 4:8"]) {
      for (const [scenario, year] of [["optimistic", 200], ["pessimistic", 399]]) {
        const cell = model.cell(model.lookup(ref), scenario);
        const events = cell.events.filter(e => e.witness_id === "ntvmr:10016");
        assert.equal(events.length, 1);
        assert.equal(events[0].event_year, year);
        const pair = model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10016");
        assert.equal(pair.state, "present");
        assert.ok(pair.claims.length);
        for (const id of pair.claims) {
          const claim = model.store.claim(id);
          assert.equal(claim.reported.osisID, cell.ref);
          assert.equal(claim.reported_indexing_tier, 3);
          assert.match(claim.citation, /^https:\/\/ntvmr\.uni-muenster\.de\//);
        }
      }
    }
    for (const ref of ["Phil 3:9", "Phil 3:18", "Phil 4:1", "Phil 4:9"]) {
      const cell = model.cell(model.lookup(ref), "optimistic");
      assert.ok(cell.events.every(e => e.witness_id !== "ntvmr:10016"));
      const pair = model.store.observation(cell.ref).reported_coverage.find(p => p.witness_id === "ntvmr:10016");
      assert.equal(pair.state, "unknown");
      assert.deepEqual(pair.claims, []);
      assert.equal(model.discovery(model.lookup(ref)).state, "bounded_search_complete");
    }
    assert.equal(model.discovery(model.lookup("Col 1:1")).state, "not_searched");
  }
});

test("complete canonical axis and reference navigation, including tiny books", () => {
  const model = createModel(data);
  assert.equal(model.books.length, 27);
  for (const reference of ["Gal 1:9", "Gal.1.9", "Galatians 1:9"]) {
    assert.equal(model.lookup(reference), model.indices.get("Gal.1.9"));
  }
  assert.equal(model.label(model.lookup("1 Corinthians 4:21")), "1 Corinthians 4:21");
  assert.equal(model.label(model.lookup("3 John 1:15")), "3 John 1:15");
  assert.equal(model.lookup("John 3:999"), -1);
  assert.equal(model.lookup("invalid"), -1);
  assert.equal(model.cell(model.lookup("John 3:16"), "optimistic").state, "uncollected");
});

test("endpoint switch preserves intervals, rankings, unknowns, and common scale", () => {
  const model = createModel(data), index = model.lookup("Gal 1:9");
  const optimistic = model.cell(index, "optimistic"), pessimistic = model.cell(index, "pessimistic");
  assert.deepEqual(optimistic.events.map(e => e.event_year), [300, 400]);
  assert.deepEqual(pessimistic.events.map(e => e.event_year), [399, 499]);
  assert.equal(model.store.observation(optimistic.ref).reported_coverage[0].state, "unknown");
  assert.equal(model.minimum, 150); assert.equal(model.maximum, 550);
  assert.equal(model.witness("ntvmr:20001"), "GA 01");
});

test("edition-filtered coordinates are distinct from uncollected and dated", () => {
  const fixture = copy(); fixture.metadata.filters.include_bracketed = false;
  const model = createModel(fixture);
  assert.equal(model.cell(model.lookup("Matt 17:21"), "optimistic").state, "filtered");
  assert.equal(model.cell(model.lookup("Mark 16:9"), "optimistic").state, "filtered");
  assert.equal(model.cell(model.lookup("Matt 1:1"), "optimistic").state, "uncollected");
});

test("explicit contested reports and absent/unknown states survive without fabricated events", () => {
  const fixture = copy(), row = fixture.observations["Gal.1.1"];
  row.reported_coverage[0].state = "contested";
  row.reported_coverage[1].state = "absent";
  row.reported_coverage[2].state = "unknown";
  row.dating_alternatives.combinations = [{assessments: [], scenarios: {optimistic: [], pessimistic: []}}];
  const model = createModel(fixture), cell = model.cell(model.lookup("Gal 1:1"), "optimistic");
  assert.equal(cell.contested, true); assert.equal(cell.state, "no_date"); assert.deepEqual(cell.events, []);
  assert.deepEqual(model.store.observation(cell.ref).reported_coverage.map(p => p.state), ["contested", "absent", "unknown"]);
});

test("on-demand alternatives reverse order without expanding corpus combinations", () => {
  const fixture = copy(), row = fixture.observations["Gal.1.1"];
  fixture.dates["4"] = {...fixture.dates["1"], assessment_id: 4, date_min: 450, date_max: 600};
  const original = row.dating_alternatives.combinations[0];
  row.dating_alternatives.combinations.push({assessments: ["4", "2", "3"], scenarios: {
    optimistic: [{...original.scenarios.optimistic[1], rank: 1}, {...original.scenarios.optimistic[2], rank: 2},
      {...original.scenarios.optimistic[0], assessment_id: 4, rank: 3, event_year: 450}],
    pessimistic: [{...original.scenarios.pessimistic[1], rank: 1}, {...original.scenarios.pessimistic[2], rank: 2},
      {...original.scenarios.pessimistic[0], assessment_id: 4, rank: 3, event_year: 600}]
  }});
  // More than 256 global combinations, without any need to enumerate them.
  for (let i = 10; i < 19; i++) for (let j = 0; j < 2; j++) {
    const id = String(i * 10 + j);
    fixture.dates[id] = {...fixture.dates["1"], assessment_id: Number(id), witness_id: `synthetic:${i}`};
  }
  const model = createModel(fixture), index = model.lookup("Gal 1:1");
  assert.equal(model.cell(index, "optimistic").events[0].event_year, 200);
  model.selection.set("ntvmr:10046", "4");
  assert.equal(model.cell(index, "optimistic").events[0].witness_id, "ntvmr:20001");
  assert.equal(model.cell(index, "pessimistic").events.at(-1).event_year, 600);
  assert.equal(model.maximum, 650);
  assert.equal(model.cell(model.lookup("Gal 1:2"), "optimistic").state, "unavailable_combination");
  const overflowInput = structuredClone(fixture);
  overflowInput.observations["Gal.1.1"].dating_alternatives = {state: "too_many_combinations", combinations: [], combination_count: 257};
  const overflowModel = createModel(overflowInput);
  assert.equal(overflowModel.cell(index, "optimistic").state, "too_many_combinations");
  assert.deepEqual(overflowModel.cell(index, "optimistic").events, []);
});

test("pointer mapping respects zoom, scroll, boundaries, and a 7,957-verse axis", () => {
  assert.equal(hitIndex(0, 1000, 0, 1000, 7957), 0);
  assert.equal(hitIndex(1000, 1000, 0, 1000, 7957), 7956);
  assert.equal(hitIndex(-100, 1000, 0, 1000, 7957), 0);
  assert.equal(hitIndex(500, 1000, 1500, 4000, 7957), 3978);
  assert.equal(hitIndex(1000, 1000, 3000, 4000, 7957), 7956);
});

test("simultaneous years share one count step, with no negative geometry", () => {
  assert.deepEqual(segments([{event_year: 200}, {event_year: 200}, {event_year: 400}], 550),
    [{from: 200, to: 400, count: 2}, {from: 400, to: 550, count: 3}]);
  assert.deepEqual(segments([], 550), []);
});

test("an empty export still has a navigable corpus and a finite neutral scale", () => {
  const fixture = copy(); fixture.observations = {}; fixture.dates = {}; fixture.claims = {};
  const model = createModel(fixture);
  assert.equal(model.hasEvents, false);
  assert.equal(model.minimum, 0); assert.equal(model.maximum, 500);
  assert.equal(model.cell(model.lookup("Gal 1:1"), "optimistic").state, "uncollected");
});

test("shared stores restore every selected source field and chart value against the independent oracle", () => {
  for (const fixture of [transferFixture(), sparseFixture(), transferFixture("explorer-empty")]) {
    const {normalized, ...versions} = fixture;
    for (const raw of [structuredClone(normalized), ...Object.values(versions)]) {
      const model = createModel(raw), store = model.store;
      for (const [id, value] of Object.entries(normalized.claims)) assert.deepEqual(store.claim(id), value);
      for (const [id, value] of Object.entries(normalized.dates)) assert.deepEqual(store.date(id), value);
      for (const [ref] of normalized.coordinates) {
        assert.deepEqual(store.observation(ref), normalized.observations[ref] || null);
        if (normalized.observations[ref]) {
          const totals = {present: 0, unknown: 0, contested: 0, absent: 0};
          for (const pair of normalized.observations[ref].reported_coverage) totals[pair.state]++;
          assert.deepEqual(store.summary(ref).coverage_totals, totals);
        }
      }
      for (const selected of ["1", "2"]) {
        model.selection.set("fictional:a", selected);
        for (const [i, [ref, editorial]] of normalized.coordinates.entries()) {
          const row = normalized.observations[ref], status = row?.editorial_status || editorial;
          const filtered = status === "omitted" && !normalized.metadata.filters.include_omitted ||
            status === "bracketed" && !normalized.metadata.filters.include_bracketed;
          const combo = row?.dating_alternatives.combinations.find(combo => combo.assessments.every(id =>
            model.selection.get(normalized.dates[id].witness_id) === String(id)));
          for (const scenario of ["optimistic", "pessimistic"]) {
            const events = !filtered && row ? (combo?.scenarios[scenario] || []).map(({coverage_claim_ids, ...event}) => event) : [];
            const cell = model.cell(i, scenario);
            assert.deepEqual(cell.events, events);
            assert.equal(cell.state, filtered ? "filtered" : !row ? "uncollected" :
              row.dating_alternatives.state === "too_many_combinations" ? "too_many_combinations" :
              !combo && row.dating_alternatives.combinations.length ? "unavailable_combination" : events.length ? "dated" : "no_date");
            assert.equal(!!cell.contested, !filtered && !!row?.reported_coverage.some(pair => pair.state === "contested"));
            assert.deepEqual(segments(cell.events, model.maximum), segments(events, model.maximum));
          }
        }
      }
    }
  }
});

test("full-axis evaluation shares read-only chart records without decoding coverage; selection cache stays bounded", () => {
  const {normalized, version3} = sparseFixture();
  Object.freeze(version3.metadata); // Shallow-frozen callers still get deeply read-only records.
  const model = createModel(version3), store = model.store;
  assert.equal(createDataStore(store), store);
  assert.equal(createModel(model), model);
  for (const scenario of ["optimistic", "pessimistic"]) {
    for (let i = 0; i < normalized.coordinates.length; i++) {
      const cell = model.cell(i, scenario);
      assert.equal(Object.hasOwn(cell, "observation"), false);
      assert.ok(cell.events.every(event => !Object.hasOwn(event, "coverage_claim_ids")));
      segments(cell.events, model.maximum); model.discovery(i);
    }
  }
  assert.equal(store.diagnostics().observationDecodes, 0);
  assert.equal(store.diagnostics().coverageDecodes, 0);
  assert.equal(store.diagnostics().cachedObservations, 0);
  assert.equal(Object.hasOwn(model.data, "observations"), false);
  assert.equal(store.chartAlternatives("Gal.1.1"), store.chartAlternatives("Gal.2.1"));
  const events = model.cell(model.lookup("Gal 1:1"), "optimistic").events;
  assert.equal(Reflect.set(events[0], "rank", 999), false);
  assert.throws(() => events.push({}), TypeError);
  const first = store.observation("Gal.1.1");
  assert.equal(store.observation("Gal.1.1"), first);
  assert.throws(() => first.reported_coverage[0].claims.push("changed"), TypeError);
  assert.equal(Reflect.set(store.claim("101").reported, "osisID", "changed"), false);
  assert.equal(store.claim(101), store.claim("101"));
  assert.equal(Reflect.set(store.date("1"), "date_min", 999), false);
  assert.equal(Reflect.set(store.data.metadata.filters, "include_omitted", true), false);
  for (let visit = 0; visit < 100; visit++) for (const [ref] of normalized.coordinates) {
    assert.deepEqual(store.observation(ref), normalized.observations[ref] || null);
    assert.ok(store.diagnostics().cachedObservations <= 1);
  }
  assert.notEqual(store.observation("Gal.1.1"), first);
  assert.equal(store.claim("101").reported.osisID, "Gal.1.1");
  model.selection.set("fictional:a", "2");
  assert.equal(model.cell(model.lookup("Gal 1:1"), "optimistic").events.at(-1).event_year, 300);
});

test("store validation checks unused contexts, templates, coverage, and date references before mounting", () => {
  for (const mutate of [
    raw => raw.claim_contexts.push(null),
    raw => raw.discovery_records.push(null),
    raw => raw.coverage_contexts.push({...raw.coverage_contexts[0], claims: []}),
    raw => raw.coverage_contexts.push({...raw.coverage_contexts[0], date_assessments: ["missing"]}),
    raw => raw.coverage_records.push([0, ["missing"]]),
    raw => raw.coverage_defaults.push([-1]),
    raw => raw.observation_contexts.push({...raw.observation_contexts[0], discovery: -1}),
    raw => raw.observation_contexts.push({...raw.observation_contexts[0], dating_alternatives: -1}),
    raw => raw.observation_contexts.push({...raw.observation_contexts[0], reported_coverage: []}),
    raw => raw.ranking_templates.push(null),
    raw => {const template = structuredClone(raw.ranking_templates[0]); template.combinations[0].assessments = ["missing"]; raw.ranking_templates.push(template);},
    raw => {const template = structuredClone(raw.ranking_templates[0]); template.combinations[0].scenarios.optimistic[0].assessment_id = 999; raw.ranking_templates.push(template);},
    raw => {const template = structuredClone(raw.ranking_templates[0]); template.combinations[0].scenarios.optimistic[0].coverage_claim_ids = ["literal", [999]]; raw.ranking_templates.push(template);},
    raw => {const template = structuredClone(raw.ranking_templates[0]); template.combinations[0].scenarios.optimistic[0].coverage_claim_ids = ["unsupported"]; raw.ranking_templates.push(template);}
  ]) {
    const {version3} = transferFixture(); mutate(version3);
    assert.throws(() => createDataStore(version3), /Invalid|Dangling|contains/);
  }
  for (const kind of ["normalized", "packed", "phase1", "phase2", "phase3", "version3"]) {
    const raw = transferFixture()[kind]; delete raw.dates["1"];
    assert.throws(() => createDataStore(raw), /Dangling date reference/);
  }
  const {version3} = transferFixture(), unused = structuredClone(version3.ranking_templates[0]);
  unused.combinations[0].scenarios.optimistic[0].event_year = 9999;
  version3.ranking_templates.push(unused);
  version3.observation_contexts.push({...version3.observation_contexts[0], dating_alternatives: version3.ranking_templates.length - 1});
  assert.equal(createModel(version3).maximum, 450);
});

test("full expansion remains independently mutable for all published versions, even from frozen store inputs", () => {
  for (const kind of ["normalized", "packed", "version3"]) {
    const fixture = transferFixture(), raw = fixture[kind], expected = structuredClone(fixture.normalized);
    createDataStore(raw);
    const first = expandData(raw), second = expandData(raw);
    first.metadata.filters.include_omitted = true;
    first.claims["102"].reported_extra.values.push("changed");
    first.observations["Gal.1.1"].reported_coverage[0].date_assessments.push("changed");
    first.observations["Gal.1.1"].dating_alternatives.combinations[0].scenarios.optimistic[0].coverage_claim_ids.push(999);
    assert.deepEqual(second, expected);
    assert.deepEqual(first.observations["Gal.1.2"], expected.observations["Gal.1.2"]);
    assert.deepEqual(expandData(raw), expected);
  }
});

test("mounted selection and source details render identical safe text across versions with a reused model", () => {
  const fixture = transferFixture(), snapshots = [];
  for (const kind of ["normalized", "packed", "version3"]) {
    const raw = fixture[kind];
    raw.metadata.counts = {verse_count: 6, witness_count: 7, graphable_coordinates: 3,
      mapping_gaps: 1, witness_verse_pairs: {present: 3, unknown: 2, absent: 1, contested: 1}};
    const model = createModel(raw), dom = explorerDOM(), app = mount(dom.root, model);
    dom.draw();
    assert.equal(model.store.diagnostics().cachedObservations, 1);
    const details = dom.nodes.get("source-details");
    details.open = true; details.dispatch("toggle");
    const capture = () => ["witnesses", "claims", "summary", "discovery-summary"].map(name => dom.snapshot(dom.nodes.get(name)));
    const initial = capture(), contents = dom.text(dom.nodes.get("claims"));
    for (const claim of Object.values(fixture.normalized.claims).filter(item => item.source_ref === "Gal.1.1")) {
      assert.ok(contents.includes(JSON.stringify(claim.reported, null, 2)));
      assert.ok(contents.includes(claim.source_locator));
      assert.ok(contents.includes(claim.source_sha256));
      assert.ok(contents.includes(claim.qualifications));
    }
    assert.ok(contents.includes('</script>'));
    assert.equal(dom.nodes.get("claims").children.some(item => item.tag === "script"), false);
    model.selection.set("fictional:a", "2"); app.setScenario("pessimistic");
    const alternative = capture();
    assert.ok(app.selectVerse("Gal 1:2")); const second = capture();
    assert.ok(app.selectVerse("Gal 1:5")); const unresolved = capture();
    assert.ok(app.selectVerse("Gal 1:6")); const filtered = capture();
    assert.ok(app.selectVerse("Gal 1:7"));
    assert.equal(details.hidden, true); assert.equal(dom.nodes.get("claims").children.length, 0);
    assert.equal(model.store.diagnostics().cachedObservations, 0);
    snapshots.push([initial, alternative, second, unresolved, filtered, capture()]);
    app.destroy();
  }
  assert.deepEqual(snapshots[1], snapshots[0]); assert.deepEqual(snapshots[2], snapshots[0]);
});
