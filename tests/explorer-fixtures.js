const {readFileSync} = require("node:fs");
const {join} = require("node:path");

// Read fresh copies so model selections and malformed-input tests stay isolated.
// The version 1 file is the expected oracle; version 2 is a retained snapshot.
function transferFixture(name = "explorer-normalized") {
  const read = version => JSON.parse(readFileSync(join(__dirname, "fixtures", `${name}.v${version}.json`), "utf8"));
  return {normalized: read(1), packed: read(2)};
}

module.exports = {transferFixture};
