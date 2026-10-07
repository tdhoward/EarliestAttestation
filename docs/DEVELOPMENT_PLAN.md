# Development plan

## Product and working structure

Maintain one central collection in `data/` and one app in
`web/attestation-explorer/`. Data collection updates the existing registers and
`data/attestations.json`; the HTML/JS/CSS remain independent of the dataset.
Do not create book-specific charts, numbered dataset revisions, milestone reports,
or permanent replay databases. Use ignored `data/.cache/` for temporary work.
Source attribution belongs with the data; software history belongs in Git.

The project collects explicit scholarly reports of Greek NT manuscript contents
and dates. It does not perform manuscript scholarship. Follow [AGENTS.md](../AGENTS.md)
and the [source contract](NTVMR_SOURCE_REPORT_CONTRACT.md). Unknown, contested,
reported-absent, uncollected, and filtered states must stay distinct. Preserve
complete date alternatives and count any reported portion once per witness.

## Current implementation

The current register reuses retained reports for 17 witnesses across all 27
books. Default data contains 7,941 reference coordinates,
7,928 graphable coordinates, 16,640 present witness/verse pairs, 118,357 unknown
pairs, and no absent or contested pairs. Thirteen coordinates have no exact
reported match and remain unknown. Sixteen supplementary omitted coordinates,
including Romans 16:24, remain in the underlying reference scope.

Galatians, Hebrews, and Ephesians have completed independent indexed searches within IDs 10000–19999;
the other books and catalogue ranges do not gain discovery completion merely
through document reuse. Multiple bounded scopes can coexist in the central
discovery register. All rankings describe collected witnesses only.

The Hebrews pilot found ten candidates and collected nine new witnesses while
reusing P46. It used 19 successful proxy requests after six unsuccessful direct
attempts, staying within its 25-attempt budget. The new reports add 163 presence
pairs. Canonical NTVMR URLs supply citations; the owner-supplied local proxy is
an access route. TLS verification is not a prerequisite for source collection.

The Ephesians search found P46, P49, P92, and P132, reused P46, and collected the
other three witnesses. Their reports add 45 presence pairs: 41 in Ephesians and
four in 2 Thessalonians. Reuse does not complete discovery for 2 Thessalonians.
The run used seven successful proxy requests and three sandbox-denied attempts,
within its declared 25-attempt budget. Every prior claim, date alternative, and
witness/verse state survived the addition unchanged.

The current JSON is **2,007,743 bytes** (about 2.01 MB), down **83.91%** from
12,476,223 bytes in version 2. The lossless version 3 transfer shares claim and
coverage contexts, discovery records, ranking templates, and observation metadata;
coverage uses exact defaults with sparse exceptions or dense fallback. The
17-witness normalized payload remains 39,599,390 bytes. All sizes include final
newlines. The browser validates and retains shared read-only tables for charting,
resolving full observations only for selection and source details. Versions 1 and
2 remain supported through fetch and the file picker; the full-expansion API
retains independently mutable normalized data. Browser memory is unmeasured.

Phases 0–5 of the [data size optimization guide](DATA_SIZE_OPTIMIZATION.md) are
complete. The production writer and dataset now use numeric version 3, while
private Phase 1/2/3 candidates remain available for offline compatibility checks.
The complete current output restores every field exactly in Python and Node,
matching the fresh offline build and the Phase 0 normalized baseline. Both chart
scenarios match across all 7,957 coordinates, including observations, events,
count bands, discovery, and scale bounds. Two fresh builds produce identical
bytes. Full-size work-session comparisons stay in ignored cache storage.

Shared fictional version 1 oracles and version 2/3 snapshots check both languages,
source fields, coverage states, complete date choices, ties, mapping gaps, filters,
missing observations, empty exports, and dense/sparse coverage. Rollout checks
cover deterministic refresh, current/stale `--check`, failures preserving previous
data, unchanged app assets, fixture-based collector output, and malformed loading
with retry. Phase 5 validates unused table records and claim/date references before
mounting, evaluates the chart without decoding coverage pairs, shares precomputed
read-only events, and caches at most one complete observation. Loading reuses the
validated model. All selected observations and source fields match the independent
normalized baseline exactly; both chart scenarios match the previous model across
all 7,957 coordinates. Offline DOM tests preserve displayed source text across
versions 1/2/3.

Five isolated Node processes per path, with the same input, warm-up and explicit
GC procedure, measured median retained heap after 2,000 selections at **16.72 MB**
for shared runtime data versus **66.99 MB** for full expansion on the same revision:
a **75.04%** reduction. The guide records parse/model/chart/selection measurements
and practical limits; these are not browser or peak-memory benchmarks. Work stops
at Phase 5 at the owner's request. HTTP compression (Phase 6) remains pending.
Both build `--check` commands, all **134 Python tests**, all **37 Node tests**,
and the final focused runtime checks passed offline.

The data builder validates raw hashes, provenance, mappings, identity, complete
date intervals, and derived results in a fresh temporary SQLite database. Builds
are offline and replace one current JSON file. The app requests that file on load.
The request collector retains budget/resume checkpoints in ignored cache storage.
Older review-table code remains a compatibility implementation, outside the app's
scholarly-report path; its judgments are never admitted as scholarly assertions.

## Next development work

1. Broaden bounded independent witness discovery. Declare a book/range and request
   budget; reuse each document's metadata and contents; update the central register.
   Do not constrain discovery to the witnesses already collected for nearby verses.
   A useful next scope is 2 Thessalonians within IDs 10000–19999, reusing P92's
   newly retained reports while searching for candidates independently.
2. Establish provider access expectations before bulk collection. Use the
   owner-supplied local proxy when direct access is unavailable; cite canonical
   NTVMR endpoints. Preserve blocked states, honor limits, and do not change
   routes or identities to bypass a provider block.
3. Extend supported mappings and source-reported date applicability only when
   required by collected data. Keep ambiguous mappings and claims visible; do not
   infer them from manuscript examination.
4. Keep collection efficient and the app usable as the dataset grows. Measure
   witnesses, usable reports, graphable coordinates, unresolved records, request
   cost, and browser data size. Prefer concrete bottlenecks over new infrastructure.
   Phases 0–5 of the [data size and memory optimization guide](DATA_SIZE_OPTIMIZATION.md)
   are complete; the current work authorization stops at Phase 5. When separately
   authorized, continue with Phase 6's deployment compression where supported.

## Acceptance

- New collection appears in the existing app after refreshing its data file.
- Existing books, witnesses, citations, qualifications, and date alternatives
  survive additions without duplicate witness counts or inferred adjacent coverage.
- Every active claim is attributable to a scholarly source. Explicit disagreement
  is retained and deferred; missing information remains unknown.
- Discovery completeness is scoped independently of coverage and rankability.
- Offline source, normalization, data-loading, and chart tests pass. No manuscript
  examination, local server launch, or live request is part of routine verification.
