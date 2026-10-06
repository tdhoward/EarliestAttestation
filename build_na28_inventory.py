#!/usr/bin/env python3
"""Build a reference-only NA28 inventory from the pinned publisher coordinate ledger."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from controlled_ntvmr import NT_BOOKS, validate_inventory


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data/reference/publisher-coordinates.json"
OUTPUT = ROOT / "data/reference/na28.json"
REVIEW = ROOT / "data/reference/coordinate-clarifications.json"
PASSAGE_REVIEW = ROOT / "data/reference/passage-identifications.json"
INVENTORY_ID = "na28-nt-reference-provisional-v1"
PUBLISHER_CODES = (
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL",
    "EPH", "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM",
    "HEB", "JAS", "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
)


def ref_key(ref: str) -> tuple[int, int, int]:
    book, chapter, verse = ref.split(".")
    if book not in NT_BOOKS:
        raise ValueError(f"Unknown New Testament book: {book}")
    return NT_BOOKS.index(book), int(chapter), int(verse)


def apply_coordinate_review(source: dict, review: dict) -> dict:
    """Apply a cited direct NA28 check without changing the pinned v1 ledger."""
    if set(review) != {"format_version", "base_inventory_id", "inventory_id",
                       "source_url", "reviewed_on", "reviewer", "osis_book",
                       "chapter", "verse_numbers", "note"}:
        raise ValueError("Invalid coordinate review fields")
    if (review["format_version"] != 1 or
            review["base_inventory_id"] != INVENTORY_ID or
            review["inventory_id"] != "na28-nt-reference-provisional-v2" or
            review["osis_book"] != "1Cor" or review["chapter"] != 4 or
            review["source_url"] != "https://www.die-bibel.de/en/bible/NA28/1CO.4" or
            review["verse_numbers"] != list(range(1, 22)) or
            not all(isinstance(review[field], str) and review[field].strip()
                    for field in ("reviewed_on", "reviewer", "note"))):
        raise ValueError("Unsupported or incomplete coordinate review")
    updated = copy.deepcopy(source)
    chapter = next((row for row in updated["chapters"]
                    if row["osis_book"] == "1Cor" and row["chapter"] == 4), None)
    if (chapter is None or
            chapter["source_url"] != "https://www.die-bibel.de/en/bible/UBS5/1CO.4" or
            chapter["verse_numbers"] != review["verse_numbers"] or
            not chapter.get("source_note", "").startswith("UBS5 coordinate fallback")):
        raise ValueError("The pinned 1 Corinthians 4 fallback has changed")
    chapter["source_url"] = review["source_url"]
    chapter["source_note"] = review["note"]
    return updated


def validate_passage_review(passage_review: dict) -> dict:
    if set(passage_review) != {"format_version", "base_inventory_id", "inventory_id",
                               "reviewed_on", "reviewer", "passages"}:
        raise ValueError("Invalid passage review fields")
    if (passage_review["format_version"] != 1 or
            passage_review["base_inventory_id"] != "na28-nt-reference-provisional-v2" or
            passage_review["inventory_id"] != "na28-nt-reference-provisional-v3" or
            not all(isinstance(passage_review[field], str) and passage_review[field].strip()
                    for field in ("reviewed_on", "reviewer")) or
            not isinstance(passage_review["passages"], list) or
            not passage_review["passages"]):
        raise ValueError("Unsupported or incomplete passage review")
    passages = {}
    for row in passage_review["passages"]:
        if (not isinstance(row, dict) or
                set(row) != {"osis_ref", "passage_citation", "passage_note"} or
                not all(isinstance(value, str) and value.strip() for value in row.values()) or
                row["osis_ref"] in passages):
            raise ValueError("Invalid or duplicate passage identification")
        passages[row["osis_ref"]] = row
    return passages


def build(source: dict, review: dict | None = None,
          passage_review: dict | None = None) -> dict:
    if source.get("format_version") != 1 or source.get("edition") != "NA28":
        raise ValueError("Unsupported coordinate source")
    if passage_review is not None and review is None:
        raise ValueError("Passage identifications require the v2 coordinate review")
    if review is not None:
        source = apply_coordinate_review(source, review)
    passages = validate_passage_review(passage_review) if passage_review else {}
    chapters = source["chapters"]
    if len(chapters) != 260:
        raise ValueError("Expected 260 New Testament chapters")
    if source["publisher"] != "Deutsche Bibelgesellschaft, Novum Testamentum Graece, 28th revised edition (2012)":
        raise ValueError("Publisher source changed; review before rebuilding")

    skipped = set(source["skipped_coordinates"])
    if len(skipped) != len(source["skipped_coordinates"]):
        raise ValueError("Duplicate skipped coordinate")
    mappings = {}

    bracketed = set()
    for passage in source["double_bracketed_passages"]:
        first, last = ref_key(passage["first"]), ref_key(passage["last"])
        if first > last or not passage["source_url"]:
            raise ValueError("Invalid double-bracket passage")
        bracketed.add((first, last))
    partial = {row["osis_ref"]: row["note"] for row in source["partial_double_bracket"]}

    verses = []
    seen_chapters = set()
    seen_skipped = set()
    seen_mappings = set()
    seen_bracketed = set()
    seen_partial = set()
    seen_passages = set()
    prior_book = None
    prior_chapter = 0
    for chapter in chapters:
        book, number = chapter["osis_book"], chapter["chapter"]
        if book not in NT_BOOKS or type(number) is not int or number < 1:
            raise ValueError("Invalid chapter reference")
        if prior_book != book:
            if prior_book is not None and NT_BOOKS.index(book) != NT_BOOKS.index(prior_book) + 1:
                raise ValueError("Books out of canonical order")
            if number != 1:
                raise ValueError(f"First chapter missing in {book}")
            prior_chapter = 0
        if number != prior_chapter + 1 or (book, number) in seen_chapters:
            raise ValueError(f"Missing, duplicate, or unordered chapter: {book}.{number}")
        seen_chapters.add((book, number))
        prior_book, prior_chapter = book, number
        markers = chapter["verse_numbers"]
        publisher_id = f"{PUBLISHER_CODES[NT_BOOKS.index(book)]}.{number}"
        if (not chapter["source_url"].startswith("https://www.die-bibel.de/") or
                not chapter["source_url"].endswith("/" + publisher_id)):
            raise ValueError(f"Publisher URL does not match chapter: {book}.{number}")
        if not markers or markers[0] != 1 or any(
            type(v) is not int or v <= 0 or (i and v <= markers[i - 1])
            for i, v in enumerate(markers)
        ):
            raise ValueError(f"Invalid verse markers in {book}.{number}")
        marker_set = set(markers)
        fallback = chapter.get("source_note", "").startswith("UBS5 coordinate fallback")
        for verse in range(1, markers[-1] + 1):
            ref = f"{book}.{number}.{verse}"
            key = ref_key(ref)
            entry = {"osis_ref": ref, "editorial_status": "main", "ntvmr_refs": []}
            if verse not in marker_set:
                if ref not in skipped:
                    raise ValueError(f"Unrecorded gap in publisher markers: {ref}")
                entry["editorial_status"] = "omitted"
                entry["editorial_note"] = "Number absent from the publisher's displayed NA28 chapter; coordinate retained for comparison, not a claim of physical absence."
                seen_skipped.add(ref)
            elif fallback:
                entry["editorial_status"] = "uncertain"
                entry["editorial_note"] = "Coordinate checked in the publisher's UBS5 display; direct NA28 chapter display was unavailable and needs confirmation."
            else:
                for first, last in bracketed:
                    if first <= key <= last:
                        entry["editorial_status"] = "bracketed"
                        entry["editorial_note"] = "Verse lies within the publisher's double-bracketed passage; its inclusion must remain visible in exports."
                        seen_bracketed.add(ref)
                        break
            if ref in partial:
                entry["editorial_note"] = partial[ref]
                seen_partial.add(ref)
            if ref in passages:
                if entry["editorial_status"] != "omitted":
                    raise ValueError(f"Passage identification is not for an omitted coordinate: {ref}")
                entry["passage_citation"] = passages[ref]["passage_citation"]
                entry["editorial_note"] += " " + passages[ref]["passage_note"]
                seen_passages.add(ref)
            if ref in mappings:
                entry["ntvmr_refs"] = [mappings[ref]]
                seen_mappings.add(ref)
            else:
                entry["mapping_note"] = "Reference coordinate only; source mappings are derived from collected reports."
            verses.append(entry)
    if len({book for book, _ in seen_chapters}) != 27 or len(seen_chapters) != 260:
        raise ValueError("Incomplete New Testament chapter coverage")
    if (seen_skipped != skipped or seen_mappings != set(mappings) or
            seen_partial != set(partial) or seen_passages != set(passages)):
        raise ValueError("Source exceptions refer to missing coordinates")
    if len(seen_bracketed) != 26:
        raise ValueError("Unexpected double-bracket passage length")
    if len(verses) != 7957:
        raise ValueError("Unexpected coordinate total")

    manifest = {
        "format_version": 1,
        "inventory_id": (passage_review["inventory_id"] if passage_review else
                         review["inventory_id"] if review else INVENTORY_ID),
        "edition": "NA28",
        "scope": (f"Provisional whole-New-Testament reference coordinates from 27 books and 260 chapters; direct NA28 publisher displays checked; {len(passages)} omitted traditional passages identified; remaining editorial and NTVMR mapping review pending."
                  if passage_review else
                  "Provisional whole-New-Testament reference coordinates from 27 books and 260 chapters; direct NA28 publisher displays checked; remaining editorial and NTVMR mapping review pending."
                  if review else "Provisional whole-New-Testament reference coordinates from 27 books and 260 chapters; publisher display checked except 1 Cor 4 UBS5 fallback; editorial and NTVMR mapping review pending."),
        "source_citation": ("Deutsche Bibelgesellschaft, Novum Testamentum Graece, 28th revised edition (2012), public chapter pages enumerated in data/reference/publisher-coordinates.json, captured 2026-09-29. The 1 Corinthians 4 direct NA28 check is recorded in data/reference/coordinate-clarifications.json. Traditional passage identification is recorded in data/reference/passage-identifications.json. Reference numbers only; no Greek text reproduced."
                            if passage_review else
                            "Deutsche Bibelgesellschaft, Novum Testamentum Graece, 28th revised edition (2012), public chapter pages enumerated in data/reference/publisher-coordinates.json, captured 2026-09-29. The 1 Corinthians 4 direct NA28 check is recorded in data/reference/coordinate-clarifications.json. Reference numbers only; no Greek text reproduced."
                            if review else "Deutsche Bibelgesellschaft, Novum Testamentum Graece, 28th revised edition (2012), public chapter pages enumerated in data/reference/publisher-coordinates.json, captured 2026-09-29. One chapter uses the publisher's UBS5 coordinate display as a flagged fallback. Reference numbers only; no Greek text reproduced."),
        "reuse_terms": "Reference coordinates only; no NA28 or UBS5 edition text reproduced. Source text copyright Deutsche Bibelgesellschaft; this manifest asserts no right to republish it.",
        "mapping_citation": "Reference inventory only. Exact reported OSIS matches are mapped by build_collection.py.",
        "reviewer": (f"Codex automated source-coordinate review, 2026-09-29; {review['reviewer']}, {review['reviewed_on']} for 1 Cor 4; {passage_review['reviewer']}, {passage_review['reviewed_on']} for omitted passage identification; independent editorial and mapping review pending"
                     if passage_review else
                     f"Codex automated source-coordinate review, 2026-09-29; {review['reviewer']}, {review['reviewed_on']} for 1 Cor 4; independent editorial and mapping review pending"
                     if review else "Codex automated source-coordinate review, 2026-09-29; independent editorial and mapping review pending"),
        "verses": verses,
    }
    validate_inventory(manifest)
    return manifest


def render(manifest: dict) -> str:
    lines = ["{"]
    for key, value in manifest.items():
        if key == "verses":
            continue
        lines.append(f'  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},')
    lines.append('  "verses": [')
    for i, verse in enumerate(manifest["verses"]):
        comma = "," if i + 1 < len(manifest["verses"]) else ""
        lines.append("    " + json.dumps(verse, ensure_ascii=False, separators=(",", ":")) + comma)
    lines.extend(["  ]", "}"])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--check", action="store_true", help="Verify the current reference file without writing")
    args = parser.parse_args(argv)
    manifest = build(json.loads(args.source.read_text(encoding="utf-8")),
                     json.loads(REVIEW.read_text(encoding="utf-8")),
                     json.loads(PASSAGE_REVIEW.read_text(encoding="utf-8")))
    if args.check:
        if json.loads(OUTPUT.read_text(encoding="utf-8")) != manifest:
            raise SystemExit("Reference inventory differs; rebuild with python build_na28_inventory.py")
    else:
        from build_collection import write_json
        write_json(OUTPUT, manifest)
    counts = {status: sum(row["editorial_status"] == status for row in manifest["verses"])
              for status in ("main", "bracketed", "omitted", "uncertain")}
    print(json.dumps({"inventory_id": manifest["inventory_id"], "coordinates": len(manifest["verses"]),
                      "mapped": sum(bool(row["ntvmr_refs"]) for row in manifest["verses"]),
                      "editorial_status": counts, "checked": args.check}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
