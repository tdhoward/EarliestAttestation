# Explorer regression fixtures

`explorer-normalized.v1.json` is an independently specified fictional oracle.
It covers duplicate reports, present/absent/unknown/contested states, missing and
filtered observations, tied dates, complete alternative intervals, combination
overflow, subset event claim lists, qualifications, Unicode, and JSON types.
`explorer-empty.v1.json` covers an empty collection with a navigable axis.

The matching v2/v3 and phase1/phase2/phase3 files are frozen compatibility
snapshots. Do not regenerate them with a newer writer. The sparse variants extend
the fictional oracle with repeated observations, reordered and duplicate witness
identities, different date applicability, dense fallback and sparse overrides.
`sparse_fixture()` in Python and `sparseFixture()` in JavaScript independently
construct the expected normalized values without using a codec.

Version 4 tests pack these oracles with the production writer and compare both
Python and JavaScript decoders with the projected expected records. Tests check
source fields, dates, coverage totals, rankings, alternative selection, numeric
sequence encodings, malformed references, mutation isolation and lazy decoding.

`collection-pilot.json` fixes the register and discovery inputs for the original
25-witness pilot. It references retained captures in `data/sources/`.
`explorer-pilot.v4.json` is its bounded browser fixture, rebuilt and compared with
those inputs by collection tests. These fixtures keep historical regression cases
stable as the production corpus grows. Browser tests must not expand and clone
the user's multi-million-claim `data/attestations.json`.

Full-current-collection audits and temporary measurements belong in ignored
`data/.cache/`. Test fixtures are not alternate product datasets.
