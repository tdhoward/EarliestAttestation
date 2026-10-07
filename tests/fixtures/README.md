# Explorer compatibility oracle

`explorer-normalized.v1.json` is the independently specified expected data for
the storage optimization work. Every witness, source assertion, date, and
qualification in it is fictional. It contains no manuscript transcription or
examination. Python packs this file and Node compares its expansion directly
with this expected file, rather than only comparing two codec outputs.

The fixture includes:

- Galatians 1:1 and 1:2 with the same observation metadata and complete ranking
  alternatives, but different ordered claim IDs; multiple claims per witness;
  explicit absence, contested reports, and unknowns with and without claims.
- Two complete intervals for `fictional:a`, a tied interval for `fictional:g`,
  and an unrankable date for `fictional:f`.
- Galatians 1:3 with only the first date combination available and an event
  whose claim list is a proper subset of its coverage pair's claim list.
- Galatians 1:4 with combination overflow and independently different
  `ranking_state` and `dating_alternatives.state` values.
- Galatians 1:5 with unresolved mapping and the distinct
  `unresolved_reference_mapping` unknown reason; ordinary missing reports use
  `no_explicit_mapped_report`.
- Galatians 1:6 with a filtered, bracketed observation, and Galatians 1:7 with
  a coordinate but no observation.
- Ordered arrays, numeric event IDs versus string lookup IDs, Unicode, quoted
  source text, nulls, missing fields, extra fields, and boolean/number values.

`explorer-empty.v1.json` is the separate empty-export expected case: its axis
remains navigable, while observations, claims, and dates are empty.

The matching `*.v2.json` files are frozen compatibility snapshots of the current
transfer layout. Keep them when introducing newer writers; do not regenerate
them with a future packer. Both Python and Node test these files against the
version 1 expected data. `app.test.js` uses the same fixture for loading tests,
and `explorer.test.js` uses it for chart and selection assertions.

Full collection baselines are work-session artifacts in ignored `data/.cache/`,
never test fixtures or product inputs.

The `*.phase1.json` files exercise the private `format_version: "3-phase1"`
candidate codec. They share ranking templates and observation contexts, with
dense version 2 coverage records and version 2 claim records. Numeric version 3
is reserved for the complete planned schema; the production writer still emits
version 2. Python checks these snapshots against `pack_explorer_data_phase1()`
and the independent version 1 oracle, and passes fresh packing to Node as well.
Node uses them for exact decoding, fetch/file loading, chart states, alternative
selection, mutation isolation, and malformed-reference tests.

Galatians 1:1 and 1:2 share the same context and template but recover their own
ordered numeric claim IDs through `["pair"]`. Galatians 1:3's subset is retained
as `["literal", [301]]`. Python also supplies reordered, missing/duplicate-pair,
boolean-versus-number, and string-versus-number fallback cases directly to Node.

The `*.phase2.json` snapshots use private `format_version: "3-phase2"` and
retain the same independent version 1 expected data. Claims use tagged compact
index tuples or complete literal details; coverage records share contexts and
retain ordered claim-ID lists. Coverage remains dense. Python verifies fresh
packing against the snapshots and passes it to Node; Node checks exact decoding,
loading, chart states, alternatives, malformed tuples/references, and mutation
isolation. Additional Python cases alter each compact-eligibility condition and
send the resulting literal fallbacks directly to Node, including Unicode, nulls,
extra/missing fields, noncanonical locators/IDs, and safe-integer boundaries.
The production writer and current data remain version 2; numeric version 3 is
still reserved for the complete schema.

The `*.phase3.json` snapshots use private `format_version: "3-phase3"`, adding
ordered coverage defaults and sparse exceptions alongside dense fallback. The
normalized and empty snapshots still expand to the same independent version 1
files. `explorer-sparse.phase3.json` expands to a synthetic extension of that
fictional oracle, constructed without codecs by `sparse_fixture()` in the Python
tests and `sparseFixture()` in `explorer-fixtures.js`. Both constructions repeat
the original values for storage tests; they do not collect or infer reports.
Python checks fresh packing against all snapshots and sends fresh packing and
the independent expected values to Node.

The sparse extension repeats the first observation twelve times in chapter 2,
then eight times with its first two witnesses swapped in chapter 3. Chapter 4
adds empty coverage, duplicate and missing witness identities, a witness subset,
an expensive exception list, and changed date applicability. Original unknown
claims, both unknown reasons, contested/absent states, present defaults, missing
observations, and complete alternatives remain covered. Node checks exact
decoding, chart/selection equivalence, fetch/file loading, malformed defaults and
ordered overrides, and mutation isolation. Python also checks modal ties,
type-sensitive witness grouping, and default-table cost accounting. Production
remains version 2; numeric version 3 rollout belongs to Phase 4.
