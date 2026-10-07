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

`report_explorer.py` writes the lossless version 3 JSON transfer format. It stores
shared claim provenance, coverage contexts, discovery records, ranking templates,
and observation contexts once, with zero-based table indices. Eligible index
claims use reversible tagged tuples; other claims retain complete literal details.
Coverage uses ordered exact defaults and sparse exceptions where they save space,
with dense fallback for other observations. A coordinate without an observation
stays uncollected. See [the format contract](DATA_SIZE_OPTIMIZATION.md#code-ownership-and-intended-design)
for tuple positions, tags, and tables.

Both decoders retain version 1 and 2 support. The loader rejects malformed tuples,
invalid indices, dangling claim references, and conflicting claim fields, then
restores the version 1 normalized structure for the chart model. This retains every
unknown pair, qualification, reported object, citation, complete date alternative,
and precomputed event. Expanded version 3 observations and their nested values
are independently mutable, despite shared transfer records.

The current 17-witness file is **2,007,743 bytes** (about 2.01 MB), compared with
12,476,223 bytes in version 2 and 39,599,390 bytes normalized, including final
newlines. This is an **83.91%** reduction from version 2. The browser still eagerly
expands the file; runtime memory sharing and HTTP compression are pending phases
5 and 6. Browser memory remains unmeasured. The browser uses the computed events
without reinterpreting sources. Raw reports stay in the central source directory;
collection updates change only the data.

## Verification

Use `npm test` for loading, failures/retry, local file fallback, navigation,
endpoint selection, discovery, date alternatives, and chart geometry.
Python tests cover source fidelity, mappings, deduplication, ranking, uncertainty,
deterministic builds, and updates that leave the app assets untouched.
No local server or live source request is required for these checks.
