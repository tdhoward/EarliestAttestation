# John 1:1–5 fifth-witness and later-supplement review

Reviewed 2026-10-05 by Codex. Independent human validation: **pending**.

The [five-witness chart](../examples/john1-five-witness-prototype.html) adds
Washingtonianus (GA 032) to the existing P66, P75, Sinaiticus, and Alexandrinus
reviews. All five verses now have five distinct physical witnesses, 25 cited
partial-coverage decisions, and one conditional dating combination. This supplies
the later-supplement case requested by the [development plan](DEVELOPMENT_PLAN.md#next-development-work).
The earlier [four-witness chart](../examples/john1-prototype.html), manifest, and
replay remain available.

## Identity, physical layer, and page link

The [IGNTP/ITSEE supplement transcription](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_032S_John.xml)
identifies **032S**, document key **20032**, and Smithsonian Institution, Freer
Gallery of Art, shelfmark **06.274**. The [Smithsonian collection record](https://collections.si.edu/search/detail/edanmdm%3Afsg_F1906.274)
identifies Washington Manuscript III / the Freer Gospels as **F1906.274**.
These shelfmark forms are retained; no separate physical witness is inferred
from the supplement siglum. The [IGNTP sigla explanation](https://itseeweb.cal.bham.ac.uk/iohannes/majuscule/sigla.html)
identifies suffix S as replacement leaves by a later hand.

The transcription opens on **folio 57r, column 1**. The newly captured
[NTVMR metadata](../tests/fixtures/washingtonianus_metadata_probe.json) identifies
**page 1130**, folio **57r Suppl**, indexed **John 1:1–15**. The
[captured coverage index](../tests/fixtures/washingtonianus_coverage_probe.json)
explicitly associates John 1:1–5 with that page. The supplement suffix is kept
alongside the transcription's shorter folio label. The index supports the
location link; the transcription supports survival.

J. Bruce Prior's [article opening](https://www.galaxie.com/article/bbr11-2-05),
*Bulletin for Biblical Research* 11.2 (2001), p. 233, “The Freer Gospels,” first
paragraph, identifies the replacement quire as covering John 1:1 through 5:11a.
The separately downloaded original-hand transcription begins at 5:11; its opening
is a source lead for a future boundary review, not evidence added here.
The publicly accessible article opening was sufficient for this bounded check;
the remainder requires a subscription and was not accessed.

The [pinned TEI excerpt](../tests/fixtures/washingtonianus-john1-transcription.json)
retains the full header and contiguous opening through John 1:5, with only two
balancing closing tags added. Its full-download SHA-256 is
`498a19869cf25fff8318fbef2b2bfa3281c4db6cb5bcd2c57f6d583d530dca6c`.
The header credits IGNTP, Catherine Smith's XML conversion, and ITSEE, records
version 2.1 (2013) and subsequent revisions through 2024-05-13, and supplies
CC BY 4.0 reuse terms. No manuscript image was inspected or reproduced.
Retrieval timestamps fall on 2026-10-06 UTC, corresponding to this review's
2026-10-05 date in America/Los_Angeles.

## Surviving text and writing-unit assignment

| Verse | Direct anchor | TEI line marker |
| --- | --- | --- |
| John 1:1 | αρχη | P57rC1L2-032S |
| John 1:2 | ουτος | P57rC1L3-032S |
| John 1:3 | παντα | P57rC1L4-032S |
| John 1:4 | αυτω | P57rC1L6-032S |
| John 1:5 | κατελαβεν | P57rC1L8-032S |

All five anchors are direct words outside apparatus, supplied or unclear letters,
abbreviation expansions, and marginal or inscription text. John 1:2 contains an
unclear letter elsewhere; the intact anchor does not rely on it. No correction
apparatus occurs within these five verse elements. Every decision remains
conservatively **partial**, without certifying whole-verse survival or exact NA28
wording.

All five coverage reviews link to `032-john-opening-supplement`, with kind
**supplement**, within physical witness `032-washingtonianus`. A `firsthand`
designation in this transcription refers to the writing of the replacement
quire; it does not establish original-codex writing or justify an earlier date.
The replay guards the reviewed anchors, identity, page, and line locations.
It is not a general TEI survival or hand classifier.

The existing immutable John 1 coordinate inventory and its five direct mappings
are reused. Its original scope description records the earlier subset's creation;
the new manifest and policy identify this five-witness expansion. The provisional
whole-NT inventory has not been changed or certified.

## Conditional supplement date

Prior qualifies the replacement quire's date as **perhaps to the seventh or
eighth century**. The [short source quotation and locator](../tests/fixtures/washingtonianus-supplement-date-source.json)
retain that qualification. Converting both complete centuries gives the single
conditional interval **601–800 CE inclusive**. No narrower range, probability,
preferred scholar, or independently established current consensus is asserted.
This is one recorded assessment, not exhaustive dating-source discovery.

NTVMR's manuscript-level `originYear` is **V**, **400–499 CE**. These fields remain
in the captured metadata and replay database. They are **not applied to the
opening replacement quire**, which receives the separately cited assessment.
The older witnesses retain their existing conditional date inputs.

| Scenario | P66 | P75 | 01 | 02 | 032 supplement |
| --- | ---: | ---: | ---: | ---: | ---: |
| Optimistic, CE | 101 | 201 | 301 | 400 | 601 |
| Pessimistic, CE | 300 | 300 | 400 | 499 | 800 |

These events apply to each of the five verses, counting each physical witness
once and reaching five witnesses only at the supplement event. No date is selected
in either policy. The exporter enumerates currently stored valid alternatives;
its `complete` state does not certify source discovery or historical validation.

## Offline reproduction and verification

Use a fresh database destination; the replay refuses existing paths. All commands
below use checked-in inputs without network requests:

```powershell
python replay_john1_supplement.py --db data/john1-five-witness-replay.sqlite --dry-run
python replay_john1_supplement.py --db data/john1-five-witness-replay.sqlite
python audit_reviewed.py --db data/john1-five-witness-replay.sqlite --benchmark benchmarks/john1-five-witness-evidence-benchmark-v1.json
python export_attestation.py --db data/john1-five-witness-replay.sqlite --inventory na28-john1-prototype-subset-v2 --policy john1-supplement-conditional-v1 --dataset-output data/john1-five-witness-complete.json --graph-output examples/john1-five-witness-graph-input.json
python render_attestation.py --graph-input examples/john1-five-witness-graph-input.json --output examples/john1-five-witness-prototype.html
python -m unittest discover -s tests -v
```

A fresh `data/john1-five-witness-check-20261005.sqlite` replay has **zero audit
findings**, passes **25/25 cited coverage cases**, and makes **zero replay network
attempts**. Six new regressions exercise actual supplement dating, anchor and
location changes, mistaken original-layer/date reuse, falsely asserted human
validation, safe dry runs and existing destinations, and a synthetic coverage
withdrawal. Withdrawing 032 at one verse leaves the other four witnesses there
and all five at neighboring verses. All **114 offline tests** pass, including
the retained P52, John 1, John 6, P46, and Galatians increments.
Automated checks establish reproducibility;
they do not constitute independent historical checking.

| Measure | This increment |
| --- | ---: |
| Added coordinates / reused mapped coordinates | 0 / 5 |
| Added physical witnesses / positive witness–verse pairs | 1 / 5 |
| Total physical witnesses / positive pairs | 5 / 25 |
| Added writing units / coverage assignments | 1 supplement / 5 |
| Added valid date assessments | 1 |
| Graphable verses / conditional combinations per verse | 5 / 1 |
| Controlled NTVMR requests / successful responses | 2 / 2 |
| University downloads for 032 / 032S | 1 / 1 |
| Replay network attempts / audit findings | 0 / 0 |
| Cited benchmark cases passed | 25 / 25 |

NTVMR collection used one worker, a two-attempt budget, and the project's existing
configured access proxy, with both responses retained in a separate ignored
collection database. Manual review covered five anchors and line locations,
one identity/page reconciliation, one writing-layer assignment, and one qualified
date-source check. About 30 seconds elapsed between the supplement-download
timestamp and the last index response. This measures that retrieval interval,
not source-reading time or total work. Source scouting also inspected a
Claromontanus transcription and unsuccessful Vaticanus leads; none contributed
evidence to this increment. End-to-end review effort was not separately timed.
The repeated cost remains source reading and per-verse layer assignment, so this
increment does not justify a new bulk-import framework. It uses the existing
schema, review APIs, exporter, and renderer.

## Independent review questions

All answers are **unanswered**. Record **agree**, **disagree**, or **unable to
assess**, with reviewer identity, date, notes, and corrections. Keep human answers
separate from Codex reviews and automated results. These questions check faithful
recording, not which scholar's dating argument should win.

1. **Identity and location:** does the [032S header](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_032S_John.xml)
   identify document 20032 and shelfmark 06.274, and does the
   [metadata capture](../tests/fixtures/washingtonianus_metadata_probe.json),
   page 1130, label the same opening folio as `57r Suppl`? Check the five explicit
   [index pairs](../tests/fixtures/washingtonianus_coverage_probe.json).
   Does the supplement belong to one physical Washingtonianus codex?
2. **Five survival decisions:** do the table's words and exact line markers in
   `John.1.1`–`John.1.5` support partial surviving Greek, independently of unclear,
   supplied, expanded, or marginal text? Compare the
   [pinned excerpt](../tests/fixtures/washingtonianus-john1-transcription.json)
   with the published transcription. Greek/TEI expertise may be needed.
3. **Layer applicability:** do the 032S identification, NTVMR supplement label,
   [IGNTP siglum convention](https://itseeweb.cal.bham.ac.uk/iohannes/majuscule/sigla.html),
   and Prior's p. 233 paragraph support assigning all five anchors to a replacement
   quire? Does keeping its writing separate from the original codex avoid claiming
   that `firsthand` automatically means the original codex's scribe?
   Specialist manuscript expertise may be needed.
4. **Date fidelity:** does [Prior's article opening](https://www.galaxie.com/article/bbr11-2-05),
   p. 233, first paragraph under “The Freer Gospels,” support the qualified
   seventh-or-eighth-century assessment and John 1:1–5:11a applicability?
   Does 601–800 preserve both complete centuries and the qualification, while
   keeping NTVMR's V / 400–499 metadata separate? Do not choose a preferred date.
5. **Graph and limits:** does the [chart](../examples/john1-five-witness-prototype.html)
   reproduce the event table, count 032 and its supplement once, and clearly retain
   partial survival, conditional dating, incomplete discovery, and pending human
   validation? Check all five verse rows.

The next useful source increment is a timed, small batch around the same codex's
John 5:11 supplement/original boundary, using both retrieved transcriptions and
explicit page links. No boundary claim is established here. Whole-NT mappings,
exhaustive discovery, broader benchmark coverage, and independent historical
publication review remain open.
