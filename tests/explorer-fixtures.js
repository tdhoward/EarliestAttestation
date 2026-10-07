const {readFileSync} = require("node:fs");
const {join} = require("node:path");

// Read fresh copies so model selections and malformed-input tests stay isolated.
// Version 1 is the expected oracle; version 2 and candidates are codec snapshots.
function transferFixture(name = "explorer-normalized") {
  const read = version => JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.v${version}.json`), "utf8"));
  const phase1 = JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.phase1.json`), "utf8"));
  const phase2 = JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.phase2.json`), "utf8"));
  const phase3 = JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.phase3.json`), "utf8"));
  return {normalized: read(1), packed: read(2), phase1, phase2, phase3};
}

// Expected values are cloned from the independent fictional oracle, without
// using any codec. Keep this construction in sync with sparse_fixture() in
// test_report_explorer.py. These repeated assertions are synthetic test values.
function sparseFixture() {
  const {normalized} = transferFixture();
  function add(ref, row) {
    normalized.coordinates.push([ref, "main"]);
    normalized.observations[ref] = row;
  }
  for (let verse = 1; verse <= 12; verse++) {
    add(`Gal.2.${verse}`, structuredClone(normalized.observations["Gal.1.1"]));
  }
  for (let verse = 1; verse <= 8; verse++) {
    const row = structuredClone(normalized.observations["Gal.1.1"]);
    row.reported_coverage.splice(0, 2, ...row.reported_coverage.slice(0, 2).reverse());
    add(`Gal.3.${verse}`, row);
  }
  for (let verse = 1; verse <= 6; verse++) {
    const row = structuredClone(normalized.observations["Gal.1.4"]);
    let pairs = structuredClone(normalized.observations["Gal.1.1"].reported_coverage);
    if (verse === 1) pairs = [];
    else if (verse === 2) pairs = [pairs[0], structuredClone(pairs[0])];
    else if (verse === 3) {pairs = [pairs[0]]; delete pairs[0].witness_id;}
    else if (verse === 4) pairs = pairs.slice(0, 3);
    else if (verse === 5) pairs.forEach(pair => {pair.extra_storage_case = [true, 1, null];});
    else pairs[0].date_assessments = ["2"];
    row.reported_coverage = pairs;
    add(`Gal.4.${verse}`, row);
  }
  const phase3 = JSON.parse(readFileSync(join(__dirname, "fixtures", "explorer-sparse.phase3.json"), "utf8"));
  return {normalized, phase3};
}

module.exports = {transferFixture, sparseFixture};
