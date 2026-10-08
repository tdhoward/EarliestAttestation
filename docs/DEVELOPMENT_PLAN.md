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

The central register contains 2,351 witnesses and 4,026 retained responses across
all 27 books. The current app data has 7,941 graphable coordinates, 2,250,193
reported-present witness/verse pairs and 16,419,098 unknown pairs. Discovery and
candidate-collection states remain those recorded by the retained searches.

The browser uses version 5 JSON, produced by both collection writers through
`browser_format.py`. Claims use numeric columns and shared coordinate references;
providers and ranking events are interned. Exact coverage links use compact
numeric sequences and contextual claim-ID differences. Ordinary coordinate status
is a default; discovery uses per-book summaries; date selection stores only
constraints for competing choices. Full source evidence remains in the registers
and captures. The current file is 21,246,486 bytes. All content claims, complete
date records, coverage states, rankings and displayed discovery summaries survive
the projection unchanged.

The runtime validates compact columns without expanding the witness/verse matrix,
uses the narrowest safe typed arrays, shares chart events, and resolves selected
source details on demand. An offline Node/V8 model measurement retained about
122 MB of heap plus array buffers, down from 320 MB; browser overhead is additional.
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
scopes. No new live collection is implied by implementing or testing this tool.
See [overnight collection](BOUNDED_WITNESS_DISCOVERY.md#overnight-catalogue-collection).

Catalogue collection defaults to valid inventory date ranges beginning before
1000 CE, with unknown dates and retained earlier scholarly alternatives remaining
eligible. The cutoff is configurable and applies to unfinished jobs on resume;
captured reports remain preserved. Date exclusions retain source evidence and
reasons and do not count as pending collection or coverage assertions. The app
qualifies discovery completion by the declared date scope. Fewer than five
witnesses per verse is acceptable; complete date alternatives remain unchanged.

## Next development work

1. Broaden bounded independent witness discovery to all 27 books across papyri,
   majuscules, minuscules, and lectionaries. The
   [planned catalogue scope](BOUNDED_WITNESS_DISCOVERY.md#planned-catalogue-scope)
   defines the four ID ranges. Use the overnight catalogue collector with a
   declared time budget and optional request ceiling, or independent book/range
   pilots. Reuse retained reports, import captures offline, and refresh the
   central app data afterward.
   Do not constrain discovery to the witnesses already collected for nearby verses.
   The earliest five are ranked per verse and may span categories and widely
   separated dates. Continue toward the declared date-filtered scope across all
   four categories even where five witnesses or early papyrus attestations have
   already been collected. Do not extend beyond the default 1000 CE earliest-date
   cutoff solely to fill five places; unknown dates and retained earlier estimates
   remain eligible, and fewer than five witnesses is acceptable.
   Jude within IDs 10000–19999 remains a useful smaller independent scope when
   running a book-index pilot; it does not limit catalogue-wide collection.
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
- Progress toward all four categories is supported by independently recorded
  book/range searches. Completing a declared scope does not complete unsearched
  categories or establish exhaustive manuscript-corpus discovery.
- Offline source, normalization, data-loading, and chart tests pass. No manuscript
  examination, local server launch, or live request is part of routine verification.
