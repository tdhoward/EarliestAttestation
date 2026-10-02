# EarliestAttestation

Collect the earliest surviving Greek evidence for each verse of **NA28**, with up
to five distinct witnesses per verse and both ends of each witness's proposed date
range. The intended chart follows traditional New Testament book/chapter/verse
order, places more recent years at the top, and changes color as the witness count
increases from one to five.

A surviving part of a verse counts as evidence for that verse. It does not establish
that the whole verse, its exact NA28 wording, or neighboring verses survived. For
example, P52 preserves portions of John 18:31–33 and 18:37–38; this project must not
fill in 18:34–36. See the [coverage reference and review](docs/DATA_REVIEW.md).

## Development direction

The [John 1:1–5 prototype chart](examples/john1-prototype.html) now replays four
source-reviewed physical witnesses, writing-unit links, conditional date inputs,
and a source-linked table from checked-in inputs. Its five verses each have P66,
P75, 01, and 02 in the conditional rankings. Alexandrinus (02) now has five
image-checked verse reviews tied to captured NTVMR page metadata. A cited
20-case coverage benchmark guards the replay. The new
[John 6:49–53 boundary chart](examples/john6-gap-prototype.html) now has twelve
positive and three physical-absence decisions for P66, P75, and Alexandrinus,
with fifteen cited benchmark cases. Its witness counts vary across a directly
reviewed lacuna. The first [Pauline papyrus increment](docs/GAL1_P46_REVIEW.md)
now adds P46 at Galatians 1:1–5, five cited coverage decisions, and two equal
conditional date alternatives in a [reproducible chart](examples/gal1-p46-prototype.html).
The next work is overlapping witnesses in that passage, alongside independent
source checking of the existing evidence and a later supplement or boundary case.
The [development plan](docs/DEVELOPMENT_PLAN.md#next-development-work) defines the
scope, acceptance criteria, and subsequent expansion; it is the source of current
development priorities. The [bounded scope and development log](docs/PROTOTYPE_SCOPE.md)
records the John 1:1–5 several-witness target and the P52 chart increment.

The next-passage workflow now carries physical coverage and absence reviews into
the export and chart, including witnesses with no usable dates. Conflicts,
withdrawals, and coordinates without a review remain visible. The John 6 increment
now exercises this workflow with cited positive and physical-absence reviews.

Continue to inspect and expand this labeled prototype while data review continues.
Whole-NT mapping completion, exhaustive discovery, the full representative
benchmark, and independent human publication review remain open. Displayed
evidence needs citations and faithful recording, with unknowns, competing dates,
discovery limits, and review status visible. Historical releases
must meet the separate [publication requirements](docs/DEVELOPMENT_PLAN.md#prototype-and-historical-publication-expectations).

When a bounded evidence set is ready for human review, Codex will prepare
[specific review questions](docs/DEVELOPMENT_PLAN.md#human-review-question-packets)
with source links, exact locations, and the claims to check. The project owner can
answer **agree**, **disagree**, or **unable to assess**, and add corrections.
Checks needing specialist expertise will be identified. Human answers will be
recorded separately from agent reviews, with unresolved points kept explicit;
reviewers need not settle scholarly dating disputes. The first
[bounded review packet](docs/JOHN6_GAP_REVIEW.md#independent-review-questions)
is now written for the John 6 increment. Human answers and automated packet
generation remain pending; this does not block ongoing prototype development.

Measure progress by usable graph output, reviewed witnesses and verses, and the
effort needed to add them. Use that experience to justify targeted batch imports
or mapping automation before scaling. New infrastructure must address a concrete
need in the active milestone. Preserve the existing P52 regression cases;
additional P52 dating research is outside this milestone. Supplementary collection
remains part of the project but must not block the core prototype.

## Skipped verses and graph inclusion

Collect and retain evidence for traditional verse numbers skipped by NA28 as
supplementary data, tagged `omitted` in the inventory. Apply the same coverage,
writing-layer dating, and distinct-witness counting rules as for other verses;
do not presume that their witnesses are later or assign dates from edition status.
For each coordinate, cite a reference identifying the traditional passage and
verify its manuscript-index mappings, since NA28 main-text wording cannot anchor
that identification.

The default graph will exclude `omitted` coordinates, with an **Include verses
omitted from NA28** option. Bracketed passages will have a separate inclusion
control. Graphs, exports, and summary counts must identify the active filters and
the resulting verse population. Filtering a view must preserve the underlying
evidence. Edition omission, verified manuscript absence, physical damage, and
unreviewed or missing indexing are separate states.

The inventory already retains the 16 skipped coordinates. The offline
[`export_attestation.py`](export_attestation.py) command implements the default
filter and optional inclusion for graph data. The bounded offline
[`render_attestation.py`](render_attestation.py) command renders a static chart and
source table from that output. A positive
coverage review for an `omitted` coordinate requires a cited traditional-passage
identification in a new, immutable inventory snapshot and an explicit NTVMR mapping.
Completing this supplementary dataset is not a prerequisite for completing the
core NA28 dataset. See the [inventory policy](docs/NA28_INVENTORY.md#supplementary-collection-and-display-policy).

```powershell
python export_attestation.py --db data/na28-inventory-v3.sqlite --inventory na28-nt-reference-provisional-v3 --policy example-policy --dataset-output data/attestation-complete.json --graph-output data/attestation-graph.json
```

Add `--include-omitted` to show skipped coordinates in graph data, or
`--exclude-bracketed` to filter bracketed passages independently. Both outputs
record inventory and dating policy IDs; the graph output records its filters and
counts. Uncomputed or stale selected-policy rankings have no selected-policy graph
events. The complete export retains their status and any prior ranking entries for
audit; current alternative-date calculations can still be available separately.
The example inventory database has no rankings, so its exported verses will be
`uncomputed` until reviewed evidence and rankings are added to that database.
Format v2 also carries `dating_alternatives` for coordinates with coverage reviews.
It enumerates combinations of stored valid date assessments by writing unit and
computes both endpoint rankings for each combination without choosing a scholar.
Each combination lists assessment IDs, complete intervals, original notation, and
citations. It uses at most 256 combinations per verse; larger sets report
`too_many_combinations` and contain no partial results. `complete` means all
combinations of the currently stored, rankable assessments were enumerated, not
that source discovery or historical validation is complete. Unknown or invalid
dates remain excluded with an explicit reason. The graph input sets the older
selected-policy `scenarios` field to `null` when alternative results exist;
consumers should use `dating_alternatives.combinations` in that case. The complete
dataset retains selected-policy snapshots for audit. The 256-combination cap is
an implementation limit, not a dating policy: nine units with two assessments
each already exceed it. Future development should support bounded exploration of
explicit combinations when needed, keeping all assessments accessible and
uncomputed outcomes visible. On-demand calculation is not implemented. See the
[ranking direction](docs/DEVELOPMENT_PLAN.md#5-rank-independently-for-both-date-scenarios).

Version 2 exports also include an additive per-verse `evidence` object, independent
of dates and the first-five ranking cutoff. It carries the latest coverage review
per indexed page and latest physical-absence decision per witness, with citations,
source locations, reviewers, timestamps, and change/conflict flags. Earlier review
history remains in the database. `positive_witness_ids` and `absent_witness_ids`
exclude conflicts; `conflicting_witness_ids` lists those separately. A stale positive
review, uncertain or withdrawn absence, or rejected index entry does not count as
verified absence. Absence-only coordinates need neither an NTVMR mapping nor a
ranking. An empty evidence list means no recorded review, not physical absence.
Both exports count positive, absent, and conflicting witness/verse pairs for their
own verse population. The chart lists these reviews even without dated events;
older version 2 inputs remain readable but label their missing review details.

## Manuscript dating policy

This project records scholarly dating assessments and preserves their uncertainty.
Project contributors are not qualified to resolve manuscript dating disputes, and
resolving them is outside the project's scope.

- Defer to scholarly consensus whenever it is known, citing the source that
  establishes that consensus and preserving its stated range and qualifications.
  A single catalogue entry or the project's own count of opinions does not by
  itself establish consensus.
- Where consensus is unknown or disputed, treat the various sourced scholarly
  date ranges as equally valid possibilities. Retain each complete range with its
  citation; do not choose a preferred scholar, narrow or average the ranges, or
  merge their endpoints into a new manuscript date. Equal treatment does not
  assign numerical probabilities to the alternatives.
- Preserve original date notation and document any conversion to numeric years.
  If bounds cannot be represented faithfully, retain the assessment as unknown
  for numeric ranking rather than inventing precision. Disagreement between
  usable ranges is not the same as having no usable date information.
- Review checks faithful source recording and application to the relevant
  manuscript or writing layer. It does not authorize contributors to adjudicate
  the underlying dating arguments. Resolving dating disputes is not a
  prerequisite for continuing collection, coverage work, or development.

P52 remains an illustrative manuscript and regression-test fixture. Its existing
source notes are retained, but settling its date or extending its dedicated
dating review is not a project milestone.

## Current status

The 2026-10-02 UTC Pauline increment passes **96 offline tests**. A fresh P46
Galatians 1:1–5 replay has zero audit findings, passes all five cited benchmark
cases, and exports two conditional date alternatives for each verse with zero
network attempts. Its [source review and replay commands](docs/GAL1_P46_REVIEW.md)
include exact locations and five unanswered human-review questions. P46 counts
as one physical witness across its two holding institutions. Discovery and
independent historical validation remain incomplete.

This is a Python/SQLite research prototype. Controlled collection, append-only
reviews, writing-unit dating, and both first-five ranking scenarios are implemented
through schema version 12. A bounded static chart renderer and the four-witness
John 1 prototype are reproducible; a validated whole-corpus export remains open.
**The legacy `ntvmr.sqlite` is exploratory and should not be used to make historical
claims.** The [original review](docs/DATA_REVIEW.md) found:

- 7,959 seeded references, 1,326 earliest-result rows, 13 selected manuscripts,
  and zero stored manuscript-to-verse coverage rows.
- A reproducible search problem: `lang=gr`, used by the prototype, excludes P52
  in a bounded John 18:31 probe. `lang=grc` and an omitted language filter return
  it. The returned record itself says `lang=g`; request and response language
  codes need an explicit, tested mapping.
- The coverage parser misses the actual `osisID` field in the P52 response.
- Only the earliest lower-bound candidate is retained. That cannot supply the
  first five witnesses or independently ranked pessimistic results.
- The verse seed uses KJV versification, which is not an NA28 verse inventory.

The replacement collector addresses those collection and data-model defects with
explicit parsing, separate checkpoints, retained candidates, and reviewed inventory,
identity, coverage, and date records. This does not repair or certify the legacy
results. The [offline P52 index sample](examples/p52-index-sample.json) remains a
single-witness candidate index.

A [provisional whole-New-Testament NA28 coordinate inventory](docs/NA28_INVENTORY.md)
now covers all 27 books and 260 chapters. It contains 7,957 reference coordinates:
7,941 numbered markers from publisher displays plus 16 skipped traditional
numbers retained as `omitted`. The v2 snapshot confirms 1 Corinthians 4's 21
numbered markers against the publisher's direct NA28 display, clearing the v1
UBS5 fallback flag. V3 adds publisher cited traditional-passage identifications
for all 16 skipped coordinates while keeping their NTVMR mappings unresolved. Only five John 18
coordinates have source-checked NTVMR mappings; 7,952 remain explicitly
unmapped. V3 was imported into a separate local database and verified; it is
reproducible from its pinned review record, but the inventory is not yet
editorially certified or ready for whole-NT attestation claims.

The subsequent 2026-10-01 evidence-export review passed **84 offline tests**.
A fresh offline John 1 replay still has 20 positive witness/verse pairs, zero
audit findings, and all 20 benchmark cases passing. The regenerated chart adds
physical-review details; the historical evidence and conditional dates are unchanged.

The 2026-10-01 fourth-witness increment passed **81 offline tests** on Python 3.12.6.
Its replay creates 20 cited partial witness/verse decisions,
20 writing-unit assignments, seven date observations, and one conditional ranking
combination for each of five coordinates. Its fresh structural audit has zero
findings, and all 20 cited coverage benchmark cases pass. The conditional
optimistic years are 101, 201, 301, and 400 CE; pessimistic years are 300, 300,
400, and 499 CE, drawn from broad source date ranges. These are
possible chart inputs, not settled manuscript dates or claims of exhaustive
earliest attestation. The [replay commands](#john-1-four-witness-prototype)
use no network; the local collection attempts and databases are ignored by Git.

The progress check on 2026-09-30 passed **70 offline tests** on Python 3.12.6.
The subsequent graph increment passed **72 offline tests** and a fresh P52
replay audit with zero findings; the older local database counts below are
read-only observations, not changes made by that replay.
Read-only inspection of `data/ntvmr-v2.sqlite` found ten John 18 inventory
coordinates, five explicit NTVMR mappings, one physical witness, and five cited
partial-coverage decisions.
An earlier combined audit passed all five evidence cases and both source controls
with zero findings. It has **no writing units, coverage-unit assignments, date
assessments, selected dates, or ranking snapshots**;
`historical_validation_complete` remains false. These counts describe the inspected
local snapshot, which is not distributed with the repository. It is still on v11
and needs a backed-up additive schema upgrade before the current read-only audit
can run. The separate full-inventory databases have coordinates and mappings but
no witness evidence; the inventory alone cannot produce attestation events.

The [bounded P52 dating review](docs/P52_DATING_REVIEW.md) checks cited sources as
a Codex review and records an original writing unit, four competing dating
observations, and an explicit unresolved selection under
`p52-cautious-source-v1`. It replays into a separate database; the local reviewed
snapshot counts above have not changed. Its null selection is a legacy replay
state, not a requirement to resolve P52's date. Stored ranking snapshots still
use one selected assessment per writing unit under each policy. The offline export
now enumerates conditional rankings over stored valid alternatives. The normal
P52 replay now assigns its five coverage reviews to the cited original writing
unit, so a fresh replay and export produce two conditional date cases without
manual SQL or a test-only assignment. The static chart renders those cases and
marks the five neighboring coordinates as unresolved. It remains a one-witness
workflow check. The John 1 replay supplies the first several-witness prototype.
Documented consensus and broader witness review remain implementation work.
Broader witness coverage, discovery completeness, and certification and mapping
of the existing provisional whole-NT inventory remain open.
Use the [development plan](docs/DEVELOPMENT_PLAN.md)
for current priorities and acceptance criteria; the original review is the legacy
baseline.

A small, budgeted live check on 2026-09-29 found P52 at John 18:31 and P66,
P75, 01, and 02 at John 1:1. The [captured four-witness search responses](tests/fixtures/john_named_probe.json)
show that codex names can be JSON numbers. These lookups do not establish complete
discovery or verified physical coverage.

The [P66 coverage response captured on 2026-10-01](tests/fixtures/p66_coverage_probe.json)
contains 970 explicit verse/page pairs and a chapter-level `John.2` marker.
The coverage parser validates chapter markers and preserves them in the raw
response, but creates index candidates only for explicit verse entries. It never
expands a chapter marker into verses. An index containing only chapter markers
has no individual verse candidates; that does not establish physical absence.

The [P75](tests/fixtures/p75_coverage_probe.json) and
[01](tests/fixtures/sinaiticus_coverage_probe.json) captures include valid
book-level markers such as `John`. The parser retains those markers in the raw
response and imports only explicit verse/page pairs. All three index responses
are replayable offline.

A bounded catalogue lookup now accepts up to 20 explicit document IDs in one
request, preserves every returned record, and reports IDs that were not returned.
An unfiltered lookup is marked complete for that declared ID set only when every
requested ID appears and the reported count matches. A passage-filtered lookup
cannot establish that status. Unfiltered live probes for five IDs and then P52
alone timed out on 2026-09-29 and remain checkpointed as pending; they yielded no
completeness claim.

The metadata stage now checks the manuscript response's nested `docID`, catalogue
name, and language before marking it complete. Its v5 `document_metadata` snapshot
keeps the source's language and date notation verbatim, with numeric date bounds
only when the interval is valid. Unknown or invalid catalogue dates stay out of
numeric bounds. These are source metadata, not selected scholarly date assessments
or verified witness identities. A prior v4 metadata checkpoint is replayed from its
cached response when its normalized snapshot is missing.

Document classification is now a separate, append-only v6 review record. A reviewer
can mark a discovered document `retain`, `exclude`, or `uncertain`, with source type,
reason, citation, reviewer, and the stored response ID. Named-search and catalogue
reports show the latest decision while retaining excluded candidates in the report.
`review_source_changed` flags when a newer successful response to the same request
has different content. `retain` means a Greek manuscript candidate should be kept
for further review; it does not verify any verse or settle physical witness identity.

Physical witness identity is now a separate, append-only v7 decision. A reviewed
catalogue document can be linked to a stable, manually chosen witness ID. Multiple
document IDs can share that identity only through explicit links with citations.
Corrections and unlinks keep their history. Candidate reports show the
current witness ID and flag links needing renewed review after a document
reclassification or source change. No identity link verifies verse coverage.

The v8 inventory importer stores a coordinate list as an immutable snapshot and
requires a source citation and reviewer. It keeps numeric Matthew-to-Revelation
order, editorial status, and
explicit NTVMR mappings, including unresolved coordinates. It rejects verse ranges
and does not derive NA28 membership from KJV chapter maxima. A cited, reference-only
[John 18:30–39 NA28 subset](benchmarks/p52-na28-john18-subset-v1.json) is now imported
for the P52 benchmark. The [v3 provisional whole-NT manifest](benchmarks/na28-nt-reference-provisional-v3.json)
has also been imported separately; remaining editorial cases and most NTVMR mappings
need further review. The inventory report leaves whole-NT certification
unconfirmed. Book IDs follow the [OSIS New Testament list](https://wiki.crosswire.org/OSIS_Book_Abbreviations).

To check and import the full coordinate manifest offline:

```powershell
python build_na28_inventory.py --check
python build_na28_inventory.py --review benchmarks/na28-coordinate-review-v2.json --check
python build_na28_inventory.py --review benchmarks/na28-coordinate-review-v2.json --passage-review benchmarks/na28-passage-identifications-v1.json --check
python sync_ntvmr.py --offline --db data/na28-inventory-v3.sqlite --import-inventory benchmarks/na28-nt-reference-provisional-v3.json
```

## Run the offline checks

Python 3.10+ is required; verification currently uses Python 3.12.6. The active
collector, audits, and tests use only the standard library. The test suite makes no network
requests and creates temporary databases; it does not need a local snapshot.

```powershell
python -m unittest discover -s tests -v
python audit_ntvmr.py --db ntvmr.sqlite
python audit_ntvmr.py --db ntvmr.sqlite --json
```

The audit opens an existing database read-only. It checks dates, references,
coverage links, stale result dates, and cached search contracts. Exit codes are
`0` for no detected structural issues, `1` for data-quality findings, and `2` if
the audit could not run. **Exit code 1 is expected for the current database.**
A passing audit alone does not verify historical dates, physical survival,
NA28 membership, or completeness of the source corpus.

`ntvmr.sqlite` is a local snapshot and may not be present in a fresh clone. Run its
audit only when the file is available. The human-readable snapshot findings are
recorded in the review document. To check an existing reviewed database, use the
[reviewed-data audit commands](#reviewed-data-audit-and-p52-replay) below. Use the
auditors for read-only inspection; collector report commands also open the schema
for additive upgrades.

## Controlled collection

[`sync_ntvmr.py`](sync_ntvmr.py) uses only the Python standard library. It creates
a separate replacement database, requires explicit document IDs or named search
scope and a positive network request budget for live work, and uses the official
HTTPS API by default. It has offline replay, immutable source responses, durable
attempt records, and separate
metadata and coverage job states. The conservative five-second spacing is a
project default, not a confirmed NTVMR quota.

`data/ntvmr-v2.sqlite` names the replacement database; its current SQLite
`user_version` is **12**. This filename is not the schema version. Always pass
`--db` explicitly: the CLI default is `ntvmr-v2.sqlite` in the working directory.
`--offline` prevents network requests but still permits local writes. Collector
`--dry-run` skips the requested collection or review writes but opens the database
and creates or upgrades its schema. It is not a read-only preflight or proof that
a later decision will satisfy every database constraint.

```powershell
python sync_ntvmr.py --help
python sync_ntvmr.py --offline --fixture-p52 --db data/ntvmr-v2.sqlite --run-id fixture-p52 --export-p52 examples/p52-index-sample.json
python sync_ntvmr.py --offline --db data/ntvmr-v2.sqlite --doc-id 10052 --run-id review --dry-run
python sync_ntvmr.py --offline --fixture-p52 --fixture-language-probe --db data/ntvmr-v2.sqlite --run-id p52-language --search-ref John.18.31 --search-ga-num P52
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --run-id john-named-probe --search-ref John.18.31 --search-ga-num P52 --search-ga-num P66 --search-ga-num P75 --request-budget 3 --dry-run
python sync_ntvmr.py --offline --fixture-john-list --db data/ntvmr-v2.sqlite --run-id john-list-fixture --catalogue-doc-id 10066 --catalogue-doc-id 10075 --catalogue-index-ref John.1.1 --catalogue-limit 10
```

The legacy code is retained as [`legacy_sync_ntvmr.py`](legacy_sync_ntvmr.py) for
review, with direct execution disabled. The original `ntvmr.sqlite` is untouched;
its local SQLite backup is `data/ntvmr-legacy-backup.sqlite`. Both local v2 and
backup databases are ignored by Git. To make a backup from another legacy file,
use `--archive-legacy SOURCE --archive-to DESTINATION` once. The backup checks
integrity and table row counts.

Live named searches require a positive request budget and use the same request
spacing and durable raw-response cache as document collection. `--search-lang` can
replay a literal language filter; the default omits it. A search report declares
its scope, per-query state, and any known document whose indexed coverage conflicts
with a search result. `count` and returned rows are checked, but a match does not
prove exhaustive results. `--refresh-search` explicitly reruns a selected lookup.
If Python cannot validate the service's TLS chain, configure `SSL_CERT_FILE` to a
trusted CA bundle; keep certificate verification enabled.

`--request-budget` caps total recorded attempts for a `--run-id`, including earlier
invocations and retries; it is not a fresh allowance on resume. Check the dry-run
summary's prior attempts before choosing the total cap. `--max-run-seconds` is an
optional time budget for the current invocation. Keep live checks separately
scoped; the offline test and benchmark workflow needs no live calls.

Use `--catalogue-doc-id` to declare a bounded ID set. `--catalogue-index-ref` is an
optional passage filter, and `--catalogue-limit` is an approximate page cap, not a
document count. `--refresh-catalogue` explicitly retries that scope. After
collecting each document's coverage with `--doc-id` under the same run ID,
`--scope-check-ref` inverts the completed indexes for selected verses and compares
them with any named passage searches in that run. It marks later replaced coverage
as stale. These rows remain index candidates; a missing row is not proof that text
was physically absent.

For a manual document review, take `doc_id` and `response_id` from a candidate
report and run `sync_ntvmr.py` separately with `--review-doc-id`,
`--review-response-id`, `--review-decision`, `--review-source-type`,
`--review-reason`, `--review-citation`, and `--reviewer`. This command makes no
network requests. Decisions must agree with source type: `retain` requires
`greek_manuscript`, `exclude` requires `printed_edition` or `other`, and
`uncertain` requires `uncertain`. Earlier decisions remain in `candidate_review`.

To link a retained document to a physical witness, use its reviewed response ID:

```powershell
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --identity-doc-id 10052 --identity-response-id RESPONSE_ID --witness-id p52 --witness-label "P52" --identity-reason "Physical object identified" --identity-citation "Source citation" --identity-reviewer "Reviewer name"
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --identity-report
```

An existing witness ID does not need `--witness-label`. To correct a mistaken link,
use `--identity-unlink` in place of `--witness-id` and `--witness-label`, with a new
reason and citation. Linking and reporting make no network requests. The database
does not infer aliases or joins from catalogue names or numeric IDs.

To import a reference-only inventory manifest and inspect a stored subset:

```powershell
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --import-inventory path/to/reviewed-inventory.json --dry-run
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --import-inventory path/to/reviewed-inventory.json
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --inventory-report INVENTORY_ID --inventory-book John --inventory-limit 20
```

The JSON manifest needs `format_version: 1`, a unique `inventory_id`, `edition`,
`scope`, `source_citation`, `reuse_terms`, `mapping_citation` (or `null` if no verse
is mapped), `reviewer`, and a `verses` array in numeric canonical order. Each verse
needs one `osis_ref`, `editorial_status` (`main`, `bracketed`, `omitted`, or
`uncertain`), and an explicit `ntvmr_refs` list. An empty mapping list means
unresolved, not absent; it needs a `mapping_note`. Non-main coordinates need an
`editorial_note`. Changed mappings also need a note. Corrections use a new inventory
ID. Filtering by book happens before `--inventory-limit`; omitted and uncertain
coordinates remain in the report with their status. This import makes no network
requests and does not validate textual evidence.

The v9 coverage-review path records an append-only decision for one indexed page
and one explicit inventory mapping. It requires a current retained document and
physical witness link. A reviewer supplies a checked-image, reviewed-transcription,
or catalogue-content-statement citation and marks the text `partial`, `full`,
`uncertain`, or `rejected`. `withdrawn` corrects an earlier decision while retaining
its history. The report counts current positive decisions once per physical witness
and verse; it flags decisions whose index response or identity link has changed.
These counts are limited to the reviewed records in that inventory, and whole-NT
completion remains false. The local benchmark database now has five cited P52
partial-coverage reviews in the bounded NA28 subset; independent human source
review and broader witness coverage remain open.

```powershell
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --coverage-review-inventory INVENTORY_ID --coverage-review-ref John.18.31 --coverage-review-ntvmr-ref John.18.31 --coverage-review-doc-id 10052 --coverage-review-page-id 10 --coverage-review-response-id RESPONSE_ID --coverage-review-status partial --coverage-review-evidence-type reviewed_transcription --coverage-review-reason "Visible Greek text checked" --coverage-review-citation "Specific transcription and location" --coverage-review-reviewer "Reviewer name"
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --coverage-report INVENTORY_ID --coverage-report-ref John.18.31
```

The review and report commands make no network requests. Use the response ID from
the stored coverage index; a search-response ID is a different source record.

The v12 [physical absence review](review_absence.py) records a directly checked
gap or other absence at a physical witness and inventory verse, including a
specific source location, citation, reason, and reviewer. It does not require an
NTVMR index row or verse mapping. Accepted evidence types are `checked_image` and
`reviewed_transcription`; absence cannot be inferred from a missing API hit.
Decisions are append-only: `absent`, `uncertain`, or `withdrawn`. A withdrawal
requires a current prior decision. A current `absent` decision that conflicts
with positive coverage is flagged by the report and audit, and holds ranking for
that verse until reviewed. No real physical absence has been recorded for the
five neighboring P52 index controls.

```json
{"format_version":1,"inventory_id":"INVENTORY_ID","osis_ref":"John.18.34","witness_id":"WITNESS_ID","decision":"absent","evidence_type":"checked_image","source_locator":"Specific folio and gap","reason":"What the checked source shows","citation":"Specific image or transcription citation","reviewer":"Reviewer name"}
```

```powershell
python review_absence.py --db data/ntvmr-v2.sqlite --action path/to/absence.json --dry-run
python review_absence.py --db data/ntvmr-v2.sqlite --action path/to/absence.json
python review_absence.py --db data/ntvmr-v2.sqlite --report INVENTORY_ID --ref John.18.34
```

The absence action's dry run validates JSON without opening the database. A real
action or report opens the schema and can upgrade an older replacement database;
back it up first. These commands make no network requests.

The v10 dating contract adds manually identified writing units (`original`,
`correction`, `supplement`, or `uncertain`) under a physical witness. A reviewed
coverage decision can be linked to one unit with a cited, append-only assignment.
Each unit can retain competing date assessments with their original notation,
source citation, consultation date, reviewer, and inclusive CE bounds. A separate
selection records which complete assessment is in force under a named `policy_id`;
selecting `null` withdraws that policy's selection. Unknown and invalid assessments
have no numeric bounds. A later
writing layer gets its own unit and date; it does not inherit the original hand's
date. Superseded coverage links remain in the report as history and are marked
`current_positive: false`.

These commands describe the existing storage interface. A `select_date` action
identifies the input to a particular calculation; it does not establish scholarly
consensus or make that assessment preferable to other sourced alternatives.
Without known consensus, any calculation using a single range must be labeled
as conditional on that range. Complete output must preserve the alternatives
and their effects on rankings, as required by the dating policy above.

Use `--dating-action path/to/action.json` for one offline decision and
`--dating-report WITNESS_ID` to inspect its units, competing dates, selection
history, and coverage links. Each action must have exactly the shown fields:

```powershell
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --dating-action path/to/action.json
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --dating-report example-object
```

```json
{"action":"create_unit","unit_id":"example-original","witness_id":"example-object","label":"Original hand","kind":"original","reason":"Hand identification","citation":"Specific source citation","reviewer":"Reviewer name"}
{"action":"assign_coverage","coverage_review_id":1,"unit_id":"example-original","reason":"Writing layer identified","citation":"Specific source citation","reviewer":"Reviewer name"}
{"action":"assess_date","unit_id":"example-original","status":"valid","date_min":100,"date_max":200,"original_notation":"Source's original notation","citation":"Specific dating source","consulted_on":"2026-09-29","reviewer":"Reviewer name"}
{"action":"select_date","unit_id":"example-original","assessment_id":1,"policy_id":"policy-v1","reason":"Documented dating policy","reviewer":"Reviewer name"}
```

Each line above is a separate JSON file; the IDs and dates are synthetic examples.
For an unknown or invalid assessment, set
both date bounds to `null`. To remove a coverage-unit link or date selection, set
`unit_id` or `assessment_id` to `null` in the corresponding action and give a
reason. The [P52 dating manifest](benchmarks/p52-dating-review-v2.json) preserves
the captured NTVMR 125-175 catalogue interval, two unbounded source descriptions,
and Barker's second-or-third-century assessment normalized to 101-300 CE. Its
policy selects `null`, so it supplies no selected-policy ranking. Its valid
assessments remain usable as conditional alternatives once coverage-unit links
are recorded; the null selection does not make those ranges unusable.

The new collector does not yet discover all candidates, resolve physical witness
aliases automatically, resolve NA28 verse membership, or establish indexing tiers.
A coverage index row is a **candidate**,
not automatically verified surviving text. A live run must be separately scoped,
budgeted, and reviewed against provider expectations before scaling.

The v11 ranking snapshot computes the optimistic and pessimistic first five
physical witnesses for one inventory verse and dating policy from current positive
coverage reviews with selected valid writing-unit dates. It retains date intervals,
event years, evidence and dating citations, and their source IDs. Multiple pages or
catalogue documents linked to one witness count once; multiple dated writing units
are resolved independently for each scenario. A report flags changed inputs as
`stale`, and a failed coverage refresh as `failed` while preserving the prior
snapshot. Changed index or identity evidence also holds the earlier snapshot as
`stale` until it is reviewed again. An `empty` result means no eligible dated
witness among reviewed records
for that verse; it does not establish physical absence or complete discovery.

```powershell
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --ranking-inventory INVENTORY_ID --ranking-ref John.18.31 --ranking-policy POLICY_ID --dry-run
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --ranking-inventory INVENTORY_ID --ranking-ref John.18.31 --ranking-policy POLICY_ID --compute-ranking
python sync_ntvmr.py --db data/ntvmr-v2.sqlite --ranking-inventory INVENTORY_ID --ranking-ref John.18.31 --ranking-policy POLICY_ID
```

These commands make no network requests. Ranking reports return a nonzero exit
status for `uncomputed`, `incomplete`, `stale`, or `failed` results. The bounded P52
coverage replay has no selected date. A provisional
whole-NT coordinate inventory exists, but most mappings, broader witness evidence,
and discovery completeness remain unresolved. A validated historical ranking is
not yet available. Prototype graph development can proceed for a declared scope
with sourced conditional dates and explicit limitations. P52's unselected date
does not require contributors to settle the dating dispute.

## John 1 four-witness prototype

The [review manifest](benchmarks/john1-reviewed-v3.json) cites the physical
transcriptions and image, witness identities, writing units, and date observations
for P66, P75, Codex Sinaiticus (01), and Codex Alexandrinus (02). The
[v2 subset inventory](benchmarks/john1-na28-subset-v2.json) cites direct NTVMR
coordinate mappings. The captured complete index responses and earlier named
searches are checked-in fixtures. Alexandrinus coverage comes from inspection of
the [public INTF image](https://ntmss.info/images/webfriendly/20002/20002x00490XX_INTF.jpg),
right column, lines 1–10, linked to page 490 by captured metadata. The
[British Library catalogue](https://searcharchives.bl.uk/catalog/040-002353500)
supplies its identity and date fields. Use an unused database path; the replay
rejects an existing destination before making changes:

```powershell
python replay_john1_prototype.py --db data/john1-prototype-v3.sqlite --dry-run
python replay_john1_prototype.py --db data/john1-prototype-v3.sqlite
python audit_reviewed.py --db data/john1-prototype-v3.sqlite --benchmark benchmarks/john1-evidence-benchmark-v1.json
python export_attestation.py --db data/john1-prototype-v3.sqlite --inventory na28-john1-prototype-subset-v2 --policy john1-conditional-source-v1 --dataset-output data/john1-prototype-complete-v3.json --graph-output data/john1-prototype-input-v3.json
python render_attestation.py --graph-input data/john1-prototype-input-v3.json --output examples/john1-prototype.html
```

The resulting [static chart](examples/john1-prototype.html) is the bounded
four-witness prototype. Its dates are conditional on broad source intervals:
P66 101–300, P75 201–300, 01 301–400, and 02 400–499 CE. The last interval
preserves the British Library's explicit numeric fields; it is not a conversion
of its fifth-century label to 401–500. Qualitative dating observations
without stated endpoints remain visible but unrankable. Each writing unit has a
null policy selection because no preferred scholar or documented consensus was
established; the exporter computes conditional combinations from the stored valid
assessments. The chart is labelled incomplete discovery and validation. It does
not claim the earliest extant manuscript in the full corpus, independent human
review, or exact NA28 wording.

The [coverage benchmark](benchmarks/john1-evidence-benchmark-v1.json) checks all
20 cited partial-coverage decisions. It asserts no selected-policy dates because
the graph uses conditional assessments. Automated tests separately check both
endpoint rankings and confirm that withdrawing evidence removes the witness.
These are reproducibility checks, not an independent scholarly review. Add
`--review benchmarks/john1-reviewed-v2.json` with a fresh database path to rebuild
the earlier three-witness scope. Earlier manifests are preserved.

Alexandrinus's image bears both the numbers 66 and 42. NTVMR labels page 490
`66r`; the British Library uses `42r` for the John opening. The review preserves
these source-specific labels and the image hash without asserting a general
foliation conversion. The image itself remains an external source; replay uses
the checked-in review and captured metadata without downloading it again.

The P66 transcription directly shows surviving Greek in John 1:1–5 without a
separate correction reading in those verse elements. Its captured NTVMR index
lists each verse on both page IDs 3 and 10. The [captured manuscript metadata](tests/fixtures/p66_metadata_probe.json)
identifies page ID 10 as folio 1 with John 1:1–14; page ID 3 lacks a folio label.
The replay verifies this link from the checked-in response. The index remains a
locator; the IGNTP transcription supplies the physical verse evidence.

## John 6 survival-boundary prototype

The [John 6:49–53 chart](examples/john6-gap-prototype.html) shows P66 and P75 throughout
the five verses and Alexandrinus at 6:49–50, followed by three directly reviewed
physical absences. A surviving beginning counts for 6:50 despite its lost ending.
Both endpoint scenarios therefore show witness counts of **3, 3, 2, 2, 2**.
Dates remain conditional on the stored catalogue assessments.

The [source review and human-review packet](docs/JOHN6_GAP_REVIEW.md) explains
the explicit transcription lacuna, page links, correction handling, source
licenses, measurements, and remaining checks. The replay uses checked-in inputs
and refuses an existing destination. It rebuilds John 1 v3 in the new database
to reuse its reviewed identities and indexes; the John 6 export selects only
the new five-verse inventory.

```powershell
python replay_john6_gap.py --db data/john6-gap-review-v2.sqlite
python audit_reviewed.py --db data/john6-gap-review-v2.sqlite --benchmark benchmarks/john6-gap-evidence-benchmark-v2.json
python export_attestation.py --db data/john6-gap-review-v2.sqlite --inventory na28-john6-gap-subset-v1 --policy john6-conditional-source-v1 --dataset-output data/john6-gap-complete-v2.json --graph-output data/john6-gap-input-v2.json
python render_attestation.py --graph-input data/john6-gap-input-v2.json --output examples/john6-gap-prototype.html
```

The increment passes fifteen cited evidence cases with zero audit findings and zero
replay network attempts. All **91 offline tests** pass. The three-witness scope is
incomplete; Sinaiticus and other witnesses have no coverage decisions in
this new inventory. Their lack of review is not physical absence. The provisional
whole-NT inventory and existing local databases are unchanged.

The default manifest is `benchmarks/john6-gap-reviewed-v2.json`. To reproduce the
earlier two-witness increment, pass `--review benchmarks/john6-gap-reviewed-v1.json`
with a fresh destination and audit using its v1 benchmark. Both review versions
retain the same coordinate inventory and conditional dating policy.

## Reviewed-data audit and P52 replay

The read-only reviewed-data audit checks SQLite integrity and foreign keys,
recomputes stored first-five ranking entries, and flags stale snapshots. It reports
counts by inventory book, review, physical absence and index state, latest document source type,
collection-job state, and the start century of valid date assessments. This is a
structural check; a clean result does not certify historical evidence.

```powershell
python audit_reviewed.py --db data/ntvmr-v2.sqlite --json
python audit_reviewed.py --db data/ntvmr-v2.sqlite --benchmark benchmarks/p52-evidence-benchmark-v1.json --source-controls benchmarks/p52-source-controls-v1.json --date-source benchmarks/p52-date-source-v1.json
python audit_reviewed.py --db data/ntvmr-v2.sqlite --source-controls benchmarks/p52-source-controls-v1.json
python audit_reviewed.py --db data/ntvmr-v2.sqlite --date-source benchmarks/p52-date-source-v1.json
```

A benchmark JSON file uses `format_version: 1`, a `benchmark_id`, `inventory_id`,
`policy_id`, and a nonempty `cases` array. Each case has `osis_ref`, `witness_id`,
`expected_coverage` (`positive`, `rejected`, or `absent`), `coverage_citation`,
`reviewed_on`
(ISO date), and `expected_date` and `date_citation` (both `null` when no date is
asserted). A date is a two-element inclusive CE interval, for example `[100, 200]`.
The audit requires the cited current review and, when supplied, a selected valid
date interval with the same citation. An `absent` case requires a current direct
physical absence review and no conflicting positive coverage. It exits `1` on
findings and `2` if the audit cannot run. Format version 2 requires shared
`coverage_citation` and
`reviewed_on` fields and an `expected_status` field per case. The checked-in P52
benchmark has five positive, explicitly `partial` coverage cases and no selected
date; it is not a complete scholarly validation gate. An older replacement
database may need the collector's additive schema upgrade before this audit can
run. Back it up with SQLite backup first, then run
`python sync_ntvmr.py --offline --db data/ntvmr-v2.sqlite --dry-run`.
That command changes the schema; it is not part of a read-only audit.

The [P52 source controls](benchmarks/p52-source-controls-v1.json) compare the
stored, pinned NTVMR index response with the surviving portions identified in
[Hurtado's description of the fragment](https://era.ed.ac.uk/bitstream/1842/648/2/P52_TB_article.pdf)
(introduction, p. 1). They require five indexed coordinates on the recorded pages
and flag unexpected neighboring coordinates or a changed source response. A pass
means this captured **candidate index** aligns with that bounded source check.
It does not validate an NA28 inventory, physical text, date, or earliest ranking.
If the source response changes, review it and version the controls instead of
silently replacing the pinned snapshot.

To reproduce the [cited P52 review](benchmarks/p52-reviewed-v1.json) from a fresh
clone, use a separate database path. The replay imports the captured index and
date sources, bounded NA28 inventory, physical identity, five partial-coverage
decisions, and the [writing-unit and dating review](benchmarks/p52-dating-review-v2.json).
The latter has four date assessments and a null policy selection. The final
command audits that same replay database:

```powershell
python replay_p52_benchmark.py --db data/p52-review-replay.sqlite --dry-run
python replay_p52_benchmark.py --db data/p52-review-replay.sqlite
python audit_reviewed.py --db data/p52-review-replay.sqlite --benchmark benchmarks/p52-evidence-benchmark-v1.json --source-controls benchmarks/p52-source-controls-v1.json --date-source benchmarks/p52-date-source-v1.json
```

The [P52 static chart preview](examples/p52-graph-preview.html) is generated
offline from the same checked-in inputs. Starting with a new database path:

```powershell
python replay_p52_benchmark.py --db data/p52-graph-preview.sqlite
python export_attestation.py --db data/p52-graph-preview.sqlite --inventory na28-john18-p52-subset-v1 --policy p52-cautious-source-v1 --dataset-output data/p52-graph-preview-complete.json --graph-output data/p52-graph-preview-input.json
python render_attestation.py --graph-input data/p52-graph-preview-input.json --output examples/p52-graph-preview.html
```

The chart covers ten John 18 coordinates. Five have reviewed partial P52
coverage and two rankable conditional date ranges; five remain uncomputed.
Each conditional chart shows both date endpoints, and the table cites the
coverage and dating sources, including observations unsuitable for numeric
ranking. The preview does not meet the several-witness milestone. The renderer
accepts at most 20 included verses and shows an explicit overflow state if
global dating combinations exceed 256; it does not pick an arbitrary case.
Run the export with `--include-omitted` or `--exclude-bracketed` to change the
graph population before rendering.

An offline integration test uses a temporary database and a test-only policy to
select Barker's broad
101-300 CE assessment. It verifies both scenario years for all five verses, the
cited benchmark and source controls, and detection of a corrupted ranking entry.
The test database is discarded; the checked-in P52 policy remains unselected and
the replay above creates no ranking snapshots.

The replay is offline and idempotent for matching records. Its `--dry-run`
validates the checked-in manifests without opening the target database, so it
cannot detect conflicts with existing decisions. A real replay stops on conflicting
prior decisions, but fixture and collection writes can already have occurred;
the whole replay is not one transaction. Use a separate path for a reproducibility
check and back up an existing reviewed database before applying a replay to it.
Replaying v2 over an unchanged v1 dating review appends Barker's assessment and
a new null selection while preserving the prior entries.
Its reviewer is identified as a Codex source review; an independent human check
of coverage and faithful recording of the library and published sources remains
necessary before using these records for a historical publication. This check
does not require resolving competing dating assessments. The five missing
neighboring verses remain source controls, not invented negative page reviews.

The separate [P52 date-source control](benchmarks/p52-date-source-v1.json) pins
the captured catalogue search response and checks its verbatim `II (M)` notation,
125–175 CE bounds, and `g` language code. It records the competing caution in
[Nongbri's dating study](https://www.cambridge.org/core/journals/new-testament-studies/article/abs/palaeography-precision-and-publicity-further-thoughts-on-pryliii457-p52/1D4E56BF0E9D4DDDA313D0C2754E2F28)
without assigning numeric bounds to that argument. Passing the source check does
not create a `date_assessment` or select a date for ranking. To replay the
captured date source separately into a local replacement database without a
network request, use the command below. The full P52 review replay already imports
this source, so it does not need this extra step:

```powershell
python sync_ntvmr.py --offline --fixture-p52 --fixture-language-probe --db data/ntvmr-v2.sqlite --run-id p52-date-source --search-ref John.18.31 --search-ga-num P52
```

The [official NTVMR API](https://ntvmr.uni-muenster.de/community/vmr/api/) is the
initial source. INTF distinguishes the Greek Liste from its broader manuscript
catalogue; source type and language must be validated explicitly. See
[INTF's explanation](https://ntvmr.uni-muenster.de/de/intfblog/-/blogs/liste-greek-and-manuscript-catalogue-all-).
No published request quota was established in this review. The plan uses one
worker, a configurable conservative delay, persistent caching, and a stop on
access blocks; a proxy or VPN should not be used to evade a block.

## Date scenarios and chart semantics

For each verse, retain every eligible, verified witness and its sourced date
assessments. Use the documented consensus range when consensus is known; otherwise
carry the competing ranges as equally valid alternatives. Within each explicitly
identified dating alternative, rank all candidates twice: by `date_min` for the
optimistic view, and by `date_max` for the pessimistic view. Select the first five
separately in each view; their membership and order may differ.

The optimistic/pessimistic pair describes the two ends of the ranges used in a
calculation; it does not resolve differences between scholars. Exports and charts
must identify those inputs and expose alternative ranges and resulting changes
in membership or order without silently favoring one. A manuscript still counts
once per verse in each result, however many dating assessments it has. The offline
export now supplies these conditional combinations for reviewed coordinates with
rankable dates. The bounded static chart renders them; a data model for documented
consensus is still needed.

Moving from older to newer years, a verse becomes colored at its first witness's
scenario date and changes shade at witnesses two through five. Unknown or
unprocessed verses remain explicitly marked as unknown. These are scenarios
within the collected evidence and chosen date assessments, not confidence
intervals or proof of a verse's date of composition.

Apply the [verse inclusion policy](#skipped-verses-and-graph-inclusion) to each
graph and its summary counts. A coordinate excluded by a filter must not appear
as a verse with no attestation.

## Files

| Path | Purpose |
| --- | --- |
| `sync_ntvmr.py`, `controlled_ntvmr.py` | Controlled collection and additive v12 schema in the v2 replacement database |
| `export_attestation.py` | Offline complete-inventory and filtered graph-data export |
| `render_attestation.py`, `examples/john1-prototype.html` | Bounded offline chart renderer and four-witness John 1 prototype, with physical-review provenance |
| `review_absence.py` | Offline cited physical absence decisions and reports |
| `replay_p52_benchmark.py`, `benchmarks/` | Offline, cited P52 subset inventory and review replay |
| `replay_john1_prototype.py`, `benchmarks/john1-reviewed-v2.json` | Offline, cited John 1 review replay with three covered witnesses and 02 identity |
| `build_na28_inventory.py`, `benchmarks/na28-coordinate-source-v1.json` | Reproducible publisher-coordinate ledger and provisional whole-NT inventory builder |
| `legacy_sync_ntvmr.py` | Disabled legacy collector retained for review |
| `audit_ntvmr.py` | Read-only offline audit of the legacy database |
| `audit_reviewed.py` | Read-only audit of the reviewed database and cited benchmarks |
| `tests/` | Audit and controlled collector tests; captured P52 API fixtures |
| `examples/p52-index-sample.json` | Offline, single-witness index sample |
| `ntvmr.sqlite` | Existing local exploratory snapshot, when available |
| `NTVMR Bruno/` | Manual API examples using the official HTTPS origin |
| `docs/DATA_REVIEW.md` | Findings, evidence, source checks, and limitations |
| `docs/DEVELOPMENT_PLAN.md` | Ordered implementation work and validation gates |
| `docs/PROTOTYPE_SCOPE.md` | Declared John 1 scope, source leads, and graph development measures |
| `docs/NA28_INVENTORY.md` | Full coordinate inventory report, exceptions, and unresolved mappings |

Project code is licensed under [GPL-3.0](LICENSE). Source metadata, images,
transcriptions, and edition text have their own terms; the code license does not
grant redistribution rights to those materials.
