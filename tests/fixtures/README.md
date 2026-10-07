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
