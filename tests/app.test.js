const {test} = require("node:test");
const assert = require("node:assert/strict");
const {DATA_URL, loadData, start} = require("../web/attestation-explorer/app.js");

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
  nodes.file.files = [{text: async () => JSON.stringify({...data, local: true})}];
  await nodes.file.listeners.change();
  assert.equal(mounted[1].local, true);
});
