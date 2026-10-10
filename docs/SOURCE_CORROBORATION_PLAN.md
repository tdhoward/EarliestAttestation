# Source corroboration plan

Agreed scope: 2026-10-09. First check a few examples of NTVMR representing internal
verse omissions; then limit further investigation to claims affecting the first
five collected witnesses per verse. Broader source pilots, new general-purpose
collectors, and collection-wide corroboration are outside the current work.
Follow [AGENTS.md](../AGENTS.md) and the [development plan](DEVELOPMENT_PLAN.md).

**Current status:** the scoped review is complete; independent comparisons remain
deferred where unavailable. See [next actions and verification](#next-actions-and-verification)
for outcomes and the conditions that reopen affected checks. Steps 1 and 2 below
record the agreed method, not an instruction to restart collection.

## Purpose and present limitation

Determine whether the John 7:53–8:11 indexing issue can reasonably be treated as a
local correction, and focus further checking on the evidence used by the app's
first-five rankings. One usable scholarly report remains sufficient. A problem
with a particular passage does not establish that other NTVMR contents reports
are faulty.

The saved NTVMR index includes all twelve verses of John 7:53–8:11 for P66, P75,
and Vaticanus. Those exact entries now remain as unknown index contributions;
Wallace's explicit omission report supplies coverage. Relevant saved page ranges:

| Witness | NTVMR page ID | Indexed range in captured metadata |
| --- | --- | --- |
| [P66](../data/sources/ntvmr-10066-metadata-591ac6c6de89106b.json) | 480 | John 7:52–53; John 8:1–16 |
| [P75](../data/sources/ntvmr-10075-metadata-f23780f58cf31e65.json) | 840 | John 7:49–53; John 8:1–22 |
| [Vaticanus](../data/sources/ntvmr-20003-metadata-93125714bc733b74.json) | 1300 | John 7:32–53; John 8:1–19 |

The [retained endpoint documentation](../data/reference/contracts/biblicalcontent_get_.json)
describes `detail=long` as expanding page ranges into individual entries.
[Retained Wallace excerpts](../data/sources/wallace-john-pa-f2077311ebf42d87.json)
report omission in P66, P75, Sinaiticus, and Vaticanus, and presence in Bezae.
[Retained Houghton excerpts](../data/sources/houghton-john-pa-a12b86ef2108d68c.json)
supply context and Bezae's identifier cross-reference. Citations, exact statements,
qualifications, and retrieval metadata stay with those captures.

The [checking register](SOURCE_CHECKS.md)
preserves the five original passage comparisons and five current rechecks. These
known cases are separate from first-five target selection. The comparisons remain
`insufficient_detail`, because the index cannot independently establish the
reported omissions or confirm Bezae's presence. Wallace's explicit assertions
are now active; Houghton remains contextual. No provider explanation has been
established. Chasing forum leads is not a prerequisite for this treatment.

The initial acquisition made three requests (two publications and the first forum
lead), within a five-request/180-second limit with five-second spacing. The forum
returned HTTP 403; requests stopped, and the other two leads were unattempted.
Full publication downloads stay in the ignored research cache; retained excerpts,
hashes, and extracted assertions are in `data/sources/`. The saved contents reports
have twelve scoped entries each for P66, P75, Vaticanus, and Bezae, and none for
Sinaiticus. Missing Sinaiticus entries do not corroborate absence.

## Completed omission sample: 2026-10-09

The declared three-case sample used Vaticanus (NTVMR 20003) in each case, the same
saved metadata and `detail=long` fields as the John comparison, and tier-3 pages.
NET Bible's published prose notes explicitly name B among witnesses omitting
each exact verse. Only those assertions were extracted; no manuscript text,
apparatus, image, or explanation of textual origin was analyzed.

| Exact scope | Retained scholarly assertion | Saved page ID and range | Expanded entry |
| --- | --- | --- | --- |
| Matthew 17:21 | [NET note](../data/sources/net-omission-matt-17-21-4705cb5b1cce3e9d.json) | 270: Matthew 17:9–27; 18:1–6 | `Matt.17.21` included |
| Mark 15:28 | [NET note](../data/sources/net-omission-mark-15-28-7d6ecab96fd9948e.json) | 710: Mark 15:14–42 | `Mark.15.28` included |
| Acts 8:37 | [NET note](../data/sources/net-omission-acts-8-37-a6cf47d7af86f509.json) | 1630: Acts 8:26–40; 9:1–11 | `Acts.8.37` included |

The register pins exact expanded entries, metadata page fields, source hashes,
citations, excerpt locators, retrieval dates, and qualifications. All three
controls record `insufficient_detail`: none supplied an internal index exclusion.
The bounded conclusion is inconclusive about NTVMR's general convention and does
not support calling John a confirmed local error. It does demonstrate that these
three comparable expanded entries cannot independently establish verse presence
against an explicit published omission. This does not invalidate unrelated entries.

Research was limited to NET Bible notes, eight page requests and ten minutes,
with five-second spacing. One three-query search and three successful web page
opens supplied the notes. A separate direct download returned HTTP 403; requests
stopped without retries. Short rendered excerpts are retained with their hashes;
original HTTP bytes were unavailable. No live NTVMR requests were made.

The documented treatment is limited to the three contradicted John ranges for
P66, P75, and Vaticanus and the three exact control verses for Vaticanus. Their
raw index entries remain visible with unknown admission and evidence links.
Explicit Wallace reports establish absence for P66, P75, Sinaiticus, and
Vaticanus in the twelve John verses and presence for Bezae. Sinaiticus's missing
index entries never supply absence. Bezae's compatible index and publication
reports count one witness. All date estimates and other index entries remain
unchanged. The three control coordinates remain subject to the existing edition
filter; their registered omission assertions do not change that filter.

## Step 1: Check how NTVMR represents internal omissions

Use a small sample, initially three to five cases, where an explicit scholarly
publication reports that a particular manuscript omits specific verses within
a passage. This control sample may include witnesses outside the first five.

1. Reuse saved scholarly reports, catalogue metadata, verse-content responses,
   and endpoint documentation. Select named witnesses and exact verse scopes.
   If additional requests are needed, declare sources, time/request budgets,
   and pacing before starting; honor provider blocks.
2. Compare the reported omissions with breaks in NTVMR's saved page ranges and
   their expanded verse entries. Prefer the same indexing fields, comparable
   indexing tiers, and where possible the same manuscripts as the John case.
   Record the exact fields, captures, and qualifications that make each example
   comparable.
3. Distinguish the published omission assertion from the observed index gap.
   A gap alone establishes neither manuscript absence nor the reason for it.
   Do not determine omissions from images, Greek transcriptions, apparatuses,
   physical damage, or neighboring verse contents.
4. Stop after the declared sample and budget. Record usable examples and
   inconclusive cases; failure to find a suitable control does not establish a
   universal indexing limitation or trigger a collection-wide investigation.

Comparable examples would establish that NTVMR can represent internal exclusions
and support a localized indexing error as the working explanation for the John
entries. They would not prove uniform practice throughout NTVMR or constitute a
provider-confirmed correction. Keep that inference separate from scholarly
content assertions. Provider clarification is useful when available, but is not
required before documenting a practical, passage-specific treatment.

Apply the findings to the five retained John cases, preserving each one's actual
report state. If NTVMR cannot supply reliable verse presence for this passage,
document that limitation and use usable explicit scholarly reports for the
affected witness/verse pairs. Keep otherwise usable NTVMR reports in use. A
general importer change requires evidence of a general problem; the known case
does not by itself justify withdrawing unrelated NTVMR coverage.

## Step 2: Check only claims affecting the first five

The review scope is the union of witnesses appearing among the first five
collected witnesses for any verse, across both lower- and upper-date-endpoint
modes and all retained complete date alternatives. It is not five manuscripts
for the whole New Testament.

- Select targets from the existing compact rankings in `data/attestations.json`,
  linked back to the central register and captures. Deduplicate canonical
  witnesses and witness/verse checks across verses and scenarios. Target selection
  does not require a full collection rebuild or a witness/verse object matrix.
- Review only the verse-presence claims and date reports that place those
  witnesses in the first five. Selection for one verse does not authorize a
  review of all that manuscript's contents. Preserve each competing date range
  in full; do not choose a preferred scholar or merge endpoints.
- After a correction, update the affected rankings. If another witness enters
  the first five, check the relevant claims for that replacement. Apply the
  same rule across both date modes and alternatives.
- Where rankings are unavailable, including date-combination overflow, record
  the limitation rather than silently selecting an alternative or expanding a
  corpus-wide combination set.
- Stop when the current first-five claims and any promoted replacements have
  recorded scoped outcomes. Unresolved cases can remain visible and deferred;
  missing corroboration does not negate an otherwise usable report. Fewer than
  five usable witnesses is acceptable. Do not investigate lower-ranked witnesses
  merely to broaden coverage.

Use additional scholarly sources only as needed for these selected claims.
There is no current general source-discovery pilot or requirement to corroborate
every captured manuscript. Further broad collection remains deferred.

## Evidence, storage, and app consequences

Retain the existing central collection, source captures, checking register, and
app. The [checking schema](SOURCE_CHECKS.md) documents the implemented evidence
links, comparison outcomes, follow-up, and recheck detection; no replacement
register or new tracking system is needed.

- `data/sources/` and `data/reference/` retain source material and field contracts,
  with citations, retrieval dates, hashes, exact locators, and qualifications.
  Keep known upstream dependencies; repeated access points need not be independent
  evidence.
- `data/collection.json` holds identities and scholarly claims.
  `data/source_checks.json` holds only scoped comparisons and follow-up.
  Keep the five existing John checks and their evidence. New checks are limited
  to the small omission sample and relevant first-five claims.
- `data/attestations.json` remains the single derived app input. Project only
  relevant discrepancy details and evidence links when implementing the correction.
  A collection-wide progress dashboard is not part of this work.
- Preserve original claims and captures when revising extraction or admission.
  Recheck affected in-scope comparisons after source or extraction changes; do not
  inherit stale agreement or reopen unrelated collection-wide review.

Registered scholarly assertions determine coverage. Any reported surviving portion
counts once per witness/verse. Missing entries are unknown; absence requires an
explicit scholarly report. An ambiguous index contribution is unknown, and an
independently usable report may establish presence or absence. Actual incompatible
explicit content reports are contested and excluded from ordinary presence counts
and rankings while unresolved. Keep both sources visible. A working explanation
about indexing must not become an invented scholarly assertion or disagreement.

The app's evidence and counts must agree for the affected cases. Preserve complete
competing dates as alternatives, without turning different dates into a content
conflict. Human review checks faithful extraction, citation, and usability; it
does not require manuscript examination or scholarly certification.

## Next actions and verification

- [x] Record the small internal-omission sample and its bounded conclusion.
- [x] Apply a documented treatment to John 7:53–8:11 and correct the affected
  evidence, counts, and rankings in the existing app.
- [x] Select the first-five scopes after correction and record the current John
  first-five outcomes, including promoted replacements.
- [x] Review the remaining selected checks from retained evidence, record
  unavailable independent comparisons as deferred, and stop at the scope above.

The CLI now selects deduplicated first-five scopes directly from compact ranking
tables and can append uncovered scopes to the existing checking register. Both
endpoint modes and every exported date combination participate. Unavailable
rankings are disclosed rather than filled in. Rerun selection after corrections
to queue promoted replacement claims without reopening unrelated manuscript
contents. Selection alone does not complete a check; the current selected scopes
now have reviewed evidence and recorded outcomes.

The corrected selection includes 198 witnesses and 39,776 witness/verse pairs.
Sixteen edition-filtered coordinates have unavailable rankings. Current John
rankings promote GA 032, GA 07, and GA 047; their exact passage claims and the
current five's complete catalogue dates have scoped outcomes. The saved publication
excerpts have no explicit assertions for GA 029, GA 032, GA 07, or GA 047 and no
comparable complete dates for the current five, so those
outcomes remain `insufficient_detail` with deferred follow-up. One usable catalogue
report remains sufficient.

On 2026-10-10, offline extraction review completed the remaining 391 checks:
198 exact content scopes and 193 complete catalogue-document date scopes. The
content checks traced 42,513 tier-3 entries for the remaining 39,716 selected
witness/verse pairs to the retained document, page, OSIS field, indexing metadata,
and admission qualifications. Every selected coordinate had an admitted
reported-presence claim. The date checks preserved complete intervals, notation
types, provenance, and qualifications and matched the compact ranking reports.
Earlier John outcomes and all source claims remain unchanged.

None of these remaining scopes has a comparable explicit assertion in the five
registered publication captures. Their outcomes are therefore `insufficient_detail`
with deferred follow-up, not independently corroborated agreement. Each check
pins the relevant catalogue captures, stable scoped claim IDs, and retained
endpoint documentation. This establishes faithful extraction under the current
contract; it does not establish manuscript contents or resolve index semantics.

All 198 selected witnesses, 39,776 witness/verse pairs, and 198 complete date
reports now have scoped outcomes, including the previously checked John claims
and promoted replacements. The register has 408 current outcomes and five
superseded comparisons, with no unreviewed or stale checks. Refreshing selection
adds no work; the sixteen unavailable rankings remain explicit. The current
stop condition is reached. Reopen only affected checks when evidence, extraction,
or admission changes, or when a correction promotes new first-five claims.
Independent comparison remains deferred; no live requests or collection rebuild
were needed for this review.

Use focused offline checks for the selected evidence and any changed behavior.
Documentation edits, target selection, and scoped comparisons do not require a
production rebuild. Rebuild the app data when registered claims or output behavior
change, retaining the enforced memory budget and compact representation. Do not
repeat full builds merely to measure checking progress. No live collection or
local server is part of routine verification.

Remove obsolete exploratory scripts, duplicate inspection output, and old run
logs when no longer needed. Preserve original evidence, useful checking tools,
bounded regression fixtures, and collection checkpoints. Software revision
history belongs in Git; temporary work belongs in ignored `data/.cache/`.
Contacting providers or posting reports still requires the owner's explicit
instruction.
