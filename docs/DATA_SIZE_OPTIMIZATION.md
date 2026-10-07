# App data size and memory optimization guide

Status: Phases 0 and 1 completed on 2026-10-06; phases 2–6 remain planned.
The correctness oracle and Phase 1 candidate codec are in place. The production
writer and current data remain on version 2; the app has a matching candidate
decoder while its loading and runtime behavior remain unchanged. Work stopped
at Phase 1 at the owner's request. This guide is based on offline work on
2026-10-06. Complete later phases in order when authorized, with the focused
checks below before moving on. Phase 6 depends on the deployment environment.

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

Introduce browser transfer `format_version: 3`. This is independent of the
existing scholarly graph export's version 3. Python and JavaScript expansion
must continue to accept browser versions 1 and 2 and return normalized version 1.
Keep those expansion functions as exact, independently mutable compatibility
views even after the runtime gains an immutable shared store.

Implement a version 3 candidate packer alongside the current writer until phase
4. Define the final schema before switching the writer; do not publish several
incompatible layouts under version 3 during the intermediate phases.

The implemented Phase 1 candidate is `pack_explorer_data_phase1()` and uses the
private string marker `format_version: "3-phase1"`. Python expansion and the
JavaScript decoder accept it for offline checks and fixture loading. Numeric
version 3 stays reserved for the complete schema below. The candidate retains
version 2 claim tuples and coverage objects, adds ranking/observation tables,
and uses only dense coverage encodings. Later phases must retain an explicit
candidate marker until the complete version 3 writer is ready; this intermediate
layout is not the production version 3 contract.

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
runtime-memory measurement was performed. Phase 2 is the next planned step;
phases 2–6 have not been implemented.

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

The current `app.js` expands on fetch and file selection. `createModel()` also
accepts packed input through `expandData()`. `refreshCells()` retains one cell
per coordinate, and each cell currently holds its expanded observation. Merely
adding a lazy decoder while leaving those paths intact will still expand and
retain the whole coverage matrix.

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

## Completion and handoff

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
