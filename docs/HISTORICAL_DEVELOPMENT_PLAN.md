# Historical development plan

> **Superseded on 2026-10-05 ? historical record only.** The project owner
> clarified that this project captures scholarly reports of dates and verse
> contents and must never perform manuscript examination. The examination tasks,
> word-anchor requirements, physical reviews, specialist questions, and scholarly
> publication gates below are withdrawn. They are not current instructions or
> accepted evidence. Use [AGENTS.md](../AGENTS.md), the
> [current development plan](DEVELOPMENT_PLAN.md), and the
> [current README](../README.md). Existing commands are retained for historical
> reproduction; a successful replay does not make agent-derived claims eligible
> for active results. No code, fixture, database, or chart was changed by archiving
> this document.

Original document follows; its former requirements and next steps are superseded.

---

# Development plan

This plan directs development toward a usable graph of surviving Greek verse
evidence, supported by reproducible collection and review. The
[2026-09-29 code/data review](DATA_REVIEW.md) is the historical baseline for the
disabled legacy collector; its defects are not a current implementation checklist.
The [README](../README.md) contains command syntax and reproducibility instructions.

The [witness scope](../README.md#witness-scope) governs all development: only
surviving copies of the New Testament texts qualify. Quotations and allusions in
other works are outside the current corpus, including direct patristic quotations.

The [manuscript dating policy](../README.md#manuscript-dating-policy) governs this
plan: defer to documented scholarly consensus when known; otherwise preserve
sourced date ranges as equally valid possibilities. Contributors are not
qualified to adjudicate manuscript dating disputes. Validation checks faithful
use of sources, not resolution of those disputes. P52 is an example and test
fixture, and its dating uncertainty does not block broader project work.

## Progress reviewed on 2026-09-30

The replacement database filename remains `ntvmr-v2.sqlite`; the current schema is
**v12**. Implementation and scholarly validation have separate completion criteria.

| Area | Implemented and checked | Still required |
| --- | --- | --- |
| Controlled collection | Budgeted single-worker HTTP, immutable responses, durable attempts, metadata/coverage checkpoints, offline fixtures and explicit P52 parsing | Provider expectations before bulk access; broader live contract coverage |
| Candidate discovery | Named-witness searches, resumable lookups for up to 20 explicit IDs, scoped index inversion and omission reports | Exhaustive discovery beyond a declared ID set; unresolved unfiltered catalogue probes |
| Source type and physical identity | Source-linked metadata and append-only classification, identity links, corrections and change flags | Review additional documents and joined fragments; no automatic identity inference |
| Edition inventory and coverage | Immutable inventory imports with numeric canonical order and explicit mappings; provisional 27-book, 260-chapter NA28 coordinate inventory with 7,957 rows; v2 directly confirms 1 Corinthians 4 coordinates, and v3 cites all 16 traditional skipped passages; append-only indexed page/verse and direct physical absence reviews; witness deduplication | Confirm remaining flagged editorial cases, review 7,952 pending NTVMR mappings, independently check real absence cases; whole-NT inventory is not certified |
| Writing units and dates | Separate writing layers, coverage assignments, competing cited assessments and policy selections; reproducible P52 example with four dating observations and a null selection | Record documented consensus where known and retain equal alternatives otherwise; check source fidelity; no date assessment or selection in the inspected local database |
| Both ranking scenarios | Independent first-five selection per physical witness, deterministic ties, provenance, change detection and atomic snapshots; offline export enumerates conditional rankings for stored valid date combinations, including the cited P52 replay with normal writing-unit links | Add documented-consensus status and a wider independently checked benchmark; no ranking snapshot in the inspected local database |
| Validation and publication | Read-only reviewed audit, cited P52 replay, index and catalogue-date controls; offline complete-inventory and filtered graph-data export; bounded static chart and source table; cited four-witness John 1 prototype; physical review provenance independent of dating | Wider independently checked scholarly benchmark and validated corpus export |

The 2026-09-30 progress review reran all **70 offline tests on Python 3.12.6**
successfully and inspected the local databases read-only. The earlier combined
reviewed audit reported zero findings: five of five P52 evidence cases passed,
and both source controls passed. The local `data/ntvmr-v2.sqlite` contains one
inventory with ten coordinates (John 18:30–39), five explicit NTVMR mappings, one physical witness,
and five `partial` coverage reviews. It contains zero writing units, coverage-unit
assignments, date assessments, selections, or ranking snapshots. This v11 database
needs a backed-up additive v12 upgrade before the current read-only audit can run. The separate
[P52 dating review](P52_DATING_REVIEW.md) replays
four assessments and a null selection into a fresh database; it has not been
applied to that inspected local snapshot. The existing local
`data/p52-review-replay.sqlite` still contains the earlier three assessments and
no coverage-unit assignments or rankings. The three local whole-NT inventory
databases contain coordinates and five mappings each, but no witness evidence.
These local files are not distributed; checked-in manifests describe reproducible
inputs, not proof that a local database has been updated.
`historical_validation_complete` remains false; a clean structural audit does not
complete the historical-publication requirements.

The 2026-09-30 graph increment passed **72 offline tests**. A fresh, separate
`data/p52-graph-preview.sqlite` replay has ten John 18 coordinates, five positive
P52 coverage reviews linked to one original writing unit, four date assessments
(two numerically rankable), and no selected-policy rankings. Its structural and
source audit had zero findings, five of five evidence cases passed, and both
source controls passed. The offline export and static renderer produce
two conditional endpoint charts with a source table; the five neighboring
coordinates remain unresolved. This one-witness preview does not complete the
several-witness prototype. The older local databases described above were not
modified by that fresh replay.

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

The 2026-10-01 proxy access check captured a [P66 index response](../tests/fixtures/p66_coverage_probe.json)
with a chapter-level `John.2` marker that previously stopped parsing. The parser
now retains that marker in the raw response and imports only the 970 explicit
verse/page pairs. A cached retry on a temporary SQLite backup of
`data/proxy-access-check-20261001.sqlite` succeeded with zero new requests and
unchanged raw responses. All **75 offline tests** passed, including chapter-only
and malformed-entry checks. This cleared the P66 parsing obstacle for John 1;
physical coverage and mapping review followed in the next increment.

The 2026-10-01 [John 1 replay](../replay_john1_prototype.py) supplies that
bounded physical review. Its checked-in inputs cite the IGNTP P66 transcription,
the Vatican Library P75 transcription, and the Codex Sinaiticus Project
transcription. Two additional official NTVMR coverage responses are pinned as
fixtures. Book-level markers in those responses are retained without inventing
verse entries. A fresh replay has five mapped John 1 coordinates, three linked
physical witnesses, 15 partial coverage decisions, 15 writing-unit assignments,
six date observations, and one conditional ranking combination per verse. Its
reviewed-data audit has zero findings, and all **78 offline tests** passed. The
chart includes the unreviewed 02
search candidate and labels the limits of discovery and validation. This
completes the bounded prototype milestone, not historical publication review.

The 2026-10-01 source and identity check records 02 as Codex Alexandrinus from
the British Library's Royal MS 1 D VIII catalogue. It remains a coverage-pending
candidate; the catalogue's John folio range does not prove verse-level survival.
The P66 IGNTP transcription supports surviving Greek in John 1:1–5 without a
separate correction reading in those verse elements, but the captured NTVMR index
lists each verse on both page IDs 3 and 10. The [captured NTVMR metadata](../tests/fixtures/p66_metadata_probe.json)
labels page ID 10 as folio 1 containing John 1:1–14, resolving that index-page
choice for the replay. The [v2 review manifest](../benchmarks/john1-reviewed-v2.json)
replays the 02 identity without adding coverage or a ranked date.

The subsequent fourth-witness increment adds five Alexandrinus image reviews
and writing-unit links through the [v3 manifest](../benchmarks/john1-reviewed-v3.json).
All **81 offline tests** pass. A fresh replay has zero audit findings and passes
all **20 cited coverage benchmark cases**. It exports and renders four witnesses
per verse with zero replay network attempts. The v2 replay remains available;
existing databases are not migrated or overwritten by this increment. See the
[source review and measurements](PROTOTYPE_SCOPE.md#fourth-witness-and-regression-benchmark-2026-10-01).

## Next development work

The [John 1:1–5 prototype](PROTOTYPE_SCOPE.md) now includes four reviewed witnesses
and 20 positive witness/verse pairs. The v3 review adds image-checked Alexandrinus
coverage, a captured page link, and the British Library's explicit 400–499 CE
catalogue bounds. A cited 20-case coverage benchmark checks reproducibility;
earlier manifests remain available.

The follow-up code review found and closed a gap before passage expansion:
physical-absence reviews were available to audits and ranking exclusions but were
missing from exports and charts. The export now retains current coverage and
absence decisions with their provenance, regardless of dating eligibility. The
chart identifies absent, uncertain, withdrawn, conflicting, stale, and unreviewed
evidence separately. Synthetic regressions exercise these cases; they do not add
a physically reviewed historical gap. Continue with the source work below rather
than another collection framework. The next increment should:

1. Check source fidelity independently for the displayed John 1 evidence and
   date applicability, including any distinct
   writing layers. Keep the existing Codex source review identifiable until that
   check occurs. Record documented dating consensus only where a cited source
   establishes it; preserve other dates as conditional alternatives.
2. Review one additional bounded passage or witness set with varying survival.
   The [John 6:49–53 increment](JOHN6_GAP_REVIEW.md) now supplies a directly
   reviewed transcription boundary: twelve positive pairs and three physical
   absences for P66, P75, and Alexandrinus, with fifteen cited benchmark cases.
   The third-witness milestone is complete. The first bounded Pauline case,
   [P46 at Galatians 1:1–5](GAL1_P46_REVIEW.md), now has five cited partial reviews,
   explicit page/folio links, an original-writing unit, and two conditional dates.
   The [Galatians overlap increment](GAL1_OVERLAP_REVIEW.md) adds Alexandrinus with
   five further partial reviews, reconciled page/folio links, and a separate original
   writing unit. The chart now has two witnesses per verse and preserves both P46
   date alternatives. The [Sinaiticus increment](GAL1_SINAITICUS_REVIEW.md) now
   completes another overlapping-witness review: five original-base-text anchors,
   explicit exclusion of recorded corrections, reconciled folio 278v/page 1580,
   and two separate valid date inputs plus a qualified unknown observation. Its
   three-witness chart has fifteen positive pairs and four equal conditional
   combinations. The [Washingtonianus supplement increment](JOHN1_SUPPLEMENT_REVIEW.md)
   now supplies a source-documented later replacement quire at John 1:1–5,
   extending that chart to five witnesses and 25 positive pairs. Its separate
   conditional 601–800 CE assessment preserves the source's qualification and
   avoids applying the manuscript's earlier catalogue date to replacement text.
   The [John 5:9–13 boundary batch](JOHN5_BOUNDARY_REVIEW.md) now reviews that
   supplement/original division: five positive page decisions yield four positive
   witness/verse pairs, while the empty John 5:12 transcription remains uncertain.
   John 5:11 retains separately dated portions on both pages but counts as one
   codex, with a tested fallback to its supplement if the original review is
   withdrawn. Next, check the John 5:12 image/source question and add an overlapping
   witness to the same mapped passage. Time source reading separately from
   implementation; retain per-verse exceptions rather than inferring survival
   from indexing or empty transcription elements.
   The ready human-review questions remain
   unanswered. Continue bounded, budgeted collection without claiming exhaustive
   discovery.
3. Expand source-checked NTVMR mappings and reviewed witness coverage in small
   batches. Measure the repeated review effort first; preserve individual
   provenance and exception review. Keep the provisional whole-NT inventory's
   certification separate from the John 1 subset.

The John 6 increment reuses the existing review interfaces and adds no schema or
collection framework. Its offline replay, export, and
[chart](../examples/john6-gap-prototype.html) show counts of 3, 3, 2, 2, 2 across
the five verses in both endpoint scenarios. The 2026-10-02 UTC verification
passes **91 tests**, all fifteen John 6 benchmark cases, and all 20 retained John 1
cases. The fresh structural audit has zero findings. The original two-witness
increment used two transcription downloads and about four minutes of source work.
Adding P75 used one transcription download, two budgeted metadata attempts (one
timeout, one success), and about five minutes of retrieval and page reconciliation.
Its five partial reviews exclude supplied text as evidence. Earlier manifests
remain reproducible. Historical validation remains incomplete.

The 2026-10-02 UTC P46 increment passes **96 offline tests** and all five new
benchmark cases with zero structural audit findings. Its offline
[replay](../replay_gal1_p46.py) produces a
[five-verse chart](../examples/gal1-p46-prototype.html) from pinned sources.
The NTVMR 200–225 CE and Michigan third-century (201–300 CE) assessments remain
separate equal alternatives, with consensus unknown. The codex's two holding
institutions count as one witness. Four budgeted NTVMR attempts (two timeouts,
two successes through the existing proxy) and one successful transcription
download supplied the new fixtures. Source work took approximately five minutes;
the replay uses no network or schema changes. Five specific human-review questions
are ready in the source review document, with no answers recorded.

The 2026-10-02 [Galatians overlap review](GAL1_OVERLAP_REVIEW.md) adds five
Alexandrinus decisions using the existing page metadata and index plus a newly
pinned university transcription. The [two-witness replay](../replay_gal1_prototype.py)
has zero structural findings, passes ten cited evidence cases, and produces two
conditional date combinations for each of five verses. All **102 offline tests**
pass. This adds one physical witness, one original-writing unit, five assignments,
and one catalogue date assessment without new coordinates or schema changes.
Two university transcriptions were downloaded; only Alexandrinus was incorporated.
There were no new NTVMR requests and no replay network attempts. Manual review
covered five anchors, one page reconciliation, and one date-source check; elapsed
source-review time was not reliably measured across the interrupted session.
The remaining cost is per-verse source/layer review. Nine specific human-review
questions are prepared and unanswered; discovery remains incomplete.

The 2026-10-02 [Sinaiticus writing-layer review](GAL1_SINAITICUS_REVIEW.md) passes
**108 offline tests** and all **15 cited Galatians evidence cases**, with zero
structural findings and zero replay network attempts. The separate
[three-witness replay](../replay_gal1_sinaiticus.py) reuses both earlier manifests
and leaves their replays and charts available. It adds one original-writing unit,
five coverage assignments, two valid conditional date assessments, and one
qualified unknown observation. Source-specific 300–399 and 301–400 CE inputs
remain separate; corrected readings do not supply anchors or acquire the
original-writing date. One metadata response was retrieved through the existing
configured proxy after a direct timeout, and a university-source verification
matched the already retrieved transcription. Source and implementation work took
approximately ten minutes after the first metadata attempt; isolated review time
was not measured. Five specific independent-review questions are ready and
unanswered. Historical validation and discovery remain incomplete.

The 2026-10-05 [Washingtonianus supplement review](JOHN1_SUPPLEMENT_REVIEW.md)
passes **114 offline tests**, with **25/25 cited John 1 coverage cases**, zero
fresh audit findings, and zero replay network attempts. Its separate
[five-witness replay](../replay_john1_supplement.py) adds one physical witness,
one supplement writing unit, five coverage assignments, and one qualified
conditional date assessment. The five verses reach five witnesses at 601 CE in
the optimistic scenario and 800 CE in the pessimistic scenario. The manuscript's
400–499 CE catalogue fields remain in captured metadata and are not applied to
the replacement quire. Two budgeted NTVMR requests succeeded through the project's
configured proxy; the original and supplement transcriptions were downloaded
separately. About 30 seconds elapsed from the supplement capture to the final
index capture, excluding source reading and earlier scouting. Manual review
covered five anchors/lines, one page/identity link, and one layer/date source
check; total review time was not separately measured. No schema or collection
framework changed. Five specific independent-review questions are ready and
unanswered; discovery and historical validation remain incomplete.

The 2026-10-05 [Washingtonianus boundary review](JOHN5_BOUNDARY_REVIEW.md) passes
**121 offline tests** and **5/5 cited benchmark cases**, with zero fresh audit
findings and zero replay network attempts. Its [chart](../examples/john5-boundary-prototype.html)
adds five source-mapped coordinates, six page reviews (five positive, one
uncertain), two writing units, and two separate conditional date assessments for
one codex. The original 400–499 CE input applies only to reviewed text on 65r;
the qualified 601–800 CE input applies to the replacement quire on 64v. An empty
John 5:12 element is retained as uncertain without a physical-absence claim.
Two university downloads matched the cached full sources; existing NTVMR captures
were reused with no new NTVMR requests. A recorded 6-minute-16-second interval
includes source reconciliation, fixture/replay implementation, and the first
audit/export/render, excluding initial inspection and later tests/documentation.
It does not measure isolated reading or total effort. Five independent-review
questions are ready and unanswered. Existing schema, review APIs, exporter, and
renderer suffice; the shared benchmark gains an explicit uncertain expectation
for this real exception. Discovery and historical validation remain incomplete.

### Prototype implementation checklist (completed for the bounded scope)

The following work produced the first static chart and source table. The
[declared target](PROTOTYPE_SCOPE.md) was John 1:1–5, beginning with P75, 01,
and P66 while retaining 02 as a discovered candidate.

1. **Declare a bounded passage and witness set.** Aim for roughly 5–10 verses and
   at least three distinct real witnesses, with overlapping reviewed coverage so
   the graph exercises increasing counts. John 1 is a practical starting candidate
   because named probes already returned P66, P75, 01, and 02 at John 1:1; those
   hits still require coverage review. Choose the exact scope from accessible
   sources, document it, and keep unresolved work visible. Do not wait for all
   7,952 pending mappings or exhaustive corpus discovery. Any additional live
   requests remain explicitly scoped and budgeted.
2. **Finish the ordinary data path for that scope.** Record source-checked
   mappings, identities, coverage, writing units, coverage-unit assignments, and
   cited date assessments in reproducible inputs. A replay must create the links
   needed for rankings without manual SQL or test-only setup. Record cited
   consensus where known and explicitly unknown consensus otherwise; preserve
   applicable alternatives and source qualifications. Unknown consensus does not
   require an open-ended literature search or a preferred date. Reuse the existing
   collector and review interfaces; add only what this workflow demonstrates is
   missing.
3. **Build and inspect the graph alongside the data work.** Show both endpoint
   scenarios, conditional dating inputs, source links, and missing-work states.
   Keep source review by an agent identifiable. An explicitly labeled synthetic
   preview can establish chart behavior while real evidence is collected, but it
   does not satisfy the real-witness milestone. Whole-corpus certification and
   independent human publication review do not block prototype implementation.
4. **Measure the effort before widening scope.** Record reviewed coordinates,
   distinct witnesses, positive witness/verse pairs, graphable verses, pending
   mappings and assignments, source-review time, manual actions, and network
   attempts for the declared scope. Identify the largest repeated cost. Introduce
   targeted batch imports or reusable, source-supported mapping rules only where
   the example justifies them. Preserve individual provenance, immutable inputs,
   and review of exceptions; a coordinate mapping never establishes coverage.
   A brief development log is sufficient for these measurements; no reporting
   subsystem is needed for this milestone.

### Prototype acceptance

- A documented command sequence rebuilds a fresh database, exports its data, and
  generates the graph and table offline from checked-in, cited inputs. It does
  not depend on ignored local databases or test-only assignments.
- The declared passage has several real, distinct witnesses with overlapping
  sourced coverage and usable date assessments. All coordinates in the chosen
  scope remain accounted for; unavailable evidence is explicit. Retain all
  discovered candidates, even when fewer than five can be ranked.
- The graph follows canonical verse order, places newer years at the top, and
  matches the table's independent optimistic/pessimistic counts, capped at five.
  Sources, full ranges, partial coverage, active filters, and the included verse
  population are inspectable. Preserve the omission and bracket controls; use
  labeled fixtures to check cases outside the chosen passage.
- Every displayed dating combination is identified as conditional unless it
  follows documented consensus. Stored alternatives are accessible without a
  preferred scholar or assigned probabilities. Uncomputed combinations and
  overflow are visible. Existing synthetic tests can exercise competing dates,
  six-candidate membership changes, and edge cases absent from the real passage;
  do not invent real evidence to satisfy a test shape.
- The ordinary replay/export path passes applicable offline tests and structural
  audits. The graph is labeled **prototype: incomplete discovery and validation**
  and describes results as earliest among its reviewed, dated witnesses. It does
  not claim exhaustive historical earliest attestation. Passing these checks
  completes this milestone, not historical validation.

### Expansion after the prototype

Use the measured workflow to broaden inventory mappings and manuscript coverage
in bounded increments. Expand the source benchmark to P66/P75, a Pauline papyrus,
a major codex, a later supplement, and a substantial gap as coverage grows;
completing all these cases is not a prerequisite for the first graph. The current
positive review path requires an indexed page and explicit mapping. The separate
v12 physical-absence path supports direct evidence without an index row. It now
has source-reviewed Alexandrinus lacuna cases as well as synthetic regressions;
independent human checking of the real cases remains open.

Keep the existing P52 fixtures and manifests. Further dedicated P52 dating
research, exact-wording attestation, new witness categories, and general review
platform features are outside the next milestone. Supplementary omitted-verse
collection remains required but separately tracked; it cannot block the core
prototype or a validated core release. Full navigation and zoom can follow the
bounded graph. Increase collection volume only after the relevant API contract
and provider expectations are established.

The sections below define continuing correctness and publication requirements,
including already implemented behavior. They are not a sequential prerequisite
list for prototype development. This next-work section controls task selection;
do not restart completed collection or ranking work.

## Prototype and historical-publication expectations

| Output | Required before use |
| --- | --- |
| Synthetic chart preview | Clearly identified fictional inputs, correct chart semantics, and no historical claims |
| Bounded real-data prototype | Cited evidence and faithful date recording for displayed witnesses; explicit scope, review status, incomplete discovery, and unresolved work; reproducible offline results |
| Historical release for a declared scope | Applicable source-based benchmarks and audits pass with no unexplained failures; independent human checks of coverage and source fidelity; versioned evidence and dating inputs, explicit discovery limitations, and claims restricted to the reviewed scope |
| Whole-NT attestation claims | The historical-release requirements across the claimed corpus, reviewed edition/mapping coverage, and a defensible discovery-completeness basis for those claims |

Prototype labeling does not permit invented coverage, suppressed alternatives,
unsupported dates, or misrepresented human approval. Publication review checks
source fidelity and coverage; it does not settle dating disputes. Unfinished
supplementary collection does not block publication of a validated core scope.

## Research contract

1. **Reference edition:** NA28, selected by the project owner. Store its explicit
   verse inventory and an edition identifier; do not equate KJV chapter maxima
   with edition membership. Preserve traditional coordinates, with explicit
   policies for omitted numbers, brackets, and verse-boundary differences.
   Collect skipped traditional verses as supplementary evidence tagged `omitted`.
   Default graphs exclude them, with an explicit inclusion option and a separate
   bracketed-passage control. Edition status never determines manuscript coverage
   or dating. Apply the same evidence standards to both collection scopes.
2. **Attestation:** identifiable surviving Greek text from any part of that verse
   in an eligible manuscript copy of the New Testament text itself.
   Record partial/full/uncertain status. Exact agreement with all NA28 words is
   outside the initial scope. Physical lacunae, reconstructed text, inferred
   neighbors, and inferred complete books do not qualify. A quotation or allusion
   in another work does not establish verse coverage within this project.
3. **Initial corpus:** surviving Greek manuscript copies of the New Testament
   texts themselves, including eligible fragments and lectionaries.
   Classify multilingual witnesses by their Greek
   content. Printed editions are reference resources, not ancient witnesses.
   Quotations, paraphrases, and allusions in other works are excluded, including
   verbatim quotations by Justin Martyr or other patristic authors. A manuscript
   preserving such a work is not an eligible copy of the quoted New Testament
   text. Neither the date of that manuscript nor the author's composition date
   makes it eligible for coverage, witness counts, or rankings.
   Keep amulets, ostraca, and other source categories explicit and outside the
   combined graph until an inclusion policy is settled and versioned; their
   contents must also satisfy the direct-copy requirement. Translations remain
   outside the Greek manuscript series. Adding indirect evidence requires an
   explicit future scope change and is not a planned expansion of this corpus.
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
- Apply the direct-copy scope during document review. A Greek manuscript of a
  different work containing a biblical quotation is `other`, with decision
  `exclude` and a cited reason; Greek language or an exact wording match alone
  cannot justify `greek_manuscript` and `retain`.
- Validate `status=success` and explicit endpoint structures. Unknown JSON shapes
  are contract errors, never silently empty lists. Add captured list, singleton,
  empty, error, and truncated/malformed fixtures.

**Acceptance:** known eligible early witnesses are discoverable; print editions
and quotations/allusions in other works are excluded from the manuscript series;
duplicates do not increase witness counts; every run reports a declared discovery
scope and completeness status.
The old 37-candidate cache is retained for comparison, not used as the complete
corrected corpus.

## 3. Build the NA28 inventory and evidence schema

The [v3 provisional coordinate manifest](../benchmarks/na28-nt-reference-provisional-v3.json)
and [publisher source ledger](../benchmarks/na28-coordinate-source-v1.json) now
cover all New Testament chapters without reproducing edition text. Its 7,952
unreviewed NTVMR mappings remain empty by design. Confirm editorial cases and
source-identify the mapping to the NTVMR versification in a new snapshot. Avoid
assuming an API v11n ID named `NA28` exists; verify supported values or supply a
reviewed mapping. The [1 Corinthians 4 review](../benchmarks/na28-coordinate-review-v2.json)
records the direct publisher check; v1 retains the original UBS5 fallback. The
[skipped-passage review](../benchmarks/na28-passage-identifications-v1.json)
identifies all 16 traditional passages without asserting NTVMR mappings or witness coverage.

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

For skipped coordinates, retain a cited identification of the traditional passage
and any relevant boundary or wording notes alongside the reviewed index mappings.
These identify the supplementary target without claiming NA28 main-text membership.
Keep edition omission, verified physical absence, damage, and unknown or unreviewed
coverage distinct. Collect evidence irrespective of the default display filter.

**Acceptance:** stable order from Matthew to Revelation with numeric chapters and
verses; no invented verse from a range string; no accidental mixing of editions;
unknown/omitted/bracketed coordinates have defined export behavior. Changing the
requested subset filters an existing database before applying a verse limit.
Skipped-coordinate evidence survives display exclusion, and every supplementary
coordinate accepted for coverage has a cited passage identification and reviewed
mapping.

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
uses complete assessments and records which ones it uses. Stored snapshots use one
assessment per unit per policy. The offline export also calculates both endpoint
rankings for every combination of stored valid unit dates up to its explicit cap;
it does not resolve scholarly disputes.
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

Preserving and exposing alternatives is required; eagerly enumerating their
entire Cartesian product is an implementation choice. The current exporter caps
enumeration at 256 combinations per verse and returns `too_many_combinations`
with no combinations above that limit. Nine writing units with two assessments
each already require 512 combinations. Do not silently truncate, fall back to a
preferred assessment, average ranges, or interpret overflow as no evidence.

Exercise this limit in the prototype's presentation. Before expanding to data
that exceeds it, provide a bounded way to inspect outcomes, such as calculating
explicitly identified combinations on demand with equal access to every stored
assessment. Distinguish results computed for chosen inputs from exhaustive
enumeration; never label a partial exploration complete. On-demand calculation
and a consensus representation are future work, not existing exporter features.
The first bounded graph can use the current complete enumeration where it fits
and an explicit overflow display elsewhere. Do not build a general scenario
framework before the example demonstrates a need.

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

## 6. Validate source fidelity and coverage for historical publication

Build the prototype while developing a reviewed benchmark with stable citations,
recorded source dates, positive and negative verse coverage, and expected sourced
date assessments.
Retain P52 as an existing example; expand to P66/P75, one Pauline papyrus, one
major codex, a late supplement, and a witness with a substantial gap. Do not
hardcode their dates from memory.
The benchmark should test individual evidence claims rather than asserting one
famous manuscript must always win. Expand this benchmark incrementally; the whole
representative set is not required before drawing the first bounded graph.

Dating validation establishes that source ranges, qualifications, conversions,
and any documented consensus are faithfully represented. Where consensus is
unknown, it checks preservation of equal alternatives. Neither human reviewers
nor agents are tasked with deciding which dating argument is correct. A disputed
date is not a benchmark failure or a publication blocker when its uncertainty is
represented faithfully; missing citations or concealed alternatives are defects.

Apply these validation layers to the relevant behavior and evidence. Independent
human checking is required for historical publication, not to begin implementing
or inspecting a labeled prototype. Record which checks have actually occurred.

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

### Human review question packets

When a bounded evidence set is ready for independent human checking, Codex will
prepare a small review packet for the project owner. Prepare the sources and
specific questions before requesting answers. Continued development and source
collection do not require the owner to review unfinished evidence. This is the
planned review workflow; packet generation and answer import are not currently
implemented features.

Each item should identify the verse, physical witness, writing unit where
relevant, and versioned claim or review record being checked. Supply the source
link, precise page/folio/line or transcription location, the recorded claim, and
any source qualifications. Make the evidence accessible without requiring the
reviewer to reconstruct the collection process.

Use specific questions adapted to the evidence, for example:

| Check | Question to the human reviewer |
| --- | --- |
| Verse survival | Can you identify surviving text from this verse at the cited location? |
| Extent or absence | Does the cited evidence support the recorded partial survival or physical absence? Is the apparent gap physical damage, a textual omission, or unresolved? |
| Date-source fidelity | Does the recorded range reproduce the source's notation and qualifications, with any numeric conversion explained faithfully? |
| Writing-layer applicability | Does the source support applying that date to the writing layer containing the reviewed text? |
| Physical identity | Do the cited records describe distinct manuscripts, or parts of the same physical witness? |

For each proposed claim, offer **agree**, **disagree**, and **unable to assess**,
with space for notes and corrections. Label checks that can be made directly
from a catalogue or quoted source separately from checks requiring Greek,
palaeographic, or codicological expertise. An owner response is human review of
the checks actually performed; it does not automatically establish specialist
validation. Route specialist questions for qualified review when needed.

Record the human reviewer's identity, review date, answers, notes, and exact
claim/source versions separately from Codex reviews and automated checks.
Retain prior decisions when recording corrections. Unanswered questions,
disagreements, and inability to assess remain explicit; silence is not approval.
Report which claims were checked and which remain unresolved before evaluating
the publication requirements for that scope. Neither the owner nor a specialist
is asked to settle competing scholarly dating arguments: the check is faithful
recording and applicability, preserving sourced alternatives and uncertainty.

## 7. Export and build the graph

Develop exports and the graph during the bounded prototype milestone. Apply the
historical-publication requirements before presenting results as a validated
historical release. Export a versioned dataset retaining every inventory
coordinate in its declared scope, including supplementary `omitted` coordinates,
in canonical order,
with edition status, zero-to-five witnesses per scenario,
event years, full date intervals, source/evidence links, and completeness status.
An export should identify its edition, source snapshot, inclusion/dating policy,
and validation version. Include consensus status and its supporting citation where
known; otherwise expose equally valid alternative ranges and their ranking
outcomes. Preserve original notation and conversions as well as numeric bounds.
It must support reproduction without fresh API requests.

Keep the complete dataset separate from filtered graph exports. The offline
[`export_attestation.py`](../export_attestation.py) command implements these data
filters; [`render_attestation.py`](../render_attestation.py) now builds a bounded
static chart and table from its graph input. The John 1 several-witness prototype
now uses this path; historical validation remains future work. Default graphs
exclude `omitted` coordinates and provide an **Include verses omitted from NA28**
option; bracketed passages have a separate inclusion control. Record active
filters and the resulting verse population in every graph export and summary.
Recompute aggregate counts and denominators for that population without deleting
underlying evidence or treating excluded coordinates as unattested. Report core
and supplementary collection completeness separately. Unfinished supplementary
collection does not block publication of the validated core scope. Apply the same
evidence standard to core and supplementary records within each output's declared
review status; supplementary evidence in a historical release must pass the same
applicable publication checks.

Plot verse positions horizontally and CE years vertically, **newer at the top**.
Moving upward from earlier to later years, show no witness color before the first
event, then one-through-five colors; after the fifth event retain the fifth color.
Equal-year events occur together, with no invented visible interval between them.
Use the same axis bounds and color legend for both scenarios. Show unknown or
unfinished evidence separately from the pre-first-witness portion of a completed
series. Identify included omitted/bracketed coordinates by their edition status.

Start with the bounded chart and an accompanying table of ranked witnesses, both
date bounds, partial coverage status, and source links. Add book/chapter navigation
and zoom when expanding to a larger scope. A static
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
checks to verify default omission exclusion, optional inclusion, independent
bracketed-passage filtering, preserved stored evidence, and consistent exported
filters and summary denominators. Verify that unknown evidence and excluded
coordinates remain distinguishable. Use static
tests and production builds for frontend verification. Do not start a development
server or probe localhost unless the project owner asks.

## Working and documentation rules

- Keep the current status and next-work list in this plan aligned with the actual
  schema, commands, fixtures, and observed database contents. Update the README's
  summary when a milestone changes; retain the original data review as history.
- Treat this plan as the source of current development priorities; the README
  summarizes them and documents commands. Distinguish implementation, replayable
  inputs, inspected local data, and historical validation. Date observations and
  identify the database inspected; an updated manifest does not update local data.
- Report each development increment against the prototype or a declared expansion:
  what became graphable, what evidence was added, what obstacle was removed, and
  what remains. Schema versions and test counts alone do not measure delivery.
  Include the review-effort measurements before recommending a larger collection.
- Tie each new schema, audit, abstraction, or feature to a concrete failure or
  unmet requirement in the active milestone. Prefer completing the existing path;
  defer speculative generalization and broad refactoring. Do not create a new
  research or approval prerequisite from an unresolved scholarly disagreement.
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
