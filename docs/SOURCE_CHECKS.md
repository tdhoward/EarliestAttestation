# Scoped source checks

The version-1 register in `data/source_checks.json` records what has been compared,
the exact scope, and what still needs work. It is not a manuscript coverage store.
`data/collection.json` selects it through `source_checks`. The normal offline build
validates the register and its retained evidence. Full checks stay outside browser
data; the affected index claims project their scoped admission reasons and evidence
links, alongside active scholarly content reports.

Under the [current plan](SOURCE_CORROBORATION_PLAN.md), use this register for the
small internal-omission sample, the existing John cases, and claims affecting the
first five collected witnesses per verse across both date modes and retained date
alternatives. Include replacements entering those five after corrections. Do not
populate a queue for every captured manuscript or review a selected manuscript's
unrelated verses. The CLI reads compact ranking tables to select and deduplicate
targets without decoding coverage vectors or rebuilding the collection.

Inspect or verify it without requests or a full collection rebuild:

```powershell
python source_checks.py --details
python source_checks.py --pending
python source_checks.py --check
python source_checks.py --first-five
python source_checks.py --queue-first-five
```

`--pending` lists queued checks, checks needing recheck, and open or deferred
follow-up. This durable queue is maintained in the register; the command does not
rewrite earlier results. `--check` fails on invalid evidence or stale completed
checks. A normal collection build validates evidence but allows stale checks, so
unrelated collection can continue. No temporary SQLite IDs enter the register.

`--first-five` is read-only and reports exact witness/verse scopes, complete retained
date reports, and unavailable ranking scopes. `--queue-first-five` appends only
selected content scopes and whole-document date checks not already represented
by a recorded check. It refreshes only empty, unreviewed first-five queue entries,
so targets leaving the five are removed from pending selection and replacements
are added. Completed outcomes and pinned evidence remain unchanged. Repeating
selection does not duplicate work. Queue selection is not a completed comparison;
unavailable ranking scopes are retained in `selection_limitations`.

## Version 1 schema

The root object has `format_version: 1` and a `checks` list. Each record has:

| Field | Contract |
| --- | --- |
| `check_id` | Distinct stable ID identifying this comparison, not a manuscript-wide validation flag. |
| `witness_id`, `doc_ids` | The canonical collection witness and distinct registered document IDs. Aliases must already have a cited collection identity report. |
| `kind` | `content` or `date`; checking one does not check the other. |
| `scope` | Content: `{"verses": ["John.7.53", "John.8.1", ...]}` with every coordinate listed explicitly. Date: `{"applicability": "catalogue_document"}`. Portion-specific dates are not supported. |
| `method` | `{"id": "scoped-source-comparison", "version": 1, "source_contract": "ntvmr-source-reports-v1"}`. Changed method/version/contract requires recheck. |
| `checked_on` | ISO calendar date for a completed comparison; null for queued work. |
| `outcome` | `not_yet_checked`, `agreement`, `disagreement`, or `insufficient_detail`. |
| `explanation` | What the result establishes and what remains unresolved. |
| `evidence` | Pinned source references described below. Completed comparisons require evidence. |
| `follow_up` | `state` (`open`, `deferred`, `resolved`), a nonempty `reason`, and supporting `evidence`. Resolution requires a capture/hash, locator, and exact retained correction or clarification statement. Earlier captures and outcomes remain. |
| `access_attempts` | Optional separate list of source URL, timezone-bearing `attempted_at`, access `state` (`success`, `failed`, `blocked`), and failure reason where applicable. An access failure is not an evidence outcome. |
| `superseded_by` | Optional completed recheck ID with the same canonical witness, document IDs, kind, and exact scope. Archived evidence remains validated; missing links and cycles fail validation. |
| `index_observations` | Optional exact expanded entries and metadata page fields retained for omission controls, separate from published assertions and validated against pinned captures. |

An evidence reference records `role` (`ntvmr`, `comparison`, `context`), `stage`
(`metadata`, `coverage`, `scholarly`, `contract`), a relative `capture_file`, its
`body_sha256`, an extraction `source_locator`, `interpretation`, and `claim_ids`.
NTVMR evidence also names `doc_id`. Contents evidence must pin its metadata
capture because indexing tiers and metadata hashes qualify its extraction.
Coverage evidence pins `index_limitations` when scoped index admission has changed.
A missing pin means the original unrestricted extraction, so earlier checks remain
verifiable. Admission changes require recheck.
Scholarly evidence names the stable `report_id` and the report's `admission` state.
Capture paths must remain in the central data directory.

`interpretation` is one of:

- `explicit`: usable content or date assertions in the declared scope.
- `ambiguous_index`: index entries whose meaning in this comparison remains unresolved.
- `missing_entries`: an observation that the retained report supplies no scoped
  claims; this never asserts absence.
- `context`: identity, field documentation, or background without comparison assertions.

Stable claim IDs have the form `content:<sha256>` or `date:<sha256>`. The digest
uses the complete normalized extraction and provenance, excluding temporary row
IDs and snapshot ordinals. The validator reconstructs claims from pinned captures
and verifies the witness, scope, source identity, and all scoped claims in each
comparison capture. Selecting only the convenient claims from a snapshot is rejected.
Repeated identical claims do not turn a scoped check into broader validation.

The comparison method uses explicit assertions only. Any reported portion agrees
with presence; explicit opposing presence/absence reports disagree. Missing or
ambiguous evidence cannot establish agreement or an opposing assertion. A content
agreement needs comparable assertions for every listed verse. A conflict within a
partially comparable scope is still a disagreement, not an agreement on the rest.
Date comparisons use complete numeric intervals and applicability, retaining all
alternatives, notation, and qualifications. Different overlapping intervals disagree
as date estimates; the method does not rank scholars or establish consensus.

## Current versus archived evidence

Each check reconstructs its original extraction from the pinned files. Replacing
the collection's selected metadata/contents snapshot, changing a publication or
its extracted claims, changing admission, or changing the method/contract yields
`needs_recheck`. Old captures must remain available. A corrupt or dangling archived
link is an error; a legitimate new source selection is a recheck condition.
An additional report with claims in the exact checked scope also requires recheck;
adding a report for unrelated verses does not reopen the comparison.

The CLI returns `current`, `needs_recheck`, `not_yet_checked`, or `superseded` per record. Its
summary separates all `recorded_outcomes` from `current_outcomes`, preventing stale
agreement from appearing as current checking progress. Neither summary measures
whole-manuscript validation or discovery completeness. Follow-up remains separate.
An earlier check becomes `superseded` only when its completed successor chain
ends in a current check. Its evidence is still validated, but it does not enter
the pending queue or current outcome counts. A stale successor reopens recheck work.

## Additional scholarly reports

`additional_reports` accepts existing inline reports or references of this form:

```json
{"capture_file": "sources/example-publication.json", "admission": "pending_contract_review"}
```

Referenced files retain the report's provider/author, title, citation, canonical
URL, timezone-bearing retrieval timestamp, exact retained material and hash,
locators, qualifications, known upstream dependencies, and extracted coverage/date
claims. Reference entries cannot override captured evidence. Admission defaults
to `active` for compatibility. `pending_contract_review` retains and validates
extractions without adding them to ordinary coverage, dates, or rankings. This
explicit staging state allows review before changing index semantics. Checking
records themselves never supply coverage overrides.
An extracted claim can supply its exact `statement` or a `statement_span` pair
of character offsets `[start, end)` into the retained `raw_body`. Spans keep the
same short scholarly excerpt from being duplicated in every verse claim; the
normalizer resolves and retains the exact statement. Invalid spans and simultaneous
text overrides are rejected. This interface is for published prose assertions,
never manuscript transcription or word-survival analysis.

The retained John comparisons, acquisition limits, omission controls, and current
first-five outcomes are documented in the
[source corroboration plan](SOURCE_CORROBORATION_PLAN.md). That document owns the
findings and stopping point; this guide owns commands and the evidence schema.
Exact checks, source locators, qualifications, and supersession links remain in
`data/source_checks.json` and the cited captures.

`--pending` includes deferred independent follow-up even after all selected scopes
have outcomes. Deferred follow-up is distinct from unreviewed or stale work and
does not authorize broader collection.
