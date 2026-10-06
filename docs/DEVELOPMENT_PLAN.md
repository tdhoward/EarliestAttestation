# Development plan

**Scope reset: 2026-10-05.** This is the current development plan. It replaces
the [historical plan](HISTORICAL_DEVELOPMENT_PLAN.md), whose manuscript examination
and specialist-validation requirements are withdrawn. Follow
[AGENTS.md](../AGENTS.md) and the [README](../README.md) for the same scope boundary.
Older review notes and their next-work lists do not override this plan.

## Project contract

Build a reproducible dataset and chart of what scholarly sources report about
the estimated ages and verse contents of surviving Greek New Testament copies.
The owner and agents are collecting and organizing scholarship, not producing it.

- **Sources:** prefer NTVMR's documented metadata and verse-content reports.
  Accept explicit claims from other scholarly catalogues or publications when
  needed. One usable scholarly report suffices; do not require independent
  corroboration or our own examination before counting it.
- **Presence:** any reported surviving portion counts as that verse being present
  for a witness. Do not require complete preservation, exact NA28 wording, a
  minimum fragment size, or a word anchor. Preserve an optional source-supplied
  partial/full description without making it a counting prerequisite.
- **Boundary:** never download or inspect manuscript images to determine contents,
  dates, identity, hands, corrections, or damage. Never infer these from Greek
  transcription text, apparatus interpretation, or empty transcription elements.
  Explicit published assertions may be extracted without examining their underlying
  text. A citation to an image or transcription is not itself a scholarly claim
  about which verses survive.
- **Uncertainty:** explicit disagreement between scholarly reports about a
  witness's verse contents is `contested`; retain both reports and defer the case.
  Missing or ambiguous information is `unknown`. Missing API hits alone establish
  neither absence nor disagreement. Do not adjudicate contested cases or ask the
  owner to examine manuscripts to resolve them.
- **Dates:** retain each reported estimate, original notation, qualifications,
  source, and applicability. Preserve complete competing intervals equally unless
  a source establishes consensus. Do not independently date a manuscript or
  choose, average, narrow, or merge scholarly ranges.
- **Identity and portions:** count one reported physical witness once per verse.
  Record aliases, fragment joins, supplements, corrections, and distinct dated
  portions only when sources explicitly identify them. No independent hand or
  writing-layer classification is required or allowed.
- **Corpus and edition:** retain the Greek direct-copy scope, NA28 coordinates,
  and supplementary traditional skipped verses described in the README. Exclude
  quotations/allusions in other works. Edition omission says nothing about a
  manuscript's reported contents or estimated age.
- **Claims:** results describe earliest witnesses reported in the collected
  sources and declared discovery scope. They do not certify manuscript contents,
  resolve scholarship, date composition, or establish exhaustive discovery.

## Current implementation and migration status

The existing Python/SQLite collector already supplies budgeted collection,
immutable responses, cache replay, explicit document scopes, and source indexes.
A provisional NA28 inventory, deduplication, endpoint rankings, offline exports,
and static charts are available. Reuse these components.

Schema v12 also contains manual coverage reviews, physical-absence decisions,
writing units, and ranking gates from the superseded approach. Existing benchmarks
and examples include agent interpretations of images and transcriptions. Their
passing tests demonstrate software behavior and reproducibility, not compliance
with the current source-report policy.

The scope-reset documentation itself did not migrate data or implement behavior.
The subsequent [source-report increment](NTVMR_SOURCE_REPORT_CONTRACT.md) now
provides an immutable batch/claim path, explicit `contested` handling, version 3
exports, and a bounded Galatians chart. It reuses response storage, inventories,
endpoint rankings, and SVG charts while excluding the old review gates and inputs.
Legacy positive/absence conflict flags remain historical behavior, separate from
the new scholarly-claim states. Existing databases were not migrated.

Existing fixtures, replays, charts, and local databases remain unchanged. The
unfinished John 5 overlap manifests and image/transcription-review drafts from
the interrupted increment are not accepted inputs. Preserve their history if
needed, but do not use or extend their inferred claims in the next dataset.

## Next development work

The first bounded milestone is implemented: Galatians 1:1–10, three witnesses,
six reused document captures, 29 reported-present pairs, one unknown pair, no
reported conflicts or absences, 10 graphable coordinates, and zero replay network
requests. The new path retains conflicts and date alternatives, exercised with
synthetic software tests. Its attribution audit excludes historical agent claims
for this increment; it does not complete a repository-wide audit.

**Next priority: expand this path efficiently** with additional documented
document batches and coordinate subsets. Reuse metadata and contents once per
document and invert reports locally. Before broad search discovery, implement
the now-documented `partial`/`afterDocID` continuation contract with offline tests.
Unsupported changed mappings and portion-specific date applicability remain
bounded-contract limitations. Audit further historical claims only when needed
for the next active dataset; preserve their history.

The milestone sequence below remains the project roadmap, with steps 1–4 now
implemented for the declared Galatians subset. Do not restart a manuscript
research programme.

1. **Establish the source-field contract.** Inspect existing captures and API
   documentation to identify which fields explicitly report contents, date bounds,
   identity, and collection completeness. Distinguish search matches, contents
   assertions, and broad summaries. If a contract remains unclear, use a bounded,
   budgeted check or retain uncertainty; do not inspect the manuscript.
2. **Adapt the existing normalization and ranking path.** Store attributable
   scholarly claims and count any reported portion as present. Remove dependence
   on agent word anchors, image reviews, or independently assigned writing units.
   Implement explicit `contested` coverage with retained opposing reports. Keep
   unknowns, failures, and reported absences distinct. Do not bypass old gates by
   fabricating a review or marking every report as physically verified.
3. **Audit attribution of existing examples.** Separate explicit scholarly reports
   from our prior inferences. Re-source a claim from an explicit report when
   available; otherwise exclude it from active outputs while retaining its history.
   An unsupported agent claim is not a disagreement between scholars. Do not
   grandfather a claim because a benchmark, citation URL, or chart already exists.
4. **Produce the first compliant bounded chart.** Select a small passage/witness
   set for which captured source reports are usable. Replay from fresh storage,
   export, and render with citations, date alternatives, and visible unknown or
   contested cases. The old John 5 examination task has no priority over this path.
5. **Expand collection efficiently.** Fetch each manuscript's metadata and contents
   once where possible, invert verse-to-witness relationships locally, and broaden
   batches and coordinate mappings under documented contracts. Defer contested
   cases without blocking other manuscripts. Measure usable records and request
   cost before introducing further abstractions.

No new general review system, specialist approval process, compulsory
multi-source corroboration, or dedicated P52 dating investigation is required.
The primary obstacle to remove is the pipeline's dependence on our own
manuscript judgments, not a shortage of such judgments.

### Acceptance for the next milestone

- Every active date and coverage claim identifies a scholarly provider or author,
  the specific reported field or statement, citation, retrieval/consultation date,
  and source response or snapshot where available.
- A source-reported partial verse gives one full presence count, with no image,
  Greek-text interpretation, or independent writing-layer check in the workflow.
- A declared source disagreement is retained as `contested`, shown separately,
  and excluded from ordinary presence counts while deferred. Unknown and
  explicitly reported absent cases remain distinguishable. Other cases proceed.
- Repeated pages, aliases, fragments reported as joined, and date alternatives
  do not multiply one witness. Both endpoint rankings and their provenance are
  correct for the chosen source intervals.
- A fresh offline replay produces the bounded chart with no network requests;
  relevant software tests and structural audits pass. No server or localhost
  probe is needed.
- Report the collected scope, present/contested/unknown records, graphable
  coordinates, mapping gaps, and collection cost. Do not substitute schema
  versions or old benchmark counts for delivered functionality.

## 1. Controlled collection

Use the official HTTPS NTVMR origin by default with a configurable base URL and
clear project user agent. Prefer cached responses and document batches over
repeated requests per verse. Preserve raw responses, endpoint, parameters,
retrieval timestamps, hashes, attempts, and parse outcomes separately.

Keep live collection explicitly scoped and budgeted. Budgets include previous
attempts under the same run ID and retries. Use one worker with the existing
minimum interval, honor `Retry-After`, and stop/checkpoint on authentication,
blocking, or repeated rate-limit responses. Do not change identity to bypass a
block. Establish provider expectations before bulk access. Keep tests offline;
live calls are source collection or contract checks, not routine final validation.

A failed refresh preserves the previous source snapshot and marks its collection
state; it must not masquerade as an empty contents report. Back up existing SQLite
files before migrations and use fresh destinations for reproducibility checks.

## 2. Source contracts and discovery

NTVMR's documented contents assertions can directly support reported presence.
They do not require independent image or transcription verification. Check field
semantics once per supported contract and version, rather than examining each
manuscript to validate the catalogue.

Captured long contents responses contain explicit `osisID`, `docID`, and `pageID`
entries. The parser must handle documented structures, not infer verse references
from arbitrary strings. Preserve broad chapter/book summaries without expanding
them unless the source's contract explicitly supplies that meaning. Unknown or
malformed response shapes are contract errors, not empty results.

Preserve original language and type fields and normalize them under documented
rules. Existing P52 language-filter fixtures remain useful parser/discovery
regressions. Report bounded document and passage-search scopes honestly; matched
result counts alone do not prove exhaustive discovery. A search omission relative
to a contents report is a discovery discrepancy, not automatically a scholarly
claim of absence or a contested verse.

## 3. Inventory, mappings, and provenance

Use the versioned NA28 coordinate inventory and explicit mapping to the source's
reference system. Check mapping rules against documented versification and
published coordinate metadata. Batch a supported rule with recorded exceptions;
do not require per-verse manuscript examination. Keep unresolved mappings visible.

Record enough information to reproduce every normalized assertion:

| Record | Required information |
| --- | --- |
| Source snapshot | Provider/author, endpoint or citation, parameters, retrieval date, raw response/hash when available |
| Witness | Source identifier, reported type/language/identity, explicitly documented aliases or joins |
| Contents claim | Witness, source and mapped verse, presence/absence/uncertainty assertion, exact source field or statement, qualifications |
| Date assessment | Witness or explicitly identified portion, original notation, full bounds if usable, source and applicability |
| Derived result | Snapshot, source claims, inventory/mapping version, filters, dating inputs, state, endpoint events |

This is a logical contract, not a requirement for a new generalized schema.
Adapt existing storage with only changes needed for the active milestone. Preserve
older source versions and decisions when correcting extraction or attribution.

## 4. Reported verse contents and contested cases

The following states are implemented by the new source-report batch path.
They do not change the behavior of the legacy v12 review tables:

| State | Meaning and counting |
| --- | --- |
| Reported present | A scholarly source reports any portion of the verse; counts once per eligible physical witness |
| Reported absent | A scholarly source explicitly reports absence; no presence event |
| Unknown | Missing, ambiguous, or unusable contents information; no inferred absence |
| Contested | Scholarly sources make incompatible explicit claims about the same witness/verse; retain both, show separately, defer and omit from ordinary presence counts |

Disagreement about partial versus full extent alone does not contest presence:
both reports count as present under this project's rule. A missing entry in a
non-exhaustive source is not an explicit negative claim. Different page fragments
or different manuscripts must not be mistaken for contradictory reports about
the same witness. Record conflicting source assertions without deciding who is
right. Technical collection/parse errors remain separate from these claim states.

Do not infer textual omission, physical damage, or survival from an image,
transcription gap, empty element, or reconstructed word. If a scholarly source
explicitly reports a cause, retain that qualification as its statement.

## 5. Rank independently for both date scenarios

Start with all eligible reported-present witnesses with usable sourced intervals
`[date_min, date_max]`. Preserve every complete interval and its applicability.
Use documented consensus when known; otherwise expose equally valid alternatives
without adjudication. Unknown numeric bounds stay unrankable, while the reported
contents remain visible. Unknown consensus is not a blocker.

- Optimistic: sort by `(date_min, date_max, stable_witness_id)` and take up to five.
- Pessimistic: sort by `(date_max, date_min, stable_witness_id)` and take up to five.

Calculate each scenario independently for each declared date combination. For a
physical witness with multiple explicitly source-identified qualifying portions,
derive its event once per scenario and count it once. Never independently infer
such portions or their dates to satisfy a storage requirement. Ties are ordered
deterministically without claiming historical precision.

Retain complete competing ranges; do not merge their endpoints. The existing
exporter caps exhaustive combinations at 256 per verse and reports overflow
explicitly. Keep that limit visible; on-demand exploration and structured
consensus storage are future work only when a concrete need arises.

## 6. Verify faithful data handling

Verification establishes that software faithfully captures and presents scholarly
reports. It does not establish that their scholarship is correct. Tests should
cover parsing, explicit reference mappings, attribution, any-portion counting,
identity deduplication, contested/unknown/absence handling, date alternatives,
ranking reversal, ties, changed sources, and offline reproduction.

Historical image/word-anchor benchmarks are records of the old approach, not
acceptance standards for the new dataset. Reuse their software cases where useful,
but replace or exclude unsupported historical assertions. A clean structural
audit is not proof of a source claim; a source claim does not require new
manuscript examination or independent scholarly certification.

### Human review question packets

Older packets asking the owner to read Greek, inspect images, identify hands,
or assess survival are withdrawn. Do not ask for their completion or route them
for specialist approval as a project prerequisite. No automated packet system
is needed for the current milestone.

Optional human checks may ask whether we copied a catalogue field correctly,
preserved the source's qualification, linked the right record, or displayed a
known disagreement. Record actual corrections and attribution accurately.
Neither the owner nor agents should resolve the underlying scholarship.

## 7. Export and build the graph

Retain complete source claims separately from the filtered graph output. Show
both endpoint scenarios, full date intervals, citations, dating inputs, coverage
states, collection scope, and mapping/collection gaps. Contested cases remain
inspectable without requiring resolution to render the rest of the graph.

Keep canonical verse order horizontally and CE years vertically, newer at the
top. Use one shared scale and color legend for both scenarios. Counts rise from
one through five as distinct witness events occur; equal-year events occur
together. A source-reported fragment counts as one verse presence. Unknown,
contested, filtered-out, and explicitly reported absent cases remain distinct.

Preserve the default exclusion and optional inclusion of supplementary `omitted`
coordinates and the independent bracketed-passage filter. Every output identifies
its filters and verse population. Supplementary collection does not block the
core result. Include a source table so provenance is accessible without hover.

## Prototype and historical-publication expectations

The earlier requirement for independent human manuscript checks or scholarly
certification before publication is withdrawn. Release checks concern software
correctness, faithful attribution, and transparent scope:

| Output | Required before use |
| --- | --- |
| Synthetic preview | Clearly fictional inputs and correct chart behavior |
| Bounded source-report chart | Attributable reported contents/dates, correct normalization and counting, visible uncertainty/disagreements, declared scope, offline reproduction |
| Wider source-report release | The same requirements across its declared collected scope, versioned inputs, passing relevant checks, explicit discovery and mapping limits |

Never label an agent's inference as a scholarly report. No output should claim
independent historical validation or exhaustive earliest-attestation discovery
without a basis in its source scope. Specialist examination and settlement of
scholarly disagreements are not project deliverables or release gates.

## Working and documentation rules

Keep this plan and the README aligned with implemented behavior. Clearly label
planned features and historical observations. Preserve the archived plan and
review notes for provenance, with prominent notices that their examination tasks
and publication gates are superseded.

Make source collection, software verification, and optional extraction review
traceable without presenting agents or the owner as manuscript scholars. Use
fresh databases or backups, preserve immutable inputs, and run appropriate
offline checks for changed code. Do not start a development server or probe
localhost unless the owner explicitly asks. New infrastructure must remove a
concrete obstacle in the active collection-to-chart milestone.
