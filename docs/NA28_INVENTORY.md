# Provisional NA28 New Testament reference inventory

The current [v3 inventory manifest](../benchmarks/na28-nt-reference-provisional-v3.json)
contains reference coordinates for all 27 New Testament books and 260 chapters.
The [coordinate ledger](../benchmarks/na28-coordinate-source-v1.json) records the
publisher page and numbered markers for every chapter. The
[builder](../build_na28_inventory.py) reproduces the manifest from that ledger.
The [v2 review record](../benchmarks/na28-coordinate-review-v2.json) replaces the
1 Corinthians 4 fallback with a direct publisher NA28 check. The [v1 manifest](../benchmarks/na28-nt-reference-provisional-v1.json)
and its source ledger remain unchanged. The [v3 passage review](../benchmarks/na28-passage-identifications-v1.json)
identifies all 16 traditional skipped passages while leaving their NTVMR mappings unresolved.
Only verse coordinates and source metadata are retained; no edition text is copied.
This is a machine-checked, provisional inventory, not an independent editorial
certification of every NA28 verse or a complete NTVMR mapping.

The source is Deutsche Bibelgesellschaft's online *Novum Testamentum Graece*,
28th revised edition (2012). For example, its pages for
[Matthew 17](https://www.die-bibel.de/en/bible/NA28/MAT.17),
[John 5](https://www.die-bibel.de/en/bible/NA28/JHN.5), and
[2 Corinthians 13](https://www.die-bibel.de/en/bible/NA28/2CO.13)
show the coordinate markers and editorial gaps reflected here. The ledger links
each of the other 257 chapters individually. The publisher's
[Mark 16](https://www.die-bibel.de/en/bible/NA28/MRK.16),
[Luke 22](https://www.die-bibel.de/en/bible/NA28/LUK.22), and
[John 7–8](https://www.die-bibel.de/en/bible/NA28/JHN.7) displays provide the
double-bracketed passage markers recorded in the manifest.

The NA28 display for 1 Corinthians 4 repeatedly timed out during the v1 extraction,
so v1 used the publisher's [UBS5 page](https://www.die-bibel.de/en/bible/UBS5/1CO.4)
and marked its 21 coordinates `uncertain`. On 2026-09-30 the publisher's
[NA28 page](https://www.die-bibel.de/en/bible/NA28/1CO.4) displayed all 21
numbered markers directly. V2 marks those coordinates `main`; no NTVMR mapping
or manuscript coverage is inferred from this check. The publisher also provides a
[comparison of NA28 and UBS5](https://www.die-bibel.de/en/en/bible-society-and-biblical-studies/greek-new-testament/comparison-na28-ubs5/).
The combined publisher displays supplied the NA28 coordinate markers for
[John 11](https://www.die-bibel.de/bibel/NA28%2CLU17/JHN.11) and
[Philippians 4](https://www.die-bibel.de/bibel/NA28%2CUBS5/PHP.4).
The ledger records each exception and its exact page.

## Import result

On 2026-09-29, the v1 manifest was imported offline with the existing importer into
`data/na28-inventory-v1.sqlite`. On 2026-09-30, v2 was imported into
`data/na28-inventory-v2.sqlite`, and v3 into `data/na28-inventory-v3.sqlite`.
These local databases are ignored by Git; the
versioned manifests are the reproducible inputs. V2 has the same coordinate and
mapping counts, with 21 statuses changed from `uncertain` to `main`:

| Measure | Count |
| --- | ---: |
| Books / chapters | 27 / 260 |
| Publisher numbered verse markers | 7,941 |
| Skipped traditional coordinates retained as `omitted` | 16 |
| Total inventory coordinates | 7,957 |
| `main` / `bracketed` / `omitted` / `uncertain` (v2) | 7,915 / 26 / 16 / 0 |
| Source-checked NTVMR mappings | 5 |
| NTVMR mappings pending review | 7,952 |
| Duplicate coordinate IDs / foreign-key failures | 0 / 0 |

The first stored coordinate is `Matt.1.1`; the last is `Rev.22.21`.
The source display has 13 numbered verses in 2 Corinthians 13 and 15 in
3 John 1. No coordinate was inferred from the legacy KJV seed.

The 16 skipped coordinates are Matt.17.21, Matt.18.11, Matt.23.14,
Mark.7.16, Mark.9.44, Mark.9.46, Mark.11.26, Mark.15.28,
Luke.17.36, Luke.23.17, John.5.4, Acts.8.37, Acts.15.34,
Acts.24.7, Acts.28.29, and Rom.16.24. Here `omitted` means that the
publisher's NA28 chapter display skips the traditional number. It says nothing
about whether a manuscript contains text associated with that number.

The 26 `bracketed` coordinates are Mark 16:9–20, Luke 22:43–44, and
John 7:53–8:11. Luke 23:34 remains `main` with a note that the publisher
double-brackets only part of that verse. These status choices describe the
displayed edition and remain subject to independent editorial review.

The five NTVMR mappings are John 18:31–33 and 18:37–38, checked against the
[captured P52 response](../tests/fixtures/p52_coverage_probe.json). Every other
coordinate has an empty `ntvmr_refs` array and an explicit pending note. The
publisher's verse number alone does not prove how NTVMR indexes a witness.
In particular, omitted or bracketed edition coordinates are not physical
absence claims. The importer's `whole_nt_complete` report field is currently
always false; edition and mapping review are still outstanding.

## Supplementary collection and display policy

Retain the 16 skipped traditional coordinates and collect their manuscript
evidence as supplementary data. `omitted` is an edition-status tag, not a reason
to discard a candidate or its reviewed evidence. Apply the same coverage,
writing-layer dating, and distinct-witness counting standards as for the core
inventory. Establish dates and witness support individually; edition status does
not imply a late date or any particular amount of surviving evidence.

Before accepting coverage, cite a reference identifying the traditional passage
represented by each skipped coordinate and review its NTVMR mappings. A matching
verse number alone is insufficient, and the skipped NA28 number supplies no
main-text wording for comparison. Preserve relevant passage-boundary and wording
notes without expanding the project into exact-wording attestation.

The planned default graph excludes `omitted` coordinates and offers an **Include
verses omitted from NA28** option. Bracketed passages have a separate inclusion
control. Keep editorial uncertainty explicit. Record inclusion settings and the
resulting verse population in graph exports and summary counts; filtering a view
never deletes stored evidence. Distinguish edition omission from verified
manuscript absence, a physical lacuna, and unreviewed or missing indexing. A
filtered-out coordinate is not a zero-attestation result.

V3 cites the publisher's Lutherbibel 1912 displays for all 16 skipped
traditional passages. For example, [John 5](https://www.die-bibel.de/bibel/LU12/JHN.5)
labels the angel and stirred pool passage as verse 4. The publisher's
[NA28 John 5 display](https://www.die-bibel.de/en/bible/NA28/JHN.5) skips that
number. The [review record](../benchmarks/na28-passage-identifications-v1.json)
links each checked traditional passage and notes its location. The Romans 16:24
identification uses the publisher's indexed combined display because its direct
page did not load during review. These reviews do not claim
that a Greek manuscript preserves any of the passages. A one-request named NTVMR lookup for `John.5.4` and
`05` timed out on 2026-09-30; its mapping remains unresolved.

The current inventory supplies coordinate tags and 16 passage identifications;
it does not establish manuscript coverage. The offline exporter implements the
graph-data filters, but there is no graph UI. Positive coverage review for an
`omitted` coordinate requires its cited `passage_citation` and an explicit NTVMR
mapping. Existing immutable inventory snapshots remain
unchanged. Supplementary collection can
proceed alongside core collection, but its completion is not a prerequisite for
core NA28 dataset completion or publication. Report completeness separately for
the core and supplementary scopes, and apply the same validation requirements to
any supplementary evidence included in a published graph.

## Reproduce the inventory

To reproduce the manifest and import from a fresh checkout:

```powershell
python build_na28_inventory.py --check
python build_na28_inventory.py --review benchmarks/na28-coordinate-review-v2.json --check
python build_na28_inventory.py --review benchmarks/na28-coordinate-review-v2.json --passage-review benchmarks/na28-passage-identifications-v1.json --check
python sync_ntvmr.py --offline --db data/na28-inventory-v1.sqlite --import-inventory benchmarks/na28-nt-reference-provisional-v1.json --dry-run
python sync_ntvmr.py --offline --db data/na28-inventory-v3.sqlite --import-inventory benchmarks/na28-nt-reference-provisional-v3.json
python sync_ntvmr.py --offline --db data/na28-inventory-v3.sqlite --inventory-report na28-nt-reference-provisional-v3 --inventory-book John --inventory-limit 10
```

The importer is idempotent for each exact manifest. Corrections require new
inventory IDs because imported snapshots are immutable. The next work is to
check the other flagged editorial cases, identify the remaining skipped
traditional passages, and establish NTVMR mappings in a
separately reviewed, versioned snapshot. No manuscript dating judgment is involved.
