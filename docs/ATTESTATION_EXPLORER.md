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

## Browser format

Both `build_collection.py` and `collect_source_discovery.py` call
`browser_format.pack_browser_data()` to write version 4. The source register,
reference inventory, discovery register and captured reports remain the collection
of record. The app file is a derived view, with these unused fields omitted:

- Documents retain only witness IDs and display labels; identity reports,
  hashes and capture status remain in the source collection.
- Source snapshots retain response IDs, canonical links and query parameters,
  retrieval dates and hashes for the app's citation panel. Local transport URLs,
  endpoint bookkeeping and capture paths are omitted when a canonical URL exists.
- Metadata omits batch/build identifiers and detailed discovery candidate records;
  displayed scope definitions, candidate lists, qualifications and states remain.

All content claims, exact reported fields, qualifications, citations, retrieval
information, complete date alternatives, coverage pairs, discovery states and
ranking events are retained. Shared provider names are referenced by ID. Standard
NTVMR index claims use numeric columns for claim ID, context ID, reference ID,
page ID and locator index. References link coordinate IDs to the exact reported
content code. Other claim shapes retain literal records. Repeated ranking events
are stored once and linked by numeric IDs.

Coverage uses context IDs, claim counts and ordered claim IDs, plus exact dense
vectors or sparse overrides for each stored coordinate. Numeric sequences use
plain arrays, arithmetic runs, or cumulative deltas, whichever is smaller. These
encodings restore existing integers exactly; they do not infer verse ranges or
assertions. Missing observations remain uncollected.

The detailed storage contract is in [browser_format.py](../browser_format.py),
with the runtime reader in
[collection-format.js](../web/attestation-explorer/collection-format.js).
The older lossless v3 packer in `report_explorer.py` remains an intermediate and
compatibility API; it is not the production file writer.

## Runtime

Fetch and the local file picker accept versions 1–4. The version 4 store validates
all tables and references, decodes numeric columns into private typed arrays,
and caches coverage totals once. Drawing does not expand the witness/verse matrix
or millions of claims. Chart events and display records are read-only. Selected
observations are resolved on demand, with at most one full observation and 4,096
standard index claims cached. Date-choice state lives in the model.

`createDataStore(raw)` exposes `hasObservation(ref)`, `summary(ref)`,
`chartAlternatives(ref)`, `claim(id)`, `date(id)`, and `observation(ref)`.
`model.data` contains coordinates, display documents, source snapshots and ordinary
metadata. `createModel()` and `mount()` accept an existing store or model.

The explicit `expandData()` and Python `expand_explorer_data()` APIs restore a
mutable normalized view. For version 4 this is the browser projection described
above, not the omitted collection bookkeeping. Full expansion is for bounded
consumers and tests; the app never requests it on load.

## Verification

Use `npm test` for loading, failures/retry, local file fallback, navigation,
endpoint selection, discovery, date alternatives, and chart geometry.
Python tests cover source fidelity, mappings, deduplication, ranking, uncertainty,
deterministic builds, and updates that leave the app assets untouched.
No local server or live source request is required for these checks.
