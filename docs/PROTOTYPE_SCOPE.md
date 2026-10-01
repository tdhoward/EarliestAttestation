# Bounded graph scope and development log

## Several-witness target

Use **John 1:1–5** as the first several-witness passage. These five coordinates
are in the provisional NA28 inventory. The [captured named NTVMR probes](../tests/fixtures/john_named_probe.json)
returned P66, P75, 01, and 02 at John 1:1, but those hits are candidates only.
The first three witnesses to review are P75, Codex Sinaiticus (01), and P66.
Retain 02 as a discovered candidate pending its own review. No manuscript-to-verse
mapping or positive coverage decision follows from this scope declaration.

Source leads checked on 2026-09-30:

| Witness | Source lead | Review status |
| --- | --- | --- |
| P75 | [Vatican Library discussion of the John 1:1–18 leaf](https://www.vaticanlibrary.va/moduli/BodmerFarina_ing.pdf), pp. 1–3, including its transcription | Passage-level primary source located; individual verse and writing-unit decisions still need review and an NTVMR page mapping |
| 01 | [Codex Sinaiticus project manuscript page for John 1:1–38](https://www.codexsinaiticus.org/en/manuscript.aspx?book=36) and its [date explanation](https://www.codexsinaiticus.org/en/codex/date.aspx) | Primary facsimile/transcription and broad date located; page-level coverage, writing layer, and mapping still need review |
| P66 | [CSNTM Bodmer II manuscript record](https://manuscripts.csntm.org/Manuscript/Group/GA_P66_Bodmer) | Greek physical identity and broad catalogue dating lead located; inspect John 1 images and verse boundaries before recording coverage |
| 02 | [Captured named NTVMR candidate response](../tests/fixtures/john_named_probe.json) | Discovery candidate only; retain while checking source and scope |

Record each witness in a versioned replay manifest with source-checked NTVMR
mapping, physical identity, cited verse coverage, original writing unit,
coverage-unit links, and date assessments. Mark consensus status as documented
or unknown from a cited source, preserving alternatives where consensus is not
known. The cited pages above are leads, not preapproved coverage or dates.

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
