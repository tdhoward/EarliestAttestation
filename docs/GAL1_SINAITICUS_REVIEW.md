# Galatians 1:1–5 third-witness and writing-layer review

> **Historical record; scope superseded on 2026-10-05.** This document preserves
> earlier experiments and observations, not current development instructions or
> accepted scholarly claims. The project now records only explicit scholarly
> reports of dates and verse contents. Manuscript images, Greek transcriptions,
> word anchors, and our own writing-layer judgments must not be used to infer
> coverage or dates. Former human/specialist examination packets are withdrawn,
> not pending project tasks. Re-source or exclude agent-derived claims before
> reusing them in active results. Follow [AGENTS.md](../AGENTS.md) and the
> [current development plan](DEVELOPMENT_PLAN.md#next-development-work).

Reviewed 2026-10-02 by Codex. Independent human validation: **pending**.

The [three-witness chart](../examples/gal1-three-witness-prototype.html) adds
Sinaiticus to P46 and Alexandrinus at all five coordinates. It has fifteen cited
partial-coverage decisions and four equal conditional dating combinations per
verse. The [two-witness replay](GAL1_OVERLAP_REVIEW.md) and its chart remain
available. This increment followed the former overlapping-witness priority in the
[development plan](DEVELOPMENT_PLAN.md#next-development-work).

## Source identity and page reconciliation

The [INTF transcription published by ITSEE](https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_01_Gal.xml)
identifies document 20001 / GA 01 and British Library shelfmark Add. 43725. Its
header credits INTF, records proofreading by Amy Myshrall on 2021-10-19, and
publication on 13.5.2024 under Creative Commons Attribution 4.0. The
[pinned excerpt](../tests/fixtures/sinaiticus-gal1-transcription.json) preserves
that header and the contiguous opening through Galatians 1:5. Two closing
container tags balance the excerpt. A live download matched the previously
retrieved full source's SHA-256:
`548b024f232f79a1cb92a5f534ecbab6ff55ec7a4c6f9ad0a073561f9fe303aa`.

The transcription begins at **folio 278v, column 3**. Newly captured
[NTVMR metadata](../tests/fixtures/sinaiticus_metadata_probe.json) identifies
**page 1580** as folio 278v, with index content
`2Cor 13:5-13; 2Cor subscriptio; Gal inscriptio; Gal 1:1-17`.
The existing [coverage index](../tests/fixtures/sinaiticus_coverage_probe.json)
places all five Galatians coordinates on that page. Metadata and index provide
the location link; the transcription supports the positive survival decisions.
No manuscript image was inspected or reproduced for this increment.

The five mappings in the [existing coordinate inventory](../benchmarks/gal1-na28-subset-v1.json)
are reused. Its original P46-oriented scope description records how that
coordinate snapshot was assembled; the new review manifest and dating policy
declare this increment's three-witness evidence scope. No immutable inventory
is rewritten or certified as a whole-NT inventory.

## Original writing and corrections

| Verse | Intact direct base-text anchor | Relative line from Galatians 1:1 |
| --- | --- | ---: |
| Galatians 1:1 | παυλος | 1 |
| Galatians 1:2 | αδελφοι | 8 |
| Galatians 1:3 | ειρηνη | 11 |
| Galatians 1:4 | αμαρτιων | 15 |
| Galatians 1:5 | δοξα | 21 |

These are offsets through the excerpt's line-break elements, starting at the
beginning of Galatians 1:1. They are not absolute manuscript line numbers. All
five anchors are direct words outside apparatus, supplied or unclear text,
abbreviation expansions, and the corrected marginal inscription. Each positive
decision is conservatively `partial`: it does not certify complete preservation
or exact NA28 wording.

The transcription explicitly distinguishes these apparatus readings:

| Location | `orig`, `hand=firsthand` | Separate correction |
| --- | --- | --- |
| Galatians 1:1 | αυτων | `corrector1`: αυτον, above-line segment, strikethrough encoding |
| Galatians 1:4, first apparatus | περι | `corrector2`: υπερ, above-line segment, strikethrough encoding |
| Galatians 1:4, second apparatus | αιωνος του ενεστωτος | `corrector2`: ενεστωτος αιωνος, transposition marks |
| Galatians 1:4, third apparatus | empty original reading | `corrector2`: το, above-line addition |

The inscription also has an empty original reading and a corrected pagetop
margin reading. It supplies no verse evidence. Correction labels reproduce the
transcription's labels, without identifying or dating a historical corrector.

The new `01-sinaiticus-gal1-original` writing unit contains only the reviewed
main-text portions. A specific scribe is not inferred. No correction reading
supplies a coverage anchor, receives an original-writing date, or counts as an
additional physical witness. The correction distinctions remain in the pinned
source, review reasons, exported evidence, and chart. They are not independently
dated correction evidence. The replay guards the reviewed anchors and known
apparatus signatures; it is not a general TEI survival or layer classifier.

## Conditional date recording

The NTVMR metadata explicitly gives notation `IV`, lower bound **300**, and
upper bound **399**. Those numbers are copied directly. The
[Sinaiticus Project Date page](https://www.codexsinaiticus.org/en/codex/date.aspx)
describes a fourth-century date, sometimes more precisely the middle of that
century. The [pinned first sentence](../tests/fixtures/sinaiticus-date-source.json)
was checked with the web reader on 2026-10-02. The complete-century conversion
**301–400 CE** is retained separately from NTVMR's numeric fields. The qualified
middle-of-century observation remains numerically unknown because the source
states no inclusive endpoints.

These are conditional inputs for the reviewed original base text. No date is
selected, averaged, narrowed, or combined; no probability or independently
established consensus is claimed. P46 retains both earlier intervals and
Alexandrinus retains its 400–499 CE assessment.

| Conditional inputs (CE) | Optimistic events: P46, 01, 02 | Pessimistic events: P46, 01, 02 |
| --- | --- | --- |
| P46 200–225; 01 300–399; 02 400–499 | 200, 300, 400 | 225, 399, 499 |
| P46 201–300; 01 300–399; 02 400–499 | 201, 300, 400 | 300, 399, 499 |
| P46 200–225; 01 301–400; 02 400–499 | 200, 301, 400 | 225, 400, 499 |
| P46 201–300; 01 301–400; 02 400–499 | 201, 301, 400 | 300, 400, 499 |

Every combination applies to all five verses. Each scenario counts each
physical witness once. Stored policy selections remain null; the ordinary
exporter calculates combinations without choosing a preferred source.

## Offline reproduction and verification

Use a fresh destination; the replay refuses an existing path. These commands
use checked-in inputs and make no network requests:

```powershell
python replay_gal1_sinaiticus.py --db data/gal1-three-witness-replay.sqlite --dry-run
python replay_gal1_sinaiticus.py --db data/gal1-three-witness-replay.sqlite
python audit_reviewed.py --db data/gal1-three-witness-replay.sqlite --benchmark benchmarks/gal1-three-witness-evidence-benchmark-v1.json
python export_attestation.py --db data/gal1-three-witness-replay.sqlite --inventory na28-gal1-p46-subset-v1 --policy gal1-three-witness-conditional-v1 --dataset-output data/gal1-three-witness-complete.json --graph-output examples/gal1-three-witness-graph-input.json
python render_attestation.py --graph-input examples/gal1-three-witness-graph-input.json --output examples/gal1-three-witness-prototype.html
python -m unittest discover -s tests -v
```

The fresh `data/gal1-three-witness-check.sqlite` replay has **zero audit findings**
and passes **15/15 cited evidence cases**, with **zero replay network attempts**.
All **108 offline tests** pass, including the prior two-witness, P46, John 1,
John 6, and P52 regressions. New tests reject correction-only, supplied, unclear,
expanded, and hand-marked anchors; changed apparatus, page links, identity,
line locations, and dates; and falsely asserted human validation. Withdrawing
one Sinaiticus coverage review removes it from that verse's exported evidence
and conditional rankings while preserving the other witnesses and verses.
These checks establish reproducibility, not independent historical validation.

| Measure | This increment |
| --- | ---: |
| New coordinates / reused mapped coordinates | 0 / 5 |
| Added witnesses / positive witness–verse pairs | 1 / 5 |
| Total witnesses / positive pairs | 3 / 15 |
| Added writing units / coverage assignments | 1 / 5 |
| Added date assessments, valid / unknown | 2 / 1 |
| Graphable verses / combinations per verse | 5 / 4 |
| Controlled NTVMR attempts | 3: socket sandbox refusal, direct timeout, configured-proxy success |
| University verification attempts | 2: socket sandbox refusal, successful matching download |
| New index downloads / replay network attempts | 0 / 0 |
| Pending page links or writing assignments for included evidence | 0 |

NTVMR access reused the previously configured project proxy after a direct
timeout; no provider access block was encountered. The metadata fixture retains
both the transport URL and canonical source URL. Manual work covered one
identity/page reconciliation, five anchors and line locations, four verse
apparatus entries plus the inscription, and two date-source descriptions.
Approximately ten minutes elapsed from the first metadata attempt through
implementation and verification; isolated source-review time was not measured.
The repeated cost remains source and writing-layer review per verse. This
increment adds no schema or bulk-collection framework.

## Independent review questions

> **Withdrawn packet.** The questions below are preserved solely as historical
> context. Do not carry out their image, Greek-text, survival, or hand-identification
> checks, and do not ask the owner or a specialist to complete them for this
> project. Optional human checks now concern accurate copying of explicit
> published reports only.

All answers are **unanswered**. Record **agree**, **disagree**, or **unable to
assess**, with corrections, reviewer name, and review date. These questions
check source fidelity; they do not ask the reviewer to resolve dating disputes.

1. **Identity and location:** does the [TEI header and opening](https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_01_Gal.xml)
   identify GA 01 / 20001, Add. 43725, folio 278v, column 3, and does the
   [metadata capture](../tests/fixtures/sinaiticus_metadata_probe.json), page 1580,
   give the same folio and Galatians opening? Verify the index link for all five
   verses; an index match alone does not establish survival.
2. **Five positive decisions:** in `Gal.1.1`–`Gal.1.5`, do the anchors and offsets
   listed above identify surviving direct base text, sufficient for partial
   coverage of each verse? Check the [pinned excerpt](../tests/fixtures/sinaiticus-gal1-transcription.json)
   against the live source. Full-wording agreement is not required.
3. **Correction exclusion:** do the four apparatus entries reproduce the source's
   `orig/firsthand`, `corr/corrector1`, and `corr/corrector2` labels faithfully?
   Do all five coverage anchors lie outside those readings and the corrected
   inscription? Specialist TEI/manuscript expertise may be needed. Flag any
   uncertainty in assigning the reviewed base-text portions to original writing.
4. **Date fidelity and applicability:** does `originYear` in the metadata capture
   explicitly give `IV`, 300, 399? Does the [project Date page](https://www.codexsinaiticus.org/en/codex/date.aspx)
   support the separately labeled complete-century conversion 301–400 and the
   numerically unknown qualified observation? Does applying these conditionally
   to the reviewed original writing, while leaving corrections undated, represent
   the sources faithfully? Do not select a preferred date.
5. **Graph and limits:** do all four combinations in the
   [chart](../examples/gal1-three-witness-prototype.html) match the table above,
   count P46, 01, and 02 once each, and clearly retain partial-coverage, incomplete
   discovery, and pending-human-validation status?

The former examination and specialist-review follow-ups are withdrawn. Use the
[current collection-to-chart plan](DEVELOPMENT_PLAN.md#next-development-work)
and capture explicit scholarly reports without interpreting writing layers or
requiring completion of these historical review packets.
