# Development plan

## Product and working structure

Maintain one central collection in `data/` and one app in
`web/attestation-explorer/`. Data collection updates the existing registers and
`data/attestations.json`; the HTML/JS/CSS remain independent of the dataset.
Do not create book-specific charts, numbered dataset revisions, milestone reports,
or permanent replay databases. Use ignored `data/.cache/` for temporary work.
Source attribution belongs with the data; software history belongs in Git.

The project collects explicit scholarly reports of Greek NT manuscript contents
and dates. It does not perform manuscript scholarship. Follow [AGENTS.md](../AGENTS.md)
and the [source contract](NTVMR_SOURCE_REPORT_CONTRACT.md). Unknown, contested,
reported-absent, uncollected, and filtered states must stay distinct. Preserve
complete date alternatives and count any reported portion once per witness.

## Current implementation

The central collection and single app are implemented. The current export has
2,584 witnesses, 5,167 registered metadata/contents reports, and 4,479 source
snapshots associated with active evidence. Its 7,941 graphable coordinates have
2,565,038 reported-present witness/verse pairs, 17,954,458 unknown pairs, and
48 reported absences, with no contested pairs. These are export counts, not
independent content validation. The registers and `data/attestations.json` hold
the current machine-readable state.

- **Discovery:** all four retained catalogue inventories and eligible capture/import
  are complete within the declared earliest-date-before-1000 CE scope. This does
  not establish exhaustive corpus discovery. See
  [current source scope](BOUNDED_WITNESS_DISCOVERY.md#current-source-scope).
- **Corroboration:** the bounded omission sample and selected first-five extraction
  review have reached their agreed stopping point. Independent comparisons remain
  deferred where unavailable. See the
  [findings and reopening conditions](SOURCE_CORROBORATION_PLAN.md#next-actions-and-verification);
  [SOURCE_CHECKS.md](SOURCE_CHECKS.md) owns the schema and checking commands.
- **App and build:** both writers produce compact version-5 JSON; the app also
  reads versions 1–4. Builds validate provenance and rankings offline in a fresh,
  disposable database, stream records, enforce a default 2 GiB OS memory limit,
  and replace the app data atomically. See the
  [explorer contract](ATTESTATION_EXPLORER.md) for formats, runtime, verification,
  and measured resource use.

The [repository guide](README.md) maps commands, shared implementation, and data
ownership. Keep detailed behavior and findings in their primary documents rather
than copying them into this plan.

## Next development work

The current [scoped source review](SOURCE_CORROBORATION_PLAN.md#next-actions-and-verification)
has reached its agreed stop condition. There is no remaining unreviewed first-five
queue. Deferred independent comparisons remain visible; they do not require a
broader acquisition campaign. Further work is conditional on changed evidence or
rankings:

1. Recheck affected selected scopes when their source evidence, extraction,
   admission, or method changes, following
   [step 2](SOURCE_CORROBORATION_PLAN.md#step-2-check-only-claims-affecting-the-first-five).
   Both date modes and retained complete date alternatives participate. Check only
   the relevant presence claims and dates; selection for one verse does not
   authorize reviewing a witness's unrelated contents. One usable source is sufficient.
2. After a correction, update affected rankings and rerun compact queue selection
   to include promoted replacements. Empty, unreviewed selection entries are
   refreshed; completed outcomes and their evidence remain. Unavailable rankings
   stay explicit. Stop when selected claims have scoped outcomes; unresolved
   cases may remain deferred and fewer than five usable witnesses is acceptable.
3. Retain the bounded sample conclusion and current John treatment. Additional
   general omission sampling, provider contact, and broader source pilots remain
   deferred. No provider explanation or universal index rule was established.
4. Use focused offline validation during this work. Target selection and scoped
   checks do not need a production rebuild. Rebuild when registered claims or
   output behavior change, under the existing memory ceiling; avoid full-matrix
   expansion and repeated builds just to report progress.

Broader source pilots, new general-purpose collectors, and investigation of
lower-ranked witnesses are deferred. Existing discovery tools, captures, source
checks, and bounded tests remain available; the current snapshot and date cutoff
are unchanged. Any live requests needed for the sample or selected claims must
have a declared finite scope, budget, pacing, and provider access expectations.
Honor blocks and use the documented local proxy when applicable. No expansion of
the 1000 CE earliest-date scope or portion-specific date implementation is needed
for this work.

## Acceptance

- The omission sample has a bounded, cited conclusion; any localized explanation
  stays distinct from a provider-confirmed correction or universal index rule.
- The John cases have consistent evidence, coverage, counts, and rankings.
- Further checks cover only first-five claims and promoted replacements across
  both date modes and retained alternatives, with unresolved outcomes recorded.
- New collection appears in the existing app after refreshing its data file.
- Existing books, witnesses, citations, qualifications, and date alternatives
  survive additions without duplicate witness counts or inferred adjacent coverage.
- Every active claim is attributable to a scholarly source. Explicit disagreement
  is retained and deferred; missing information remains unknown.
- Discovery completeness is scoped independently of coverage and rankability.
- Progress toward all four categories is supported by independently recorded
  book/range searches. Completing a declared scope does not complete unsearched
  categories or establish exhaustive manuscript-corpus discovery.
- Offline source, normalization, data-loading, and chart tests pass. No manuscript
  examination, local server launch, or live request is part of routine verification.
