# NTVMR source-report contract v1

Implemented on 2026-10-05. This is the active bounded report-to-chart path;
historical image/transcription reviews are not its inputs. The contract ID is
`ntvmr-source-reports-v1`, the manifest format is 1, and its dataset/graph format
is 3. It uses the existing collector's response storage, inventory, endpoint
ranking function, and the source-report explorer. Three additive `scholarly_*` tables preserve
immutable report batches and claims alongside the unchanged legacy v12 tables.

## Field meanings and limits

The official [contents endpoint documentation](https://ntvmr.uni-muenster.de/community/vmr/api/biblicalcontent/get/)
and [metadata endpoint documentation](https://ntvmr.uni-muenster.de/community/vmr/api/metadata/manuscript/get/)
were captured with TLS verification on 2026-10-05 Pacific. Their raw HTML,
retrieval timestamps, URLs, and SHA-256 hashes are retained in
[`tests/fixtures/source_contract/`](../tests/fixtures/source_contract/).
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
a supported contract. The new Galatians manifest copies only publisher reference
coordinates from the existing provisional inventory and cites the long contents
entries; it contains no Greek wording, textual anchors, or image examination.

## Storage, disagreement, and dates

Each batch fixes its manifest, inventory, documents, and raw source snapshots.
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

## First active bounded result

The manifest [`gal1-source-reports-v1.json`](../benchmarks/gal1-source-reports-v1.json)
reuses six captured responses for P46, GA 01, and GA 02 across Galatians 1:1–10.
All page entries counted in this passage have source-reported indexing tier 3.
The catalogue date intervals are respectively 200–225, 300–399, and 400–499 CE.
These are catalogue alternatives in the collected scope, not a consensus claim.

| Measure | Result |
| --- | ---: |
| Declared documents / distinct witnesses | 3 / 3 |
| Coordinates / graphable coordinates | 10 / 10 |
| Reported-present witness/verse pairs | 29 |
| Unknown witness/verse pairs | 1 |
| Explicitly absent / contested pairs | 0 / 0 |
| Reference mapping gaps within this subset | 0 |
| Captured document responses reused | 6 |
| Replay network requests | 0 |

P46 at Galatians 1:9 is unknown because its captured long report contains no
entry. No absence or source disagreement has been invented. Synthetic tests
exercise actual explicit conflicts, absence, partial presence, alias joins,
date alternatives, ranking reversal, and overflow; those fictional inputs are
not part of this chart. Original collection retry costs were not measured by
this replay and are not presented as six total historical attempts.

Attribution audit for this increment: only the six catalogue captures and
publisher coordinates are admitted. Old Galatians word-anchor decisions, image
checks, writing-layer judgments, absence reviews, and dating selections are
excluded. Their files and databases remain preserved. This is not a repository-
wide attribution audit or an endorsement of old charts.

## Offline reproduction

Use a new database path on each replay. No network option exists in this command.

```powershell
python replay_source_reports.py --db data/gal1-source-reports.sqlite --dataset-output data/gal1-source-reports-complete.json --graph-output examples/gal1-source-reports-graph-input.json --html-output examples/gal1-source-reports.html
```

Open [`examples/gal1-source-reports.html`](../examples/gal1-source-reports.html)
directly. It displays a full-GNT chart with an endpoint toggle, contents states,
date inputs, source citations, exact reported contents fields, and source snapshots. The
complete dataset retains document-wide source claims and raw responses; the
graph output includes only the filtered inventory coordinates and source hashes.

Existing report batches can be exported read-only:

```powershell
python export_attestation.py --db data/gal1-source-reports.sqlite --report-batch gal1-source-reports-v1 --dataset-output data/gal1-reexport.json --graph-output data/gal1-reexport-graph.json
python render_attestation.py --graph-input data/gal1-reexport-graph.json --output data/gal1-reexport.html
python -m unittest discover -s tests -p test_source_reports.py -v
```

Next expansion: add documented document batches and supported coordinate subsets,
reusing each document's metadata and contents locally. Keep unsupported mappings,
unknown dates, provider qualifications, and explicit conflicts visible. Update
provider access expectations and bound the next discovery run before bulk access.

## Whole-Galatians expansion

Implemented on 2026-10-06. The new immutable batch
[`galatians-source-reports-v1.json`](../benchmarks/galatians-source-reports-v1.json)
reuses the same six document captures across all six Galatians chapters. Its
149 reference-only coordinates are copied from the provisional publisher
inventory v3; each direct mapping also occurs in a captured long contents
report. It admits no historical review, writing-unit, or dating-selection input.
The original 1:1–10 batch remains preserved; both active HTML examples now use
the reusable explorer, with their original report data unchanged.

| Measure | Result |
| --- | ---: |
| Declared documents / distinct witnesses | 3 / 3 |
| Coordinates / graphable coordinates | 149 / 149 |
| Reported-present witness/verse pairs | 437 |
| Unknown witness/verse pairs | 10 |
| Explicitly absent / contested pairs | 0 / 0 |
| Reference mapping gaps within this subset | 0 |
| Captured document responses reused | 6 |
| New document collection / replay network requests | 0 / 0 |

All 444 admitted page-level entries have catalogue indexing tier 3. Multiple
page reports collapse to 437 distinct witness/verse pairs. The ten unknown pairs
are P46 at Galatians 1:9; 2:10–11; 3:1; 4:1, 18–19; 5:18–19; and 6:9.
Missing entries are not absence claims. The complete reported date intervals
remain 200–225, 300–399, and 400–499 CE for P46, GA 01, and GA 02 respectively.
This is a bounded three-witness dataset, not exhaustive discovery.

The first expansion used separate chapter panels and a 200-coordinate rendering
limit. The subsequent [explorer update](ATTESTATION_EXPLORER.md), also on
2026-10-06, replaces those panels with one continuous, responsive full-GNT chart.
All 7,957 provisional coordinates have stable horizontal positions; only the 149
collected coordinates receive source reports. Uncollected and edition-filtered
coordinates are distinct. Hover/tap summaries, keyboard navigation, reference
entry, zoom, and a top-right endpoint toggle keep the thin bars usable.
Version 3 rendering supports the full inventory. Per-verse export overflow remains
explicit; the UI no longer enumerates a global date product. Legacy version 2
retains its existing renderer and limits.

```powershell
python replay_source_reports.py --manifest benchmarks/galatians-source-reports-v1.json --db data/galatians-source-reports.sqlite --dataset-output data/galatians-source-reports-complete.json --graph-output examples/galatians-source-reports-graph-input.json --html-output examples/galatians-source-reports.html
python -m unittest discover -s tests -p test_search_continuation.py -v
python -m unittest discover -s tests -p test_source_reports.py -v
```

Choose a new database path if the example destination already exists. Open
[`examples/galatians-source-reports.html`](../examples/galatians-source-reports.html)
directly. Two fresh offline replays produce identical dataset, graph, and HTML
outputs. Tests verify publisher coordinate order, retained unknowns, deduplicated
rankings, full-corpus coordinate order, compact provenance, shared year bounds,
interaction geometry, safe embedding, and response reuse. SQLite integrity and foreign-key
checks pass; the fresh batch contains no legacy review records. The two search
contract-check requests are separate from this chart's zero-cost document reuse;
historical capture attempts remain unmeasured.
