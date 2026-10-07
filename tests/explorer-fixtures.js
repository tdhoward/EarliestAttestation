const {readFileSync} = require("node:fs");
const {join} = require("node:path");

// Read fresh copies so model selections and malformed-input tests stay isolated.
// Version 1 is the expected oracle; version 2 and candidates are codec snapshots.
function transferFixture(name = "explorer-normalized") {
  const read = version => JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.v${version}.json`), "utf8"));
  const phase1 = JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.phase1.json`), "utf8"));
  const phase2 = JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.phase2.json`), "utf8"));
  return {normalized: read(1), packed: read(2), phase1, phase2};
}

module.exports = {transferFixture};
