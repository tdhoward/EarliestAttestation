# P46 Galatians 1:1–5 source review

Reviewed 2026-10-02 UTC (2026-10-01 in the owner's timezone) by Codex.
Independent human validation: **pending**.

This is the first bounded Pauline papyrus increment. It adds five mapped
coordinates, one physical witness, five partial-coverage reviews, and two
conditional date assessments to the existing offline export/chart workflow.
It does not establish exhaustive discovery or the earliest witnesses to Galatians.
The [chart](../examples/gal1-p46-prototype.html) is a labeled research prototype.

## Sources and physical coverage

The primary transcription is the
[INTF P46 Galatians transcription published by ITSEE](https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_P46_Gal.xml).
Its header identifies P46 as document 10046, names both holding institutions,
records proofreading by Amy Myshrall on 2021-10-19, and gives a publication date
of 13.5.2024. It credits INTF and states a Creative Commons Attribution 4.0
license. The [pinned excerpt](../tests/fixtures/p46-gal1-transcription.json)
retains that header, attribution, source hash, and the first five verse elements.
Two closing container tags balance the otherwise verbatim body excerpt.

The [captured NTVMR metadata](../tests/fixtures/p46_metadata_probe.json) identifies
page **1421** as folio **81r**, with content `Eph 6:20-24; Gal inscriptio; Gal 1:1-8`.
The [captured index](../tests/fixtures/p46_coverage_probe.json) assigns each of
Galatians 1:1–5 to that page. The transcription begins at the same folio and
explicitly labels these five verses. These links establish the page attribution;
the index itself is not the physical evidence.

| Verse | Surviving base-text anchor | Lines counted from Galatians 1:1 |
| --- | --- | --- |
| Galatians 1:1 | παυλος | 1–3 |
| Galatians 1:2 | παντες | 3–5 |
| Galatians 1:3 | χαρις | 5–6 |
| Galatians 1:4 | αμαρτιων | 6–9 |
| Galatians 1:5 | δοξα | 9–10 |

These are relative text-line locations, not absolute manuscript line numbers.
Each anchor is a direct base-text word outside supplied, unclear, and apparatus
elements. There is no correction apparatus in these five verse elements.
The original-writing assignment applies to the cited surviving base text only.
In particular, supplied letters in 1:4–5 do not establish survival. All five
decisions are conservatively `partial`; none claims complete preservation or
exact NA28 wording.

The publisher's [NA28 Galatians 1 display](https://www.die-bibel.de/en/bible/NA28/GAL.1)
confirms numbered markers 1–5 and the passage identification. The new immutable
[subset inventory](../benchmarks/gal1-na28-subset-v1.json) agrees with the existing
whole-NT coordinate inventory. It does not modify or certify that larger snapshot.
The Michigan [variant discussion](https://apps.lib.umich.edu/files/collections/papyrus/exhibits/reading/Paul/variants.html)
also identifies textual differences within this passage. Verse attestation does
not require identical wording.

P46's Michigan Inv. Nr. 6238 and Chester Beatty CBL BP II holdings belong to one
codex, as identified by the transcription header and NTVMR metadata. They create
one physical witness, not two. No image download or inference from a protected
image was used. The Michigan reading introduction uses a different page-number
description; this review uses the explicitly reconciled **81r / 1421** pair.

## Conditional dates

| Assessment | Source notation | Numeric interval |
| --- | --- | --- |
| NTVMR P46 catalogue metadata | `III (A)` | 200–225 CE, copied from `originYear.early` / `late` |
| Michigan Papyrus Collection exhibit | `third century AD` | 201–300 CE, explicit century conversion |

The [Michigan dating discussion](https://apps.lib.umich.edu/files/collections/papyrus/exhibits/reading/Paul/perspective.html)
attributes its estimate to palaeography and acknowledges earlier/later proposals.
Its comment about the method's approximate precision is not converted into an
additional date range. NTVMR's numeric bounds are retained directly rather than
reconstructed from its abbreviation. Both source assessments concern the codex;
their use here is limited to the reviewed original writing.

Neither source establishes scholarly consensus. Both complete intervals remain
equal conditional alternatives, with no preferred scholar, merged endpoints,
or probabilities. Each verse therefore has two conditional endpoint charts,
each counting one witness. The replay leaves the selected-policy date null;
the ordinary exporter computes the alternatives. Further sourced assessments
can be added without settling the underlying dating dispute.

## Reproduction and verification

Use a fresh database destination. These commands make no network requests:

```powershell
python replay_gal1_p46.py --db data/gal1-p46-replay.sqlite --dry-run
python replay_gal1_p46.py --db data/gal1-p46-replay.sqlite
python audit_reviewed.py --db data/gal1-p46-replay.sqlite --benchmark benchmarks/gal1-p46-evidence-benchmark-v1.json
python export_attestation.py --db data/gal1-p46-replay.sqlite --inventory na28-gal1-p46-subset-v1 --policy gal1-p46-conditional-v1 --dataset-output data/gal1-p46-complete.json --graph-output examples/gal1-p46-graph-input.json
python render_attestation.py --graph-input examples/gal1-p46-graph-input.json --output examples/gal1-p46-prototype.html
python -m unittest discover -s tests -v
```

The replay validates source hashes, identity, folio, index pairs, surviving text
anchors, edition coordinates, and recorded date bounds before creating a database.
It uses the existing review APIs and schema. Only the captured raw metadata is
inserted into the response cache; normalized metadata and all evidence decisions
are created through the ordinary interfaces. Existing destinations are refused.

The fresh replay has zero structural audit findings and passes all five cited
benchmark cases. Static export/renderer checks verify five verses, both date
alternatives, source links, and one distinct witness per scenario. Tests reject
changed page links, identity, dates, and supplied-only or corrected anchors.
The full suite passes **96 offline tests**, retaining the John and P52 regressions.
These checks establish reproducibility, not independent historical validation.

| Measure | This increment |
| --- | ---: |
| New coordinates / explicit NTVMR mappings | 5 / 5 |
| Physical witnesses / positive witness–verse pairs | 1 / 5 |
| Original writing units / coverage assignments | 1 / 5 |
| Date assessments / alternatives per verse | 2 / 2 |
| Graphable verses / pending assignments in this scope | 5 / 0 |
| Cited benchmark cases / audit findings | 5 / 0 |
| NTVMR attempts during collection | 4: two direct timeouts, two proxy successes |
| Successful transcription downloads / replay network attempts | 1 / 0 |

Source discovery, reading, and page reconciliation took roughly five minutes
of agent/tool time, excluding implementation and testing. Web navigation also
checked the primary institutional pages. The first direct XML socket attempt
was restricted by the local sandbox; the permitted download then succeeded.
The NTVMR attempt history remains in ignored `data/p46-gal-collection.sqlite`;
the successful responses are pinned fixtures with actual transport provenance.
No whole-corpus sweep or local server was used.

Source interpretation and page reconciliation remain the repeated costs. This
small increment does not yet justify another importer or collection framework.

## Independent review questions

Answer **agree**, **disagree**, or **unable to assess**, with reviewer, date,
corrections, and exact source locations. Record eventual answers separately from
the Codex manifest; none is recorded here. Greek/transcription expertise is useful
for questions 1–2. These questions check faithful recording, not scholarly dating
preferences.

1. At folio 81r, do the five anchors in the table establish surviving Greek in
   each verse without relying on supplied or uncertain letters?
2. Are the cited anchors outside correction readings, supporting their assignment
   to original writing? Does `partial` avoid overstating the evidence in 1:4–5?
3. Do the transcription's folio 81r, NTVMR metadata page 1421, and five indexed
   verse/page pairs identify the same physical page?
4. Do the two named holding institutions describe one P46 codex, as recorded in
   the transcription header and catalogue?
5. Are the catalogue bounds and Michigan century conversion recorded faithfully,
   with the full alternatives and qualifications retained? No preferred date is
   requested.

## Next useful work

Add independently source-reviewed overlapping witnesses to this same five-verse
scope, checking each new writing layer and date's applicability. The existing
Galatians transcription collection provides candidates, not automatic coverage
approval. A later increment can exercise a Pauline survival boundary or a later
supplement. Keep the John review packets open and retain all existing regression
cases. Whole-NT discovery, mapping certification, the representative benchmark,
and human publication review remain separate unfinished requirements.
