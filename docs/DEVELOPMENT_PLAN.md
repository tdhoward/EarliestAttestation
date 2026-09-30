# Development plan

This plan tracks the replacement collector and its validation gates. The
[2026-09-29 code/data review](DATA_REVIEW.md) is the historical baseline for the
disabled legacy collector; its defects are not a current implementation checklist.
The [README](../README.md) contains command syntax and reproducibility instructions.

The [manuscript dating policy](../README.md#manuscript-dating-policy) governs this
plan: defer to documented scholarly consensus when known; otherwise preserve
sourced date ranges as equally valid possibilities. Contributors are not
qualified to adjudicate manuscript dating disputes. Validation checks faithful
use of sources, not resolution of those disputes. P52 is an example and test
fixture, and its dating uncertainty does not block broader project work.

## Progress reviewed on 2026-09-29

The replacement database filename remains `ntvmr-v2.sqlite`; the current schema is
**v12**. Implementation and scholarly validation have separate completion criteria.

| Area | Implemented and checked | Still required |
| --- | --- | --- |
| Controlled collection | Budgeted single-worker HTTP, immutable responses, durable attempts, metadata/coverage checkpoints, offline fixtures and explicit P52 parsing | Provider expectations before bulk access; broader live contract coverage |
| Candidate discovery | Named-witness searches, resumable lookups for up to 20 explicit IDs, scoped index inversion and omission reports | Exhaustive discovery beyond a declared ID set; unresolved unfiltered catalogue probes |
| Source type and physical identity | Source-linked metadata and append-only classification, identity links, corrections and change flags | Review additional documents and joined fragments; no automatic identity inference |
| Edition inventory and coverage | Immutable inventory imports with numeric canonical order and explicit mappings; append-only indexed page/verse and direct physical absence reviews; witness deduplication | Whole-NT NA28 inventory, editorial/mapping review, independently checked real absence cases |
| Writing units and dates | Separate writing layers, coverage assignments, competing cited assessments and policy selections; reproducible P52 example with four dating observations and a null selection | Record documented consensus where known and retain equal alternatives otherwise; check source fidelity; no date assessment or selection in the inspected local database |
| Both ranking scenarios | Independent first-five selection per physical witness, deterministic ties, provenance, change detection and atomic snapshots; test-only P52 scenario exercises both rankings with one sourced assessment | Carry equal dating alternatives through results and benchmark them with real witnesses; no ranking snapshot in the inspected database |
| Validation and publication | Read-only reviewed audit, cited P52 replay, index and catalogue-date controls | Wider independently checked scholarly benchmark, versioned corpus export and graph |

The offline suite passes **61 tests on Python 3.12.6**. The combined reviewed audit
reports zero findings: five of five P52 evidence cases pass, and both source
controls pass. The local reviewed database contains one inventory with ten
coordinates (John 18:30–39), five explicit NTVMR mappings, one physical witness,
and five `partial` coverage reviews. It contains zero date assessments, selections,
or ranking snapshots. This inspected v11 database needs a backed-up additive v12
upgrade before the current read-only audit can run. The separate
[P52 dating review](P52_DATING_REVIEW.md) replays
four assessments and a null selection into a fresh database; it has not been
applied to that inspected local snapshot. `historical_validation_complete` remains
false; a clean structural audit does not complete the scholarly validation gate.

The [P52 replay](../replay_p52_benchmark.py) records a Codex source review citing
the library catalogue and Hurtado. It does not represent an independent human
check. Neighboring coordinates are negative **index controls**, not rejected
physical-evidence reviews. The [catalogue-date control](../benchmarks/p52-date-source-v1.json)
pins source notation and numeric bounds; it does not create a selected date.
Competing dating cautions remain separate from numeric assessments.

The small 2026-09-29 live probes found P52 at John 18:31 and P66, P75, 01, and 02
at John 1:1. Captured [named searches](../tests/fixtures/john_named_probe.json)
and the [P66/P75 list response](../tests/fixtures/john_list_probe.json) cover numeric
catalogue names and the multi-record response shape. These are candidate hits.
Unfiltered lookups for five IDs and then P52 alone timed out and remain pending
locally. Neither the successful passage probes nor those timeouts establish
exhaustive discovery. An unfiltered lookup can establish completeness only for its
explicit ID set, when every requested ID is returned and the reported count agrees.

## Next development work

1. **Broaden the verse inventory and manuscript discovery.** Curate and review
   the NA28 reference list and mappings; resolve the unfiltered catalogue contract
   with a separately scoped, budgeted check when needed. Record the inclusion
   policy and completeness of each declared scope. Preserve pending or failed
   work explicitly. Increase request volume only after these checks and provider
   expectations are established. This work does not depend on resolving P52's date.
2. **Expand the source-based benchmark in small increments.** Add P66/P75, a Pauline
   papyrus, a major codex, a later supplement, and a witness with a substantial
   gap. Cover positive and rejected claims, competing dates, and duplicate
   physical identities. The indexed coverage-review path still requires an
   indexed page and explicit mapping. A separate v12 physical-absence path now
   records a checked image or reviewed transcription at an inventory verse without
   an index row, and flags contradictions with positive coverage. Its tests are
   synthetic; independently checked real absence cases remain to be added.
3. **Carry dating uncertainty through the general ranking workflow.** Record
   cited consensus where known. Otherwise retain each sourced range as an equally
   valid possibility and expose its effect on both endpoint rankings. The current
   interface selects one assessment per writing unit under a named policy;
   complete handling and presentation of alternatives remain implementation work.
   Do not make contributors choose which scholar is correct to satisfy that
   interface. Preserve original notation, citations, and documented conversions.
4. **Exercise rankings with representative sourced inputs.** Check both endpoint
   scenarios for documented consensus and for competing ranges, including changed
   first-five membership. Reproduce results offline and check source fidelity,
   coverage, and witness deduplication. Keep existing P52 regression tests and
   manifests; its test-only ranking is sufficient for its role as an example.
   Further P52 research or a preferred P52 date is not an acceptance criterion.
5. **Export and graph only after the validation gates below.** Keep the legacy
   results, candidate index samples, synthetic ranking fixtures, and historically
   reviewed outputs explicitly labeled. A green test suite or P52 source control
   alone is not publication readiness. Validation must preserve dating uncertainty;
   it must not require scholarly disputes to be settled.

The numbered sections below retain the research requirements and acceptance
criteria, including those already implemented. Use the status table and next-work
list above to choose work; do not restart completed collection or ranking slices.

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
   citation, and assessment identity. Defer to cited scholarly consensus when
   known. Otherwise treat the various sourced scholarly ranges as equally valid
   possibilities, without project preferences or assigned probabilities. Preserve
   complete ranges rather than averaging, narrowing, or merging them. Record
   unknown consensus explicitly; a catalogue entry alone does not establish it.
   Unknown/invalid bounds remain unavailable for numeric ranking; disagreement
   between usable intervals does not make those intervals unusable. A later
   correction or addition uses the sourced date of that writing layer, not
   automatically the host manuscript's original date.
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
invented year. Preserve competing assessments as complete, separately cited
ranges. Record the evidence for any known consensus; otherwise retain equal
alternatives. A policy identifies calculation inputs, not a project judgment
about which scholar is correct. Do not combine bounds from different assessments
into a new manuscript date.

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

For each explicitly identified dating alternative and verse, start with **all**
eligible verified witnesses with a sourced date interval `[a_i, b_i]` for the
attesting writing unit. Use documented consensus where known and preserve the
various sourced ranges as equally valid possibilities otherwise. Each calculation
uses complete assessments and records which ones it uses. The existing engine
handles one assessment per unit per policy; exposing alternatives across results
remains required implementation work, not a reason to resolve scholarly disputes.
If one physical witness has multiple qualifying dated units for that verse,
derive its earliest event in
each scenario first; it still contributes only once to the witness count.

- Optimistic: sort by `(date_min, date_max, stable_witness_id)` and take five.
- Pessimistic: sort by `(date_max, date_min, stable_witness_id)` and take five.

Tie-breaks make exports deterministic, not historically certain. Store the entire
interval and provenance with every result. Preserve witnesses outside these top
five so a new dating assessment can be applied without new downloads.

The two endpoint scenarios must be evaluated within each dating alternative;
neither scenario selects the correct scholar. Results must expose how alternatives
change event years, membership, or order, without assigning preferences or
probabilities. Multiple assessments never count as multiple physical witnesses.

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
withdrawn attestation. Include documented-consensus inputs and competing ranges
with no known consensus; verify equal treatment, source traceability, and no
double-counting of a witness across its assessments. A valid empty result clears
stale rankings atomically;
a failed refresh is reported as stale/failed instead of pretending to be empty.

## 6. Validate source fidelity and coverage before graphing

Create a small reviewed benchmark with stable citations, recorded source dates,
positive and negative verse coverage, and expected sourced date assessments.
Retain P52 as an existing example; expand to P66/P75, one Pauline papyrus, one
major codex, a late supplement, and a witness with a substantial gap. Do not
hardcode their dates from memory.
The benchmark should test individual evidence claims rather than asserting one
famous manuscript must always win.

Dating validation establishes that source ranges, qualifications, conversions,
and any documented consensus are faithfully represented. Where consensus is
unknown, it checks preservation of equal alternatives. Neither human reviewers
nor agents are tasked with deciding which dating argument is correct. A disputed
date is not a benchmark failure or a publication blocker when its uncertainty is
represented faithfully; missing citations or concealed alternatives are defects.

Require these layers:

| Layer | What it establishes |
| --- | --- |
| Unit/fixture tests | Parser contracts, mapping, identity, intervals, scenario ranking |
| Temporary-DB integration tests | Transactions, resume, updates/removals, constraints, offline replay |
| Structural audits | Dangling references, stale dates, unsupported winners, missing processing |
| Source-based benchmark | Cited surviving text, faithfully recorded date assessments, and preservation of dating uncertainty for representative real witnesses |
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
and validation version. Include consensus status and its supporting citation where
known; otherwise expose equally valid alternative ranges and their ranking
outcomes. Preserve original notation and conversions as well as numeric bounds.
It must support reproduction without fresh API requests.

Plot verse positions horizontally and CE years vertically, **newer at the top**.
Moving upward from earlier to later years, show no witness color before the first
event, then one-through-five colors; after the fifth event retain the fifth color.
Equal-year events occur together, with no invented visible interval between them.
Use the same axis bounds and color legend for both scenarios. Show unknown or
unfinished evidence separately from the pre-first-witness portion of a completed
series. Show omitted/bracketed coordinates according to the edition policy.

Provide book/chapter navigation, zoom, and a tooltip/table with the ranked
witnesses, both date bounds, partial coverage status, and source links. A static
chart or interactive view must identify the dating inputs it depicts and make
alternative outcomes available without implying a preferred range. A static
export and a tabular alternative make results inspectable without relying on
hover or color. Title the chart as surviving verse evidence, not exact wording or
date of composition.

**Acceptance:** graph samples match benchmark tables; higher CE years appear
above lower ones; color counts never decrease going forward in time; missing
data are visible; both endpoint scenarios and competing dating alternatives can
be traced back to their evidence. Unresolved scholarly disagreement remains
visible and does not require project adjudication. Use static
tests and production builds for frontend verification. Do not start a development
server or probe localhost unless the project owner asks.

## Working and documentation rules

- Keep the current status and next-work list in this plan aligned with the actual
  schema, commands, fixtures, and observed database contents. Update the README's
  summary when a milestone changes; retain the original data review as history.
- Keep source observations, automated checks, and independent human review
  distinguishable. Record who actually reviewed a claim; do not present a replay
  or an agent's source review as human approval.
- Apply the manuscript dating policy consistently. Do not schedule dispute
  resolution or further P52-specific dating research as a development prerequisite.
  Source checks establish faithful recording; contributors do not approve or
  reject scholars' dating arguments.
- Use temporary or separate replay databases for verification. The two audit
  scripts are read-only; collector reports and collector `--dry-run` can create
  or upgrade the schema. The P52 replay's `--dry-run` validates manifests without
  inspecting the target database. Back up an existing database with SQLite backup
  before migrations or replay, and preserve immutable sources and review history.
- Run offline tests and the relevant declared benchmarks for changed behavior.
  Report expected legacy-audit findings separately from replacement-database
  failures. Do not use a live request as a routine verification step.
- Keep live collection explicitly scoped and budgeted. Request budgets include
  prior attempts under the same run ID; cache replay needs no new requests. Honor
  blocked or pending states and the collection rules in section 1.
