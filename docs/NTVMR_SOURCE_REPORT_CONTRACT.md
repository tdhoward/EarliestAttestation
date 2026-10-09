# NTVMR source-report contract

The central collection uses `ntvmr-source-reports-v1`. `build_collection.py` normalizes
captured reports in a temporary SQLite database, verifies source and claim integrity,
and updates `data/attestations.json` for the single explorer app. No HTML is generated.

## Known limitation and planned review

The rules below describe the current importer. Its admission of expanded NTVMR
page-index entries as presence claims needs review: the saved reports include
John 7:53–8:11 for P66, P75, and Vaticanus despite explicit published omission
reports. Whether NTVMR intends such ranges to exclude internal textual omissions
has not been established. Do not treat an indexing error or a deliberately coarse
indexing convention as the confirmed explanation.

The agreed [source corroboration plan](SOURCE_CORROBORATION_PLAN.md) sets out the
evidence, contract review, additional reports, separate checking register, and app
changes. Those changes are planned; this notice does not change normalization or
correct the current dataset. Ambiguous index semantics must remain distinct from
genuine incompatible scholarly content assertions.

## Field meanings and limits

The official [contents endpoint documentation](https://ntvmr.uni-muenster.de/community/vmr/api/biblicalcontent/get/)
and [metadata endpoint documentation](https://ntvmr.uni-muenster.de/community/vmr/api/metadata/manuscript/get/)
were captured with TLS verification on 2026-10-05 Pacific. Their raw HTML,
retrieval timestamps, URLs, and SHA-256 hashes are retained in
[`data/reference/contracts/`](../data/reference/contracts/).
Documentation collection was bounded to those two pages, with five-second
spacing. No manuscript response, image, or transcription was requested.

| Input | Meaning admitted by this contract | Limit |
| --- | --- | --- |
| `biblicalcontent/get`, `detail=long` | Documentation says this expands the page's verse range into individual entries. A validated `data.indexContents.indexContent[n]` object with `osisID`, `docID`, and `pageID` supplies a reported verse-range presence. | It reports catalogue indexing, not independently verified physical contents or full preservation. The exact object is retained. |
| Summary strings, book/chapter entries | Retained in raw snapshots. The observed empty-string `indexContent` container is accepted as an empty report. | Never expanded into verses. Empty or missing entries never assert absence. |
| `metadata/manuscript/get`, `detail=10` | Detailed catalogue information for the requested document. Observed fields `docID`, `gaNum`, `primaryName`, and `lang` identify its record. | Greek NT manuscript catalogue membership is declared in the manifest's bounded source scope; the wider NTVMR catalogue also includes other material. No exhaustive discovery is claimed. |
| `data.manuscript.originYear` | Observed `early`, `late`, and `content` fields supply the catalogue's complete numeric estimate and original notation. `content` can be a string or integer. | Preserve the supplied object, notation type, and bounds. Notation never supplies missing bounds. No century conversion, consensus inference, endpoint merging, or independently assigned writing portions. Zero/missing bounds stay unknown; malformed intervals stay invalid. |
| Metadata page `indexTier` | Provider-supplied indexing qualification, retained with the metadata hash. | The help identifies tier 4+ as AI indexing awaiting confirmation. Such entries are retained as unknown. Missing tier information is disclosed, without inventing a physical-verification requirement. |
| `liste/search` matches | Discovery candidates only in this path. | Search results and omissions are not imported as positive/negative coverage claims. |

The [search help](https://ntvmr.uni-muenster.de/community/vmr/api/metadata/liste/search/)
documents `partial` and `nextAfterDocID`/`afterDocID` continuation. On 2026-10-06
Pacific the collector was updated to follow it for named lookups and explicit
document sets. It accepts boolean or string flags in `data.manuscripts` and the
documented `X-VMR-Partial` / `X-VMR-Next-AfterDocID` header equivalents. Disagreeing
fields, malformed or nonadvancing cursors, and repeated documents are contract
errors. A count matching the returned rows does not override a partial flag.

Each continuation repeats the original filters and page limit, changing only
`afterDocID`. All requests and retries use the existing run budget, spacing,
timeout, and blocked-state behavior. Captured pages are replayed on resume;
candidates are replaced only after a terminal page is parsed. A failed refresh
keeps the previous candidate snapshot visibly stale. Refreshed first pages are
not combined with older continuation captures. Each candidate retains the
response ID of its own page; raw responses and headers remain immutable.
Dry-run cache indicators cover initial pages only, and the reported maximum
allows continuation requests within the remaining run budget.

The help and one bounded search response for IDs 10066 and 10075, filtered to
John 1:1, are retained as `metadata_liste_search_help.json` and
`search_bounded_terminal.json` in the source-contract fixture directory. This
check made two successful HTTPS requests, five seconds apart, with TLS verified:
one documentation request and one catalogue search, without images or
transcriptions. A page limit of 1 still returned both documents without a partial
flag; no second search request was made. Live partial-response shape remains
unobserved by this check. Transient session cookies were excluded from the
retained headers; the public body and its hash are unchanged. Clearly synthetic
offline tests exercise the documented
root-attribute layout and headers, budgeted resume, stale refresh protection,
count mismatches, overlapping pages, and blocks. Search rows are discovery
candidates only. Completion of a selected lookup does not establish exhaustive
manuscript discovery or provide an absence assertion.

This version accepts explicit direct OSIS-to-NA28 coordinate matches and
unmapped coordinates. Changed or multi-reference mappings are rejected pending
a supported contract. The collection builder copies publisher reference coordinates from
`data/reference/na28.json` and maps only exact references in explicit collected reports.
Unmatched coordinates remain unresolved.

## Retained catalogue variants

Offline checks of saved metadata and `detail=long` contents reports establish
the following additional shapes. Their captures retain canonical endpoint URLs,
query parameters, retrieval timestamps, raw bodies, and hashes. No manuscript
images or transcription text are involved.

- [P14's contents report](../data/sources/ntvmr-10014-coverage-bc9c68a3cc012ec7.json)
  supplies exactly `{"docID":10014,"indexContent":""}`. This is a usable empty
  catalogue report, with no verse assertions. It completes report collection;
  every missing witness/verse entry remains unknown. Nonempty strings, null,
  and malformed containers are still rejected rather than expanded.
- Greek GA catalogue records also supply the exact multilingual language codes
  `g-k`, `g-l`, `g-arb`, `g-arm`, `g-l-arb`, `g-sl`, and `g-t`, alongside the
  existing `g`, `grc`, and `grc_lat`.
  Examples are [P2](../data/sources/ntvmr-10002-metadata-f573cb15b23703d2.json),
  [GA 05](../data/sources/ntvmr-20005-metadata-8c79f99942fd35f2.json), and
  [GA 0136](../data/sources/ntvmr-20136-metadata-eda097cbb67e1a1f.json).
  Further examples are
  [GA 256](../data/sources/ntvmr-30256-metadata-7a3ec21aa17e8472.json),
  [GA 460](../data/sources/ntvmr-30460-metadata-03b26afabb603ba4.json),
  [GA 525](../data/sources/ntvmr-30525-metadata-21fa7ef5f2e9eed7.json), and
  [GA 1325](../data/sources/ntvmr-31325-metadata-68580eadb067363a.json).
  Import accepts this finite set in the declared Greek NT catalogue scope and
  retains the exact language field. Other language codes and missing GA identity
  remain unsupported; multilingual metadata does not identify writing layers.
- [GA 461's metadata](../data/sources/ntvmr-30461-metadata-a25a99b698fef284.json)
  reports `{"late":835,"early":835,"content":835}`. Both endpoints and the
  integer notation are copied exactly. Boolean, floating-point, list, and object
  notation fields remain unsupported. No notation-to-date conversion occurs.
- [GA 028's contents report](../data/sources/ntvmr-20028-coverage-1ea439c15b36f482.json)
  mixes explicit NT entries with entries labelled `Num`. Other retained reports
  include `Gen`, `Exod`, `Deut`, `Ps`, and `3Macc` book markers, including
  [GA 700's mixed report](../data/sources/ntvmr-30700-coverage-cdc680ab8342ebb0.json).
  Import validates record
  identity, reference syntax, and page IDs before projecting exact NT verse
  entries. Other-book entries and all book/chapter markers remain in raw captures
  without entering active NT claims. Unsupported mappings are not reinterpreted.

These rules address saved-response parsing and scoped extraction. Server request
failures, provider blocks, malformed reports, and missing scholarly assertions
remain separate states. Re-import reuses captures without redownloading them.

## Storage, disagreement, and dates

Each normalization build fixes its input register, coordinate inventory, documents,
and raw source snapshots. The database is temporary; only the current app data is published.
Coverage claims retain provider, citation, retrieval date, exact field/statement,
qualifications, and source response/hash. Date claims retain the complete
interval, original notation, and document applicability. The exporter checks
batch, claim, inventory, and source checksums, stored coordinate mappings, and
claim-to-response links. Database integrity and foreign keys are checked during
replay. These checks establish faithful software handling, not source correctness.

Optional `additional_reports` can retain explicit published coverage statements
and whole-witness date estimates, including their source text. Every supplied
statement must occur verbatim in the retained snapshot. Extraction of an explicit
absence statement is permitted; inference from an omitted entry is not. This
interface does not interpret manuscript text, an apparatus, or an image.

For each mapped witness/verse pair:

- Any usable reported portion is `present`, whether partial, full, or unspecified.
- An explicit source absence assertion, without a positive assertion, is `absent`.
- Missing, unmapped, ambiguous, or explicitly unconfirmed information is `unknown`.
- Incompatible explicit presence/absence assertions are `contested`; both claims
  remain inspectable and that pair contributes no ordinary presence event.

Partial/full differences do not contest presence. An unknown assertion does not
contradict a usable present/absent report. Conflicts do not block unrelated
witnesses or verses. Historical agent interpretations never supply an opposing
scholarly claim.

One NTVMR document identifies one witness by default. Assigning another witness
ID for a reported alias/join requires a cited source statement in
`identity_report`. Multiple pages, joined IDs, and complete date alternatives do
not multiply a witness. This version does not independently create portions or
hands, and does not yet support portion-specific date applicability.

All complete date intervals remain alternatives with equal standing. Each
combination ranks independently by lower and upper endpoints, selecting up to
five witnesses per scenario. Unknown/invalid bounds remain visible without event
years. The existing 256-combination export limit remains explicit per verse;
overflow does not select or truncate an alternative. The explorer chooses among
exported combinations on demand without enumerating a corpus-wide product.

Catalogue collection uses the inventory's explicit numeric `origEarly` and
`origLate` fields only to screen follow-up requests. The default exclusive
earliest-date cutoff is 1000 CE. Only positive, ordered integer bounds can exclude
a candidate; missing, zero, or invalid bounds remain eligible. A retained
scholarly estimate beginning before the cutoff also preserves eligibility.
The original `orig` notation and both numeric bounds stay in the retained row;
no notation conversion, endpoint merging, or coverage inference is performed.
Date-filter decisions retain the cutoff, reason, and source evidence separately
from coverage claims. The cutoff does not remove captured reports or truncate
date estimates. Discovery completion is qualified by this collection scope,
which may yield fewer than five witnesses for a verse.

## Central data and discovery

`data/collection.json` lists the documents, capture paths, coordinate scope, and
additional published claims. Source captures live in `data/sources/`; the current
bounded search records live together in `data/discovery.json`. Each capture retains
its raw response, URL, parameters, timestamp, hash, and transport qualifications.
These records support scholarly attribution without keeping a series of chart revisions.

Candidate discovery is independent of the existing witness pool. Multiple bounded
book/range searches can coexist in the discovery register. Search rows supply no
contents assertions. Per-verse discovery states and the app's **earliest collected**
labels distinguish usable reports from completeness of the witness search. See
[the discovery guide](BOUNDED_WITNESS_DISCOVERY.md).

The central register covers all 27 books and retains completed inventories for
all four declared catalogue ranges, alongside eleven earlier papyrus book-index
searches. Capture completion is separate from usable report import, exact verse
assertions, and date rankability. Empty reports are usable with unknown coverage;
unsupported metadata stays captured and unresolved.

[Document 31133's metadata](../data/sources/ntvmr-31133-metadata-58763816e1bf70c8.json)
is labelled `lat` by the source, outside the supported Greek language contract.
Its 1300–1399 CE inventory range is excluded by the current date scope; its raw
metadata and contents captures and import errors remain retained. This is not a
server request failure or a verse absence assertion.

See [the development plan](DEVELOPMENT_PLAN.md#current-implementation) for current
collection counts and [bounded discovery](BOUNDED_WITNESS_DISCOVERY.md#current-source-scope)
for scope qualifications. No manuscript examination or independent corroboration
of each witness is required.

These collections used the owner's local API proxy. Canonical NTVMR URLs supply
all scholarly citations;
permanent captures replace proxy origins with `<local proxy>` and preserve raw
response bodies, hashes, paths, parameters, and retrieval dates. Actual transport
addresses remain in ignored local definitions and request caches; see
[README](../README.md#collect-more-data). Per the owner's
2026-10-06 clarification, TLS verification is not a collection prerequisite and
transport notes are not scholarly contents or date qualifications.

Refresh or verify the one app data file offline:

```powershell
python build_collection.py
python build_collection.py --check
python -m unittest discover -s tests -v
```

The app reads the updated file when loaded. Its HTML, JavaScript, and CSS do not
change when documents, books, or source reports are added.
