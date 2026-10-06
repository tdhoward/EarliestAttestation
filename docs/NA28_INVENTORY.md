# NA28 reference coordinates

`data/reference/na28.json` is the current provisional reference inventory:
7,957 coordinates across 27 books and 260 chapters, including 16 skipped
traditional coordinates tagged `omitted`. Of the rest, 7,915 are `main` and
26 are `bracketed`. The first coordinate is Matthew 1:1 and the last Revelation 22:21.

The source is Deutsche Bibelgesellschaft's online *Novum Testamentum Graece*,
28th revised edition (2012). `publisher-coordinates.json` records each chapter's
publisher URL and numbered markers; `coordinate-clarifications.json` records the
direct NA28 check for 1 Corinthians 4; `passage-identifications.json` supplies
cited identification of the traditional skipped coordinates. These are source
records for the current inventory, not alternate chart datasets. No edition text
is reproduced.

The publisher reports 13 numbered verses in 2 Corinthians 13 and 15 in 3 John 1.
Bracketed passages retain their edition qualifications, including the partial-verse
qualification at Luke 23:34. An omitted or bracketed editorial status says nothing
about a manuscript's contents or date.

The inventory carries no witness coverage or preapproved NTVMR mappings.
`build_collection.py` maps only exact OSIS references observed in explicit
collected reports. Unknown mappings stay unresolved. No neighboring verse or
broad summary is expanded beyond documented source semantics.

Rebuild the current reference file with `python build_na28_inventory.py`, or
verify it without writing with `python build_na28_inventory.py --check`.
Then use `python build_collection.py` to update the app's data. All steps are offline.
