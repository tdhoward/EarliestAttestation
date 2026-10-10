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

## Project layout and current work

Use [the development plan](docs/DEVELOPMENT_PLAN.md#next-development-work) for
current priorities. Maintain one central collection under `data/` and one HTML/JS
app under `web/attestation-explorer/`. The app loads `data/attestations.json`;
`python build_collection.py` updates that file from the central source register.
Collection updates must not regenerate HTML or create book-specific datasets,
charts, numbered revision files, replay databases, or milestone reports.

The current investigation follows the narrowed
[source corroboration plan](docs/SOURCE_CORROBORATION_PLAN.md), agreed 2026-10-09:
first check a small sample of NTVMR internal-omission indexing, then review only
claims affecting the first five collected witnesses per verse across both date
modes and retained date alternatives. Check replacements that enter those five
after corrections. The control sample may include other witnesses; broader
corroboration and source-collection pilots are deferred. A passage-specific issue
does not establish that unrelated NTVMR reports are faulty.

Keep scholarly source provenance (claims, citations, captures, dates, qualifications)
with the collection. Git handles software revision history. Temporary experiments,
backups, and databases belong in ignored `data/.cache/` and are not product inputs.
Tests may retain fixtures needed to verify behavior; they are not alternate datasets.

Agent-derived coverage judgments are excluded from active results. Do not relabel
them as scholarly claims or as disagreements between scholars. The build uses a
fresh temporary database and disposes of it after producing the current data file.
Back up persistent databases before migrations. Keep documentation focused on
current behavior and next priorities, with planned features clearly identified.

## Verification and collection

- Do not start local development servers or probe localhost unless explicitly
  requested. Prefer appropriate offline tests, lint, type checks, and builds.
- Keep live collection scoped and budgeted; reuse captured responses. Honor
  provider limits and blocked states. Do not make live requests as a routine
  final verification step.
- Verify parsing, reference mapping, provenance, witness deduplication, reported
  coverage states, date handling, rankings, and chart output. Do not add tests
  that require us to determine what a manuscript physically contains.
