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
`browser_format.pack_browser_data()` to write version 5. The source register,
reference inventory, discovery register and captured reports remain the collection
of record. The app file is a derived view, with these unused fields omitted:

- Documents retain only witness IDs and display labels; identity reports,
  hashes and capture status remain in the source collection.
- Source snapshots retain response IDs, canonical links and query parameters,
  retrieval dates and hashes for the app's citation panel. Local transport URLs,
  endpoint bookkeeping and capture paths are omitted when a canonical URL exists.
- Coordinates are reference strings. A small `coordinate_statuses` map records
  exceptions to the ordinary `main` status, including omitted and bracketed verses.
- Metadata omits batch/build identifiers, collection costs and the discovery
  audit tree. `discovery_summary` retains per-book search states, distinct candidate,
  pending, eligible and excluded counts, catalogue qualifications and date cutoffs.
  Counts are unions across overlapping scopes, not sums. Full scope definitions,
  candidate IDs, search citations and captures remain in `data/discovery.json`.
  Per-observation discovery records retain state and ranking-scope qualifications.

All content claims, exact reported fields, qualifications, citations, retrieval
information, complete date alternatives, coverage pairs, discovery states and
ranking events are retained. Shared provider names are referenced by ID. Standard
NTVMR index claims use numeric columns for claim ID, context ID, reference ID,
page ID and locator index. References link coordinate IDs to the exact reported
content code. Other claim shapes retain literal records. Repeated ranking events
are stored once and linked by numeric IDs. Ranking combinations omit assessment
IDs for witnesses with exactly one valid date: those IDs cannot constrain the date
selector. Every date record, competing choice, eligible-witness count and ranking
event is retained. Newly identical ranking/discovery templates are shared again.
Observation fields with frequent identical values use explicit defaults.

Coverage uses context IDs, claim counts and ordered claim IDs, plus exact dense
vectors or sparse overrides for each stored coordinate. Numeric sequences use
plain arrays, arithmetic runs, cumulative deltas, or base64 signed varints,
whichever is smaller. A run `[start, step, count]` describes arithmetic repetition;
deltas describe successive integer differences. Varints use zigzag encoding of
signed 32-bit integers, with the decoded count stored alongside the base64 string.
Larger safe integers use the other forms. Coverage claim IDs can use differences
from the previous stored ID with the same exact coverage context, which compresses
interleaved witness reports well. These encodings restore existing integers exactly;
they do not infer verse ranges or assertions. Missing observations remain uncollected.
The 7,941 observation entries are needed: each connects a collected coordinate to
its ranking/discovery context and its exact coverage vector or sparse overrides.

The detailed storage contract is in [browser_format.py](../browser_format.py),
with the runtime reader in
[collection-format.js](../web/attestation-explorer/collection-format.js).
The older lossless v3 packer in `report_explorer.py` remains an intermediate and
compatibility API; it is not the production file writer.

## Runtime

Fetch and the local file picker accept versions 1–5. The version 4/5 store validates
all tables and references, decodes numeric columns into private typed arrays using
the narrowest safe element width (8, 16, 32 or 64 bits),
and caches coverage totals once. Drawing does not expand the witness/verse matrix
or millions of claims. Coverage offsets replace lengths after validation. Chart
events are shared across templates, and display records are read-only. Selected
observations are resolved on demand, with at most one full observation and 4,096
standard index claims cached. Date-choice state lives in the model.

`createDataStore(raw)` exposes `hasObservation(ref)`, `summary(ref)`,
`chartAlternatives(ref)`, `claim(id)`, `date(id)`, and `observation(ref)`.
`model.data` contains coordinates, display documents, source snapshots and ordinary
metadata. `createModel()` and `mount()` accept an existing store or model.

The explicit `expandData()` and Python `expand_explorer_data()` APIs restore a
mutable normalized view. For version 5 this is the browser projection described
above, not the omitted collection bookkeeping. Full expansion is for bounded
consumers and tests; the app never requests it on load.

The current 2,351-witness collection occupies 21,246,486 bytes (previously
44,236,579). The largest reduction is coverage linkage: 21.90 MB to 6.84 MB.
Observations occupy 3.67 MB (previously 5.28 MB); ranking templates 0.61 MB
(previously 5.45 MB). An offline Node/V8 measurement after creating the model,
evaluating the full chart and collecting garbage retained about 122 MB of heap
plus array buffers, versus 320 MB before. Typed buffers account for 76.65 MB,
versus 219.38 MB before. These measurements exclude DOM/browser overhead and
are not a browser process-memory guarantee. Source records and chart results
were compared against the previous file without expanding the full coverage matrix.

## Verification

Use `npm test` for loading, failures/retry, local file fallback, navigation,
endpoint selection, discovery, date alternatives, and chart geometry.
Python tests cover source fidelity, mappings, deduplication, ranking, uncertainty,
deterministic builds, and updates that leave the app assets untouched.
No local server or live source request is required for these checks.
