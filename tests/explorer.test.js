/* Run with node --test tests/explorer.test.js. Entirely offline. */
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const {join} = require("node:path");
const {expandData, createModel, hitIndex, segments} = require("../web/attestation-explorer/explorer.js");
const current = expandData(JSON.parse(readFileSync(join(__dirname, "../data/attestations.json"), "utf8")));
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

test("bounded discovery is independent of coverage, dates, and the rest of the corpus", () => {
  const discovered = structuredClone(current);
  const model = createModel(discovered);
  assert.equal(model.discovery(model.lookup("Gal 1:9")).state, "bounded_search_complete");
  assert.match(model.discovery(model.lookup("Gal 1:9")).text, /Other catalogue ranges and unindexed witnesses/);
  assert.equal(model.discovery(model.lookup("Heb 1:1")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("Eph 1:1")).state, "bounded_search_complete");
  assert.equal(model.discovery(model.lookup("2Thess 1:4")).state, "not_searched");
  assert.equal(model.discovery(model.lookup("Rom 1:1")).state, "not_searched");
  assert.equal(discovered.metadata.discovery.corpus_complete, false);
  const cell = model.cell(model.lookup("Gal 1:9"), "optimistic");
  assert.equal(cell.observation.reported_coverage.find(p => p.witness_id === "ntvmr:10046").state, "unknown");
  assert.equal(cell.observation.reported_coverage.find(p => p.witness_id === "ntvmr:10051").state, "present");
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
  assert.equal(first.observation.reported_coverage[0].state, "unknown");
  assert.deepEqual(first.events.map(e => e.event_year), [300, 400]);
  for (const ref of ["1Cor 1:1", "2Cor 1:1", "Gal 1:1", "Eph 1:1", "Phil 1:1", "Col 1:1", "1Thess 1:1"]) {
    const optimistic = model.cell(model.lookup(ref), "optimistic");
    const pessimistic = model.cell(model.lookup(ref), "pessimistic");
    assert.deepEqual(optimistic.events.map(e => e.event_year), [200, 300, 400]);
    assert.deepEqual(pessimistic.events.map(e => e.event_year), [225, 399, 499]);
  }
  const hebrews = model.cell(model.lookup("Heb 1:1"), "optimistic");
  assert.equal(hebrews.observation.reported_coverage.length, 17);
  assert.equal(hebrews.observation.reported_coverage.find(p => p.witness_id === "ntvmr:10012").state, "present");
  assert.equal(model.minimum, 150); assert.equal(model.maximum, 750);
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
