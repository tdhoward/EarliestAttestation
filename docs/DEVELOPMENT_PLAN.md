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

The current register reuses retained reports for 25 witnesses across all 27
books. Default data contains 7,941 reference coordinates,
7,928 graphable coordinates, 16,783 present witness/verse pairs, 181,742 unknown
pairs, and no absent or contested pairs. Thirteen coordinates have no exact
reported match and remain unknown. Sixteen supplementary omitted coordinates,
including Romans 16:24, remain in the underlying reference scope.

Galatians, Hebrews, Ephesians, Philippians, Colossians, 1 Thessalonians,
2 Thessalonians, 1 Timothy, 2 Timothy, Titus, and Philemon have completed
independent indexed searches within IDs 10000–19999; the other books and
catalogue ranges do not gain discovery
completion merely through document reuse. Multiple bounded scopes can coexist
in the central discovery register. All rankings describe collected witnesses only.

The Hebrews pilot found ten candidates and collected nine new witnesses while
reusing P46. It used 19 successful proxy requests after six unsuccessful direct
attempts, staying within its 25-attempt budget. The new reports add 163 presence
pairs. Canonical NTVMR URLs supply citations; the owner-supplied local proxy is
an access route. TLS verification is not a prerequisite for source collection.

The Ephesians search found P46, P49, P92, and P132, reused P46, and collected the
other three witnesses. Their reports add 45 presence pairs: 41 in Ephesians and
four in 2 Thessalonians. That reuse alone did not complete 2 Thessalonians discovery.
The run used seven successful proxy requests and three sandbox-denied attempts,
within its declared 25-attempt budget. Every prior claim, date alternative, and
witness/verse state survived the addition unchanged.

The independent 2 Thessalonians search returned P30 and P92, reused P92, and
collected P30's metadata and long contents. The report adds 21 presence pairs:
two in 2 Thessalonians and 19 in 1 Thessalonians. The catalogue's complete P30
date estimate remains 200–299 CE (`E II - A III`). Three successful proxy
requests and three sandbox-denied attempts used six of the declared 25 attempts.
That report reuse did not complete independent 1 Thessalonians discovery.

The independent 1 Thessalonians search returned P30, P46, P61, and P65. It reused
P30 and P46 and collected metadata and long contents for P61 and P65 using five
successful proxy requests within its 25-attempt budget. The new reports add 73
default presence pairs: 19 in 1 Thessalonians and 54 across Romans, 1 Corinthians,
Philippians, Colossians, Titus, and Philemon. P61 also explicitly reports the
supplementary Romans 16:24 coordinate. Complete catalogue dates remain 700–725 CE
(`VIII (A)`) for P61 and 200–299 CE (`III`) for P65. Existing claims, date
alternatives, coverage states, and other discovery scopes survived unchanged.
Those other-book reports did not establish independent discovery completion.

The independent Philippians search returned P16, P46, and P61. It reused P46
and P61 and collected P16's metadata and long contents with three successful
requests. Three earlier sandbox-denied attempts received no provider response;
all six attempts fit the declared 25-attempt budget. P16 adds 15 presence pairs
from exact reported entries for Philippians 3:10–17 and 4:2–8, with indexing tier 3.
Its catalogue fields retain numeric bounds 200–399 CE and notation `IV` exactly,
without converting or reconciling them. Missing entries remain unknown. Every
prior claim, date alternative, coverage state, and other discovery scope survived.
That addition increased app data by 12,317 bytes; no new storage or mapping
infrastructure was needed.

The independent Colossians search returned P46 and P61 and reused both witnesses'
metadata and long contents. It used one successful proxy request and three
sandbox-denied attempts with no provider response, within its 25-attempt budget.
All prior claims, complete date alternatives, coverage states, and rankings
remain unchanged. Only the 95 Colossians coordinates gain bounded discovery
completion; other scopes remain unchanged and wider catalogue discovery remains
incomplete. That search retained 49 usable responses for 21 witnesses, with no
pending candidates in seven completed scopes. App data was 2,060,609 bytes,
growing by 4,702 bytes for the search provenance and discovery state.

The independent Philemon search returned P61, P87, and P139. It reused P61 and
collected metadata and long contents for the other two with five successful
proxy requests within its 25-attempt budget. Exact entries add five presence
pairs for P87 (1:13–15, 24–25) and six for P139 (1:6–8, 18–20). Complete catalogue
date estimates remain 200–299 CE (`III`) and 300–399 CE (`IV`), respectively.
Missing entries remain unknown. All prior claims, complete dates, coverage
states, and discovery scopes survived unchanged. That addition brought the collection to
54 usable responses for 23 witnesses and eight completed scopes, with no pending
candidates. App data was 2,076,312 bytes, growing by 15,703 bytes for this addition.

The independent Titus search returned P32 and P61. It reused P61 and collected
P32's metadata and long contents with three successful proxy requests within a
25-attempt budget. Exact entries add 11 presence pairs for Titus 1:11–15 and
2:3–8, with indexing tier 3. The complete catalogue date estimate remains
200–225 CE (`III (A)`). Missing entries remain unknown. All prior claims, complete
dates, coverage states, rankings outside the added coverage, and discovery scopes
survived unchanged. Only the 46 Titus coordinates gain bounded discovery completion.
That addition brought the collection to 57 usable responses for 24 witnesses and
nine completed scopes, with no pending candidates. App data was 2,085,991 bytes,
growing by 9,679 bytes for this addition.

The independent 2 Timothy search returned no indexed candidates within
IDs 10000–19999, using one successful proxy request within a 25-attempt budget.
Only its 83 coordinates gain bounded discovery completion. A terminal empty
index does not assert manuscript absence or complete wider catalogue discovery.

The independent 1 Timothy search returned P133 and collected its metadata and
long contents with three successful proxy requests within a separate 25-attempt
budget. Exact entries add 12 presence pairs for 1 Timothy 3:13–16 and 4:1–8,
with indexing tier 3 and complete catalogue date 200–299 CE (`III`). Two page
reports for 4:3 are preserved as two claims and count as one witness/verse pair.
Missing entries remain unknown. Existing claims, dates, coverage states, rankings
outside the added coverage, and other discovery scopes survive unchanged.
Together these searches add bounded completion to 196 coordinates. The current
collection retains 61 usable reports for 25 witnesses and eleven completed
scopes, with no pending candidates. App data is 2,099,555 bytes, growing by
13,564 bytes across the two additions.

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
   A useful next scope is Jude within IDs 10000–19999, searching for candidates
   independently and reusing any retained reports for returned witnesses.
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
