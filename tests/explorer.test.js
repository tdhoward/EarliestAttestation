/* Run with node --test tests/explorer.test.js. Entirely offline. */
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const {join} = require("node:path");
const {createModel, hitIndex, segments} = require("../web/attestation-explorer/explorer.js");
const html = readFileSync(join(__dirname, "../examples/galatians-source-reports.html"), "utf8");
const data = JSON.parse(html.match(/<script id="attestation-data" type="application\/json">(.*?)<\/script>/s)[1]);
const copy = () => structuredClone(data);

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
  assert.equal(optimistic.observation.reported_coverage[0].state, "unknown");
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
  assert.deepEqual(cell.observation.reported_coverage.map(p => p.state), ["contested", "absent", "unknown"]);
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
  row.dating_alternatives = {state: "too_many_combinations", combinations: [], combination_count: 257};
  assert.equal(model.cell(index, "optimistic").state, "too_many_combinations");
  assert.deepEqual(model.cell(index, "optimistic").events, []);
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
