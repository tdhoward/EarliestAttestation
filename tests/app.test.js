const {test} = require("node:test");
const assert = require("node:assert/strict");
const {DATA_URL, loadData, start} = require("../web/attestation-explorer/app.js");
const {expandData} = require("../web/attestation-explorer/explorer.js");

// Explicitly fictional transfer records. Five coverage states and complete date
// alternatives exercise loading without making any manuscript-content judgment.
function transferFixture() {
  const context = {provider: "Fictional transfer source", citation: "https://example.invalid/report",
    retrieved_at: "2026-10-06T00:00:00Z", qualifications: "Synthetic source qualification",
    source_sha256: "synthetic hash", source_response_id: 1};
  const details = {claim_id: 1, witness_id: "synthetic:a", source_ref: "Gal.1.1",
    assertion: "present", source_locator: "synthetic field",
    reported: {osisID: "Gal.1.1", portion: "synthetic reported portion"}};
  const claimDetails = [details,
    {...details, claim_id: 2, witness_id: "synthetic:b", assertion: "absent", reported: "Synthetic explicit absence"},
    {...details, claim_id: 3, witness_id: "synthetic:c"},
    {...details, claim_id: 4, witness_id: "synthetic:c", assertion: "absent", reported: "Synthetic competing absence"}];
  const date = {assessment_id: 1, witness_id: "synthetic:a", status: "valid", date_min: 200, date_max: 250,
    original_notation: "Synthetic interval", ...context};
  const event = {witness_id: "synthetic:a", assessment_id: 1, rank: 1, event_year: 200, coverage_claim_ids: [1]};
  const discovery = {state: "candidate_collection_incomplete", corpus_complete: false,
    ranking_scope: "collected_witnesses_only", scopes: [{scope_id: "synthetic-scope", pending_candidate_ids: [2]}]};
  const coverage = ["present", "absent", "contested", "unknown", "unknown"].map((state, i) => ({
    witness_id: `synthetic:${String.fromCharCode(97 + i)}`, state,
    claims: i === 0 ? ["1"] : i === 1 ? ["2"] : i === 2 ? ["3", "4"] : [], date_assessments: i ? [] : ["1", "2"],
    unknown_reason: i === 3 ? "no_explicit_mapped_report" : i === 4 ? "explicitly_unconfirmed" : null}));
  const row = {editorial_status: "main", editorial_note: null, mapping_note: null, passage_citation: null,
    ranking_state: "complete", discovery, reported_coverage: coverage,
    dating_alternatives: {state: "complete", combination_count: 2, max_combinations: 256, eligible_witness_count: 1,
      combinations: [
        {assessments: ["1"], scenarios: {optimistic: [event], pessimistic: [{...event, event_year: 250}]}},
        {assessments: ["2"], scenarios: {optimistic: [{...event, assessment_id: 2, event_year: 300}],
          pessimistic: [{...event, assessment_id: 2, event_year: 399}]}}
      ]}};
  const empty = {...row, discovery: structuredClone(discovery), reported_coverage: [structuredClone(coverage[3])],
    ranking_state: "no_rankable_dates", dating_alternatives: {state: "too_many_combinations",
      combination_count: 257, max_combinations: 256, combinations: []}};
  const normalized = {format_version: 1, coordinates: [["Gal.1.1", "main"], ["Gal.1.2", "main"]],
    documents: [], sources: [context], metadata: {evidence_policy: "scholarly_reports_only"},
    claims: Object.fromEntries(claimDetails.map(claim => [String(claim.claim_id), {...context, ...claim}])),
    dates: {"1": date, "2": {...date, assessment_id: 2, date_min: 300, date_max: 399}},
    observations: {"Gal.1.1": row, "Gal.1.2": empty}};
  const packed = {...normalized, format_version: 2, claim_contexts: [context],
    claims: Object.fromEntries(claimDetails.map(claim => [String(claim.claim_id), [0, claim]])),
    coverage_records: coverage, discovery_records: [discovery], observations: {
      "Gal.1.1": {...row, discovery: 0, reported_coverage: [0, 1, 2, 3, 4]},
      "Gal.1.2": {...empty, discovery: 0, reported_coverage: [3]}}};
  return {normalized, packed};
}

test("shared transfer records preserve exact claims, all coverage states, discovery and complete alternatives", async () => {
  const {normalized, packed} = transferFixture();
  const restored = await loadData(async () => ({ok: true, json: async () => packed}));
  assert.deepEqual(restored, normalized);
  restored.observations["Gal.1.1"].reported_coverage[3].claims.push("changed");
  restored.observations["Gal.1.1"].discovery.scopes[0].pending_candidate_ids.push(3);
  assert.deepEqual(restored.observations["Gal.1.2"], normalized.observations["Gal.1.2"]);
  assert.deepEqual(expandData(packed), normalized);
});

test("broken shared references and conflicting provenance cause a load failure", async () => {
  for (const name of ["claim_contexts", "coverage_records", "discovery_records"]) {
    for (const index of [-1, 999, "0", true]) {
      const {packed} = transferFixture();
      if (name === "claim_contexts") packed.claims["1"][0] = index;
      else if (name === "coverage_records") packed.observations["Gal.1.1"].reported_coverage[0] = index;
      else packed.observations["Gal.1.1"].discovery = index;
      await assert.rejects(loadData(async () => ({ok: true, json: async () => packed})), /Invalid .* reference/);
    }
  }
  const {packed} = transferFixture();
  packed.claims["1"][1].citation = "Conflicting synthetic provenance";
  assert.throws(() => expandData(packed), /overrides its context/);
  delete packed.claim_contexts;
  assert.throws(() => expandData(packed), /Missing collection record tables/);
});

test("the app requests the same current data URL without a stale browser cache", async () => {
  const versions = [1, 2];
  const fetcher = async (url, options) => {
    assert.equal(url, "../../data/attestations.json");
    assert.equal(url, DATA_URL);
    assert.equal(options.cache, "no-store");
    return {ok: true, json: async () => ({format_version: 1, coordinates: [["Gal.1.1", "main"]],
      observations: {}, revision: versions.shift()})};
  };
  assert.equal((await loadData(fetcher)).revision, 1);
  assert.equal((await loadData(fetcher)).revision, 2);
});

test("missing or malformed data is a load failure rather than an empty collection", async () => {
  await assert.rejects(loadData(async () => ({ok: false, status: 404})), /404/);
  await assert.rejects(loadData(async () => ({ok: true, json: async () => ({})})), /Unsupported/);
  await assert.rejects(loadData(async () => {throw new Error("offline");}), /offline/);
});

test("a failed request offers retry and a local JSON fallback, then mounts the loaded collection", async () => {
  const node = () => ({hidden: true, listeners: {}, addEventListener(type, fn) {this.listeners[type] = fn;}});
  const nodes = {status: node(), retry: node(), "file-label": node(), file: node()};
  const loader = node(), root = node();
  loader.querySelector = selector => nodes[selector.match(/"(.*?)"/)[1]];
  const doc = {getElementById: id => id === "collection-loader" ? loader : root};
  const mounted = [];
  const explorer = {createModel: data => assert.equal(data.format_version, 1),
    mount(element, data) {assert.equal(element, root); mounted.push(data); return {destroy() {}};}};
  let fail = true;
  const data = {format_version: 1, coordinates: [["Gal.1.1", "main"]], observations: {}};
  await start(doc, explorer, async () => {
    if (fail) throw new Error("Network unavailable");
    return {ok: true, json: async () => data};
  });
  assert.equal(root.hidden, true);
  assert.equal(loader.hidden, false);
  assert.equal(nodes.retry.hidden, false);
  assert.equal(nodes["file-label"].hidden, false);
  assert.equal(mounted.length, 0);
  fail = false;
  await nodes.retry.listeners.click();
  assert.equal(root.hidden, false);
  assert.equal(loader.hidden, true);
  assert.deepEqual(mounted, [data]);
  nodes.file.files = [{text: async () => JSON.stringify({...data, local: true, format_version: 2,
    claims: {}, claim_contexts: [], coverage_records: [], discovery_records: []})}];
  await nodes.file.listeners.change();
  assert.equal(mounted[1].local, true);
});
