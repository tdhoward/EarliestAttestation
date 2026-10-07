# NTVMR source-report contract

The central collection uses `ntvmr-source-reports-v1`. `build_collection.py` normalizes
captured reports in a temporary SQLite database, verifies source and claim integrity,
and updates `data/attestations.json` for the single explorer app. No HTML is generated.

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
| Summary strings, book/chapter entries | Retained in raw snapshots. | Never expanded into verses. Missing entries never assert absence. |
| `metadata/manuscript/get`, `detail=10` | Detailed catalogue information for the requested document. Observed fields `docID`, `gaNum`, `primaryName`, and `lang` identify its record. | Greek NT manuscript catalogue membership is declared in the manifest's bounded source scope; the wider NTVMR catalogue also includes other material. No exhaustive discovery is claimed. |
| `data.manuscript.originYear` | Observed `early`, `late`, and `content` fields supply the catalogue's complete numeric estimate and original notation. | Preserve the supplied object and bounds. No century conversion, consensus inference, endpoint merging, or independently assigned writing portions. Zero/missing bounds stay unknown; malformed intervals stay invalid. |
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

The current collection reuses 20 witnesses' captured reports across all 27
books. Only exact reported OSIS matches supply presence; thirteen default
coordinates remain unresolved. This reuse establishes no new discovery
completion. Independent Galatians, Hebrews, Ephesians, 1 Thessalonians, and
2 Thessalonians searches are complete only within their declared ID range. The
Hebrews pilot collected nine new witnesses; Ephesians added P49, P92, and P132 while reusing P46;
2 Thessalonians added P30 while reusing P92; 1 Thessalonians added P61 and P65
while reusing P30 and P46. The latter search used five successful requests and
preserved all prior claims, date estimates, and coverage states. P61's other-book
reports create no additional discovery completion. These collections used the
owner's local API proxy. Canonical NTVMR URLs supply all scholarly citations;
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
