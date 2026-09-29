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
| `sync_ntvmr.py`, `controlled_ntvmr.py` | Controlled document collection and v2 schema |
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
