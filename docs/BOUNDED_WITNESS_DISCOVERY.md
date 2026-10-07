# Bounded witness discovery

Candidate discovery is independent of the witness pool already collected.
Reusing a document's contents report supplies explicit verse claims; it does
not establish that all earlier witnesses for another verse have been found.
The app therefore ranks **earliest collected witnesses** and displays discovery
status separately from reported contents and date rankability.

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
and 2 Thessalonians searches for IDs 10000–19999. The Galatians search ran
without name, date, or language search filters. It returned P46, P51, and P135;
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

Only the Galatians, Hebrews, Ephesians, and 2 Thessalonians scopes are complete.
Other books, including 1 Thessalonians despite the reused report, remain unsearched.
