# Galatians 1:1–5 overlapping-witness review

Reviewed 2026-10-02 by Codex. Independent human validation: **pending**.

The [two-witness chart](../examples/gal1-overlap-prototype.html) adds Alexandrinus
to the existing P46 passage. Each of the five verses now has two distinct physical
witnesses, ten cited partial-coverage decisions in total, and two equal conditional
date combinations. Discovery is incomplete; this is a research prototype, not an
exhaustive earliest-attestation result. The original
[P46 review and replay](GAL1_P46_REVIEW.md) remain available.

## Source and page reconciliation

The [INTF transcription published by ITSEE](https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_02_Gal.xml)
identifies document 20002 / GA 02 and British Library shelfmark Royal 1 D.VIII.
Its header credits INTF, records proofreading by Amy Myshrall on 2021-10-19,
and publication on 13.5.2024 under Creative Commons Attribution 4.0.
The [pinned excerpt](../tests/fixtures/alexandrinus-gal1-transcription.json)
retains that header, source hash, and contiguous opening through Galatians 1:5;
only two closing container tags are added to balance the excerpt.

The initial transcription markers identify **folio 127v, column 2**. Existing
[NTVMR metadata](../tests/fixtures/alexandrinus_metadata_probe.json) links 127v to
**page 1081**, with content `2Cor 13:9-14; 2Cor subscriptio; Gal inscriptio; Gal 1:1-14`.
The [captured coverage index](../tests/fixtures/alexandrinus_coverage_probe.json)
places all five coordinates on that page. The index links the physical location;
the transcription supplies the evidence of surviving verse text. The existing
[Galatians subset inventory](../benchmarks/gal1-na28-subset-v1.json) is reused.
No whole-NT mapping or inventory certification is implied.

| Verse | Intact direct base-text anchor | Relative line from Galatians 1:1 |
| --- | --- | ---: |
| Galatians 1:1 | νεκρων | 4 |
| Galatians 1:2 | παντες | 5 |
| Galatians 1:3 | ειρηνη | 7 |
| Galatians 1:4 | εαυτον | 9 |
| Galatians 1:5 | δοξα | 14 |

These are transcription line offsets, not absolute manuscript line numbers.
All anchors are intact direct words outside supplied, unclear, abbreviation
expansion, rubrication, and apparatus elements. The five verse elements have no
correction apparatus. The marginal inscription is excluded from the coverage and
writing-unit claims. Several other words contain supplied or unclear letters;
those letters do not establish survival. Each decision is `partial`, without
claiming whole-verse preservation or exact NA28 wording.

The new original-writing unit is limited to the reviewed main-text portions.
No specific scribe or separately dated correction is inferred. The review uses
the public transcription; no manuscript image was downloaded or used.

## Conditional dating and chart results

The same captured Alexandrinus metadata records notation `V`, numeric early bound
400, and late bound 499. These numeric bounds are copied directly, not converted
from the Roman numeral. This is a conditional catalogue assessment applied to
the reviewed original writing; it does not establish scholarly consensus.
P46 retains both prior assessments without choosing a preferred range.

| Conditional inputs | Optimistic events (CE) | Pessimistic events (CE) |
| --- | --- | --- |
| P46 200–225; Alexandrinus 400–499 | P46 200; 02 400 | P46 225; 02 499 |
| P46 201–300; Alexandrinus 400–499 | P46 201; 02 400 | P46 300; 02 499 |

Both combinations apply to all five verses. Each witness counts once per scenario.
No combined interval, probability, or settled manuscript date is asserted. The
selected-policy dates remain null; the ordinary exporter computes the equal
alternatives. Earlier P46 policy records remain available for audit.

## Offline reproduction and verification

Use a fresh database destination. These commands perform no network requests:

```powershell
python replay_gal1_prototype.py --db data/gal1-overlap-replay.sqlite --dry-run
python replay_gal1_prototype.py --db data/gal1-overlap-replay.sqlite
python audit_reviewed.py --db data/gal1-overlap-replay.sqlite --benchmark benchmarks/gal1-overlap-evidence-benchmark-v1.json
python export_attestation.py --db data/gal1-overlap-replay.sqlite --inventory na28-gal1-p46-subset-v1 --policy gal1-overlap-conditional-v1 --dataset-output data/gal1-overlap-complete.json --graph-output examples/gal1-overlap-graph-input.json
python render_attestation.py --graph-input examples/gal1-overlap-graph-input.json --output examples/gal1-overlap-prototype.html
python -m unittest discover -s tests -v
```

The replay validates both witnesses' source inputs before creating its database.
It refuses existing destinations and uses the existing schema and review APIs.
The fresh `data/gal1-overlap-prototype.sqlite` replay has **zero audit findings**
and passes **10/10 cited evidence cases**. The full suite passes **102 offline
tests**, retaining P46, John 1, John 6, and P52 regressions. Static export and
renderer checks verify both date combinations, two distinct witnesses per
scenario, source links, and all five verses. New tests reject changed page links,
identity, dates, lines, writing layers, and supplied-only anchors. These are
reproducibility checks, not independent historical validation.

| Measure | This increment |
| --- | ---: |
| New coordinates / reused mapped coordinates | 0 / 5 |
| Added witnesses / added positive witness–verse pairs | 1 / 5 |
| Total witnesses / positive pairs in the chart | 2 / 10 |
| Added writing units / coverage assignments / date assessments | 1 / 5 / 1 |
| Graphable verses / conditional combinations per verse | 5 / 2 |
| New NTVMR requests / replay network requests | 0 / 0 |
| Successful university transcription downloads | 2 |
| Pending page links or writing-unit assignments for included evidence | 0 |

Two initial download calls were prevented by the local socket sandbox before
network access; the two permitted downloads then succeeded. Alexandrinus was
reviewed and pinned. Sinaiticus was inspected as a possible next witness but is
not counted: its page link and writing-layer applicability need a separate review,
and its Galatians transcription includes corrections. Its full XML remains an
ignored local research file, not a dependency of this replay. Source-review elapsed
time was not reliably measured across the interrupted session. The manual work
was one page/folio reconciliation, five anchor/line reviews, and one catalogue-date
check. Reusing existing metadata and indexes avoided new NTVMR collection.
Per-verse source and writing-layer review remains the main repeated task; this
increment does not justify bulk collection or an automated survival classifier.

## Independent review questions

All answers are **unanswered**. For each item, record **agree**, **disagree**, or
**unable to assess**, plus corrections, reviewer identity, and date. Answers belong
in a separate human review record tied to `gal1-overlap-reviewed-v1`, the pinned
source hashes, and the indicated row; they must not overwrite this agent review.

| Claim to check | Source location and specific question | Expertise |
| --- | --- | --- |
| Physical identity | In the linked TEI header and pinned metadata, do GA 02, docID 20002, and Royal 1 D.VIII identify the same manuscript, distinct from P46? | Catalogue comparison |
| Page link | Does metadata page 1081 identify folio 127v, matching the TEI opening page and column 2 for all five reviewed portions? | Catalogue/TEI comparison |
| Galatians 1:1 partial survival | At TEI 127v, column 2, relative line 4, does νεκρων occur as surviving base text outside supplied or unclear content? | Greek/TEI |
| Galatians 1:2 partial survival | At the same location, relative line 5, does παντες support the recorded partial coverage? | Greek/TEI |
| Galatians 1:3 partial survival | At relative line 7, does ειρηνη support the recorded partial coverage? | Greek/TEI |
| Galatians 1:4 partial survival | At relative line 9, does εαυτον support the recorded partial coverage? | Greek/TEI |
| Galatians 1:5 partial survival | At relative line 14, does δοξα support the recorded partial coverage? | Greek/TEI |
| Date-source fidelity | Does metadata reproduce notation V and numeric bounds 400–499 without converting or narrowing them? | Catalogue comparison |
| Writing-layer applicability | Does the source support assigning only these anchors to original main writing, excluding the marginal inscription and later additions, and applying the codex assessment conditionally to them? | Greek and codicological expertise |

These checks do not ask reviewers to resolve manuscript dating disputes. Unanswered
questions remain open while prototype development continues. The next bounded
work is Sinaiticus page/layer review or a Pauline boundary/later-supplement case.
