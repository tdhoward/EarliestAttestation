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
The register holds the current record for each declared scope. Other scopes and
all existing document captures remain available. Metadata-only candidates can
resume contents collection without being skipped as already complete.

Canonical HTTPS is the default. Optional `--https-proxy` uses a configured CONNECT
proxy with canonical TLS verification. An explicitly configured `--base-url` relay
must be declared and qualified in the request definition. Do not change routes or
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

The central discovery register contains a Galatians search for IDs 10000–19999,
without name, date, or language search filters. It returned P46, P51, and P135;
all have metadata and long contents captures. GA 01 and GA 02 are additional
collected witnesses outside that range.

P51 supplies 14 Galatians presence pairs and P135 supplies 17, all with the
provider's indexing tier 3. Their exact catalogue date bounds are respectively
400–425 CE (`V (A)`) and 301–499 CE (`IV/V`). The record retains source fields,
citations, retrieval times, hashes, and request cost. Successful collection used
an existing HTTP relay; upstream TLS verification was not established, and that
qualification remains attached to its sources. Broader catalogue discovery is
still incomplete.
