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

The current JSON is approximately 12.5 MB (11.9 MiB). Lossless version 2 storage
shares repeated coverage, discovery, and claim provenance records, reducing the
17-witness expanded payload from 39.6 MB by 68.5%. The browser restores the same
normalized data before charting; earlier version 1 files remain supported.
An offline Node check parsed the file in 105 ms, expanded it in 126 ms, constructed
the chart model in 20 ms, and evaluated the full axis in 10 ms on this workstation.
The expanded result matched the complete pre-packing dataset. These are local
measurements, not browser or network benchmarks. Browser memory usage remains
unmeasured; restored unknown pairs still scale with witnesses and coordinates.

Phases 0 and 1 of the [data size optimization guide](DATA_SIZE_OPTIMIZATION.md)
are complete. The offline current build exactly matches its normalized expansion;
full-size work-session baselines stay in ignored cache storage. Shared fictional
version 1 expected fixtures and frozen version 2 snapshots now check Python and
Node decoding, source fields, coverage states, complete date choices, ties,
mapping gaps, filters, missing observations, and empty exports. Python-to-Node
packing is compared directly with the independent normalized fixture. Phase 1's
private `"3-phase1"` candidate shares rankings and observation metadata while
retaining dense version 2 coverage and claim records. It measures 6,391,574 bytes
(48.77% below current version 2), with 28 ranking templates and 37 observation
contexts. Python and Node restore every field exactly to the fresh build and
Phase 0 baseline; both scenarios match across all 7,957 chart coordinates.
The production writer and dataset remain on version 2, with a matching candidate
decoder available in the app. Work stopped at Phase 1 at the owner's request;
phases 2–6, including writer rollout and runtime sharing, are pending.

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
   When authorized, continue at Phase 2 of the
   [data size and memory optimization guide](DATA_SIZE_OPTIMIZATION.md) for
   transfer-format, runtime-sharing, and compression work with focused offline
   checks. Phases 0–1 are complete; the current work authorization stops at Phase 1.

## Acceptance

- New collection appears in the existing app after refreshing its data file.
- Existing books, witnesses, citations, qualifications, and date alternatives
  survive additions without duplicate witness counts or inferred adjacent coverage.
- Every active claim is attributable to a scholarly source. Explicit disagreement
  is retained and deferred; missing information remains unknown.
- Discovery completeness is scoped independently of coverage and rankability.
- Offline source, normalization, data-loading, and chart tests pass. No manuscript
  examination, local server launch, or live request is part of routine verification.
