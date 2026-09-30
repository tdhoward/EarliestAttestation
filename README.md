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

## Current status

This is a Python/SQLite research prototype. Controlled collection, append-only
reviews, writing-unit dating, and both first-five ranking scenarios are implemented
through schema version 11. There is no graph or validated corpus export yet.
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

The progress check on 2026-09-29 passed **54 offline tests** on Python 3.12.6.
The local reviewed database has ten John 18 inventory coordinates, five explicit
NTVMR mappings, one physical witness, and five cited partial-coverage decisions.
Its combined audit passes all five evidence cases and both source controls with
zero findings. It has **no date assessments, selected dates, or ranking snapshots**;
`historical_validation_complete` remains false. These counts describe the inspected
local snapshot, which is not distributed with the repository.

The next milestone is independent review of the P52 sources, writing unit, and
competing dating assessments, followed by a reproducible bounded ranking if a
usable date can be selected. Broader witnesses, discovery completeness, and a
whole-NT inventory remain open. Use the [development plan](docs/DEVELOPMENT_PLAN.md)
for current priorities and acceptance criteria; the original review is the legacy
baseline.

A small, budgeted live check on 2026-09-29 found P52 at John 18:31 and P66,
P75, 01, and 02 at John 1:1. The [captured four-witness search responses](tests/fixtures/john_named_probe.json)
show that codex names can be JSON numbers. These lookups do not establish complete
discovery or verified physical coverage.

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
for the P52 benchmark. **No whole-NT NA28 inventory has been imported or certified.**
The inventory report always leaves whole-NT
completion unconfirmed. Book IDs follow the [OSIS New Testament list](https://wiki.crosswire.org/OSIS_Book_Abbreviations).

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
`user_version` is **11**. This filename is not the schema version. Always pass
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
reason. No real scholarly date assessment has been entered into the repository.

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
coverage review has no selected scholarly date, and there is no whole-NT inventory or
complete discovery, so the repository has no historical ranking to publish.

## Reviewed-data audit and P52 replay

The read-only reviewed-data audit checks SQLite integrity and foreign keys,
recomputes stored first-five ranking entries, and flags stale snapshots. It reports
counts by inventory book, review and index state, latest document source type,
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
`expected_coverage` (`positive` or `rejected`), `coverage_citation`, `reviewed_on`
(ISO date), and `expected_date` and `date_citation` (both `null` when no date is
asserted). A date is a two-element inclusive CE interval, for example `[100, 200]`.
The audit requires the cited current review and, when supplied, a selected valid
date interval with the same citation. It exits `1` on findings and `2` if the
audit cannot run. Format version 2 requires shared `coverage_citation` and
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
date sources, bounded NA28 inventory, physical identity, and five partial-coverage
decisions. The final command audits that same replay database:

```powershell
python replay_p52_benchmark.py --db data/p52-review-replay.sqlite --dry-run
python replay_p52_benchmark.py --db data/p52-review-replay.sqlite
python audit_reviewed.py --db data/p52-review-replay.sqlite --benchmark benchmarks/p52-evidence-benchmark-v1.json --source-controls benchmarks/p52-source-controls-v1.json --date-source benchmarks/p52-date-source-v1.json
```

The replay is offline and idempotent for matching records. Its `--dry-run`
validates the checked-in manifests without opening the target database, so it
cannot detect conflicts with existing decisions. A real replay stops on conflicting
prior decisions, but fixture and collection writes can already have occurred;
the whole replay is not one transaction. Use a separate path for a reproducibility
check and back up an existing reviewed database before applying a replay to it.
Its reviewer is identified as a Codex source review; an independent human check
of the library and published source remains necessary
before using these records for a historical publication. The five missing
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

For each verse, retain every eligible, verified witness with its sourced
`date_min` and `date_max`. Rank all candidates twice: by `date_min` for the
optimistic view, and by `date_max` for the pessimistic view. Select the first five
separately in each view; their membership and order may differ.

Moving from older to newer years, a verse becomes colored at its first witness's
scenario date and changes shade at witnesses two through five. Unknown or
unprocessed verses remain explicitly marked as unknown. These are scenarios
within the collected evidence and chosen date assessments, not confidence
intervals or proof of a verse's date of composition.

## Files

| Path | Purpose |
| --- | --- |
| `sync_ntvmr.py`, `controlled_ntvmr.py` | Controlled collection and additive v11 schema in the v2 replacement database |
| `replay_p52_benchmark.py`, `benchmarks/` | Offline, cited P52 subset inventory and review replay |
| `legacy_sync_ntvmr.py` | Disabled legacy collector retained for review |
| `audit_ntvmr.py` | Read-only offline audit of the legacy database |
| `audit_reviewed.py` | Read-only audit of the reviewed database and cited benchmarks |
| `tests/` | Audit and controlled collector tests; captured P52 API fixtures |
| `examples/p52-index-sample.json` | Offline, single-witness index sample |
| `ntvmr.sqlite` | Existing local exploratory snapshot, when available |
| `NTVMR Bruno/` | Manual API examples using the official HTTPS origin |
| `docs/DATA_REVIEW.md` | Findings, evidence, source checks, and limitations |
| `docs/DEVELOPMENT_PLAN.md` | Ordered implementation work and validation gates |

Project code is licensed under [GPL-3.0](LICENSE). Source metadata, images,
transcriptions, and edition text have their own terms; the code license does not
grant redistribution rights to those materials.
