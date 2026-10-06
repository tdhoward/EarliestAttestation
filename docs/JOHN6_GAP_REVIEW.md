# John 6:49–53 survival-boundary review

> **Historical record; scope superseded on 2026-10-05.** This document preserves
> earlier experiments and observations, not current development instructions or
> accepted scholarly claims. The project now records only explicit scholarly
> reports of dates and verse contents. Manuscript images, Greek transcriptions,
> word anchors, and our own writing-layer judgments must not be used to infer
> coverage or dates. Former human/specialist examination packets are withdrawn,
> not pending project tasks. Re-source or exclude agent-derived claims before
> reusing them in active results. Follow [AGENTS.md](../AGENTS.md) and the
> [current development plan](DEVELOPMENT_PLAN.md#next-development-work).

Source review: 2026-10-02 UTC (2026-10-01 in the project owner's timezone).
Reviewer: Codex. Independent human validation: **pending**.

At the time of this increment, the project had a collection, review, ranking,
export, and chart path built around the now-superseded examination workflow.
The increment exercised a transcription interpretation using those interfaces;
it did not change the schema, collector, dating policy, or legacy databases.

## Evidence and limits

| Coordinate | P66 | Alexandrinus (02) | P75 (added in v2) |
| --- | --- | --- | --- |
| John 6:49 | Surviving base text, P40 C1 lines 15–17 | Surviving base text, P70v C2 lines 48–50 | Partial base text, P52r C1 lines 27–29 |
| John 6:50 | Surviving base text, P40 C1 lines 17–19 | Surviving beginning, P70v C2 lines 50–51; ending lost | Partial base text, P52r C1 lines 29–31 |
| John 6:51 | Surviving beginning, P40 C1 lines 20–21 | Inside physical lacuna | Partial base text, P52r C1 lines 31–36 |
| John 6:52 | Surviving base text, P41 C1 lines 4–7 | Inside physical lacuna | Partial base text, P52r C1 lines 36–39 |
| John 6:53 | Surviving base text, P41 C1 lines 7–11 | Inside physical lacuna | Partial base text, P52r C1 lines 39–43 |

The direct sources are the IGNTP transcriptions of
[P66](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_P66_John.xml),
[P75](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_P75_John.xml),
and [Alexandrinus](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_02_John.xml).
The [transcription viewer](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/)
explains supplied text, corrections, and other display conventions. The current
XML uses `John.6.49`-style verse labels; the older P66 XML used by the John 1
review uses `B04K6V49`-style labels. Neither source was silently substituted in
the earlier review.

The Alexandrinus transcription explicitly marks the remainder of John 6:50
as `gap reason="lacuna"`, then moves to folio 73r and John 8:52 with an opening
lacuna. Read together, these boundary markers support the reviewed absence of
6:51–53. Missing API rows alone would not support that decision. The surviving
beginning of 6:50 counts; no claim is made about the lost wording or the cause
of the physical loss. This review makes no positive writing-layer claim for
8:52, which has an apparatus reading at the resumption.

P66's 6:51 crosses pages 40 and 41. This review deliberately cites only its
page-40 portion, so it records one witness/verse decision rather than duplicate
page evidence. At 6:52 the XML has a firsthand correction; surviving base text
outside that apparatus suffices for the positive decision. That correction is
neither dated separately nor used to establish survival.

P75's folio 52r includes many supplied or uncertain letters. Each positive claim
uses identifiable surviving base text: `εφαγον` at 6:49 (line 28), `και` at 6:50
(line 31), `τις` and `εκ` at 6:51 (line 33), `προς` at 6:52 (line 37), and
`αυτου`, `αιμα`, `ουκ`, `εχετε` at 6:53 (line 42). These anchors lie outside
supplied and unclear spans. The five verse elements contain no correction
apparatus. This is an agent reading of the scholarly transcription, not a fresh
image examination or certification of all its letters.

The captured NTVMR metadata links P66 pages 360/370 to folios 40/41,
Alexandrinus page 531 to folio 70v, and P75 page 790 to folio 52r (indexed
John 6:38–54). Individual index entries confirm the twelve
positive verse/page pairs. Five direct coordinate mappings are imported into a
new bounded inventory; the provisional whole-NT inventory remains unchanged.
All positive decisions are conservatively `partial`.

The three attributed, contiguous XML excerpts are retained under the sources'
CC BY 4.0 terms, with original-source and excerpt SHA-256 values:

- [P66 excerpt](../tests/fixtures/p66-john6-transcription.json), John 6:48–53.
- [Alexandrinus excerpt](../tests/fixtures/alexandrinus-john6-transcription.json),
  the contiguous sequence John 6:48–50, 8:52–53, including the gap transition.
- [P75 excerpt](../tests/fixtures/p75-john6-transcription.json), John 6:47–53;
  the preceding verses retain the initial line-location context.

New writing-unit records identify the original copying at these locations.
They preserve the already recorded P66, P75, and Alexandrinus catalogue assessments
from [John 1 review v3](../benchmarks/john1-reviewed-v3.json), including P66's
unrankable qualitative date. Applicability to the base writing is a new Codex
review; the cited dates were not independently re-researched. The numeric ranges
remain conditional: P66 101–300 CE, P75 201–300 CE, Alexandrinus 400–499 CE.
P75's qualitative “early third century” observation also remains unrankable.
Consensus remains
unknown. Separate units describe the reviewed locations without asserting a
different scribe or copying period.

## Reproduction and measurements

Use the [README commands](HISTORICAL_REPLAY_GUIDE.md#john-6-survival-boundary-prototype).
The replay creates a fresh database, first rebuilding the fixed John 1 v3 inputs
to reuse their identities and cached indexes, then importing the John 6 inventory
and review. It refuses an existing destination. John 1 evidence remains in its
own inventory; the John 6 export contains only the five new coordinates.

The original v1 increment measured:

| Measure | Result |
| --- | ---: |
| Added coordinates and direct mappings | 5 |
| Reviewed physical witnesses in this passage | 2 |
| Added positive witness/verse decisions and unit assignments | 7 each |
| Added direct absence decisions | 3 |
| Added writing units / carried-forward date observations | 2 / 3 |
| Graphable coordinates | 5 |
| Witness counts in both endpoint scenarios | 2, 2, 1, 1, 1 |
| New NTVMR requests / offline replay requests | 0 / 0 |
| Successful direct transcription downloads | 2 |
| Source retrieval and reading elapsed time | Approximately 4 minutes |
| New cited benchmark | 10 cases: 7 positive, 3 absent |
| Fresh replay audit findings | 0 |

Timing covers source retrieval, reading the bounded XML, and reconciling page
metadata; it is approximate and includes tool overhead, not an estimate of human
review speed. One local socket attempt was denied by the sandbox before the two
successful downloads. Web source navigation was also used. No NTVMR collection
run, bulk download, local server, or protected-image access was needed.

The ten decisions are explicit manifest rows applied by existing review APIs;
there are no manual SQL inserts. The replay checks source hashes, verse sequence,
explicit gap markers, and page/folio links before creating a database. These
checks preserve the reviewed inputs; they do not independently validate the
scholarly transcription. The new tests exercise the real boundary, withdrawal,
incorrect page attribution, loss of the lacuna anchor, and preservation of an
existing destination. All **88 offline tests** pass, and the retained John 1
benchmark still passes all 20 cases.

## Independent review questions

> **Withdrawn packet.** The questions below are preserved solely as historical
> context. Do not carry out their image, Greek-text, survival, or hand-identification
> checks, and do not ask the owner or a specialist to complete them for this
> project. Optional human checks now concern accurate copying of explicit
> published reports only.

These questions are ready for a human reviewer, but no answers or approval are
recorded. Answer each **agree**, **disagree**, or **unable to assess**, with any
correction and its source location. Agreement with source recording does not
settle a manuscript's date. Greek/transcription expertise is useful for questions
1–3; selecting “unable to assess” leaves them open without blocking development.

1. In the linked Alexandrinus XML, inspect `John.6.49` and `John.6.50`, P70v C2
   lines 48–51. Does identifiable surviving Greek precede the lacuna in both
   verses, supporting `partial` coverage rather than absence for 6:50?
2. Inspect the contiguous `John.6.50` → `John.8.52` transition, its two explicit
   lacuna markers, and page break to 73r. Does it support physical absence of
   John 6:51–53, rather than merely missing indexing or an omitted verse reading?
3. In P66's `John.6.49`–`John.6.53`, inspect the locations in the table. Does base
   text on those pages establish survival without relying on supplied text or
   the correction at 6:52? Does the page-40 portion alone support the 6:51 review?
4. Compare those page labels with the captured
   [P66 metadata](../tests/fixtures/p66_metadata_probe.json) and
   [Alexandrinus metadata](../tests/fixtures/alexandrinus_metadata_probe.json).
   Do page IDs 360, 370, and 531 identify the cited locations faithfully?
5. Compare the chart's full conditional intervals with the cited catalogue
   assessments in [John 1 v3](../benchmarks/john1-reviewed-v3.json). Are the
   inherited ranges, qualitative uncertainty, and original-writing applicability
   recorded faithfully? No preference among scholars is requested.
6. In the [P75 XML](https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_P75_John.xml),
   inspect John 6:49–53 at P52r C1 lines 27–43. Do the surviving anchors listed
   above establish partial coverage without relying on supplied or uncertain
   letters? Greek/transcription expertise is useful; this is not a complete
   transcription check.
7. Compare the [P75 metadata](../tests/fixtures/p75_metadata_probe.json), page
   790, folio 52r, and its `John 6:38-54` content with the XML line labels and
   [captured verse index](../tests/fixtures/p75_coverage_probe.json). Does the
   mapping faithfully link all five reviews to that page?

Record eventual human answers separately from the Codex manifest, with reviewer,
date, question number, answer, correction/source, and unresolved points. This
packet is a document, not a new review application or a completed review.

## Third witness increment (v2), 2026-10-02 UTC

The [v2 review](../benchmarks/john6-gap-reviewed-v2.json) adds P75 using the same
interfaces. The original v1 manifest and ten-case benchmark are unchanged and
remain replayable with `--review`. The new default replay and chart use v2.

| Measure | v2 result |
| --- | ---: |
| Reviewed physical witnesses in this passage | 3 |
| Positive / physical-absence pairs | 12 / 3 |
| Added P75 coverage decisions and unit assignments | 5 each |
| Added writing units / carried-forward date observations | 1 / 2 |
| Graphable coordinates / new coordinate mappings | 5 / 0 |
| Witness counts in both endpoint scenarios | 3, 3, 2, 2, 2 |
| Pending mappings / positive unit assignments in this scope | 0 / 0 |
| New NTVMR collector attempts / offline replay attempts | 2 / 0 |
| Successful transcription downloads | 1 |
| Source retrieval, reading, and page reconciliation | Approximately 5 minutes |
| Cited benchmark cases / fresh audit findings | 15 / 0 |
| Offline tests passing | 91 |

The direct NTVMR attempt timed out and remains pending in the ignored
`data/p75-john6-collection.sqlite`. One separately budgeted attempt through the
existing local access proxy succeeded; the fixture preserves that provenance
and the canonical endpoint. A web-tool metadata navigation was unavailable.
The XML web preview did not support its content type; one sandbox socket attempt
was denied, then the permitted direct download succeeded. No bulk collection or
protected-image access occurred. Timing is approximate agent/tool elapsed time,
not human review speed; implementation and testing are excluded.

Source interpretation and page reconciliation remain the repeated costs. Five
explicit review rows, one source excerpt, and one metadata capture were sufficient;
no schema change, new importer, or manual SQL evidence inserts were needed.
Tests reject supplied-only verse material, altered transcription page labels,
wrong metadata foliation, and wrong manuscript identity before creating a database.
The retained John 1 benchmark still passes all 20 cases. Dates remain conditional,
and independent human answers to all seven questions remain pending.

## Next useful increment

The former examination increment is withdrawn. Use the
[current collection-to-chart plan](DEVELOPMENT_PLAN.md#next-development-work).
Capture explicit scholarly contents/date reports, defer unknown and contested
cases, and do not extend this document's manuscript-examination workflow.
