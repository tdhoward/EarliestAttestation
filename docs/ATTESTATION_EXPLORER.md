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

Both decoders retain version 1 and 2 support. Fetch and the file picker return a
validated, read-only store, checking the complete reference graph, including unused
tables, without expanding the coverage matrix. The chart uses shared precomputed
events, retaining their order, ranks, years, witnesses, and assessment choices.
Event claim lists are resolved only in the selected full observation. Every unknown
pair, qualification, reported object, citation, and complete date alternative survives.
The explicit `expandData()` API still restores independently mutable version 1
data for all supported inputs.

`createDataStore(raw)` takes ownership of parsed JSON and deeply freezes its records.
Its `hasObservation(ref)`, `summary(ref)`, `chartAlternatives(ref)`, `claim(id)`,
`date(id)`, and `observation(ref)` accessors separate drawing from source details.
The store retains at most one resolved observation and caches claims by unique ID.
Date-choice state stays in the model's separate selection map. `model.data` contains
ordinary collection metadata, coordinates, documents, and sources, excluding
encoded tables and the observation/claim/date lookups; use `model.store` for those
records. `cell()` returns the coordinate reference, state, shared chart events,
and applicable contested flag; it no longer contains a full observation.
`createModel()` and `mount()` accept an existing validated store or model so loading
does not construct the model twice.

The current 17-witness file is **2,007,743 bytes** (about 2.01 MB), compared with
12,476,223 bytes in version 2 and 39,599,390 bytes normalized, including final
newlines. This is an **83.91%** reduction from version 2. Phase 5 retains shared data
in the running app; five isolated Node runs per path measured median retained heap
after repeated selection at **16.72 MB**, compared with **66.99 MB** for full
expansion on the same revision. See the [measurement method and results](DATA_SIZE_OPTIMIZATION.md#phase-5-retain-shared-data-in-the-running-app).
Phase 6's offline audit measured **305,645 bytes** with gzip level 9 and verified
exact byte restoration. Deployment activation remains pending because no hosting
configuration exists in the repository; browser memory remains unmeasured.
The browser uses the computed events
without reinterpreting sources. Raw reports stay in the central source directory;
collection updates change only the data.

## Hosting compression

Enable gzip or Brotli for JSON through the deployment host or proxy while keeping
`data/attestations.json` at the same relative URL with `Content-Type: application/json`.
Compressed responses need the matching `Content-Encoding: gzip` or `br`; negotiated
responses need `Vary: Accept-Encoding`. Uncompressed responses omit
`Content-Encoding`. Verify actual response headers and exact decompressed JSON
bytes when an authorized deployment is available. See the
[hosting contract and offline measurement command](DATA_SIZE_OPTIMIZATION.md#phase-6-transport-compression-where-deployment-supports-it).

The browser continues to use `response.json()` and the JSON file picker.
`data/attestations.json` remains ordinary JSON; compression belongs to delivery
at the host. The existing `npm start` command uses Python's simple static server
and does not enable HTTP compression. Offline gzip measurements do not establish
that any deployment serves compressed data.

## Verification

Use `npm test` for loading, failures/retry, local file fallback, navigation,
endpoint selection, discovery, date alternatives, and chart geometry.
Python tests cover source fidelity, mappings, deduplication, ranking, uncertainty,
deterministic builds, and updates that leave the app assets untouched.
No local server or live source request is required for these checks.
