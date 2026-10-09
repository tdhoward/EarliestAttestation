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

The central register contains 2,584 witnesses and 5,167 registered metadata and
contents reports across all 27 books. The app projects 4,475 source snapshots
referenced by displayed evidence. Its 7,941 graphable coordinates have 2,565,074
reported-present witness/verse pairs and 17,954,470 unknown pairs, with no registered
reported absences or source disagreements. These are current export counts, not
independent content validation. The [source corroboration plan](SOURCE_CORROBORATION_PLAN.md#purpose-and-present-limitation)
records a known discrepancy for John 7:53–8:11 that is not yet reflected in the app.

The retained catalogue campaign completed all four inventories and capture after
5,123 request attempts. Its 6,199 distinct candidates include 1,323 eligible and
4,876 date-excluded candidates under the declared earliest-date-before-1000 CE
scope. Offline import resolved all 705 previously pending eligible candidates;
none remain pending. All 27 books record completion of this bounded scope. The
11 earlier book-search records are preserved. This is completion of the declared
snapshot, not exhaustive manuscript-corpus discovery.

The importer accepts the retained empty-string contents reports, integer date
notations, explicit multilingual Greek catalogue codes, and mixed-book reports.
Empty contents remain unknown; only explicit NT verse entries establish presence.
Raw reports and exact date endpoints remain unchanged. The Latin-coded catalogue
record 31133 remains unimported with its raw responses retained; its reported
1300–1399 date already excludes it from the current discovery scope.

The browser uses version 5 JSON, produced by both collection writers through
`browser_format.py`. Claims use numeric columns and shared coordinate references;
providers and ranking events are interned. Exact coverage links use compact
numeric sequences and contextual claim-ID differences. Ordinary coordinate status
is a default; discovery uses per-book summaries; date selection stores only
constraints for competing choices. Full source evidence remains in the registers
and captures. The current file is 23,951,851 bytes. All content claims, complete
date records, coverage states, rankings and displayed discovery summaries survive
the projection unchanged.

The runtime validates compact columns without expanding the witness/verse matrix,
uses the narrowest safe typed arrays, shares chart events, and resolves selected
source details on demand. An offline Node/V8 measurement of the rebuilt model
retained 116,908,803 bytes (about 117 MB) of heap plus array buffers; browser and
DOM overhead are additional. Production checks cover all 15,914 book/verse chart
cells in both date modes without expanding the witness/verse coverage matrix.
Versions 1–4 remain readable. See [the explorer documentation](ATTESTATION_EXPLORER.md)
for the format and runtime contract. Offline tests use bounded fictional and
25-witness pilot fixtures, independent of future production collection growth.

The builder validates raw hashes, provenance, mappings, identity, complete date
intervals and derived results in a fresh temporary SQLite database. Builds are
offline and atomically replace the current JSON file. The request collector
retains budget/resume checkpoints in ignored cache storage. Older review-table
code remains outside the app's scholarly-report path.

`collect_catalogue.py` now supports resumable overnight capture across all four
Greek NT catalogue ranges. Paginated inventories include records without book
indexing and queue each eligible manuscript's metadata and verse contents once for reuse
across all 27 books. Launches have a finite time budget, optional cumulative
request ceiling, at least five-second persistent spacing, and provider-block
stops; there is no 50-attempt cap. Capture, offline import, and app rebuilding are
separate commands. Format-2 catalogue scopes coexist with existing book-index
scopes. The current rebuild reused captured responses and made no live requests.
See [overnight collection](BOUNDED_WITNESS_DISCOVERY.md#overnight-catalogue-collection).

Catalogue collection defaults to valid inventory date ranges beginning before
1000 CE, with unknown dates and retained earlier scholarly alternatives remaining
eligible. The cutoff is configurable and applies to unfinished jobs on resume;
captured reports remain preserved. Date exclusions retain source evidence and
reasons and do not count as pending collection or coverage assertions. The app
qualifies discovery completion by the declared date scope. Fewer than five
witnesses per verse is acceptable; complete date alternatives remain unchanged.

## Next development work

1. Follow the agreed [source corroboration plan](SOURCE_CORROBORATION_PLAN.md).
   Clarify the NTVMR index contract, capture explicit reports for the known
   Pericope Adulterae discrepancy, implement a separate register of scoped checks,
   and make discrepancies affect the app's evidence, coverage, and rankings.
   Evaluate additional sources through a bounded pilot before broader collection.
   Reuse captures first. One usable scholarly report remains sufficient; unknown
   contents and fewer than five witnesses remain acceptable. Preserve complete
   competing dates and keep ambiguous fields visible without guessing their meaning.
2. Run further live discovery only with a declared need and finite scope, budget,
   provider access expectations, and pacing. The current snapshot includes all
   four catalogue ranges for all 27 books; it does not establish exhaustive
   manuscript-corpus discovery. Future inventories or book/range searches must be
   recorded independently. Use the owner-supplied local proxy when direct access
   is unavailable, retain canonical citations, and honor provider blocks. Preserve
   the default 1000 CE earliest-date scope unless a different scope is explicitly
   declared; do not extend it solely to fill five ranking places.
3. Extend supported mappings and source-reported date applicability only when
   required by collected reports. The current coordinate mappings have no gaps.
   Portion-specific dates remain planned; record portions, hands, joins, and
   applicability only as explicitly reported by sources.
4. Keep collection efficient and the app usable as the dataset grows. Measure
   witnesses, usable reports, graphable coordinates, unresolved records, request
   cost, browser data size, and retained runtime memory. Preserve bounded offline
   regression fixtures. Prefer concrete bottlenecks over new infrastructure.

## Acceptance

- New collection appears in the existing app after refreshing its data file.
- Existing books, witnesses, citations, qualifications, and date alternatives
  survive additions without duplicate witness counts or inferred adjacent coverage.
- Every active claim is attributable to a scholarly source. Explicit disagreement
  is retained and deferred; missing information remains unknown.
- Discovery completeness is scoped independently of coverage and rankability.
- Progress toward all four categories is supported by independently recorded
  book/range searches. Completing a declared scope does not complete unsearched
  categories or establish exhaustive manuscript-corpus discovery.
- Offline source, normalization, data-loading, and chart tests pass. No manuscript
  examination, local server launch, or live request is part of routine verification.
