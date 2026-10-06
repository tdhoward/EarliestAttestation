# Bounded P52 source and dating review

> **Historical record; scope superseded on 2026-10-05.** This document preserves
> earlier experiments and observations, not current development instructions or
> accepted scholarly claims. The project now records only explicit scholarly
> reports of dates and verse contents. Manuscript images, Greek transcriptions,
> word anchors, and our own writing-layer judgments must not be used to infer
> coverage or dates. Former human/specialist examination packets are withdrawn,
> not pending project tasks. Re-source or exclude agent-derived claims before
> reusing them in active results. Follow [AGENTS.md](../AGENTS.md) and the
> [current development plan](DEVELOPMENT_PLAN.md#next-development-work).

P52 is an example manuscript and regression-test fixture. This document preserves
the existing source review; it is not an active task to resolve P52's date.
The [project dating policy](../README.md#manuscript-dating-policy) supersedes the
former requirement to choose a preferred P52 interval after human adjudication.
Contributors are not qualified to settle manuscript dating disputes. Defer to
documented scholarly consensus where known; otherwise treat the sourced ranges
as equally valid possibilities. This review does not establish a consensus.

Reviewed by Codex on 2026-09-29. This is a fresh agent check of cited sources,
not independent human approval or a complete examination of the papyrus. The
machine-readable source review is
[`p52-dating-review-v2.json`](../benchmarks/p52-dating-review-v2.json).
The [v1 manifest](../benchmarks/p52-dating-review-v1.json) remains unchanged as
the record of the earlier three-source review.

## Inventory, identity, and surviving text

- The [publisher's NA28 John 18 page](https://www.die-bibel.de/bibel/NA28,UBS5,VUL/JHN.18)
  numbers John 18:30-39 individually. The bounded inventory records those ten
  coordinates, with explicit NTVMR mappings only for the five positive cases.
  This check does not validate the rest of NA28 or the five neighboring mappings.
- [CSNTM's P52 record](https://manuscripts.csntm.org/manuscript/Group/GA_P52)
  identifies a fragmentary Greek papyrus at Manchester under shelf number
  Gr. P. 457. Hurtado's [article](https://era.ed.ac.uk/bitstream/1842/648/2/P52_TB_article.pdf),
  introduction (p. 1), identifies P52 and P. Rylands Gk. 457 as the same fragment.
- Hurtado, p. 1, reports partial lines of John 18:31-33 on the recto and
  18:37-38 on the verso. The [Manchester catalogue search result](https://www.digitalviewer.manchester.ac.uk/search?keyword=Manchester&facetDate=0200s+C.E.)
  gives the same verses, although the catalogue page did not load reliably in this
  review. These five partial attestations match the pinned NTVMR index response
  and its pages 10 and 20. The response page IDs identify API records; they do
  not establish physical page numbering. The other five verses in the bounded
  inventory remain negative *index controls*, not reviewed physical absences.
- Hurtado, pp. 3 and 11, describes one surviving codex leaf and discusses the
  scribe across recto and verso. The extant text is therefore assigned one
  `original` writing unit in this bounded review. The consulted sources do not
  identify a separate correction or supplement here. This is a source-based
  interpretation, not a fresh image or handwriting examination.

## Competing dating observations

| Source and location | Source notation | Stored CE bounds | Use |
| --- | --- | --- | --- |
| [NTVMR captured metadata](../tests/fixtures/p52_language_probe.json), `lang=grc` response | `II (M)` | 125-175, as supplied by the API | Valid catalogue observation, unselected |
| [CSNTM manuscript details](https://manuscripts.csntm.org/manuscript/Group/GA_P52) | `2nd Century` | Unknown | Broad label; no inclusive bounds supplied |
| [Nongbri, *New Testament Studies* 66.4 (2020), abstract](https://doi.org/10.1017/S0028688520000089) | `extends into the third century` | Unknown | Widening caution; the accessible abstract supplies no numeric interval |
| [Barker, *New Testament Studies* 57.4 (2011), pp. 573-574](https://research-management.mq.edu.au/ws/portalfiles/portal/62382986/Publisher%2Bversion%2B%28open%2Baccess%29.pdf) | `II or III` | 101-300 | Full palaeographic argument; broad, valid assessment, unselected |

Nongbri's [author account](https://brentnongbri.com/2020/09/25/a-new-article-on-p52-in-new-testament-studies/)
also explains why some of Roberts's palaeographic comparisons need caution.
Only the article abstract and author account were accessible for this review;
neither provides a complete inclusive interval to enter. The NTVMR range was
recorded verbatim with its supplied bounds, without treating its narrower
catalogue observation as a consensus dating assessment.

Barker compares P52 with dated documentary hands across a long-lived script
tradition. His P52 discussion rejects a narrow placement and concludes that
second or third century is supportable; the article's conclusion reiterates the
limits of close palaeographic dating. The interval 101-300 CE is this project's
inclusive normalization of those two complete CE centuries. It is not a
statistical confidence interval, a claim that the endpoints were measured, or a
date derived from Nongbri's abstract. Barker discusses several dated comparanda,
including examples in 184, 190, 200, and 218-225 CE; those dates belong to the
comparanda, not to P52. The new assessment preserves Barker's `II or III`
notation and its source location alongside the numeric normalization.

Under `p52-cautious-source-v1`, the date selection remains explicitly `null`.
The normal replay links all five coverage reviews to the original writing unit,
but creates no selected-policy ranking snapshot. The offline exporter calculates
conditional rankings for both usable intervals. The integration test also
exercises a test-only selected-policy snapshot using Barker's interval.
Neither calculation gives an interval scholarly preference. Sourced ranges remain equally valid
possibilities unless documented consensus is known. Source descriptions without
usable numeric bounds remain visible without invented dates.

This fixture remains available for historical regression checks. Before reusing
its claims in active results, check attribution to explicit scholarly reports,
not the manuscript itself. The next work is the
[collection-to-chart pipeline](DEVELOPMENT_PLAN.md#next-development-work).
Neither a preferred P52 date nor independent manuscript certification is required.

## Scope of any future source check

No further P52-specific manuscript or dating investigation is a development
milestone. To reuse a record, identify the explicit scholarly assertion it copies
and preserve its citation, date notation, qualifications, and any documented
conversion. Verify copying and mapping only. Do not inspect images, read Greek
transcription text for survival, or infer a writing-unit assignment.

Preserve sourced date alternatives equally unless a cited source establishes
consensus. If explicit scholarly coverage reports disagree, mark the case
contested and defer it. An unsupported prior agent inference should be re-sourced
or excluded from active results, not treated as a scholarly disagreement. Follow
the [current development plan](DEVELOPMENT_PLAN.md#next-development-work).
