# Washingtonianus at the John 5:9–13 writing boundary

> **Historical record; scope superseded on 2026-10-05.** This document preserves
> earlier experiments and observations, not current development instructions or
> accepted scholarly claims. The project now records only explicit scholarly
> reports of dates and verse contents. Manuscript images, Greek transcriptions,
> word anchors, and our own writing-layer judgments must not be used to infer
> coverage or dates. Former human/specialist examination packets are withdrawn,
> not pending project tasks. Re-source or exclude agent-derived claims before
> reusing them in active results. Follow [AGENTS.md](../AGENTS.md) and the
> [current development plan](DEVELOPMENT_PLAN.md#next-development-work).

Reviewed 2026-10-05 by Codex. Independent human validation: **pending**.

The [boundary chart](../examples/john5-boundary-prototype.html) adds five mapped
coordinates and reviews one physical codex across its replacement quire and
original John writing. Five positive page decisions produce **four positive
witness/verse pairs**, because John 5:11 has surviving parts in both layers but
counts once. John 5:12 remains **uncertain**, with no dated event or physical
absence claim. This completes the timed, small boundary batch identified in the
[development plan](DEVELOPMENT_PLAN.md#next-development-work).

## Sources, coordinates, and physical identity

The IGNTP/ITSEE [032S supplement transcription](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_032S_John.xml)
ends at folio **64v**, column 1, within `John.5.11`. The
[032 transcription](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_032_John.xml)
begins at folio **65r**, column 1, with the remaining end of that verse. Both
headers identify document **20032**, Smithsonian/Freer shelfmark **06.274**.
They are portions of one physical Washingtonianus codex, not two witnesses.

Two read-only downloads on 2026-10-05 local time matched the previously retrieved
full sources byte for byte:

| Source | Full-source SHA-256 |
| --- | --- |
| 032S | `498a19869cf25fff8318fbef2b2bfa3281c4db6cb5bcd2c57f6d583d530dca6c` |
| 032 | `34e01920866b9f8fc3c026dd8e539f9a58571c5b601e5bb47c6c283672b69160` |

The pinned [supplement excerpt](../tests/fixtures/washingtonianus-john5-032s-transcription.json)
retains the verbatim header, folio/column markers, the last preceding line marker
(22), and the contiguous John 5:9–11 elements. Book/chapter containers were added
to balance the excerpt; the context markers are assembled from that same page.
The pinned [original excerpt](../tests/fixtures/washingtonianus-john5-032-transcription.json)
retains the verbatim header and contiguous opening through John 5:13, with two
closing container tags added. The source's CC BY 4.0 attribution, named creators,
extraction changes, verification times, and hashes are retained. No manuscript
image was inspected or reproduced.

Existing [NTVMR metadata](../tests/fixtures/washingtonianus_metadata_probe.json)
labels page **1280** as `64v Suppl`, with
`John 4:53-54; John 5:1-11`, and page **1290** as `65r`, with `John 5:11-22`.
The existing [coverage capture](../tests/fixtures/washingtonianus_coverage_probe.json)
lists the six explicit verse/page pairs reviewed below. No new NTVMR request was
needed. These page and index links locate evidence; they do not prove survival.

The [new immutable inventory](../benchmarks/john5-na28-subset-v1.json) retains
John 5:9–13 from the provisional whole-NT coordinate inventory. The five numbered
markers were checked against the
[publisher's NA28 John 5 display](https://www.die-bibel.de/en/bible/NA28/JHN.5).
Their direct coordinate mappings are checked against both transcriptions and the
captured index. No NA28 wording is reproduced. This is a reviewed subset, not an
update or certification of the whole-NT inventory.

## Six page decisions and the unresolved verse

| Verse | Page / folio | Direct anchor | Line marker | Decision / writing layer |
| --- | --- | --- | --- | --- |
| John 5:9 | 1280 / 64v | υγιης | `P64vC1L22-032S` | Partial / supplement |
| John 5:10 | 1280 / 64v | ιουδεοι | `P64vC1L27-032S` | Partial / supplement |
| John 5:11 | 1280 / 64v | απεκρινατο | `P64vC1L30-032S` | Partial / supplement |
| John 5:11 | 1290 / 65r | κραβαττον | `P65rC1L1-032` | Partial / original |
| John 5:12 | 1290 / 65r | None: empty `ab` | Between 5:11 and 5:13 | Uncertain / unassigned |
| John 5:13 | 1290 / 65r | ουκ | `P65rC1L2-032` | Partial / original |

Each positive anchor is an intact direct word outside supplied, unclear,
expanded, corrected, or marginal text. Line locations follow the preceding TEI
line marker, including markers inherited across verse boundaries. These are
partial-survival decisions, not claims of full preservation or NA28 agreement.

In the supplement, John 5:11 has unclear letters in two other words, followed
by intact text through `αρον τον` and `gap reason="witnessEnd"`. The original
transcription begins that verse with
`gap reason="lacuna" unit="verse" extent="rest"`, then the four intact words
`κραβαττον σου και περιπατει`. The separate captures and page labels document
the division. The leading gap in the original transcription does not establish
whole-verse absence from the combined physical codex; the supplement preserves
part of the verse as well. The replay guards these specific markers and anchors;
it is not a general survival or writing-layer classifier.

The original source's `John.5.12` element is empty despite its index entry.
There is no Greek anchor or encoded explanation of the empty element in this
excerpt. The review records **uncertain**, assigns no writing unit, and creates
no physical-absence decision. It does not infer a scribal omission, physical
damage, or a transcription error. An image or independent source check is needed
to resolve that question. NA28 edition omission is also inapplicable: the
publisher display has a numbered 12 here.

## Separate conditional dates and one witness event

[Prior's article opening](https://www.galaxie.com/article/bbr11-2-05), p. 233,
first paragraph under “The Freer Gospels,” documents the replacement quire's
extent through John 5:11a and its qualified seventh-or-eighth-century assessment.
The existing [pinned date observation](../tests/fixtures/washingtonianus-supplement-date-source.json)
is reused: **601–800 CE**, retaining the qualification “perhaps” and both complete
centuries. The source paragraph was checked again for this boundary review.

NTVMR's manuscript-level `originYear` gives notation **V**, explicit lower bound
**400**, and upper bound **499**. Those numeric fields are copied without century
reconversion and applied conditionally to reviewed original writing on 65r.
They are not applied to the replacement quire on 64v. The page and transcription
division supports this applicability; no named original scribe is inferred.

The two intervals date different writing units. They are not competing dates for
the same text, and they are not merged into a new interval. Both units belong to
`032-washingtonianus`. Consensus remains unknown, date-source discovery is
incomplete, and stored policy selections remain null.

| Verse | Optimistic event, CE | Pessimistic event, CE | Qualifying portion |
| --- | ---: | ---: | --- |
| John 5:9 | 601 | 800 | Supplement |
| John 5:10 | 601 | 800 | Supplement |
| John 5:11 | 400 | 499 | Original ending; supplement retained separately |
| John 5:12 | — | — | Uncertain survival |
| John 5:13 | 400 | 499 | Original |

For John 5:11, the existing ranking code independently takes the earliest
qualifying surviving part per physical witness in each endpoint scenario.
The original ending qualifies before the supplement in both scenarios. Both
assessments and coverage reviews remain in the export and source table, even
though only one witness event is drawn. Withdrawing the original page review
moves that verse's event to 601 / 800 while keeping the witness count at one;
withdrawing both page reviews removes the event.

## Offline reproduction, checks, and measured effort

Use a fresh database destination. These commands use only checked-in inputs:

```powershell
python replay_john5_boundary.py --db data/john5-boundary-replay.sqlite --dry-run
python replay_john5_boundary.py --db data/john5-boundary-replay.sqlite
python audit_reviewed.py --db data/john5-boundary-replay.sqlite --benchmark benchmarks/john5-boundary-evidence-benchmark-v1.json
python export_attestation.py --db data/john5-boundary-replay.sqlite --inventory na28-john5-boundary-subset-v1 --policy john5-boundary-conditional-v1 --dataset-output data/john5-boundary-complete.json --graph-output examples/john5-boundary-graph-input.json
python render_attestation.py --graph-input examples/john5-boundary-graph-input.json --output examples/john5-boundary-prototype.html
python -m unittest discover -s tests
```

The fresh `data/john5-boundary-check-20261005.sqlite` replay has **zero audit
findings**, passes **5/5 cited benchmark cases**, and makes **zero replay network
attempts**. The benchmark now accepts an explicit `uncertain` coverage
expectation: it requires a current cited uncertain review, with neither positive
survival nor a recorded physical absence. It permits no numeric date for that
expectation. The original positive, rejected, and absent expectations remain
supported.

Seven new regressions check offline reproduction, both layer assignments and
date applicability, distinct-witness counting, withdrawal and fallback, unsafe
survival/absence inferences from the empty verse, changed anchors/locations/gaps,
false human-validation status, and safe dry runs/existing destinations. All
**121 offline tests** pass. Structural checks and benchmark agreement establish
reproducibility; historical validation remains incomplete.

| Measure | This increment |
| --- | ---: |
| New source-mapped coordinates | 5 |
| Reviewed physical witnesses / positive witness–verse pairs | 1 / 4 |
| Positive page reviews / uncertain page reviews | 5 / 1 |
| Writing units / positive coverage assignments | 2 / 5 |
| Valid conditional date assessments / selected dates | 2 / 0 |
| Graphable coordinates / unresolved coordinates | 4 / 1 |
| Conditional combinations per graphable coordinate | 1 |
| New NTVMR requests / replay network attempts | 0 / 0 |
| Successful university verification downloads | 2 |
| Benchmark cases passed / audit findings | 5 / 0 |

The recorded working interval from **2026-10-06 00:58:27 to 01:04:43 UTC**
(2026-10-05, 5:58:27–6:04:43 PM Pacific) is **6 minutes 16 seconds**. It includes
source reconciliation, live-source verification, fixture/manifest assembly,
replay implementation, and the first audit/export/render. It excludes initial
project inspection and later regression/documentation work; it is not isolated
source-reading time or total task time. A sandbox socket refusal preceded the
two successful university requests. The existing NTVMR captures were reused.

The batch reuses existing schema, coverage/dating APIs, exporter, and renderer.
The only shared change adds the real uncertain case to the existing benchmark
checker. Reviewing two sources produced five positive page decisions in that
measured interval, with one exception needing further source review. These
numbers do not justify whole-corpus automation or a general TEI classifier.

## Independent review questions

> **Withdrawn packet.** The questions below are preserved solely as historical
> context. Do not carry out their image, Greek-text, survival, or hand-identification
> checks, and do not ask the owner or a specialist to complete them for this
> project. Optional human checks now concern accurate copying of explicit
> published reports only.

All answers are **unanswered**. Record **agree**, **disagree**, or **unable to
assess**, with reviewer identity, date, corrections, and notes. Keep human
answers separate from Codex reviews and automated checks.

1. **One physical codex and page links:** do both linked transcription headers
   identify 20032 / 06.274, and do metadata pages 1280 and 1290 label 64v Suppl
   and 65r as recorded? Check each of the six explicit index pairs.
2. **Survival and exact boundary:** do the five intact anchors and line markers
   support partial survival, excluding supplied/unclear/expanded or corrected
   text? Does 032S end within `John.5.11`, while 032 preserves its four-word
   ending? Check the two pinned excerpts against the published transcriptions.
   Greek/TEI or manuscript expertise may be needed.
3. **Unresolved John 5:12:** does the empty element support retaining uncertainty
   without a survival or physical-absence claim? Can the
   [65r image identified by NTVMR](https://ntmss.info/images/webfriendly/20032/F1906.274.129.jpg)
   or another independent source resolve whether verse 12 was omitted or the
   transcription needs correction? An image was not checked by this review;
   specialist assistance may be needed.
4. **Layer/date applicability:** does Prior's cited paragraph support the later
   quire's extent and qualified date, and does the page/transcription division
   support keeping 601–800 on 64v separate from the catalogue's V / 400–499
   conditional input on 65r? Check faithful recording, without choosing a scholar
   or claiming established consensus.
5. **Graph and fallback:** does the chart reproduce the event table, retain
   both John 5:11 assessments and page reviews, count that physical codex once,
   and show John 5:12 as uncertain? Are incomplete discovery and pending human
   validation clearly stated?

The former John 5:12 image-examination task and overlapping-witness examination
increment are withdrawn. Seek only explicit scholarly contents reports; preserve
unknowns or disagreements without interpreting the manuscript or its transcription.
Use the [current collection-to-chart plan](DEVELOPMENT_PLAN.md#next-development-work).
