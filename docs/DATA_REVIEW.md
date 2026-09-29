# Code and data review

Review date: 2026-09-29. Reference edition selected by the project owner: **NA28**.
This review describes the collector now preserved as
[`legacy_sync_ntvmr.py`](../legacy_sync_ntvmr.py); the safe entry point is now
[`sync_ntvmr.py`](../sync_ntvmr.py).
This review covers the former sync implementation, the local `ntvmr.sqlite`, the Bruno examples,
official API documentation, and a small set of direct P52 API checks. It does not
certify the corpus or the dates of every manuscript.

## Conclusion

Keep NTVMR as the initial catalogue/index source, but rebuild the derived results
after repairing collection and evidence validation. The present dataset measures
the minimum date among a restricted search result, without confirming surviving
verse evidence. Its earliest-result table is not suitable for the proposed chart.

The strongest explanation for the implausibly late results is now reproducible:
the collector's `lang=gr` filter excludes P52 in a controlled query, whereas
`lang=grc` and no language filter find it. The coverage parser also misses the
actual response field. Both problems must be fixed before larger runs; changing
the language string alone would leave the other correctness defects in place.

## Local snapshot

The database was inspected with SQLite URI `mode=ro`. `PRAGMA integrity_check`
returned `ok`. The file was not migrated, recomputed, or refreshed.

| Measurement | Observed value |
| --- | ---: |
| Seeded references | 7,959 across 27 books |
| Earliest-result rows | 1,326 |
| Seeded references without a result | 6,633 |
| Selected manuscripts | 13 |
| Coverage rows (`manuscript_verse`) | **0** |
| Cached responses | 1,343, all with HTTP status 200 |
| Cached search responses | 1,327 |
| Cached manuscript-detail responses | 14 |
| Cached versification responses | 2: KJV/John and KJV/NT |
| Unique candidate document IDs in cached searches | 37 |

Cache timestamps span 2025-12-29T23:44:23Z through 2025-12-30T02:13:26Z.
The cached URLs use the private proxy address configured in the script. The file's
SHA-256 at review was
`8e20bdb2a0377598f845791773fcd11e183b972bc407e90e5be5997379af8826`.

| Selected witness | Stored interval, CE | Earliest-result rows |
| --- | --- | ---: |
| GA 1 / docID 30001 | 1100–1199 | 1,179 |
| GA 2952 / docID 32952 | 900–999 | 106 |
| GA 2932 / docID 32932 | 900–1000 | 14 |
| P133 / docID 10133 | 200–299 | 12 |
| P134 / docID 10134 | 200–399 | 3 |
| Eight witnesses with T-prefixed names | Several intervals | 12 |

The distribution is a strong diagnostic warning, not a substitute for checking
individual witnesses. The cache contains candidates named NA22, NA25, NA26,
NA27, Erasmus 1516, and Stephanus 1550/1551 as well as manuscript candidates.
None of those named printed editions is a selected winner in this snapshot, but
they would contaminate a naive first-five implementation.

Existing results cover all seeded references in 1 Corinthians, 1 John, 1 Peter,
1 Thessalonians, and 1 Timothy, plus 235 references in 2 Corinthians and 242 in
John. John 18:31–38 was **not processed**, so the database does not directly record
an incorrect P52 result there. The cached zero-result query is `2Cor.13.14`;
that is a failed discovery outcome to investigate, not proof of no witness.

All stored manuscripts have detailed metadata. No orphaned selected witnesses,
invalid selected date intervals, or stored date mismatches were detected. These
structural successes do not compensate for the absence of coverage validation.

## Source checks

NTVMR is an INTF research resource and a sensible starting point. Its catalogue
is broader than the Greek Liste: a document appearing in an API result does not
itself establish eligibility as a Greek New Testament manuscript. INTF explicitly
distinguishes these collections in its
[catalogue explanation](https://ntvmr.uni-muenster.de/de/intfblog/-/blogs/liste-greek-and-manuscript-catalogue-all-).

The [search endpoint help](https://ntvmr.uni-muenster.de/community/vmr/api/metadata/liste/search/)
describes `indexContent` as matching some part of a requested passage. Its `limit`
is an approximate page limit, with complete documents returned even when they
exceed it; the documentation mentions 200. Do not assume this is ordinary
document pagination, invent an `offset` parameter, or interpret `pagecount` as
the number of result pages. Establish a complete discovery strategy explicitly.
The help still gives `gr` as its language example, so documentation alone does
not resolve the observed behavior.

### Controlled language comparison

Three sequential requests used the official HTTPS host, `gaNum=P52`,
`indexContent=John.18.31`, `detail=document`, `format=json`, and `limit=10`.
Requests were separated by at least five seconds; all returned HTTP 200.

| Language parameter | Count | Returned witness | Returned language | Date bounds |
| --- | ---: | --- | --- | --- |
| `gr` | 0 | None | — | — |
| `grc` | 1 | P52 / 10052 | `g` | 125–175 CE |
| Omitted | 1 | P52 / 10052 | `g` | 125–175 CE |

The parsed responses and request parameters are preserved in
[`p52_language_probe.json`](../tests/fixtures/p52_language_probe.json).
This establishes a problem with the current filter for this witness on the
review date. It does not establish a universal mapping for every language,
bilingual witness, or historic API version. Cached 2025 search candidates have
codes such as `grc` and `grc_lat`, while this P52 record has `g`.

### Controlled coverage check

One request to
[`biblicalcontent/get/?docID=10052&detail=long&format=json`](https://ntvmr.uni-muenster.de/community/vmr/api/biblicalcontent/get/?docID=10052&detail=long&format=json)
returned five entries:

| Page ID | Individual `osisID` values |
| --- | --- |
| 10 | `John.18.31`, `John.18.32`, `John.18.33` |
| 20 | `John.18.37`, `John.18.38` |

The response's `data.indexContents.indexContent` is a mixed array: a summary
string followed by objects containing `osisID`, numeric `indexContent`, `docID`,
and `pageID`. The current parser does not read `osisID`, so it extracts **zero**
refs. The response is preserved in
[`p52_coverage_probe.json`](../tests/fixtures/p52_coverage_probe.json).

As an independent scholarly check, L. W. Hurtado describes the surviving partial
lines on these two sides in the introduction to
[P52 and the Nomina Sacra (2003)](https://era.ed.ac.uk/bitstream/1842/648/2/P52_TB_article.pdf).
Use the five verses as positive coverage controls and 18:30, 18:34–36, and 18:39
as negative controls **for P52**. They are not negative controls for other
manuscripts. This does not require P52 to be the earliest witness under every
dating policy, and does not turn its fragmentary text into complete verses.

The [coverage endpoint help](https://ntvmr.uni-muenster.de/community/vmr/api/biblicalcontent/get/)
describes page indexing, offsets within boundary verses, and indexing tiers; it
identifies tiers 4 and above as AI indexing awaiting human confirmation. The
sample long response does not include those fields. Determine how to retrieve
review status and lacuna information before admitting general index entries as
verified physical evidence. A `baseText` can supply calculated letters from an
edition; those letters must not be mistaken for a manuscript transcription.

The two endpoint help pages for coverage and manuscript metadata, and the one
coverage response, were fetched sequentially with five-second gaps as well.
No full sync, manuscript sweep, proxy/VPN request, or local server was run. A
local socket restriction initially prevented direct HTTP access; a subsequent
permitted bounded read succeeded. This was not evidence of an NTVMR rate block.
No published quota or reason for the user's earlier block was established.

## Confirmed code defects and required adjustments

References below identify functions in [`legacy_sync_ntvmr.py`](../legacy_sync_ntvmr.py).

| Priority | Finding | Consequence / required adjustment |
| --- | --- | --- |
| Blocking | `compute_earliest_for_verse` sends `lang=gr` | Misses P52 in the controlled probe. Test a normalized language policy against known witnesses, including bilingual records. |
| Blocking | `extract_osis_refs_from_biblicalcontent` ignores `osisID` | Actual P52 long response yields zero coverage; implement its documented/observed contract. |
| Blocking | Earliest selection occurs before coverage and never consults it | A search hit becomes a claimed attestation without physical evidence validation. Store candidates separately and rank verified coverage. |
| Blocking | Only the selected candidate is normalized/persisted | First-five and independent pessimistic rankings are impossible from these tables. Persist all candidates and their evidence. |
| High | No witness-type filter beyond language | Printed editions and other catalogue materials can become witnesses. Classify sources explicitly. |
| High | `ORDER BY osis_ref` uses string order | `1Cor.1.10` precedes `1Cor.1.2`, and 1 Corinthians precedes Matthew. Persist numeric canonical order. |
| High | `--subset` only affects seeding; existing verses are all loaded | A John run against the current database processes other books. Filter the selected inventory before limiting. |
| High | Default KJV seed; no edition membership | A chapter maximum is not an NA28 inventory. Record edition/version and omitted or bracketed verse status. |
| High | `choose_earliest_doc` rejects only a pair of zero dates | One zero bound, missing dates, reversed intervals, and unusable IDs can still win. Validate both bounds and IDs first. |
| High | One lower-bound sort determines the stored winner | That winner's upper bound is not the pessimistic earliest date across witnesses. Rank each scenario separately. |
| High | API errors and unknown response shapes can become an empty document list | Distinguish a successful empty result from failed parsing and incomplete collection. |
| High | HTTP failures are caught per verse and the run continues | 403/429 can trigger more requests; network exceptions skip the post-request sleep. Stop on blocks and use bounded retry/backoff for transient failures. |
| High | Existing `verse_earliest` rows skip metadata and coverage stages | A previously committed result with a later stage failure is never repaired automatically. Track independent stage completion. |
| High | Recompute returning no candidate leaves an old result in place | Stale attestation survives a successful empty refresh. Replace derived results atomically after validated processing. |
| Medium | All errors eventually lead to `return 0` | Automation cannot tell a failed run from success. Return failure/partial status and a summary. |
| Medium | No result count/completeness validation | Retain search diagnostics and prove discovery completeness within declared bounds. |
| Medium | `manuscript_verse` primary key is just document + verse | Multiple pages and sources collapse into one record. Separate detailed evidence from deduplicated witness/verse pairs. |
| Medium | Coverage insertion uses `INSERT OR IGNORE` | Corrected refs and withdrawn evidence cannot replace stale rows. Version or replace a successful coverage snapshot. |
| Medium | No foreign keys are declared despite enabling their pragma | Orphans are possible. Add actual constraints and migration tests. |
| Medium | Coverage count returns `con.total_changes` | This is cumulative connection activity, not inserted coverage rows. Measure a before/after delta. |
| Medium | Metadata detail updates raw JSON but not normalized dates | Search dates can remain inconsistent with a newer detail record. Reconcile source assessments explicitly. |
| Medium | Session object created as a dataclass default | All clients share a session. Use an instance factory and close connections/sessions. |

Additional parser probes confirmed that `{pageID: 10, osisRef: "John.18.31"}`
loses its page ID because the ref is extracted first. A range such as
`John.18.31-John.18.33` is accepted as one fake verse, while a display string
`John 18:31-33` is ignored. Arbitrary `ref`/`key`/`verse` fields are too permissive
for evidence extraction. Parse only known structures; validate individual refs
against the inventory. Prefer the long endpoint's individual entries. Never fill
a range between the first and last surviving verse across a lacuna.

`get_page_ids_for_doc` assumes page IDs occur at the root of extracted manuscript
records. Nested page handling and the actual `detail=page` response contract still
need a fixture. The fallback has not been demonstrated to recover missing coverage.

## Operational and provenance gaps

The hardcoded private HTTP proxy makes the collector machine-specific. Use the
official HTTPS origin by default with explicit configuration for ordinary network
requirements. Neither impersonating a browser in `make_session` nor switching
network identity addresses rate limits. The existing default is one second after
a completed request, with no `Retry-After` handling, request budget, or block stop.

`api_cache` keys include the entire URL, so switching from proxy to official host
misses old cache entries. It overwrites prior responses on refresh and shares the
business transaction; failures can roll back useful downloaded evidence. Separate
immutable response history and durable download checkpoints from normalization.
Retain request parameters, response status/headers, retrieval time, content hash,
origin/transport, parser version, and the evidence-to-response link.

There is no offline replay mode. Existing rows also prevent `--refresh` alone from
refreshing their processing, and `--reseed` can reuse a cached response. The current
cache TTL plus 2025 retrieval dates would cause broad re-fetching during new work.
Use old cached data for diagnostics, but do not relabel its filtered candidate set
as a corrected complete corpus.

Dates are currently stored as one interval with no bibliographic assessment or
policy. Preserve the source's original notation alongside its numeric bounds.
The observed P52 interval of 125–175 is a catalogue assessment, not a measured date
or a permanent scholarly consensus. Do not replace it with a hardcoded 125, an
average, or an unsourced merged range. Later alternative assessments should remain
separate and selectable.

## Verification delivered

[`audit_ntvmr.py`](../audit_ntvmr.py) is a read-only, dependency-free audit of the
legacy schema. On this snapshot it reports:

- 1,326 earliest results with no matching coverage row;
- 6,633 seeded refs without a result;
- 1,327 cached searches using the suspect `gr` filter;
- two KJV versification responses, which cannot establish NA28 membership.

All 12 audit unit tests passed on Python 3.12; Python compilation and local
documentation-link checks also passed. The database's SHA-256 was unchanged after
the review. The unit tests use temporary databases and captured source responses. They check
read-only behavior, missing/unsupported databases, bad intervals, orphaned links,
stale dates, missing evidence, HTTP/application errors, search shape/count errors,
singleton/empty responses, and CLI exit codes. They do **not** certify the legacy
collector or prove that all surviving witnesses have been discovered. The P52
coverage fixture supports the next parser implementation; the auditor itself does
not parse coverage responses or validate indexing tiers.

Run the commands in the [README](../README.md). The next implementation work and
its scientific acceptance tests are specified in the
[development plan](DEVELOPMENT_PLAN.md).
