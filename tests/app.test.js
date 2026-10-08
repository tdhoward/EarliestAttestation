const {test} = require("node:test");
const {readFileSync} = require("node:fs");
const {join} = require("node:path");
const assert = require("node:assert/strict");
const {DATA_URL, loadData, start} = require("../web/attestation-explorer/app.js");
const {expandData, createModel} = require("../web/attestation-explorer/explorer.js");
function assertStore(store, expected) {
  assert.deepEqual(store.data.coordinates, expected.coordinates);
  for (const [ref] of expected.coordinates) {
    assert.equal(store.hasObservation(ref), Object.hasOwn(expected.observations, ref));
    assert.deepEqual(store.observation(ref), expected.observations[ref] || null);
  }
  for (const [id, claim] of Object.entries(expected.claims)) assert.deepEqual(store.claim(id), claim);
  for (const [id, date] of Object.entries(expected.dates)) assert.deepEqual(store.date(id), date);
}
const {transferFixture, sparseFixture} = require("./explorer-fixtures.js");

test("shared transfer records preserve exact claims, all coverage states, discovery and complete alternatives", async () => {
  for (const name of ["explorer-normalized", "explorer-empty"]) {
    const {normalized, packed, version3, phase1, phase2, phase3} = transferFixture(name);
    for (const input of [normalized, packed, version3, phase1, phase2, phase3]) {
      assertStore(await loadData(async () => ({ok: true, json: async () => input})), normalized);
    }
    if (name === "explorer-empty") continue;
    const restored = expandData(packed);
    assert.equal(packed.observations["Gal.1.1"].reported_coverage[4],
      packed.observations["Gal.1.2"].reported_coverage[4]);
    restored.observations["Gal.1.1"].reported_coverage[4].claims.push("changed");
    restored.observations["Gal.1.1"].discovery.scopes[0].pending_candidate_ids.push(3);
    assert.deepEqual(restored.observations["Gal.1.2"], normalized.observations["Gal.1.2"]);
    assert.deepEqual(expandData(packed), normalized);
  }
});

test("broken shared references and conflicting provenance cause a load failure", async () => {
  for (const name of ["claim_contexts", "coverage_records", "discovery_records"]) {
    for (const index of [-1, 999, "0", true]) {
      const {packed} = transferFixture();
      if (name === "claim_contexts") packed.claims["101"][0] = index;
      else if (name === "coverage_records") packed.observations["Gal.1.1"].reported_coverage[0] = index;
      else packed.observations["Gal.1.1"].discovery = index;
      await assert.rejects(loadData(async () => ({ok: true, json: async () => packed})), /Invalid .* reference/);
    }
  }
  const {packed} = transferFixture();
  packed.claims["101"][1].citation = "Conflicting synthetic provenance";
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
  assert.equal((await loadData(fetcher)).data.revision, 1);
  assert.equal((await loadData(fetcher)).data.revision, 2);
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
  let modelBuilds = 0;
  const explorer = {createModel(store) {modelBuilds++; return {store};},
    mount(element, model) {assert.equal(element, root); mounted.push(model.store); return {destroy() {}};}};
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
  assert.equal(mounted[0].hasObservation("Gal.1.1"), false);
  assert.equal(modelBuilds, 1);
  nodes.file.files = [{text: async () => JSON.stringify({...data, local: true, format_version: 2,
    claims: {}, claim_contexts: [], coverage_records: [], discovery_records: []})}];
  await nodes.file.listeners.change();
  assert.equal(mounted[1].data.local, true);
});

test("the file picker loads versions 1, 2, 3 and candidate codecs against the shared oracle", async () => {
  const node = () => ({hidden: true, listeners: {}, addEventListener(type, fn) {this.listeners[type] = fn;}});
  const nodes = {status: node(), retry: node(), "file-label": node(), file: node()};
  const loader = node(), root = node();
  loader.querySelector = selector => nodes[selector.match(/"(.*?)"/)[1]];
  const doc = {getElementById: id => id === "collection-loader" ? loader : root};
  const mounted = [];
  const explorer = {createModel, mount(element, data) {
    assert.equal(element, root); mounted.push(data.store); return {destroy() {}};
  }};
  await start(doc, explorer, async () => {throw new Error("Offline fixture loading");});
  for (const name of ["explorer-normalized", "explorer-empty"]) {
    const {normalized, packed, version3, phase1, phase2, phase3} = transferFixture(name);
    for (const input of [normalized, packed, version3, phase1, phase2, phase3]) {
      nodes.file.files = [{text: async () => JSON.stringify(input)}];
      await nodes.file.listeners.change();
      assertStore(mounted.at(-1), normalized);
      assert.equal(root.hidden, false);
      assert.equal(loader.hidden, true);
    }
  }
  const {normalized: sparseExpected, phase3: sparse, version3: sparse3} = sparseFixture();
  for (const input of [sparse, sparse3]) {
    assertStore(await loadData(async () => ({ok: true, json: async () => input})), sparseExpected);
    nodes.file.files = [{text: async () => JSON.stringify(input)}];
    await nodes.file.listeners.change();
    assertStore(mounted.at(-1), sparseExpected);
  }
  const production = JSON.parse(readFileSync(join(__dirname, "fixtures/explorer-pilot.v4.json"), "utf8"));
  const fetched = await loadData(async () => ({ok: true, json: async () => production}));
  nodes.file.files = [{text: async () => JSON.stringify(production)}];
  await nodes.file.listeners.change();
  assert.equal(mounted.at(-1).formatVersion, 4);
  assert.deepEqual(mounted.at(-1).observation("1Tim.4.3"), fetched.observation("1Tim.4.3"));
  assert.equal(root.hidden, false);
  const {normalized, packed, version3, phase2} = transferFixture();
  packed.observations["Gal.1.1"].reported_coverage[0] = -1;
  phase2.coverage_records[0][0] = -1;
  const brokenSparse = structuredClone(sparse), brokenSparse3 = structuredClone(sparse3);
  brokenSparse.observations["Gal.1.1"][1][2] = [[0, 0], [0, 0]];
  version3.claims["101"][1] = -1;
  brokenSparse3.observations["Gal.1.1"][1][2] = [[0, 0], [0, 0]];
  const successfulLoads = mounted.length;
  for (const broken of [packed, phase2, brokenSparse, version3, brokenSparse3]) {
    nodes.file.files = [{text: async () => JSON.stringify(broken)}];
    await nodes.file.listeners.change();
    assert.equal(mounted.length, successfulLoads);
    assert.equal(root.hidden, true);
    assert.equal(nodes.retry.hidden, false);
  }
  nodes.file.files = [{text: async () => JSON.stringify(normalized)}];
  await nodes.file.listeners.change();
  assertStore(mounted.at(-1), normalized);
  assert.equal(root.hidden, false);
});

test("a malformed version 3 fetch can be retried with corrected data", async () => {
  const node = () => ({hidden: true, listeners: {}, addEventListener(type, fn) {this.listeners[type] = fn;}});
  const nodes = {status: node(), retry: node(), "file-label": node(), file: node()};
  const loader = node(), root = node();
  loader.querySelector = selector => nodes[selector.match(/"(.*?)"/)[1]];
  const doc = {getElementById: id => id === "collection-loader" ? loader : root};
  const {normalized, version3} = sparseFixture(), broken = structuredClone(version3), mounted = [];
  broken.coverage_defaults[0][0] = -1;
  let response = broken;
  await start(doc, {createModel, mount(element, data) {
    assert.equal(element, root); mounted.push(data.store); return {destroy() {}};
  }}, async () => ({ok: true, json: async () => response}));
  assert.equal(root.hidden, true);
  assert.equal(nodes.retry.hidden, false);
  assert.equal(mounted.length, 0);
  response = version3;
  await nodes.retry.listeners.click();
  assert.equal(mounted.length, 1);
  assertStore(mounted[0], normalized);
  assert.equal(root.hidden, false);
  assert.equal(loader.hidden, true);
});
