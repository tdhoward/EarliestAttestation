# App data size and memory optimization guide

Status: Phases 0–5 completed on 2026-10-06; Phase 6's offline audit and hosting
handoff completed on 2026-10-06. Deployment compression activation remains pending.
The production writer and current data now use the complete numeric version 3
schema. Python and JavaScript restore every field exactly, with version 1 and 2
compatibility retained. The app now retains shared read-only data for charting and
resolves full observations only for selection. Repository work is complete
through compression measurements and hosting requirements.
There is no deployment configuration in this repository to enable HTTP compression.
Activation and live response-header verification depend on a deployment environment.
This guide is based on offline work on 2026-10-06.

## Objective and constraints

Reduce `data/attestations.json` and the app's memory use while preserving the
complete normalized data and existing visible behavior. Keep one central
collection, one current JSON file, and one app.

Follow [AGENTS.md](../AGENTS.md) and the
[source contract](NTVMR_SOURCE_REPORT_CONTRACT.md). This is a storage and loading
change. Preserve scholarly reports, exact reported values, citations, hashes,
retrieval dates, qualifications, complete competing date intervals, and source
links. Preserve array order, value types, nulls, missing fields, and identifiers.
JSON object key order need not survive decoding; generated output must still be
deterministic. Do not change reference mappings, discovery scope, witness
identity, coverage classification, or ranking policy.

Unknown, explicit absence, contested, uncollected, and filtered states must
remain distinct. A missing observation must never become an unknown observation
merely because its coordinate exists. Do not infer adjacent coverage or examine
manuscript images, Greek transcription text, or apparatuses.

Use retained local inputs only. No live collection, local server launch, or
localhost probing is needed. Experiments and full-size baselines belong in
ignored `data/.cache/`. Small synthetic regression fixtures may live in `tests/`.
Do not add a second production dataset or a persistent normalization database.

## Measured opportunity

The audit used 17 witnesses, 7,957 display coordinates, 7,941 observations,
17,135 coverage claims, 16,640 present pairs, and 118,357 unknown pairs.
The file occupies 12,476,223 bytes, including its final newline.
Tables below exclude that newline; MB measurements use decimal units.

| Section in version 2 | Compact JSON bytes |
| --- | ---: |
| Observations, including date combinations and ranking events | 6,706,233 |
| Claims | 3,653,544 |
| Coverage records | 1,877,724 |
| Coordinates | 167,503 |
| All other sections and enclosing syntax | 71,218 |

Experiments serialized and decoded the entire payload, then compared it with
the original version 2 object. Every experiment preserved all fields.

| Compatible changes accumulated | Result bytes, excluding final newline |
| --- | ---: |
| Existing version 2 | 12,476,222 |
| Share ranking templates | 7,693,332 |
| Also share observation metadata | 6,306,394 |
| Also compact claims and share coverage contexts | 1,769,061 |
| Also store coverage as defaults plus exceptions | 1,574,313 |

The current data yielded 28 ranking templates, 37 observation contexts, and 51
coverage contexts. These counts describe the measured input; never hard-code
them. The scratch prototype, if still available, is
`data/.cache/size-audit.py`; it assumes today's claim shapes and is not a
production implementation or required build input.

Source metadata, documents, and dates together use about 43 KB. Raw source
responses are already excluded from this transfer file. Exact `reported` fields
are displayed in the source-details panel. Concentrate on representation and
sharing instead of deleting provenance.

An offline Node measurement found about 32.8 MB of retained heap for parsed
version 2 and 52.1 MB after expansion, measured above an empty-process baseline
with garbage collection exposed. These are neither peak-memory measurements nor
browser benchmarks. Gzip level 9 reduced the existing JSON to 546,720 bytes;
the fully compacted prototype compressed to 294,185 bytes.

## Code ownership and intended design

| File | Work |
| --- | --- |
| `report_explorer.py` | Version 3 packing and exact Python expansion; keep normalized `build_explorer_data()` output unchanged |
| `web/attestation-explorer/explorer.js` | Matching decoder, then a shared runtime data store and model accessors |
| `web/attestation-explorer/app.js` | Version-compatible loading; later stop eager expansion |
| `build_collection.py` | Switch the writer only after both decoders pass; preserve atomic output and `--check` |
| `collect_source_discovery.py` | Keep its output on the same packer; exercise with offline fixtures |
| `tests/test_report_explorer.py`, `tests/test_collection.py` | Exact restoration, deterministic builds, malformed inputs, and source fidelity |
| `tests/app.test.js`, `tests/explorer.test.js` | Cross-language decoding, loader paths, runtime behavior, and chart equivalence |
| `README.md`, `docs/ATTESTATION_EXPLORER.md`, `docs/DEVELOPMENT_PLAN.md` | Update implemented behavior and measured results at rollout |

The production browser transfer uses `format_version: 3`. This is independent
of the existing scholarly graph export's version 3. Python and JavaScript expansion
must continue to accept browser versions 1 and 2 and return normalized version 1.
Keep those expansion functions as exact, independently mutable compatibility
views even after the runtime gains an immutable shared store.

Phases 1–3 retained private candidates alongside the version 2 writer until the
Phase 4 rollout. Numeric version 3 now uses the complete schema below; the
intermediate layouts were never published as production version 3.

The retained Phase 1 candidate is `pack_explorer_data_phase1()` and uses the
private string marker `format_version: "3-phase1"`. Python expansion and the
JavaScript decoder accept it for offline checks and fixture loading. It retains
version 2 claim tuples and coverage objects, adds ranking/observation tables,
and uses only dense coverage encodings. The Phase 2 candidate is
`pack_explorer_data_phase2()` with `format_version: "3-phase2"`; it adds the
documented tagged claim tuples and shared coverage contexts while retaining
dense coverage. The Phase 3 candidate is `pack_explorer_data_phase3()` with
`format_version: "3-phase3"`; it adds exact coverage defaults and sparse
exceptions, retaining dense fallback. Both decoders accept all three candidates.
`pack_explorer_data()` now emits this complete layout with numeric version 3;
these private candidate markers are not production format contracts.

Use this layout as the implementation contract. Tuple positions and tags are
part of the format, documented beside both codecs; do not emit schema descriptions
on every row.

| Version 3 field | Stored form |
| --- | --- |
| `coordinates`, `coordinate_inventory`, `metadata`, `documents`, `sources`, `dates` | Existing values, unchanged |
| `claim_contexts`, `discovery_records` | Existing shared-object approach |
| `claims[id]` | `["ntvmr_index_v1", contextIndex, [indexContent, osisID, pageID, locatorIndex]]` or `["literal", contextIndex, detailsObject]` |
| `coverage_contexts` | Objects containing all coverage fields except `claims` |
| `coverage_records[index]` | `[coverageContextIndex, claimIdStrings]` |
| `ranking_templates` | Complete dating-alternative objects with event claim references encoded as described in phase 1 |
| `observation_contexts` | All observation fields except `reported_coverage`; `discovery` and `dating_alternatives` are table indices |
| `coverage_defaults` | Ordered vectors of coverage-record indices for sparse observations |
| `observations[ref]` | `[observationContextIndex, coverageEncoding]` |
| Dense `coverageEncoding` | `["dense", coverageRecordIndices]` |
| Sparse `coverageEncoding` | `["sparse", defaultsIndex, [[position, coverageRecordIndex], ...]]` |

Build tables in deterministic first-encounter order. Intern by complete JSON
value, preserving type distinctions; Python's `True == 1` is not an acceptable
deduplication rule. Keep string claim/date lookup IDs distinct from numeric
event IDs. Preserve supported extra fields rather than silently projecting them
away. If a compact encoding cannot reproduce a valid record exactly, use its
literal or dense representation.

## Phase 0: establish the correctness oracle

Completed on 2026-10-06. `python build_collection.py --check` accepted the current
offline build, and `build_data()` matched `expand_explorer_data(current_file)`
exactly. The work-session baseline is in ignored
`data/.cache/size-optimization-phase0-2026-10-06/`: `attestations.v2.json` is the
unchanged 12,476,223-byte production file, and `normalized.v1.json` is its
39,599,390-byte independently built normalized result. Both sizes include the
final newline. These cache files are temporary references, not build inputs.

The [fixture guide](../tests/fixtures/README.md) documents the shared fictional
version 1 oracle, frozen version 2 compatibility snapshots, and empty-export
case. Python checks both retained versions and deterministic current packing;
its integration test passes Python's packed data to Node and compares the whole
decoded object with the independent version 1 fixture. Node uses the same files
for exact decoding, fetch/file-picker loading, coverage states, alternative
selection, ties, unresolved mapping, overflow, filters, and empty data. JSON
comparison distinguishes booleans from numbers and preserves array order, nulls,
missing fields, and extra fields. The existing collection equality test remains
the full-collection oracle.

Verification: all 10 Python explorer tests and 20 `npm test` tests passed, along
with the focused current-collection equality test. Production JSON remains
12,476,223 bytes; no compression or runtime-memory implementation or measurement
was performed in this phase. Phase 1 implementation is recorded below.

The completed scope was:

1. Verify the current build offline and capture the existing file in
   `data/.cache/` for this work session. Compute normalized data with
   `build_data()` and confirm it equals `expand_explorer_data(current_file)`.
   Do not check a full-size baseline into Git.
2. Retain small version 1 and version 2 compatibility fixtures. Add one shared
   fictional normalized fixture that Python can pack and Node can decode. Use
   ordinary explicitly fictional field assertions, never manuscript examination.
3. Include two verses that share metadata but have different claim IDs, multiple
   claims for one witness, explicit absence and contested reports, unknown with
   and without a claim, both unknown reasons, and an unresolved mapping. Include
   a filtered coordinate, a coordinate without an observation, and an empty
   export case. Reuse existing cases where possible.
4. Include two complete date alternatives for one witness, an unrankable date,
   tied endpoints, an unavailable selected combination, and combination overflow.
   Keep a case where `ranking_state` differs from `dating_alternatives.state`;
   the current synthetic loader fixture already has one.

Focused checks: baseline equality; existing Python explorer tests; `npm test`.
Use the normalized fixture as the independent expected result, not just a
packer/decoder round trip that could share the same bug.

## Phase 1: share rankings and observation metadata

Completed on 2026-10-06. The candidate shares complete ranking alternatives
through exact, ordered, type-preserving claim-reference tags and interns every
remaining observation field. Discovery records keep their existing sharing;
coverage remains dense. Literal fallback preserves subsets, reordered lists,
type differences, and cases without a unique matching witness pair. Both
decoders reject invalid table indices/tags, dangling claim references, and
ambiguous pair recovery. Expanded candidate observations and their nested
values are independently mutable and do not alias the packed input. Complete
date alternatives, ranks, years, extra fields, nulls, missing fields, and the
independent `ranking_state` field survive exactly.

The current collection produces 28 ranking templates and 37 observation
contexts, discovered from the input rather than hard-coded. Compact candidate
JSON occupies **6,391,574 bytes**, including its final newline, versus the
unchanged **12,476,223-byte** production version 2 file: a **48.77%** reduction.
Two candidate packings produced identical bytes. Candidate expansion in Python
and Node matched the complete fresh `build_data()` result and the Phase 0
normalized baseline exactly. An offline Node check compared all 7,957 chart
coordinates in both scenarios, including full observations, events, count-band
segments, discovery, and scale bounds. Work-session candidate/results files are
in ignored `data/.cache/size-optimization-phase1-2026-10-06/`; they are not build
inputs or additional production datasets.

Verification: all 16 focused Python explorer tests and 23 `npm test` tests
passed. Shared fictional fixtures cover exact cross-language expansion,
literal fallbacks, alternative selection, fetch/file loading, malformed data,
extra fields, type distinctions, and mutation isolation. The production writer,
collection inputs, and current data file were unchanged. No compression or
runtime-memory measurement was performed in Phase 1. Phase 2 implementation
is recorded below.

The completed scope was:

1. For each normalized observation, copy its `dating_alternatives`. Preserve
   state, combination counts, limits, assessment lists, both scenario orders,
   event years, ranks, and every complete combination. Do not recalculate ranks
   in the packer or browser, or enumerate combinations across the whole corpus.
2. Within each event, replace `coverage_claim_ids` with a tagged encoding:
   `["pair"]` when its exact list can be recovered from the unique coverage pair
   for that event's witness, or `["literal", originalIds]` otherwise. Recovery
   uses that pair's claim order, selecting claims whose stored assertion is
   `present`, and returning their original numeric `claim_id` values.
3. Require exact ordered, type-preserving equality before choosing `"pair"`.
   This is deduplication of already stored claim references, not a new content
   judgment. Valid subsets, different orders, and other nonmatching lists use
   `"literal"`. A decoder must reject dangling claim references or ambiguous
   pair lookups; it must not silently return an empty list.
4. Intern the resulting alternative objects into `ranking_templates`. The
   current collection should share many templates once verse-specific IDs are
   removed. No assumption about the number of alternatives is allowed.
5. Intern each observation's remaining fields, including its ranking-template
   index and discovery-record index, into `observation_contexts`. Initially use
   dense coverage indices. Preserve nulls and the independent `ranking_state`
   field instead of assuming it is always an alias of another field.
6. Implement the same decoding rules in Python and JavaScript. Fully expanded
   observations must not acquire shared mutable nested objects.

Focused checks: compare the whole normalized fixture in both languages; verify
shared templates restore different claim IDs for the two verses; exercise the
literal event fallback and alternative selection. Reject missing tables,
negative/out-of-range/noninteger indices, booleans, and unknown tags. Mutating
one expanded observation must not change another or the packed input.

## Phase 2: compact claims and coverage records

Completed on 2026-10-06. The private `"3-phase2"` candidate shares complete
coverage contexts and stores coverage records as context indices plus ordered
claim-ID strings. Every other coverage field survives, including all date
assessments, witness identity, states, unknown reasons, and supported extra
fields. Contexts and complete records are interned in deterministic first-encounter
order with type-sensitive JSON keys; observations retain dense coverage vectors.

Eligible index claims use `ntvmr_index_v1`; the decoder mechanically restores
their duplicated fields and canonical locator text. Other claims keep their
complete details through `literal`, including publication assertions, additional
fields, missing/null values, type differences, and alternate locator spellings.
Claim and locator integers must be safe for JavaScript. Document/page IDs are
also conservatively kept literal unless they are safe integers; no ID is coerced.
Both decoders reject bad tuple lengths/tags, invalid indices, unsafe compact
IDs, context/detail collisions, and dangling coverage claim references.
Expanded coverage and claim values remain independently mutable.

The current collection yields 51 coverage contexts and 16,674 complete coverage
records. All 17,135 current claims meet compact eligibility; fictional regression
fixtures also exercise publication-style literal claims. The 28 ranking templates
and 37 observation contexts are unchanged. Candidate JSON occupies
**2,179,689 bytes**, including its final newline, versus **6,391,574 bytes** for
Phase 1 and the unchanged **12,476,223-byte** production version 2 file:
**65.90%** incremental reduction and **82.53%** reduction from production.
These are measurements of this input, not hard-coded table counts or size caps.

Two candidate packings produced identical bytes. Python and Node expansion
matched the complete fresh offline `build_data()` result and Phase 0 normalized
baseline exactly. Both chart scenarios matched across all 7,957 coordinates,
including complete observations, events, discovery, count-band segments, and
scale bounds. Work-session candidate, normalized result, and measurements stay
in ignored `data/.cache/size-optimization-phase2-2026-10-06/`.

Verification: all 22 focused Python explorer tests and 26 `npm test` tests passed.
The independent fictional oracle checks both codecs and fetch/file loading,
complete alternatives, coverage states, fallbacks, malformed input, Unicode,
type distinctions, and mutation isolation. The production writer, current data
file, collection inputs, and source captures were unchanged. No compression or
runtime-memory measurement was performed. Phase 3 implementation is recorded
below.

The completed scope was:

1. Split each coverage record into a context containing every field except
   `claims`, plus its ordered claim-ID list. Intern contexts and then complete
   coverage records. Preserve `state`, `unknown_reason`, witness identity, and
   the entire date-assessment list; do not replace a witness's alternatives with
   a single chosen date.
2. Use `ntvmr_index_v1` only when all of these conditions hold exactly:
   - Claim details have precisely `claim_id`, `source_ref`, `page_id`, `reported`,
     and `source_locator` after existing context extraction.
   - `reported` has precisely `docID`, `indexContent`, `osisID`, and `pageID`.
   - The numeric claim ID equals the canonical integer spelling of its map key;
     `source_ref` equals `reported.osisID`; `page_id` equals `reported.pageID`;
     and `reported.docID` equals the context's `doc_id`, including value types.
   - The locator is exactly `data.indexContents.indexContent[N]`, where `N` is
     a nonnegative integer in canonical decimal spelling. Leading zeros or an
     alternate locator spelling must use the literal path.
   - Integers reconstructed by JavaScript are safe integers. Never coerce
     strings, booleans, nulls, or unsafe numeric IDs into the compact shape.
3. Store the four varying values shown in the schema. Reconstruct duplicated
   fields and the locator text mechanically. Keep `indexContent` exactly as
   reported; do not infer it from the coordinate or decode it into new claims.
4. Encode every other valid claim as `literal`, retaining its complete details
   object. This includes publication statements, non-NTVMR sources, extra
   reported fields, and new source shapes. Continue rejecting context/detail
   collisions instead of overwriting one provenance value with another.
5. Preserve claim-context provenance and indexing qualifications verbatim.
   Do not introduce special omission rules for nulls or common strings here;
   existing contexts already share them.

Focused checks: one compact NTVMR fixture and one publication-style literal
fixture decode identically in Python and Node. Alter each compact-eligibility
condition and verify lossless fallback. Include non-ASCII text, quotes, nulls,
missing fields, extra fields, and string-versus-number distinctions. Assert that
claims, dates, and unknown reasons survive multiple claims per witness. Test
bad tuple lengths, unknown tags, conflicting fields, and dangling references.

## Phase 3: sparse coverage with exact defaults

Completed on 2026-10-06. The private `"3-phase3"` candidate groups nonempty
coverage vectors by their complete ordered witness identities, with JSON value
types preserved. Missing or duplicate identities retain dense mode. Each default
position uses the most frequent exact coverage-record index; ties use the lowest
index, which follows record first encounter. Defaults can contain present,
absent, contested, or unknown records, including unknown records with claims.
No new observation or scholarly assertion is created.

Each row uses ordered exceptions only when its sparse encoding is smaller than
its dense encoding. A group shares a default only when the total savings pay for
the serialized default vector, table separator, and initial field/table overhead.
Empty lists and expensive exception lists stay dense. Both decoders validate all
default vectors, including unused ones, and reject invalid default/record indices,
malformed tuple lengths/tags, duplicate or unordered positions, and out-of-range
positions. Expanded coverage, claim references, and rankings remain independently
mutable without altering shared defaults or the packed input.

The current collection yields one default vector, **7,928 sparse observations**,
and **13 dense observations**. The 51 coverage contexts, 16,674 coverage records,
28 ranking templates, and 37 observation contexts remain unchanged. Candidate
JSON occupies **2,007,752 bytes**, including its final newline, versus
**2,179,689 bytes** for Phase 2 and the unchanged **12,476,223-byte** production
version 2 file: **171,937 bytes / 7.89%** incremental reduction and **83.91%**
reduction from production. The candidate remains slightly above the Phase 4
2 MB aim; these measured sizes do not impose a collection-growth cap.

Two candidate packings produced identical bytes. Python and Node expansion
matched the complete fresh offline `build_data()` result and Phase 0 normalized
baseline exactly. Both chart scenarios matched across all 7,957 coordinates,
including full observations, events, discovery, count-band segments, and scale
bounds. The unchanged version 2 writer also reproduced the production file's
exact bytes. Work-session candidate, fresh normalized result, and measurements
stay in ignored `data/.cache/size-optimization-phase3-2026-10-06/`.

Verification: all 28 focused Python explorer tests and 29 `npm test` tests passed.
The independent fictional oracle and its synthetic sparse extension cover
dense/sparse equivalence, different witness orders and subsets, empty coverage,
defaults containing present records, unknown claims and both unknown reasons,
date applicability, omitted observations, deterministic ties, typed identities,
group costs, malformed data, mutation isolation, fetch/file loading, and
alternative selection. The production writer, current data file, collection
inputs, and source captures were unchanged. No compression or runtime-memory
measurement was performed in Phase 3. Phase 4's production rollout is recorded
below; phases 5–6 remain planned.

The completed scope was:

1. Retain dense mode for every observation. For compatible coverage vectors,
   build an explicit ordered default vector of coverage-record indices. Group
   observations by the same ordered witness sequence before sharing a default.
   Select the most frequent exact index at each position, with a deterministic
   tie-break. A default is a storage value, not a scholarly assertion inferred
   for other verses. It can be present as well as unknown.
2. Encode differing positions as ordered `[position, recordIndex]` exceptions.
   Only reference a default when applying those exceptions reproduces the
   original array exactly. Preserve date applicability and both unknown reasons
   through their actual records. Unknown claims must not be discarded.
3. Compare serialized group costs, including the default-table overhead; keep
   dense mode where sparse mode does not save space. Use dense mode for empty
   coverage and incompatible witness sequences. Do not assume every observation
   covers all documents or that there is exactly one global witness sequence.
4. Decode only the observation keys stored in the file. Sparse storage must not
   create observations for omitted or uncollected coordinates. Reject duplicate
   override positions, invalid positions, wrong tuple lengths, and dangling
   default or coverage references.

Focused checks: dense and sparse forms restore the same ordered arrays; ordinary
unknown and unresolved-mapping unknown stay different; an absent observation
stays absent. Include a different witness order, an empty coverage list, a
default containing a present record, and an unknown pair containing a claim.
Rerun exact full-collection restoration and measure the incremental saving.

## Phase 4: switch the builder and verify the complete pipeline

Completed on 2026-10-06. `pack_explorer_data()` now writes numeric version 3 using
the complete Phase 3 schema. `refresh()` and the collector's fixture-based offline
write path use that same packer. Python and JavaScript retain version 1/2 decoder
paths and the private candidates. Small numeric version 3 fixtures cover the
independent fictional oracle, empty export, and synthetic sparse extension.
Atomic compact output and disposable normalization databases are unchanged.

The rebuilt production JSON is **2,007,743 bytes**, including its final newline,
versus the **12,476,223-byte** version 2 baseline: **10,468,480 bytes / 83.91%**
saved. It retains 51 coverage contexts, 16,674 coverage records, 28 ranking
templates, 37 observation contexts, one coverage default, 7,928 sparse observations,
and 13 dense observations. It is 7,743 bytes above the 2 MB aim; the complete
documented schema and exact fidelity are preserved without a production size cap.

Two fresh offline builds produced identical bytes. Python expansion matched the
complete fresh `build_data()` output and Phase 0 normalized baseline with JSON
types and array order checked. Node decoded Python's production output against
the independently serialized fresh normalized result, and also restored the
retained version 2 baseline exactly. Both chart scenarios matched across all
7,957 coordinates, including complete cells/observations, events, count-band
segments, discovery, and scale bounds. Full-size comparison files and measurements
stay in ignored `data/.cache/size-optimization-phase4-2026-10-06/`.

Verification includes all 30 focused Python explorer tests, 8 offline discovery
tests, and 32 `npm test` tests. Rollout tests cover fetch/file loading of versions
1/2/3, malformed version 3 failure and retry, exact restoration, mutation isolation,
deterministic refresh, current/stale `--check` without writes, failed validation
preserving the previous file, failed atomic replacement cleanup, and app assets
surviving refresh. All 134 Python tests and both build `--check` commands passed;
the complete offline checks are recorded at handoff below.
Collection registers, source captures, and reference inputs are unchanged.
No compression or runtime-memory measurement was performed in Phase 4. That
authorization stopped at Phase 4; Phase 5's later implementation is recorded below.

The completed scope was:

1. Switch `pack_explorer_data()` to the complete version 3 writer. Keep both
   older decoder paths and their small fixtures. Ensure `refresh()` and the
   offline collector write path use the same writer. Keep `write_json()` atomic
   and compact, and preserve the disposable build database behavior.
2. Rebuild `data/attestations.json` from the current central inputs. Compare its
   expansion with `build_data()` and, if inputs did not change during the work,
   with the phase 0 normalized baseline. Verify every field, not just counts.
3. In an offline integration check, pass Python's packed result through the
   JavaScript decoder and compare with independently serialized normalized
   Python data. Temporary files for the full collection stay in `data/.cache/`
   or the test runner's temporary directory.
4. Update format-version assertions and tests of storage-specific structure.
   Keep all existing assertions about claims, mappings, counts, source fidelity,
   rank order, complete dates, and app assets surviving a data refresh.
5. Update the README, explorer documentation, and development plan to describe
   the implemented layout and measured size. Do not present the runtime-memory
   phase as complete merely because transfer compression has shipped.

Focused checks: two builds produce identical bytes; `--check` accepts current
output and rejects stale output without modifying it; failed validation leaves
the previous data file intact. Use fixture-based collector tests, not a live
discovery run. Test fetch and file-picker loading of versions 1, 2, and 3, plus
malformed-data failure and retry.

For this 17-witness input, aim for less than 2 MB, allowing overhead for tags and
fallbacks absent from the prototype. Record actual bytes and reduction from the
version 2 baseline. Do not hard-code a production-file byte cap that will fail
merely because legitimate collection grows; use a stable synthetic fixture for
any permanent size-regression assertion. Never trade data fidelity for the cap.

## Phase 5: retain shared data in the running app

Completed on 2026-10-06. `createDataStore()` validates the full reference graph,
including unused contexts, templates, defaults, coverage records, and claim/date
references, directly in the packed tables. Fetch and file selection return this
store. The parsed input and shared records are deeply frozen; date selection
remains separate. Version 1/2 and all retained candidate adapters are supported.
`expandData()` remains an exact, independently mutable compatibility view,
including when its input has already been frozen by a store.

`summary()` counts coverage states from shared records without constructing pairs.
Chart alternatives share precomputed event fields and omit claim lists; the scale
visits each referenced template once (28 in this collection). Cells and drawing
runs contain coordinate references and drawing state, with no full observations.
Selection and source details call `observation()` and claim/date accessors. The
observation cache retains at most one verse; claim caching is by unique ID.
Loading and mounting reuse the same validated model.

Both chart scenarios match the pre-refactor compatibility model across **7,957
coordinates**, including states, contested flags, event order, rank, year,
assessment selection, count-band segments, discovery, and scale bounds. All
**7,941 observations**, **17,135 claims**, and **17 date records** match the
independent normalized baseline exactly. Full expansion also matches it. Python
passes fresh packing and literal/type/Unicode fallbacks to both the JavaScript
expander and store, checked against independent fictional values. Offline DOM
tests exercise the actual selection/source renderer across versions 1/2/3,
including safe text, alternatives, unknowns, filters, and missing observations.

Structural checks confirm full-axis chart evaluation invokes neither the
observation nor coverage decoder, does not retain observations in cells, and
shares read-only events. Repeated selection keeps the cache bounded at one verse.
Existing independently mutable expansion guarantees remain tested for all
published versions. Malformed loading, file fallback, retry, and unchanged URL
behavior remain covered.

Node v22.14.0 retained heap measurements used five fresh isolated processes per
path, identical current version 3 input, the same fictional warm-up, and three
explicit GC calls before each sample with `--expose-gc`. Values below are medians
above each warmed empty-process baseline, in bytes (decimal MB in parentheses).
The compatibility path uses the current `expandData()` and normalized model
adapter on the same revision. Raw JSON source strings, temporary observations,
packed inputs after construction, and comparison models were dropped before
sampling. These are retained heap measurements, not peak or browser memory.

| Stage | Compatibility full expansion | Shared runtime |
| --- | ---: | ---: |
| Parsed version 3 JSON | 12,125,928 (12.13 MB) | 12,125,928 (12.13 MB) |
| Model constructed | 68,406,104 (68.41 MB) | 17,812,904 (17.81 MB) |
| Both chart scenarios evaluated | 66,979,440 (66.98 MB) | 16,393,160 (16.39 MB) |
| Repeated selection | 66,987,256 (66.99 MB) | 16,716,720 (16.72 MB) |

Chart evaluation retains the current scenario's 7,957 cells and 206 drawing runs.
Selection visits 2,000 dispersed coordinates, accesses the immediate five witness
cards, and accesses full source details every twentieth visit. The shared store
ends with one cached observation and 653 unique cached claims. Its retained heap
is **75.04% lower** after repeated selection; full-axis drawing decoded no coverage
pairs. GC/JIT activity can reduce later samples; these are stage snapshots, not
monotonic or peak measurements. No machine-specific memory limit is a unit test.
Scratch scripts, per-run measurements, and full-collection comparison results
stay in ignored `data/.cache/size-optimization-phase5-2026-10-06/`.

The production JSON remains **2,007,743 bytes**, down **83.91%** from the
12,476,223-byte version 2 baseline. The writer, source registers, captures, and
reference inputs are unchanged. No new compressed-size measurement or transport
configuration work was performed during Phase 5. Phase 6's subsequent offline
work is recorded below; browser memory remains unmeasured.

The completed scope was:

1. Add an internal `createDataStore(rawData)` abstraction in `explorer.js` that
   accepts all supported versions. Validate the complete reference graph before
   mounting, including unused records, without materializing normalized copies.
   Preserve the explicit `expandData()` API and its independent-copy behavior
   for compatibility, tests, and consumers requesting a full expansion.
2. Expose small read accessors: `hasObservation(ref)`, `summary(ref)`,
   `chartAlternatives(ref)`, `claim(id)`, `date(id)`, and `observation(ref)`.
   Metadata, documents, sources, and coordinates may remain ordinary data.
   `chartAlternatives()` exposes the existing precomputed years, ranks,
   witnesses, and assessment selections through shared records. It does not
   reconstruct per-event claim lists merely to draw the chart.
3. Make shared runtime records read-only and keep selection state in its own
   maps. `observation(ref)` resolves a complete normalized observation only when
   needed for selection or source details. Bound any observation cache, for
   example to the selected verse; never retain every visited expanded verse.
   Claim caching may be keyed by unique claim ID rather than by occurrence.
4. Refactor model initialization, scale calculation, discovery access, and first
   selected-coordinate lookup to use the store. Inspect each unique ranking
   template once for scale bounds. Compute contested flags or coverage totals
   from shared indices without allocating all witness/verse objects. Older
   normalized inputs can use an adapter; do not route version 3 through a full
   expansion to support them.
5. Refactor `cell()`, `cachedCells`, and `runs` to hold only drawing state, shared
   chart events, and coordinate references. Remove full observations from the
   corpus-wide cache. Have `renderSelection()` and `renderClaims()` request the
   selected observation; have claim and date rendering use store accessors.
   If `cell().observation` or `model.data` changes, update all callers and tests
   explicitly instead of hiding eager expansion behind a property getter.
6. Change fetch and file-picker loading in `app.js` to validate and return a
   store. Update `show()`/`mount()` to reuse the validated model rather than build
   it twice. Keep the same URL, reload behavior, failure/retry handling, and
   safe text rendering. Decouple `loadData()` tests from an incidental normalized
   return shape; retain separate exact expansion tests.

Focused checks: compare every coordinate's state, contested flag, event order,
rank, year, and assessment selection with the compatibility model for both
scenarios. Compare `segments()` results to verify the chart's count bands.
Compare selected full observations and displayed source fields exactly, and
exercise alternative selection, discovery, filters, empty data, and overflow.
Retain mutation-isolation tests for full expansion; add read-only-sharing tests
for the new store instead of weakening those earlier guarantees.

Add one small structural allocation check: a full-axis chart evaluation must not
invoke the full-observation decoder or create a witness object for every unknown
pair. Moving selection repeatedly must not grow an unbounded observation cache.
Use fixtures and test instrumentation rather than brittle wall-clock limits.

Measure memory in isolated offline Node processes using `--expose-gc`, identical
input, and the same warm-up/GC procedure. Report retained heap above baseline
after parse, model construction, chart evaluation, and repeated selection. Drop
unused source strings and comparison models before measuring. Compare medians
of a few runs against the compatibility path on the same revision. Aim to
eliminate the expanded coverage matrix and show a meaningful reduction; do not
turn machine-specific megabyte or timing values into unit-test requirements.
Label results as Node measurements; browser memory remains unmeasured unless
separately inspected through an explicitly requested browser run.

## Phase 6: transport compression where deployment supports it

Offline audit and hosting handoff completed on 2026-10-06. Deployment activation
remains explicitly pending. The repository contains no app deployment, host/proxy,
or CI configuration to edit or validate. Its only server command is `npm start`,
which runs `python -m http.server 8000 --bind 127.0.0.1`. No deployment was available
for response-header verification.

The exact current JSON bytes, including the final newline, were compressed in
memory with Python 3.12.6 and zlib 1.3.1 using `gzip.compress(..., mtime=0)`.
For each level, decompression restored the original bytes exactly and a second
compression produced identical bytes. The canonical input's SHA-256 was
`a3136b21900a97197338f0732812c654c995559354925b06dd3e6b9b7937b88f`.

| Representation | Bytes | Reduction from canonical JSON |
| --- | ---: | ---: |
| Canonical version 3 JSON | 2,007,743 | — |
| Gzip level 6 | 318,653 | 84.13% |
| Gzip level 9 | 305,645 | 84.78% |

These are offline sizes, not deployed transfer measurements. Brotli was not
measured. Measurements and hashes remain in ignored
`data/.cache/size-optimization-phase6-2026-10-06/compression-measurements.json`;
the cache is not a build input. No compressed product file was created.

The hosting requirement is to enable the chosen host or proxy's supported gzip
or Brotli compression for JSON at the existing data URL
(`../../data/attestations.json` relative to the app directory).
When negotiating encodings, return `Vary: Accept-Encoding` alongside any existing
`Vary` fields. An actual gzip response must include:

```http
Content-Type: application/json
Content-Encoding: gzip
Vary: Accept-Encoding
```

Use `Content-Encoding: br` for an actual Brotli response. Serve ordinary JSON
without `Content-Encoding` to clients receiving an uncompressed representation.
Setting headers alone does not compress the body. The host must serve the same
logical JSON for each representation and preserve the app/data relative paths.
Activation is complete only after host configuration and authorized deployment
checks verify those headers and exact decompressed bytes.

Keep `attestations.json` as the canonical JSON artifact and preserve direct local
file loading. HTTP compression is a separate delivery optimization; it does not
replace the storage or memory changes above.

1. Inspect existing deployment configuration, if any. Enable gzip or Brotli for
   JSON at that existing host or proxy using its supported configuration. Serve
   the same logical URL with the correct `Content-Encoding`, JSON content type,
   and `Vary: Accept-Encoding` when negotiating representations.
2. Leave `response.json()` and the JSON file picker free of custom decompression
   dependencies. Do not replace `attestations.json` with gzip bytes, commit a
   second `.gz` product input, introduce a backend solely for compression, or
   change `npm start` just to obtain compressed local transfer.
3. If there is no deployment configuration to edit, document the hosting
   requirement and leave activation explicitly pending. The current `npm start`
   uses Python's simple static server. An offline gzip size is a measurement,
   not evidence that a deployment is serving compressed responses.

Focused checks: in memory or ignored scratch storage, compress and decompress
the exact JSON bytes and assert byte equality; record compressed size and level.
Use any existing offline configuration validation. Do not launch a server or
probe localhost for this phase. Live response-header checks require an available,
authorized deployment verification context.

To repeat the offline measurement from the repository root without creating a
compressed file:

```powershell
@'
import gzip
from pathlib import Path

raw = Path("data/attestations.json").read_bytes()
print(f"JSON: {len(raw):,} bytes")
for level in (6, 9):
    encoded = gzip.compress(raw, compresslevel=level, mtime=0)
    assert gzip.decompress(encoded) == raw
    assert encoded == gzip.compress(raw, compresslevel=level, mtime=0)
    print(f"gzip level {level}: {len(encoded):,} bytes; exact round trip")
'@ | python -
```

## Completion and handoff

Phase 6 offline handoff on 2026-10-06: the deployment audit found no configuration
to edit. Gzip levels 6 and 9 restored the exact canonical bytes and were
deterministic, with sizes of **318,653** and **305,645 bytes** respectively.
Both build `--check` commands, all **37 Node tests**, and `git diff --check`
passed; the canonical JSON remains **2,007,743 bytes**, and collection inputs and
app code are unchanged. The hosting contract
above is the remaining deployment task: enable compression and verify live
headers and decoded bytes when a deployment is available. No server, localhost
probe, or live request was used. Earlier exact normalized/cross-language,
chart-equivalence, and Node memory results remain recorded below; this phase
does not introduce new codec or browser-memory measurements.

Phase 5 handoff on 2026-10-06: `python build_collection.py --check`,
`python build_na28_inventory.py --check`, all **134 Python tests**, all **37 Node
tests**, and `git diff --check` passed. The final added coverage-total,
deep-freeze, and unused-template scale checks also passed in a focused Node run.
Exact full-collection expansion, selected observations and source fields, and
both chart scenarios passed as recorded above. Runtime data now stays shared;
the production file remains 2,007,743 bytes. The measured Node memory reduction
is 75.04% after repeated selection; browser memory remains unmeasured. Phase 6
is pending and was not started. Verification used retained local inputs and
fictional fixtures, with no server, localhost probe, or live source requests.

Earlier Phase 4 handoff on 2026-10-06: `python build_collection.py --check`,
`python build_na28_inventory.py --check`, all **134 Python tests**, all **32 Node
tests**, and `git diff --check` passed. Exact full-collection Python/Node decoding
and both chart scenarios also passed as described above. Current data uses numeric
version 3; phases 5–6 were pending at that handoff. Compression and runtime-memory
measurements were outside that rollout. Verification used retained local inputs and fictional
fixtures, without starting a server or making live source requests.

Run focused tests after each phase. At the writer rollout and after the runtime
refactor, run the complete offline checks once the relevant focused checks pass:

```powershell
python build_collection.py --check
python build_na28_inventory.py --check
python -m unittest discover -s tests -v
npm test
```

For codec-only iterations, use the narrower Python command:

```powershell
python -m unittest discover -s tests -p test_report_explorer.py -v
```

Do not rerun collection or start the app as a final sanity check. Review the diff
to ensure only intended code, fixtures, documentation, and the current derived
JSON changed. Source captures and registers should be unchanged by this work.

Report which phases shipped, exact normalized/cross-language equivalence results,
old and new JSON bytes, compressed bytes, runtime measurements and their method,
and any deployment-only work still pending. Update this guide's status and the
central development plan so future agents can distinguish implemented behavior
from remaining work. No phase requires independent manuscript scholarship.
