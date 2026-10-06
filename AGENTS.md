# Project scope and working rules

## Scholarly reports only

EarliestAttestation is a data collection and visualization project. It records
what scholarly sources report about the estimated dates and verse contents of
Greek New Testament manuscripts. It does not perform manuscript scholarship.
This boundary was clarified by the project owner on 2026-10-05 and supersedes
examination or specialist-review tasks in older project documents.

- Never download or inspect manuscript images to determine contents, dates,
  hands, corrections, physical damage, or identity. Do not ask the owner to do so.
- Never read Greek transcription text, select surviving word anchors, interpret
  an apparatus or an empty transcription element, or infer manuscript contents
  or writing layers from them. A scholarly transcription is not permission to
  perform our own textual examination. Explicit published content assertions
  may be captured as assertions without analyzing the underlying text.
- Prefer NTVMR's documented catalogue metadata and verse-content reports.
  Establish the meaning of the API fields through documentation and bounded
  contract checks. Use explicit reports in other scholarly catalogues or
  publications when needed. A source's image link is not a content assertion.
- One usable scholarly report is sufficient; independent corroboration of every
  witness is not required. Keep the source's identity, exact reported claim or
  field, citation, retrieval date, qualifications, and raw response where available.
- Any reported surviving portion counts as the verse being present for counting
  and graphing. Do not require a complete verse, exact NA28 wording, a minimum
  number of letters, or a word-level survival check.
- Explicit disagreement between scholarly sources about a witness's verse
  contents is `contested`. Preserve both claims, keep the case visible, defer
  adjudication, and continue other collection. Missing or ambiguous information
  is `unknown`; a missing index entry alone is neither absence nor disagreement.
- Record absence only when a scholarly source explicitly reports it. Do not
  infer neighboring verses or expand a broad contents summary beyond the
  source's documented meaning.
- Copy scholarly date estimates and their qualifications. Preserve competing
  ranges as complete, equally valid alternatives unless a cited source establishes
  consensus. Do not average, narrow, merge endpoints, or decide which scholar is
  right. Record distinct portions, hands, supplements, or fragment joins only as
  explicitly reported by sources; do not identify them independently.
- Human review, when useful, checks faithful extraction and citation. Neither
  specialist manuscript examination nor independent scholarly certification is
  a prerequisite for this project's collection, graph, or release.

## Current work and historical material

Use [the development plan](docs/DEVELOPMENT_PLAN.md#next-development-work) for
current priorities. The next milestone is a reproducible NTVMR collection-to-chart
path based on reported dates and verse contents, with unknown and contested cases
visible. Prefer completing that path over more research or review infrastructure.

Older review notes, replays, benchmarks, and charts preserve development history;
they do not authorize examination. Agent-derived coverage judgments must be
replaced by explicit scholarly reports or excluded from active results. Do not
relabel those judgments as scholarly claims or as disagreements between scholars.
A passing historical benchmark establishes reproducibility, not source authority.
The unfinished John 5 overlap drafts are not approved inputs for a new increment.

Keep documentation of existing behavior separate from planned changes. The scope
reset does not itself implement `contested` storage or remove old review gates.
Preserve source and decision history when correcting records, and use fresh
databases or SQLite backups before migrations or replays.

## Verification and collection

- Do not start local development servers or probe localhost unless explicitly
  requested. Prefer appropriate offline tests, lint, type checks, and builds.
- Keep live collection scoped and budgeted; reuse captured responses. Honor
  provider limits and blocked states. Do not make live requests as a routine
  final verification step.
- Verify parsing, reference mapping, provenance, witness deduplication, reported
  coverage states, date handling, rankings, and chart output. Do not add tests
  that require us to determine what a manuscript physically contains.
