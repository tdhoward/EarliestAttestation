# Bounded graph scope and development log

## Several-witness target

Use **John 1:1–5** as the first several-witness passage. These five coordinates
are in the provisional NA28 inventory. The [captured named NTVMR probes](../tests/fixtures/john_named_probe.json)
returned P66, P75, 01, and 02 at John 1:1, but those hits are candidates only.
The first three witnesses reviewed were P75, Codex Sinaiticus (01), and P66.
The fourth-witness increment below adds 02 from a checked image and a captured
page link. No coverage decision follows from the scope declaration itself.

Source leads checked on 2026-09-30:

| Witness | Source lead | Review status |
| --- | --- | --- |
| P75 | [Vatican Library discussion of the John 1:1–18 leaf](https://www.vaticanlibrary.va/moduli/BodmerFarina_ing.pdf), pp. 1–3, including its transcription | Verse and writing-unit review completed in the 2026-10-01 prototype increment |
| 01 | [Codex Sinaiticus project manuscript page for John 1:1–38](https://www.codexsinaiticus.org/en/manuscript.aspx?book=36&chapter=1) and its [date explanation](https://www.codexsinaiticus.org/en/codex/date.aspx) | Verse and scribe A review completed in the 2026-10-01 prototype increment |
| P66 | [CSNTM Bodmer II manuscript record](https://manuscripts.csntm.org/Manuscript/Group/GA_P66_Bodmer) and [IGNTP transcription](https://epapers.bham.ac.uk/id/eprint/1759/) | Greek identity, verse, and original-writing review completed in the 2026-10-01 prototype increment |
| 02 | [Captured named NTVMR candidate response](../tests/fixtures/john_named_probe.json); [British Library catalogue](https://searcharchives.bl.uk/catalog/040-002353500); [INTF opening John image](https://ntmss.info/images/webfriendly/20002/20002x00490XX_INTF.jpg) | Five image-checked verse reviews, page link, main-writing unit, and catalogue date added in the fourth-witness increment |

The versioned John 1 replay manifest records source-checked NTVMR mappings,
physical identities, cited verse coverage, original writing units,
coverage-unit links, and date assessments. Consensus status is explicitly
unknown for each reviewed witness; the numeric outcomes are conditional on
the cited catalogue ranges. All four named candidates now have positive coverage
reviews for this scope; discovery beyond those names remains incomplete.

## Measured graph increment, 2026-09-30

The first chart used the existing cited P52 replay to exercise the ordinary path.
Its input and output are reproducible by the [README commands](../README.md#reviewed-data-audit-and-p52-replay).
The fresh `data/p52-graph-preview.sqlite` replay is separate from previously
inspected databases.

| Measure | Result |
| --- | ---: |
| Included coordinates | 10 John 18 verses |
| Source-reviewed physical witnesses | 1 |
| Positive witness/verse pairs | 5 |
| Graphable coordinates | 5 |
| Coordinates with unresolved mapping | 5 |
| Coverage-unit assignments replayed | 5 |
| Valid numeric date assessments | 2 of 4 stored observations |
| Conditional global chart cases | 2 |
| Network attempts in this increment | 0 |
| Fresh replay audit findings | 0 |

The source-review time for the earlier P52 evidence was not recorded, so it
cannot be inferred from this replay. The largest repeated cost is not yet
measured; record page and mapping review time and manual actions during John 1
collection before building batch import rules. The P52 chart has one witness and therefore does
not satisfy the several-witness milestone.

## John 1 three-witness increment, 2026-10-01

The [review manifest](../benchmarks/john1-reviewed-v1.json) cites the IGNTP P66
transcription, Vatican Library P75 transcription, and Codex Sinaiticus Project
transcription. The [new inventory snapshot](../benchmarks/john1-na28-subset-v2.json)
records five direct NTVMR mappings, supported by the P66, P75, and 01 captured
index responses. The [offline replay](../replay_john1_prototype.py) applies those
reviews and produces the [static graph](../examples/john1-prototype.html).

| Measure | Result |
| --- | ---: |
| Included coordinates | 5 John 1 verses |
| Source-reviewed physical witnesses | 3: P66, P75, 01 |
| Positive witness/verse pairs | 15, conservatively partial |
| Graphable coordinates | 5 conditional cases |
| Pending mappings in this subset | 0 |
| Coverage-unit assignments replayed | 15 |
| Date observations | 6, three complete numeric intervals |
| Conditional combinations per verse | 1 |
| Retained search candidates pending verse review | 1: 02 |
| NTVMR attempts during this increment | 4: two TLS failures and two successful index responses |
| Fresh replay network attempts | 0 |
| Fresh replay audit findings | 0 |

The two TLS failures occurred before a trusted CA bundle was configured; no
response from them was treated as evidence. The source review was not separately
timed, so a reliable minutes-per-verse measure is unavailable. The visible
repeated actions were 15 coverage decisions and 15 writing-unit assignments;
the manifest replay now applies them without manual SQL. Review of each source
and physical page remains the largest human task. The displayed interval
rankings are conditional, and no independent human publication review or
exhaustive discovery has occurred. The next bounded work is listed in the
[development plan](DEVELOPMENT_PLAN.md#next-development-work).

## Source and identity check, 2026-10-01

The [v2 review manifest](../benchmarks/john1-reviewed-v2.json) adds a cited
identity review for 02. The British Library identifies Royal MS 1 D VIII as
Codex Alexandrinus (GA 02), a fifth-century Greek parchment codex, and lists
John on folios 42r–55v. Its catalogue says the digital images are currently
unavailable. [CSNTM's GA 02 viewer](https://manuscripts.csntm.org/manuscript/Group/GA_02)
lists a John 1:1 facsimile image from the British Museum's older photographic
edition; that image is a lead for the next physical review. A book-level folio
range or image label does not establish physical survival in
each of John 1:1–5, so 02 has no coverage review, writing unit, or ranked date.
The replay remains offline and the chart still has three reviewed verse witnesses.
The fresh v2 replay records four physical identities, 15 positive
witness/verse reviews from three witnesses, and zero network attempts. Its
reviewed-data audit reports zero findings.

The [IGNTP P66 transcription](https://epapers.bham.ac.uk/id/eprint/1759/)
has surviving Greek in each John 1:1–5 verse element, with no separate
correction reading inside those elements. The [captured P66 index](../tests/fixtures/p66_coverage_probe.json)
lists all five verses against both page IDs 3 and 10. The [captured NTVMR
metadata](../tests/fixtures/p66_metadata_probe.json) labels page ID 10 as folio
1 containing John 1:1–14; page ID 3 has no folio label. The v2 replay verifies
that page link before using page ID 10. This source check was performed by Codex;
it is not independent human validation.

## Fourth witness and regression benchmark, 2026-10-01

The [v3 review](../benchmarks/john1-reviewed-v3.json) adds Alexandrinus (02) to
each of John 1:1–5. Codex inspected the [public INTF microfilm image](https://ntmss.info/images/webfriendly/20002/20002x00490XX_INTF.jpg):
the right column contains identifiable surviving portions of verse 1 on lines
1–3, verse 2 on line 3, verse 3 on lines 4–6, verse 4 on lines 6–7, and verse 5
on lines 8–10. The decisions remain conservatively `partial`. They use the
continuous main writing and do not depend on a marginal correction. No exact
wording match or attribution to a named scribe is asserted.

The [captured index](../tests/fixtures/alexandrinus_coverage_probe.json) maps
all five verses to page 490. The [captured metadata](../tests/fixtures/alexandrinus_metadata_probe.json)
links that page directly to the inspected public image and labels it `66r`.
The image itself also bears the number 42; the British Library calls the John
opening `42r`. Both labels are retained, with no general foliation conversion.
The review pins the image URL and SHA-256; the image is not redistributed.
Offline replay checks the captured page and image link, while verification of
the physical reading remains a cited source-review decision.

The British Library record supplies an explicit numeric interval of 400–499 CE
alongside its fifth-century label. The replay preserves those numeric fields;
it does not silently replace them with 401–500. The date is applied only to the
reviewed main writing and remains conditional. The [IGNTP dates table](https://itseeweb.cal.bham.ac.uk/iohannes/majuscule/dates.html)
also reports a fifth-century consensus in its edition; representing dated
consensus claims and checking their applicability remains part of the planned
source-fidelity review. This increment does not assert independently established
current consensus.

| Measure | Result |
| --- | ---: |
| Included coordinates | 5 John 1 verses |
| Source-reviewed physical witnesses | 4: P66, P75, 01, 02 |
| Positive witness/verse pairs and writing-unit assignments | 20 each |
| Added coverage decisions and assignments | 5 each |
| Date observations | 7, four complete numeric intervals |
| Conditional combinations per verse | 1 |
| Pending coverage among the four named candidates | 0 |
| NTVMR attempts | 4: two TLS failures, two successful responses |
| Offline replay network attempts | 0 |
| Cited coverage benchmark | 20 cases |
| Fresh replay audit findings | 0 |
| Coverage benchmark passed | 20 of 20 |
| Offline test suite | 81 passed |

The CA problem was resolved with the installed trusted certificate bundle while
keeping TLS verification enabled. CSNTM's image routes returned errors; the
public INTF image linked by the metadata was accessible. No protected image was
used. Retrieval and source-reading time were not separately measured. The five
new coverage decisions and five writing-unit assignments are applied by the same
manifest loop as the earlier witnesses, without manual SQL. Locating a usable
source image and reconciling its page labels were the repeated review costs.

The [evidence benchmark](../benchmarks/john1-evidence-benchmark-v1.json) pins
20 positive partial-coverage expectations with citations. It makes no selected
date claim. Regression tests check the conditional endpoint results and show
that a withdrawal fails its benchmark case and removes the witness from both
rankings. Duplicate witnesses and mismatched page/image links are rejected before
database creation. The replay refuses an existing destination, and `--review`
can rebuild v2's three-witness result into a separate database.

These changes expand the reviewed prototype, not historical certification.
Independent human checking remains open. The next useful expansion is a small
passage with a physically reviewed gap or correction, followed by a measured
batch of mappings and coverage; no new collection framework is needed for that.

## Evidence export review, 2026-10-01

The project review confirmed that source work is now the main constraint: the
four-witness John 1 replay works, but its uniformly positive coverage does not
exercise a real gap. Code inspection found that direct physical-absence decisions
were checked by the audit and ranking code but omitted from exports and the
chart. Fixing that omission is a prerequisite for displaying the planned gap case.

The exporter now carries the latest coverage and physical-absence reviews for
every coordinate, including unmapped, undated, uncertain, withdrawn, rejected,
stale, and conflicting reviews. Citations, source locations, reviewer identity,
and timestamps survive export. Positive and absent witness/verse counts exclude
conflicts and follow the active graph filters. The chart lists physical evidence
separately from dating results and explicitly identifies coordinates without a
review. No new schema, collection framework, or historical review was introduced.

All **84 offline tests** pass, including absence-only unmapped coordinates,
supplementary filters, withdrawal and uncertainty, conflicting evidence,
undated positives, stale identity links, and older graph-input compatibility.
A fresh temporary John 1 replay produced 20 positive witness/verse pairs,
zero network attempts, zero audit findings, and 20 passing benchmark cases.
The [example chart](../examples/john1-prototype.html) was rebuilt from that replay.
Existing local collection databases were not changed. Static verification was
used; no local server was started.

The next source increment remains a small passage with varying survival,
including a directly checked gap or correction. Use the existing review and
replay interfaces, record the source-reading time, and add cited positive and
negative expectations to the benchmark. The new synthetic absence checks verify
software behavior only and must not be counted as historical gap reviews.

## John 6 survival boundary, 2026-10-02 UTC

The next source increment is now implemented as the
[John 6:49–53 replay](../replay_john6_gap.py) and
[chart](../examples/john6-gap-prototype.html). The
[source review](JOHN6_GAP_REVIEW.md) records seven positive decisions and three
physical-absence decisions from bounded IGNTP transcription excerpts. In
Alexandrinus, the surviving start of 6:50 counts, while 6:51–53 lie wholly in the
explicitly marked lacuna. P66 supplies positive coverage for all five verses.

All 88 offline tests pass; the new ten-case benchmark and retained 20-case John 1
benchmark pass with zero findings on a fresh replay. The new inventory adds five
direct mappings without changing the provisional whole-NT snapshot. The source
review includes measured effort and a five-question independent human-review
packet. Human answers remain pending. A third witness at this boundary is the
next bounded expansion.

## John 6 third witness, 2026-10-02 UTC

The [v2 review](../benchmarks/john6-gap-reviewed-v2.json) adds five partial P75
decisions on folio 52r, linked to NTVMR page 790. Surviving base text establishes
the positives independently of supplied or uncertain letters. Its inherited
201–300 CE interval is conditional; the qualitative date remains unrankable.
The chart now shows counts of 3, 3, 2, 2, 2, with twelve positives and the same
three Alexandrinus physical absences. The v1 replay remains available.

All 91 offline tests and the fifteen-case John 6 benchmark pass. The retained
20-case John 1 benchmark passes, with zero fresh audit findings. One transcription
download, two budgeted metadata attempts, and approximately five minutes of
source retrieval and page reconciliation supported this increment; the
[source review](JOHN6_GAP_REVIEW.md) records access outcomes and adds two specific
human-review questions. Independent answers remain pending. The next bounded
expansion is a Pauline papyrus or later supplement, using existing review APIs.
