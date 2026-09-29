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

This is a Python/SQLite collection prototype, with no graph or validated corpus
export yet. **The existing database is exploratory and should not be used to make
historical claims.** The September 2026 review found:

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

The first implementation slice now adds controlled document collection, an explicit
long-response parser, separate metadata and coverage checkpoints, and an
[offline P52 index sample](examples/p52-index-sample.json). The sample is one
witness's indexed coordinates, not a complete set of Greek witnesses or an NA28
ranking. A second slice adds bounded named-witness passage searches and a persisted
candidate index. Search hits remain unreviewed candidates. Start with the [data/code review](docs/DATA_REVIEW.md), then the ordered
[development plan and acceptance criteria](docs/DEVELOPMENT_PLAN.md).

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

## Run the offline checks

Python 3.10+ is required for the audit; verified with Python 3.12. The audit and
its tests use only the standard library and make no network requests.

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

`ntvmr.sqlite` is a local snapshot and may not be present in a fresh clone. Tests
create their own temporary databases. The human-readable snapshot findings are
recorded in the review document.

## Controlled collection

[`sync_ntvmr.py`](sync_ntvmr.py) uses only the Python standard library. It creates
a separate v2 database, requires explicit document IDs and a positive network
request budget for live work, and uses the official HTTPS API by default. It has
offline replay, immutable source responses, durable attempt records, and separate
metadata and coverage job states. The conservative five-second spacing is a
project default, not a confirmed NTVMR quota.

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

The new collector does not yet discover all candidates, identify physical witness
aliases, resolve NA28 verse
membership, or establish indexing tiers. A coverage index row is a **candidate**,
not automatically verified surviving text. A live run must be separately scoped,
budgeted, and reviewed against provider expectations before scaling.

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
| `sync_ntvmr.py`, `controlled_ntvmr.py` | Controlled collection and additive v7 schema in the v2 replacement database |
| `legacy_sync_ntvmr.py` | Disabled legacy collector retained for review |
| `audit_ntvmr.py` | Read-only offline audit of that schema |
| `tests/` | Audit and controlled collector tests; captured P52 API fixtures |
| `examples/p52-index-sample.json` | Offline, single-witness index sample |
| `ntvmr.sqlite` | Existing local exploratory snapshot, when available |
| `NTVMR Bruno/` | Manual API examples using the official HTTPS origin |
| `docs/DATA_REVIEW.md` | Findings, evidence, source checks, and limitations |
| `docs/DEVELOPMENT_PLAN.md` | Ordered implementation work and validation gates |

Project code is licensed under [GPL-3.0](LICENSE). Source metadata, images,
transcriptions, and edition text have their own terms; the code license does not
grant redistribution rights to those materials.
