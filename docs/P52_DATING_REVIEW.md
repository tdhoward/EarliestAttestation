# Bounded P52 source and dating review

Reviewed by Codex on 2026-09-29. This is a fresh agent check of cited sources,
not independent human approval or a complete examination of the papyrus. The
machine-readable decision is
[`p52-dating-review-v1.json`](../benchmarks/p52-dating-review-v1.json).

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

Nongbri's [author account](https://brentnongbri.com/2020/09/25/a-new-article-on-p52-in-new-testament-studies/)
also explains why some of Roberts's palaeographic comparisons need caution.
Only the article abstract and author account were accessible for this review;
neither provides a complete inclusive interval to enter. The NTVMR range was
recorded verbatim with its supplied bounds, without treating its narrower
catalogue observation as a consensus dating assessment.

Under `p52-cautious-source-v1`, the date selection is explicitly `null`.
No P52 ranking is computed. Selecting a rankable scholarly date would require
a defensible complete interval and a documented source and policy decision.
The five coverage reviews are not yet linked to the writing unit; that link is
reserved for the dated ranking replay once the selection is resolved. A separate
human check of the physical evidence and dating interpretation remains open.
