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

The app uses a lossless version 3 JSON format with shared records and exact
sparse coverage. It validates and retains read-only data for charting, resolving
complete observations for selection and source details. Older version 1/2 files
remain supported. See [the explorer documentation](ATTESTATION_EXPLORER.md) for
loading and runtime behavior; the storage contract lives in `report_explorer.py`.
Offline tests cover exact Python/JavaScript restoration, source fidelity,
coverage states, date alternatives, chart behavior, and deterministic updates.

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

## Acceptance

- New collection appears in the existing app after refreshing its data file.
- Existing books, witnesses, citations, qualifications, and date alternatives
  survive additions without duplicate witness counts or inferred adjacent coverage.
- Every active claim is attributable to a scholarly source. Explicit disagreement
  is retained and deferred; missing information remains unknown.
- Discovery completeness is scoped independently of coverage and rankability.
- Offline source, normalization, data-loading, and chart tests pass. No manuscript
  examination, local server launch, or live request is part of routine verification.
