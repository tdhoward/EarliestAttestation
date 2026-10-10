# Bounded witness discovery

Candidate discovery is independent of the witness pool already collected.
Reusing a document's contents report supplies explicit verse claims; it does
not establish that all earlier witnesses for another verse have been found.
The app therefore ranks up to five **earliest collected witnesses per verse**,
including in the book view, and displays discovery status separately from
reported contents and date rankability.

The current [source corroboration work](SOURCE_CORROBORATION_PLAN.md) uses retained
captures for a small internal-omission sample and review of first-five claims.
Broader collection is deferred. The workflow below documents existing discovery
capabilities and completion semantics; it does not require another catalogue
campaign or corroboration of every discovered manuscript.

## Catalogue scope

The declared snapshot below is complete. Broader collection remains deferred.

The discovery target is all 27 New Testament books across all four NTVMR Greek
NT manuscript categories, using budgeted catalogue inventories or independent
book/category and smaller range searches:

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
and the five may span categories. The default catalogue collection scope keeps
date ranges beginning before 1000 CE, unknown dates, and known earlier scholarly
alternatives. Fewer than five witnesses per verse is acceptable within this scope.
Finding five witnesses or early papyri alone does not establish discovery
completeness. When discovery is undertaken, candidates are sought independently
in all four categories and ranked using scholarly contents and complete date
reports. That discovery scope is distinct from the current first-five review
limit; it does not require further live searches now.

The current register includes inventories for all four categories. Discovery
flags evaluate only scopes registered in `data/discovery.json`; they do not
automatically require unregistered scopes or later snapshots. Record each searched book/range independently and
retain its qualifications when reporting completion. Catalogue inventories can
include witnesses without book indexing, whose contents remain unknown until a
usable report is available. Completing the planned searches does not establish
exhaustive manuscript or verse coverage; the [discovery states](#meaning-and-states)
retain that distinction.

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
not claims about the provider's numerical quota. The 50-attempt and ten-minute
limits apply to this original format-1 pilot; the catalogue collector below
supports longer runs without that attempt cap.

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
[README](../README.md#local-api-proxy) before running. Scholarly citations always
use canonical NTVMR endpoints; TLS verification is not a collection prerequisite.
Permanent records replace the proxy origin with `<local proxy>` while preserving
raw response bodies, hashes, paths, parameters, and retrieval dates. Actual request
URLs remain only in ignored local definitions and request caches. Do not change routes or
identity to bypass a provider block. Establish provider expectations before bulk
access. Tests and data rebuilds make no live requests. The owner authorized
longer catalogue collection on 2026-10-06 while retaining five-second spacing;
this does not assert a published numerical provider quota.

## Overnight catalogue collection

`collect_catalogue.py` provides `collect`, `status`, and `import` commands.
Collection searches each of the four ranges without book, name, date, or
language filters, follows documented continuation cursors, and queues metadata
(`detail=10`) and verse contents (`detail=long`) for eligible returned IDs. It makes
no requests to images or transcriptions and does not probe every possible ID.
Each report is captured once and serves every book for which it reports contents.
Registered reports are validated and reused, including metadata-only witnesses.

The default local filter is `--earliest-date-before 1000`. It excludes follow-up
requests only when integer `origEarly` and `origLate` form a positive, ordered
range and `origEarly >= 1000`. A range of 950–1050 stays eligible with both bounds
unchanged; 1000–1099 is excluded. Missing, zero, malformed, or reversed bounds
remain eligible, after dated candidates. The tool never interprets `orig` notation.
A valid earlier estimate in retained metadata or a registered scholarly date
report also keeps the witness eligible, including explicitly registered aliases.
These are collection decisions, not new scholarly date or coverage assertions.

Use `--earliest-date-before YEAR` to change the cutoff or `--no-date-cutoff` to
disable it. The selected setting persists when omitted on resume. An older
checkpoint without a setting adopts 1000 on its first resumed collection; merely
running `status` or `import` does not change that historical campaign's scope.
Resume rechecks retained inventories and date reports before further downloads,
so it can skip existing pending jobs or reopen jobs after a wider cutoff or newly
retained earlier estimate. Previously failed jobs still require `--retry-failed`
if they become eligible again. Successful captures, complete date ranges, and
original inventories are retained. No queue schema migration is required.
An already-running collector must be stopped with Ctrl+C and relaunched to load
the change. This option limits collection, not the app's existing witness pool.

```powershell
python collect_catalogue.py collect --use-local-proxy --hours 8
python collect_catalogue.py status
```

The default campaign ID is `catalogue`. Use the same `--run-id`, route, interval,
and page limit to resume. `--use-local-proxy` reads the address kept once in the
README. Alternatively supply `--base-url "<local proxy>/community/vmr/api"`,
use `--https-proxy` for an explicitly configured CONNECT proxy, or omit route
options for canonical HTTPS. The tool never switches routes automatically.

`--hours` is a finite time budget for each launch, defaulting to eight hours.
The collector may take multiple nights. There is no fixed request-count cap;
optional `--max-requests N` caps cumulative attempts for the campaign, including
continuations and retries. An existing ceiling persists if omitted on resume;
raise it explicitly if more attempts are wanted. Time or request exhaustion and
Ctrl+C retain resumable checkpoints. Exit status is 0 for complete capture and
2 for paused, incomplete, blocked, or failed work.

`--interval` defaults to five seconds and cannot be set below five. A single
worker and a persistent pacing checkpoint maintain spacing between categories,
retries, restarts, and campaign IDs. Waiting after response completion makes the
spacing conservative. `Retry-After` cooldowns survive interrupted waits and
deadlines. Do not run another collection tool concurrently. `status` can inspect
the queue while collection is running and makes no network requests.

HTTP 401/403, HTML access challenges, and repeated HTTP 429 stop the entire
collector. The provider-block checkpoint also prevents automatic retries under
a different campaign ID. After access is actually restored, an explicit
`--access-restored-reason "reason"` records that resolution before resuming;
it does not change routes or shorten a retained cooldown. Transient failures
receive bounded retries and remain visible afterward. `--retry-failed` explicitly
retries failed document requests, preserving successful captures. Catalogue
contract failures require review of the retained response; no guessed cursor or
automatic restart can promote them to completion.

Every received response, including error responses, is committed to the ignored
queue database and archived atomically under `data/sources/`. Captures retain
raw bodies, hashes, request parameters, retrieval times, canonical source URLs,
and noncredential headers. Proxy origins are placeholders in permanent records.
A response committed before an interrupted file write is recovered from the
checkpoint without downloading it again. Keep `data/.cache/catalogue.sqlite`
until capture/import work is finished; it is a temporary checkpoint, never a
normalization database or product input.

When collection stops, import and build separately:

```powershell
python collect_catalogue.py import
python build_collection.py
```

Import is entirely offline. It validates source hashes, report shapes, reported
Greek catalogue membership, and provenance, then fills missing document fields
in `data/collection.json` without replacing existing reports, date alternatives,
identity assertions, or other discovery scopes. It registers four format-2
`catalogue_range` definitions, each with a `books` list covering all 27 books,
in `data/discovery.json`. Pagination evidence is retained in those records.
The build subsequently uses only the central register and permanent captures.
Neither overnight capture nor import changes `data/attestations.json` or app HTML.

Complete capture means the inventory and eligible queued downloads finished, not that
every response is usable under the scholarly-report contract. Unsupported or
malformed reports stay captured; import lists errors and keeps their candidates
pending while importing other usable reports. Empty contents reports stay
unknown and never establish absence. Catalogue membership is not verse presence.
Catalogue completion applies only to the declared ranges and captured snapshot;
`corpus_complete` remains false. Status reports the effective cutoff and skipped
documents with reasons. Imported scope definitions record `earliest_date_before`;
the build derives `date_excluded_candidate_ids`, `eligible_candidate_ids`, and
each candidate's decision from retained source evidence. Date-excluded candidates
remain visible without appearing as pending collection. Exclusion is separate
from verse coverage: previously captured metadata may still have unknown contents,
and no absence is inferred. Earlier estimates from nonprimary metadata are retained as validated
filter evidence. The explorer states the collection cutoff and qualifies completion
as collection of eligible candidates. Fewer than five witnesses is a valid outcome.

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

The central register retains four completed catalogue inventories for IDs
10000–19999, 20000–29999, 30000–39999, and 40000–49999, applicable to all 27 books.
The captured inventory contains 6,199 distinct candidates: 1,323 eligible and
4,876 date-excluded. Offline import resolved all 705 previously pending eligible
candidates; none remain pending. All 27 books record completion of this scope. Capture finished after
5,123 campaign request attempts, with no failed request jobs or provider block.
These are completion claims for the declared ranges and source snapshot;
`corpus_complete` remains false.

Saved responses are imported offline, including empty-string contents containers,
integer date notation, observed multilingual Greek catalogue codes, and mixed-book
contents. See [the retained variants](NTVMR_SOURCE_REPORT_CONTRACT.md#retained-catalogue-variants)
for exact fields and captures. Empty reports complete report collection without
creating verse presence or absence. Other-book entries remain in raw captures;
only explicit NT verse entries enter active claims.

The eleven earlier papyrus book-index searches remain retained for Galatians,
Hebrews, Ephesians, Philippians, Colossians, 1 Thessalonians, 2 Thessalonians,
1 Timothy, 2 Timothy, Titus, and Philemon. Catalogue inventories add independent
range-wide discovery; reusing contents by itself creates no search completion.

The current eligible, excluded, and pending counts are reported independently in
`data/attestations.json` under `metadata.discovery_summary`. The default
cutoff excludes valid inventory ranges beginning at or after 1000 CE unless a
retained earlier scholarly estimate qualifies. Unknown dates stay eligible.
Previously captured later reports are preserved; fewer than five witnesses per
verse is acceptable.

One captured metadata report,
[document 31133](../data/sources/ntvmr-31133-metadata-58763816e1bf70c8.json),
is labelled `lat` by the source and remains outside the supported Greek language
contract. Its 1300–1399 CE inventory range is date-excluded from the current
collection scope. Its raw metadata and contents captures, import errors, and
source evidence remain retained; no Greek contents, absence, or identity is
inferred from this record.
