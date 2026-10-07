# Bounded witness discovery

Candidate discovery is independent of the witness pool already collected.
Reusing a document's contents report supplies explicit verse claims; it does
not establish that all earlier witnesses for another verse have been found.
The app therefore ranks up to five **earliest collected witnesses per verse**,
including in the book view, and displays discovery status separately from
reported contents and date rankability.

## Planned catalogue scope

The discovery target is all 27 New Testament books across all four NTVMR Greek
NT manuscript categories, using independently budgeted book/category or smaller
range searches:

| NTVMR document ID range | Manuscript category |
| --- | --- |
| 10000–19999 | Papyri |
| 20000–29999 | Majuscules |
| 30000–39999 | Minuscules |
| 40000–49999 | Lectionaries |

The first digit identifies the category; the remaining four encode the
Gregory–Aland number. For example, 10045 identifies P45. See the
[NTVMR usage guide](https://digitalorientalist.com/2023/02/28/a-guide-for-using-the-new-testament-virtual-manuscript-room-part-1/)
for this ID convention. Categories and ID order do not establish manuscript age.

A verse's fifth earliest collected witness may date much later than its first,
and the five may span categories. Late results can motivate broader searches,
but neither finding five witnesses nor finding early papyri completes the
planned discovery target. Discover candidates independently in all four
categories and rank them using their scholarly contents and date reports.

This is planned scope, not completed coverage. Current discovery flags evaluate
only scopes registered in `data/discovery.json`; they do not automatically
require all four categories. Record each searched book/range independently and
retain its qualifications when reporting completion. Completing every planned
indexed search still does not establish exhaustive coverage of unindexed
witnesses; the [discovery states](#meaning-and-states) retain that distinction.

## Central collection workflow

`collect_source_discovery.py` reads `data/collection.json`, performs one declared
book/range search, reuses existing captures, and collects separate metadata and
long contents for new candidates. It updates the same central document register,
`data/discovery.json`, and `data/attestations.json`. No HTML, book-specific dataset,
or revision series is created. Raw source captures live in `data/sources/`.

Save a proposed finite request definition in ignored scratch storage, for example
`data/.cache/discovery-request.json`. Define `format_version: 1`, a stable
`scope_id`, an OSIS `book`, `doc_id_min`, `doc_id_max`, `page_limit`, a catalogue
citation, documented `access_expectations`, `request_budget`,
`minimum_interval_seconds`, and `maximum_run_seconds`. A definition must declare
1–50 attempts, at least five seconds between requests, at most 600 seconds, a
range of at most 50,000 IDs, and a page limit of 1–200. These are project safeguards,
not claims about the provider's numerical quota.

```powershell
python collect_source_discovery.py --definition data/.cache/discovery-request.json --run-id declared-run
```

The same run ID resumes against `data/.cache/collection.sqlite` within its remaining
budget. A run's definition is fixed; blocked access is never automatically retried.
An access block during metadata or contents collection stops the remaining
documents. Resuming that run preserves the original blocked job and makes no
further document requests, including refresh requests.
The register holds the current record for each declared scope. Other scopes and
all existing document captures remain available. Metadata-only candidates can
resume contents collection without being skipped as already complete.

Canonical HTTPS is the default. Optional `--https-proxy` uses a configured CONNECT
proxy. The owner-supplied local API proxy uses
`--base-url "<local proxy>/community/vmr/api"` and must be recorded in the
ignored request definition. Substitute the address documented once in
[README](../README.md#collect-more-data) before running. Scholarly citations always
use canonical NTVMR endpoints; TLS verification is not a collection prerequisite.
Permanent records replace the proxy origin with `<local proxy>` while preserving
raw response bodies, hashes, paths, parameters, and retrieval dates. Actual request
URLs remain only in ignored local definitions and request caches. Do not change routes or
identity to bypass a provider block. Establish provider expectations before bulk
access. Tests and data rebuilds make no live requests.

## Meaning and states

The [captured search help](../data/reference/contracts/metadata_liste_search_help.json)
documents book/chapter/verse indexing, finite document ranges, and continuation.
Each page repeats the original filters. The collector checks terminal/partial
flags, advancing cursors, range membership, count mismatches, and duplicate rows.
Captured pages and response headers support offline replay. Search rows themselves
create neither presence nor absence claims.

| Discovery state | Meaning |
| --- | --- |
| `not_searched` | No applicable scope is recorded |
| `search_incomplete` | An applicable scope is pending, failed, blocked, or incomplete |
| `candidate_collection_incomplete` | Search completed, but candidates still need usable metadata or contents |
| `bounded_search_complete` | Declared searches completed and returned candidates were collected |

For multiple scopes on a book, completion requires all of them to be ready.
Other books stay unsearched. `corpus_complete` remains false: a bounded indexed
query cannot establish that other ranges or unindexed witnesses contain no
earlier candidates. Missing contents entries remain unknown, never inferred absence.

## Current source scope

The central discovery register contains completed Galatians, Hebrews, Ephesians,
Philippians, Colossians, 1 Thessalonians, 2 Thessalonians, 1 Timothy, 2 Timothy,
Titus, and Philemon searches for IDs 10000–19999.
The Galatians search ran without name, date, or language search filters. It returned P46, P51, and P135;
all have metadata and long contents captures. GA 01 and GA 02 are additional
collected witnesses outside that range.

P51 supplies 14 Galatians presence pairs and P135 supplies 17, all with the
provider's indexing tier 3. Their exact catalogue date bounds are respectively
400–425 CE (`V (A)`) and 301–499 CE (`IV/V`). The record retains source fields,
citations, retrieval times, hashes, and request cost. Successful collection used
an existing HTTP relay. Their citations identify the canonical NTVMR endpoints.
Broader catalogue discovery is still incomplete.

The completed Hebrews search for IDs 10000–19999 returned P12, P13, P17, P46,
P79, P89, P114, P116, P126, and P130. It reused P46 and captured metadata and long
contents for the nine new witnesses. Those reports add 163 presence pairs.
The pilot used 19 successful requests through the owner-supplied proxy, after
six direct attempts received no source response, within a total budget of 25.

All 27 books now reuse explicit contents fields from the existing document
captures. That offline expansion creates no additional search completion.

The Ephesians search returned P46, P49, P92, and P132. It reused P46's metadata
and contents and captured both reports for each new candidate. It used seven
successful proxy requests and three sandbox-denied attempts with no provider
response, within a fixed 25-attempt budget. The new reports add 41 Ephesians
presence pairs and four 2 Thessalonians presence pairs. P49's report includes
Ephesians 4:29 and 4:31 but no exact 4:30 entry; that witness/verse pair remains
unknown. No neighboring-verse expansion or absence inference was made.

The independent 2 Thessalonians search returned P30 and P92. It reused P92's
metadata and contents and captured both reports for P30. Three successful proxy
requests followed three sandbox-denied attempts without a provider response,
using six of the fixed 25-attempt budget. P30 adds two 2 Thessalonians presence
pairs and 19 in 1 Thessalonians. Its complete catalogue date estimate is
200–299 CE (`E II - A III`). Exact entries report 1 Thessalonians 5:10 and 5:12
without 5:11; that pair remains unknown. Every prior source claim, date estimate,
and coverage state is preserved.

The independent 1 Thessalonians search returned P30, P46, P61, and P65. Reusing
P30 and P46 left only P61 and P65's metadata and long contents to collect: five
successful requests, including the search, within the declared 25-attempt budget.
P61 adds 56 default presence pairs across seven books; P65 adds 17 in
1 Thessalonians. P61's reported Romans 16:24 entry stays supplementary and is
excluded by the default omitted-coordinate filter. Their complete catalogue
dates are 700–725 CE (`VIII (A)`) and 200–299 CE (`III`), respectively. Exact
P65 entries include 1 Thessalonians 2:1 and 2:6 without entries for 2:2–5;
those missing pairs remain unknown. All earlier claims, dates, and coverage
states survived unchanged.

The independent Philippians search returned P16, P46, and P61. Reusing P46 and
P61 left only P16's metadata and long contents to collect: three successful proxy
requests, including the search, after three sandbox-denied attempts without a
provider response. All six attempts remain within the fixed 25-attempt budget.
P16 adds 15 presence pairs from exact entries for Philippians 3:10–17 and 4:2–8;
the metadata reports indexing tier 3 for both pages. Adjacent missing entries,
including 3:9, 3:18, 4:1, and 4:9, remain unknown. Its numeric date bounds 200–399 CE
and original notation `IV` are copied independently and retained exactly; no
notation conversion or reconciliation is performed. All prior claims, date
alternatives, coverage states, and other scopes survive unchanged. The
Philippians addition increased app data by 12,317 bytes.

The independent Colossians search returned P46 and P61. Both witnesses' metadata
and long contents were already retained, so only the book-index query was needed.
One successful proxy request followed three sandbox-denied attempts without a
provider response, using four of the fixed 25-attempt budget. No document reports
were refreshed. All earlier claims, complete date estimates, coverage states,
rankings, and discovery scopes survived unchanged. The 95 Colossians coordinates
gain bounded discovery completion; missing contents entries remain unknown.
That search retained 49 usable reports for 21 witnesses and seven searches,
with no pending candidates. App data was 2,060,609 bytes, growing by 4,702 bytes
for this search and its provenance.

The independent Philemon search returned P61, P87, and P139. P61's metadata and
long contents were reused, leaving five successful requests for the search and
the two new witnesses' reports, within a declared 25-attempt budget. Exact
reported entries add five presence pairs for P87 (1:13–15, 24–25) and six for
P139 (1:6–8, 18–20), with indexing tier 3. Their complete catalogue date estimates
are 200–299 CE (`III`) and 300–399 CE (`IV`). Missing entries, including P87 1:16
and P139 1:9, remain unknown. Prior claims, complete dates, coverage states, and
other discovery scopes survived unchanged. Only the 25 Philemon coordinates
gain bounded discovery completion. That addition brought the collection to 54 usable reports for
23 witnesses and eight searches, with no pending candidates. App data was
2,076,312 bytes, growing by 15,703 bytes for this addition.

The independent Titus search returned P32 and P61. P61's metadata and long
contents were reused, leaving three successful proxy requests for the search
and P32's two reports, within the declared 25-attempt budget. Exact reported
entries add 11 presence pairs for Titus 1:11–15 and 2:3–8, with indexing tier 3.
P32's complete catalogue date estimate remains 200–225 CE (`III (A)`). Missing
entries, including 1:10, 1:16, 2:2, and 2:9, remain unknown. Prior claims,
complete dates, coverage states, rankings outside the added coverage, and other
discovery scopes survived unchanged. Only the 46 Titus coordinates gain bounded
discovery completion. That addition brought the collection to 57 usable reports
for 24 witnesses and nine searches, with no pending candidates. App data was
2,085,991 bytes, growing by 9,679 bytes for this addition.

The independent 2 Timothy search returned no indexed candidates in
IDs 10000–19999. One successful proxy request completed its declared scope and
the discovery state of its 83 coordinates; it added no coverage claims or date
estimates. The empty result is retained with its exact response and provenance.
It does not assert absence, rule out unindexed witnesses, or complete other ranges.

The independent 1 Timothy search returned P133. Its metadata and long contents
were collected with three successful proxy requests, including the search,
within a separate 25-attempt budget. Thirteen exact entries add 12 presence
pairs for 1 Timothy 3:13–16 and 4:1–8, with indexing tier 3 and complete catalogue
date 200–299 CE (`III`). Both reported page entries for 4:3 are preserved; the
overlap counts once per witness/verse and creates one chart event per date
scenario. Missing entries, including 3:12 and 4:9, remain unknown. Prior claims,
dates, coverage states, rankings outside the added coverage, and other scopes
survived unchanged. Only the 113 1 Timothy coordinates gain bounded completion.

The collection now retains 61 usable reports for 25 witnesses and eleven
completed scopes, with no pending candidates. The two Timothy searches used
four successful requests and increased app data by 13,564 bytes to 2,099,555 bytes.
Only the Galatians, Hebrews, Ephesians, Philippians, Colossians, 1 Thessalonians,
2 Thessalonians, 1 Timothy, 2 Timothy, Titus, and Philemon scopes are complete.
Other books remain unsearched despite reused contents. Jude within the same ID
range is the next suggested bounded scope; reuse any retained reports for
independently returned candidates.
