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
inventory. Temporary records and the normalization database live under ignored
`data/.cache/` and are removed when the build finishes or fails. Output replacement
is atomic. A validation or memory allocation failure leaves the previous app data
intact.

The production path spools extracted claims, hashes them incrementally, and packs
one verse's coverage at a time. It retains compact tables and integer vectors,
without retaining the full witness/verse object matrix or copying it through
historical export formats. Both production writers use `build_browser_data()`;
`refresh()` returns its packed version-5 data. Normalized `build_data()` and full
expansion helpers are for bounded fixtures (at most 1,000,000 pairs).
The final integer encoder uses native numeric buffers, compares candidate JSON
sizes without serializing them, and releases consumed tables before the next
stage. A memory regression test covers a million irregular integers in a
160 MiB process budget, including exact round-trip verification.

`python build_collection.py --check` runs the same build and compares the packed
result with the current file. The default memory ceiling is 2048 MiB, configurable
with `--memory-limit-mb`; failure to install the OS limit stops the build.
Windows limits committed process memory; Unix limits virtual address space.
The command reports peak committed bytes on Windows and lifetime peak resident
bytes on Unix. These are build-process measurements, separate from browser usage.
Documentation edits and the current scoped source checks do not require this
full build. First-five review targets can be selected from the existing compact
rankings across both date modes and retained alternatives with
`python source_checks.py --first-five`; `--queue-first-five` appends uncovered
scopes to the checking register. See the [source corroboration work](SOURCE_CORROBORATION_PLAN.md). Rebuild
when registered claims or output behavior change, not merely to select targets
or measure checking progress.

Scoped index limitations retain the exact raw entry with unknown admission,
an explanation, and links to the retained scholarly assertion. Explicit published
omissions determine coverage for the corrected John cases, while compatible
presence reports for Bezae count once. These details appear in the existing source
drawer and agree with the counts and first-five rankings. Full check history and
pending work remain in the checking register.

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
`pipeline.browser_format.pack_browser_data()` to write version 5. The source register,
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
  Empty catalogue reports can complete eligible collection while their verse
  contents remain unknown. Completion does not establish exhaustive coverage.

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
Each observation entry connects a collected coordinate to
its ranking/discovery context and its exact coverage vector or sparse overrides.

The detailed storage contract is in [browser_format.py](../pipeline/browser_format.py),
with the runtime reader in
[collection-format.js](../web/attestation-explorer/collection-format.js).
The older lossless v3 packer in `pipeline/report_explorer.py` remains an intermediate and
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

## Measured resource use

The current version-5 file is 24,032,638 bytes. An offline Node/V8 measurement
retained 116,797,123 bytes (about 117 MB) of heap plus array buffers after creating
the model, evaluating both endpoint charts across the full axis, and collecting
garbage. DOM/browser overhead is additional; this is not a browser process-memory
guarantee. Source-record comparisons and chart checks avoid expanding the full
witness/verse matrix. Production checks cover all 15,914 book/verse chart cells.

The scoped-correction production build measured on 2026-10-09 took 1,115.83 seconds
and peaked at 2,115,858,432 bytes (2,017.8 MiB) of Windows committed process memory,
under the 2,048 MiB ceiling. It made zero network requests and removed temporary
records and its database. Complete dates, the coordinate axis, and rankings outside
the twelve corrected John verses matched the preceding data. These measurements
apply to that snapshot; the ceiling remains enforced as the collection grows.

## Verification

Use `npm test` for loading, failures/retry, local file fallback, navigation,
endpoint selection, discovery, date alternatives, and chart geometry.
Python tests cover source fidelity, mappings, deduplication, ranking, uncertainty,
deterministic builds, and updates that leave the app assets untouched.
No local server or live source request is required for these checks.
