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

This is a Python/SQLite collection prototype, with no graph or validated export
yet. **The existing database is exploratory and should not be used to make
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

The review adds documentation, source fixtures, and an offline audit. It does not
repair the sync pipeline or rewrite the existing database. Start with the
[data/code review](docs/DATA_REVIEW.md), then the ordered
[development plan and acceptance criteria](docs/DEVELOPMENT_PLAN.md).

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

## Existing collector

[`sync_ntvmr.py`](sync_ntvmr.py) requires `requests`. To inspect its options:

```powershell
python -m pip install requests
python sync_ntvmr.py --help
```

Do not start a full collection run until the blocking fixes in the development
plan are complete. The script currently points to a private HTTP proxy and
defaults to one second between requests. Its `--subset` option only controls
seeding, not which existing rows it processes. `--refresh` does not imply
`--recompute`, and adding `--coverage` will not revisit already-computed verses.
The planned official HTTPS default, offline mode, request budget, rate-limit
handling, and checkpoint repairs are not implemented yet.

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
| `sync_ntvmr.py` | Legacy collector and schema; known limitations above |
| `audit_ntvmr.py` | Read-only offline audit of that schema |
| `tests/` | Audit tests and small captured P52 API fixtures |
| `ntvmr.sqlite` | Existing local exploratory snapshot, when available |
| `NTVMR Bruno/` | Manual API examples, including the legacy filter/proxy settings |
| `docs/DATA_REVIEW.md` | Findings, evidence, source checks, and limitations |
| `docs/DEVELOPMENT_PLAN.md` | Ordered implementation work and validation gates |

Project code is licensed under [GPL-3.0](LICENSE). Source metadata, images,
transcriptions, and edition text have their own terms; the code license does not
grant redistribution rights to those materials.
