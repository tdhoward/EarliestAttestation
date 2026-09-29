# Development plan

This is the implementation plan following the [2026-09-29 review](DATA_REVIEW.md).
The first controlled-collection slice is implemented in `controlled_ntvmr.py`:
budgeted requests, durable raw responses and stage checkpoints, explicit P52
long-response parsing, and a single-witness offline index sample. Candidate
discovery now has a bounded named-witness lookup and an offline P52 language
regression. A budgeted live probe on 2026-09-29 returned P52 at John 18:31 and
P66, P75, 01, and 02 at John 1:1; the latter four responses are captured in
[`john_named_probe.json`](../tests/fixtures/john_named_probe.json). The codex
responses use numeric `gaNum` and `primaryName` values. These are candidate search
hits, not verified verse evidence or proof of exhaustive discovery. The
[bounded document-set probe](../tests/fixtures/john_list_probe.json) confirms
the multi-record list shape for P66 and P75 at John 1:1. It also does not prove
that larger ranges or passage searches are complete. Exhaustive discovery, the
NA28 inventory, verified evidence, rankings,
and visualization remain planned. The sample does not satisfy the later scholarly
validation gates.

The next collection increment supports one resumable catalogue lookup of up to 20
explicit document IDs, with source-linked candidates and a report of returned
IDs. Only an unfiltered lookup returning every requested ID can mark that bounded
catalogue scope complete. A passage-filtered lookup remains incomplete for that
purpose. Completed per-document indexes can be inverted for requested verses only
when their coverage checkpoints still match the active index snapshot. The
comparison flags named searches that miss a document with an index candidate.
The first five-ID unfiltered live lookup and a later P52-only unfiltered lookup
timed out on 2026-09-29; their pending jobs and transport failures are retained
locally, and no completeness result was inferred.

The metadata source-contract increment validates manuscript metadata before
completing its checkpoint. It stores a source-linked document snapshot with
catalogue names, verbatim language, original date notation, and valid/unknown/invalid
date status. This is catalogue metadata only; physical witness identity, selected
scholarly dates, and verse evidence still require review. An older completed metadata
checkpoint without this snapshot is replayed from cache when requested.

The document-review increment adds append-only document classification with a
source response, source type, reason, citation, and reviewer. Discovery and catalogue
reports show the latest decision and flag changed source content after a refresh.
Returned excluded candidates remain visible in reports; earlier decisions stay in
review history even if a refresh no longer returns a document. No classification
is inferred from its numeric ID, and a retained document is still only a candidate
for verse evidence review.

The physical-identity increment adds manually assigned witness IDs and append-only
document-to-witness links. A link requires a retained document reviewed against its
current source response, plus an identity reason, citation, and reviewer. Multiple
catalogue documents can point to one physical witness only through explicit review;
an unlink preserves the earlier decision. Reports flag links whose document
classification or source content has since changed. These links do not validate
verse coverage, dating, or a joined-fragment claim on their own.

The inventory-contract increment adds immutable, source-identified edition
snapshots with numeric canonical order, editorial status, and explicit zero-to-many
NTVMR coordinate mappings. Its importer rejects ranges, unordered or duplicate
verses, unsourced mappings, and silent replacement under one inventory ID. An
unmapped coordinate stays unresolved, and every report marks whole-NT completion
false. No NA28 inventory has been imported or certified yet; acquisition and
editorial review of that reference list remain open.

The first coverage-review increment now stores append-only, cited decisions for
individual indexed pages against explicit inventory mappings and current physical
witness links. Its report separates positive, uncertain, rejected, and withdrawn
decisions, flags changed index or identity sources, and deduplicates current positive
decisions by physical witness per edition verse. This implements an evidence-review
boundary, not a completed NA28 evidence set: the repository has no imported NA28
inventory, no real cited coverage reviews, and no selected scholarly date assessments.

The writing-unit/date increment now records separately identified writing layers,
append-only links from reviewed coverage to those layers, competing cited date
assessments, and an explicit selected assessment per layer and named dating policy.
Unknown or invalid dates
have no numeric bounds; a later correction or supplement can receive its own date.
The report retains selection history and marks superseded coverage links. No real
scholarly date assessments or rankings have been entered or calculated.

## Research contract

1. **Reference edition:** NA28, selected by the project owner. Store its explicit
   verse inventory and an edition identifier; do not equate KJV chapter maxima
   with edition membership. Preserve traditional coordinates, with explicit
   policies for omitted numbers, brackets, and verse-boundary differences.
2. **Attestation:** identifiable surviving Greek text from any part of that verse.
   Record partial/full/uncertain status. Exact agreement with all NA28 words is
   outside the initial scope. Physical lacunae, reconstructed text, inferred
   neighbors, and inferred complete books do not qualify.
3. **Initial corpus:** direct Greek manuscript witnesses, including eligible
   fragments and lectionaries. Classify multilingual witnesses by their Greek
   content. Printed editions are reference resources, not ancient witnesses.
   Keep amulets, ostraca, quotations, and other source categories explicit; their
   inclusion policy must be settled and versioned before a combined graph.
   Translations and dates of an author's composition must not silently enter the
   Greek manuscript series. Broader witness types can be separate later views.
4. **Dates:** retain inclusive lower and upper CE bounds, original source notation,
   citation, and assessment identity. Unknown/invalid dates remain unknown and
   are excluded from date ranking. A later correction or addition uses the date
   of that writing layer, not automatically the host manuscript's original date.
5. **Counting:** count distinct physical witnesses once per verse. Joined fragments,
   alternate catalogue IDs, duplicate photos, multiple pages, and repeated verse
   occurrences must not inflate the count. Five witnesses do not imply five
   genealogically independent textual traditions.
6. **Claims:** label results as earliest among the eligible, verified witnesses in
   a specified dataset snapshot and dating policy. Missing API indexing is not
   evidence that a verse was absent. Date uncertainty and discovery incompleteness
   must remain separate concepts.

## 1. Preserve the baseline and make collection controlled

- Archive the current database using SQLite backup if it is open; do not copy
  only the main file during active WAL writes. Preserve raw responses as research
  evidence. Build a versioned replacement database, with a reversible migration
  path and row-count checks. Do not carry `verse_earliest` forward as validated data.
- Default to `https://ntvmr.uni-muenster.de/community/vmr/api`; make the base URL
  configurable and replace the simulated browser headers with a clear project
  user agent. Update Bruno examples alongside the implementation.
- Implement one worker and a shared minimum request interval, provisionally five
  seconds plus small jitter. This is a conservative project default, **not a
  confirmed provider quota**. Cache hits should not cause network traffic.
- Add a request budget, offline mode, resumable run ID, and dry-run summary of
  planned calls. Count every network attempt, including retries, against the
  budget. Refresh only explicitly selected work; do not expire a whole research
  snapshot into a surprise bulk run.
- On 401/403, HTML block/challenge pages, or repeated 429, persist progress and
  stop the run. Honor `Retry-After` as seconds or an HTTP date; if the wait exceeds
  the run budget, checkpoint and exit. Retry appropriate timeouts/5xx with bounded
  exponential backoff and jitter. A 429 without a usable delay needs a conservative
  cooldown and bounded attempts. Do not switch VPN/proxy identity to continue.
- Persist raw responses and request failures independently of normalization.
  Separate parse errors, HTTP errors, valid empty results, and unfinished jobs.
  Return nonzero on failures or incomplete requested work.
- Before a bulk run, establish provider expectations for rate, bulk access, and
  attribution. No published numerical limit was verified in this review.

**Acceptance:** fake HTTP/time tests demonstrate spacing after success and
exceptions, `Retry-After` handling, retry limits, stop-on-block behavior, durable
checkpoints, zero network calls in offline mode, and no duplicate completed work
after a simulated interruption. No test should contact the live service by default.

## 2. Establish source contracts and complete candidate discovery

- Use the captured [P52 language probe](../tests/fixtures/p52_language_probe.json)
  to reproduce the old exclusion offline. Verify the corrected discovery route
  with P52, P66, P75, and major codices in a separately invoked, budgeted live
  check. Preserve language values verbatim and normalize `g`, `grc`, and bilingual
  forms only according to tested source semantics.
- Compare a known-document lookup with passage discovery. If the document has
  verified coverage but is missing from passage search, flag discovery as
  incomplete. Do not solve an unexplained omission by accepting the earliest
  remaining candidate.
- Establish the API's actual limiting/completeness behavior. `limit` is described
  in pages, and no pagination contract was verified. Prefer an approved bulk
  export or bounded catalogue/document batches when supported; record attempted
  bounds and completion. Check duplicates and result counts, but do not mistake
  a matching returned count for proof of exhaustive results.
- Prefer fetching a manuscript's metadata and coverage once, then inverting it
  locally to verse → witnesses. Persist all discovered candidates, including
  candidates rejected with a reason. Avoid fetching the same manuscript for
  hundreds of verse requests.
- Distinguish catalogue identity, physical witness identity, language, source type,
  original hands, later additions, and associated date assessments. Resolve joined
  fragments before counting. Do not infer source type solely from a numeric ID.
- Validate `status=success` and explicit endpoint structures. Unknown JSON shapes
  are contract errors, never silently empty lists. Add captured list, singleton,
  empty, error, and truncated/malformed fixtures.

**Acceptance:** known eligible early witnesses are discoverable; print editions
are excluded from the manuscript series; duplicates do not increase witness
counts; every run reports a declared discovery scope and completeness status.
The old 37-candidate cache is retained for comparison, not used as the complete
corrected corpus.

## 3. Build the NA28 inventory and evidence schema

Acquire or curate a source-identified NA28 reference inventory, with its reuse
terms and mapping to the NTVMR versification. Reproducing copyrighted edition text
is unnecessary for a reference-only inventory. Avoid assuming an API v11n ID
named `NA28` exists; verify supported values or supply a reviewed mapping.

Suggested logical entities (names can change during implementation):

| Entity | Essential information |
| --- | --- |
| `edition_verse` | Edition/version, OSIS ref, book/chapter/verse numbers, canonical ordinal, main-text/bracket/omission status |
| `witness` | Stable physical identity, catalogue aliases, source type, languages, collection/institution links |
| `writing_unit` | Part/page/hand or later addition, parent witness, applicable dating assessment |
| `date_assessment` | Writing unit or whole witness, min/max CE, original notation, citation, retrieval time, selection policy |
| `source_response` | Immutable body/hash, logical endpoint, transport URL, params, HTTP headers/status, retrieval time |
| `coverage_evidence` | Witness/writing unit, single edition verse, page/folio, partial/full/uncertain state, evidence type, reviewer/tier, response/citation link |
| `collection_job` | Run, stage, scope, pending/success/empty/failed/blocked state, attempts and timestamps |
| `ranking_snapshot` | Dataset version, edition, inclusion/dating policy, scenario, verse, rank, witness, event year |

Keep candidate index entries separate from verified `coverage_evidence` (or use an
explicit validation state). Keep multiple pages/sources for a verse; expose a
deduplicated witness/verse view for counting. Enforce foreign keys and valid
interval constraints. Keep unknown dates with explicit status, not zero or an
invented year. Preserve competing assessments; select one policy coherently rather
than taking the lowest bound from one scholar and the highest from another.

Store numeric canonical order explicitly. Resolve examples such as John 5:4,
John 7:53–8:11, Mark 16:9–20, and terminal verse numbering in 2 Corinthians and
3 John against the selected NA28 inventory. These are mapping/review cases, not
instructions to assume their editorial status from this plan.

**Acceptance:** stable order from Matthew to Revelation with numeric chapters and
verses; no invented verse from a range string; no accidental mixing of editions;
unknown/omitted/bracketed coordinates have defined export behavior. Changing the
requested subset filters an existing database before applying a verse limit.

## 4. Normalize and verify actual verse coverage

- Parse `data.indexContents.indexContent` explicitly. For the observed long
  response, ignore the summary string and read each object's `osisID`, `docID`,
  and `pageID`. Capture the page ID before creating the evidence record.
- Validate refs against the inventory/mapping. Reject malformed or unresolved
  coordinates for review. Do not extract arbitrary strings from recursively
  encountered `key`, `ref`, or `verse` fields.
- Prefer explicit individual entries. If a source supplies ranges, parse only its
  known grammar, preserve disjoint segments, and never join across a gap. Even a
  syntactically continuous page range may contain a physical lacuna or a textual
  omission; an index hit is a candidate until the evidence standard is met.
- Record whether support comes from a reviewed transcription, catalogue content
  statement, or checked image. Preserve uncertainty and reviewer notes. Exclude
  fully reconstructed/supplied text and unconfirmed automatic indexing from the
  verified graph. Treat correction hands and later supplements separately.
- Determine how the API exposes indexing tiers, offsets, and review provenance;
  the captured long sample does not answer that. If insufficient, corroborate
  decisive early entries with a source publication, transcription, or image.
- Normalize each manuscript once. Replace/version coverage atomically only after
  a successful complete parse. A failed refresh keeps the prior evidence marked
  stale; a valid changed response can withdraw old coverage with provenance.
- Track metadata and coverage completion independently of derived rankings, so
  rerunning repairs a partially completed manuscript without full re-fetching.

**Acceptance:** the P52 fixture produces exactly five witness/verse pairs on
pages 10 and 20. No P52 link is created for John 18:34–36 or other adjacent verses.
Multiple source/page records yield one counted witness. Boundary fragments,
cross-chapter refs, disjoint ranges, omitted text, absent indexing, and malformed
payloads have explicit tests. Unknown indexing is not equated with physical absence.

## 5. Rank independently for both date scenarios

For each verse, start with **all** eligible verified witnesses with a valid selected
date interval `[a_i, b_i]` for the attesting writing unit. If one physical witness
has multiple qualifying dated units for that verse, derive its earliest event in
each scenario first; it still contributes only once to the witness count.

- Optimistic: sort by `(date_min, date_max, stable_witness_id)` and take five.
- Pessimistic: sort by `(date_max, date_min, stable_witness_id)` and take five.

Tie-breaks make exports deterministic, not historically certain. Store the entire
interval and provenance with every result. Preserve witnesses outside these top
five so a new dating assessment can be applied without new downloads.

Example using fictional witnesses:

| Witness | Interval CE | Optimistic rank | Pessimistic rank |
| --- | --- | ---: | ---: |
| A | 100–300 | 1 | 3 |
| B | 150–200 | 2 | 1 |
| C | 180–250 | 3 | 2 |

The optimistic first event is 100 (A); the pessimistic first event is 200 (B),
**not** A's upper bound of 300. With more candidates, the sets of five can also
differ. For the same eligible set, the kth optimistic event must be no later
than the kth pessimistic event. Overlapping date ranges do not prove actual order.

At year `y`, the color count for scenario `s` is:

```text
count_s(verse, y) = min(5, number of distinct eligible witnesses with event_year_s <= y)
```

**Acceptance:** tests cover the ranking reversal above, different top-five
membership with at least six witnesses, ties/simultaneous events, fewer than five,
duplicate fragments/pages, invalid dates, and recomputation after a date change or
withdrawn attestation. A valid empty result clears stale rankings atomically;
a failed refresh is reported as stale/failed instead of pretending to be empty.

## 6. Establish scholarly validation before graphing

Create a small reviewed benchmark with stable citations, recorded source dates,
positive and negative verse coverage, and expected date assessments. Begin with
P52, then add P66/P75, one Pauline papyrus, one major codex, a late supplement,
and a witness with a substantial gap. Do not hardcode their dates from memory.
The benchmark should test individual evidence claims rather than asserting one
famous manuscript must always win.

Require these layers:

| Layer | What it establishes |
| --- | --- |
| Unit/fixture tests | Parser contracts, mapping, identity, intervals, scenario ranking |
| Temporary-DB integration tests | Transactions, resume, updates/removals, constraints, offline replay |
| Structural audits | Dangling references, stale dates, unsupported winners, missing processing |
| Scholarly benchmark | Cited surviving text and date assessments for representative real witnesses |
| Optional live contract test | Small, explicitly budgeted check for upstream schema/filter changes |

Report counts by book, century, source type, indexing/review state, and collection
status. Flag suspiciously late earliest results, missing expected witnesses, and
large unexplained jumps for investigation; these are review signals, not rules
that invent earlier dates. Require zero unexplained benchmark failures before
publishing historical claims. Version benchmarks when scholarship changes and
retain the prior expectations with citations.

## 7. Export and build the graph

Only after the above gates, export a versioned dataset containing every NA28
inventory coordinate in canonical order, zero-to-five witnesses per scenario,
event years, full date intervals, source/evidence links, and completeness status.
An export should identify its edition, source snapshot, inclusion/dating policy,
and validation version. It must support reproduction without fresh API requests.

Plot verse positions horizontally and CE years vertically, **newer at the top**.
Moving upward from earlier to later years, show no witness color before the first
event, then one-through-five colors; after the fifth event retain the fifth color.
Equal-year events occur together, with no invented visible interval between them.
Use the same axis bounds and color legend for both scenarios. Show unknown or
unfinished evidence separately from the pre-first-witness portion of a completed
series. Show omitted/bracketed coordinates according to the edition policy.

Provide book/chapter navigation, zoom, and a tooltip/table with the ranked
witnesses, both date bounds, partial coverage status, and source links. A static
export and a tabular alternative make results inspectable without relying on
hover or color. Title the chart as surviving verse evidence, not exact wording or
date of composition.

**Acceptance:** graph samples match benchmark tables; higher CE years appear
above lower ones; color counts never decrease going forward in time; missing
data are visible; both scenarios can be traced back to their evidence. Use static
tests and production builds for frontend verification. Do not start a development
server or probe localhost unless the project owner asks.

## Recommended first implementation slice

Deliver the controlled HTTP/cache client, explicit P52 long-response parser,
independent stage checkpoints, and an offline P52 evidence export first. Keep the
export labeled as a single-witness sample. Then expand to a reviewed set of John
witnesses, establish complete discovery within a declared scope, implement both
rankings, and finally scale to the whole NA28 inventory. Each step should pass its
offline acceptance checks before increasing request volume.
