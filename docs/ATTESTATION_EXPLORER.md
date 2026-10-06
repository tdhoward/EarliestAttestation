# Attestation Explorer

The app lives in `web/attestation-explorer/`. `index.html` loads `explorer.css`,
`explorer.js`, and `app.js` as ordinary assets. `app.js` requests the single
`data/attestations.json` file with browser caching disabled for that request.
Data updates do not modify or generate HTML.

## Open and update

Run `npm start` yourself, then open
<http://localhost:8000/web/attestation-explorer/>. Any static server serving the
repository with the same relative paths also works. No Python service or database
is needed by the browser. A static deployment needs only this app directory and
`data/attestations.json`, preserving their relative layout; include `data/sources/`
and `data/reference/` when distributing the source collection too.

Opening `index.html` directly is also supported through a local JSON file picker
when automatic loading is blocked. Choose `data/attestations.json`. A failed or
malformed load displays a retry option; it never appears as an empty collection.

`python build_collection.py` rebuilds only the current data file from
`data/collection.json`, source captures, discovery records, and the coordinate
inventory. The normalization database exists only in a temporary directory and
is removed when the build finishes. Output replacement is atomic. A validation
failure leaves the previous app data intact.

## Controls and meaning

- Optimistic and pessimistic scenarios rank lower and upper date endpoints
  independently, with a shared year scale and witness-count colors.
- Book navigation, verse entry, zoom, horizontal scrolling, pointer selection,
  touch, and keyboard arrows navigate one canonical New Testament timeline.
- Hold a verse to inspect its reported contents, full date intervals, qualifiers,
  exact claim fields, and source citations.
- Date alternatives remain complete, equally valid intervals. Select alternatives
  on demand; per-verse combination overflow stays visible and unranked.
- Uncollected coordinates, unknown witness reports, explicit absences, contested
  reports, and filtered coordinates remain distinct.
- Discovery is assessed independently by book and catalogue range. More graphed
  verses or a completed bounded query does not establish exhaustive discovery.

`report_explorer.py` compacts normalized graph data into shared claim/date tables
and per-verse observations. The version 2 JSON transfer format additionally
stores identical coverage and discovery records once and splits each claim into
a shared provenance context plus its remaining exact fields. References are
zero-based indices into `coverage_records`, `discovery_records`, and
`claim_contexts`. The loader rejects invalid indices and conflicting claim
fields, then restores the version 1 normalized structure for the chart model.
This retains every unknown pair, qualification, reported object, citation, date
alternative, and precomputed event. Previous version 1 files remain readable.
Observations are independent after expansion, despite shared transfer records.

The current 17-witness transfer file is 12.5 MB, compared with 39.6 MB expanded.
The browser uses the computed events without reinterpreting sources. Raw reports
stay in the central source directory; collection updates change only the data.

## Verification

Use `npm test` for loading, failures/retry, local file fallback, navigation,
endpoint selection, discovery, date alternatives, and chart geometry.
Python tests cover source fidelity, mappings, deduplication, ranking, uncertainty,
deterministic builds, and updates that leave the app assets untouched.
No local server or live source request is required for these checks.
