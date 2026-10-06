#!/usr/bin/env python3
"""Replay Washingtonianus at John 5:9-13 across its supplement/original boundary."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

from controlled_ntvmr import (
    Client, assign_coverage_unit, collect_stage, connect, coverage_review_report,
    create_writing_unit, encoded, import_coverage_fixture, import_edition_inventory,
    parse_coverage, parse_metadata, record_candidate_review, record_coverage_review,
    record_date_assessment, record_witness_assignment, select_date_assessment,
    validate_inventory,
)
from replay_gal1_p46 import NS, ROOT, checked_capture, read_json
from replay_john1_supplement import DATE_TEXT, DATE_URL

REVIEW = ROOT / "benchmarks/john5-boundary-reviewed-v1.json"
REFS = [f"John.5.{verse}" for verse in range(9, 14)]
SUPPLEMENT = "032-john-opening-supplement"
ORIGINAL = "032-john-original"
# This is a guard for six manually reviewed index pairs, not a TEI classifier.
ROWS = [
    ("John.5.9", 1280, SUPPLEMENT, "υγιης", 22, "partial"),
    ("John.5.10", 1280, SUPPLEMENT, "ιουδεοι", 27, "partial"),
    ("John.5.11", 1280, SUPPLEMENT, "απεκρινατο", 30, "partial"),
    ("John.5.11", 1290, ORIGINAL, "κραβαττον", 1, "partial"),
    ("John.5.12", 1290, None, None, 1, "uncertain"),
    ("John.5.13", 1290, ORIGINAL, "ουκ", 2, "partial"),
]
SOURCES = {
    "032S": ("64v", REFS[:3], "498a19869cf25fff8318fbef2b2bfa3281c4db6cb5bcd2c57f6d583d530dca6c"),
    "032": ("65r", REFS[2:], "34e01920866b9f8fc3c026dd8e539f9a58571c5b601e5bb47c6c283672b69160"),
}


def checked_transcription(fixture, siglum):
    folio, refs, source_hash = SOURCES[siglum]
    url = f"https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_{siglum}_John.xml"
    if fixture["source_url"] != url or fixture["source_sha256"] != source_hash:
        raise ValueError("Unexpected boundary transcription source")
    for part in ("header", "excerpt"):
        if hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest() != fixture[f"{part}_sha256"]:
            raise ValueError("Transcription hash mismatch")
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0">' +
                        fixture["raw_header"] + '<text><body>' +
                        fixture["raw_excerpt"] + '</body></text></TEI>')
    title = root.find(".//t:title[@type='document']", NS)
    shelfmark = root.find(".//t:msIdentifier/t:idno", NS)
    if (title is None or title.get("key") != "20032" or title.get("n") != siglum or
            shelfmark is None or shelfmark.text != "06.274"):
        raise ValueError("Boundary transcription identity mismatch")
    pages, columns = root.findall(".//t:pb", NS), root.findall(".//t:cb", NS)
    if (len(pages) != 1 or pages[0].get("n") != folio or
            pages[0].get("{http://www.w3.org/XML/1998/namespace}id") != f"P{folio}-{siglum}" or
            len(columns) != 1 or columns[0].get("n") != "1"):
        raise ValueError("Boundary transcription page/column changed")
    verses = root.findall(".//t:div[@type='chapter']/t:ab", NS)
    if [verse.get("n") for verse in verses] != refs:
        raise ValueError("Boundary transcription verse scope changed")
    parents = {child: parent for parent in root.iter() for child in parent}
    locations = {}
    line = None
    for node in root.iter():
        if node.tag == f"{{{NS['t']}}}lb":
            line = node.get("n")
        locations[node] = line
    for verse in verses:
        ref = verse.get("n")
        if verse.attrib != {"n": ref} or verse.findall(".//t:app", NS):
            raise ValueError("Writing-layer change needs a new boundary review")
        ancestor = verse
        while ancestor is not None:
            if "hand" in ancestor.attrib:
                raise ValueError("Writing-layer change needs a new boundary review")
            ancestor = parents.get(ancestor)
        if any("hand" in node.attrib for node in verse.iter()):
            raise ValueError("Writing-layer change needs a new boundary review")
        if ref == "John.5.12":
            if len(verse) or (verse.text and verse.text.strip()):
                raise ValueError("Uncertain empty verse requires a new survival review")
            continue
        row = next(row for row in ROWS if row[0] == ref and
                   row[1] == (1280 if siglum == "032S" else 1290))
        words = [word for word in verse.findall("t:w", NS)
                 if not len(word) and not word.attrib and word.text == row[3]]
        if len(words) != 1:
            raise ValueError("Reviewed surviving boundary anchor missing or ambiguous")
        if locations[words[0]] != f"P{folio}C1L{row[4]}-{siglum}":
            raise ValueError("Reviewed boundary line anchor changed")
    gaps = root.findall(".//t:gap", NS)
    boundary = next(verse for verse in verses if verse.get("n") == "John.5.11")
    expected_gap = ({"reason": "witnessEnd"} if siglum == "032S" else
                    {"reason": "lacuna", "unit": "verse", "extent": "rest"})
    if (len(gaps) != 1 or gaps[0].attrib != expected_gap or
            gaps[0] is not boundary[-1 if siglum == "032S" else 0]):
        raise ValueError("Reviewed supplement/original boundary marker changed")
    if siglum == "032" and [word.text for word in boundary.findall("t:w", NS)] != [
            "κραβαττον", "σου", "και", "περιπατει"]:
        raise ValueError("Reviewed original verse ending changed")
    return verses


def load_inputs(review_path=REVIEW):
    review = read_json(review_path)
    date.fromisoformat(review["reviewed_on"])
    expected = {
        "format_version": 1, "review_id": "john5-boundary-reviewed-v1",
        "inventory_fixture": "benchmarks/john5-na28-subset-v1.json",
        "inventory_id": "na28-john5-boundary-subset-v1",
        "policy_id": "john5-boundary-conditional-v1", "doc_id": 20032,
        "witness_id": "032-washingtonianus", "consensus_status": "unknown",
        "metadata_fixture": "tests/fixtures/washingtonianus_metadata_probe.json",
        "index_fixture": "tests/fixtures/washingtonianus_coverage_probe.json",
        "date_source_fixture": "tests/fixtures/washingtonianus-supplement-date-source.json",
    }
    if (any(review.get(key) != value for key, value in expected.items()) or
            review.get("independent_human_validation") is not False):
        raise ValueError("Unsupported Washingtonianus boundary review scope")
    for key in ("reviewer", "witness_label", "classification_citation", "identity_citation",
                "consensus_note", "discovery_note"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Review requires {key}")
    inventory = read_json(ROOT / review["inventory_fixture"])
    validate_inventory(inventory)
    if (inventory["inventory_id"] != review["inventory_id"] or inventory["edition"] != "NA28" or
            [(row["osis_ref"], row["editorial_status"], row["ntvmr_refs"])
             for row in inventory["verses"]] != [(ref, "main", [ref]) for ref in REFS]):
        raise ValueError("Boundary inventory scope changed")
    metadata, index = (read_json(ROOT / review[key]) for key in ("metadata_fixture", "index_fixture"))
    payload = checked_capture(metadata, "metadata/manuscript/get", "10", 20032)
    if parse_metadata(payload, 20032)["ga_num"] not in ("032", "32"):
        raise ValueError("Boundary metadata identity mismatch")
    manuscript = payload["data"]["manuscript"]
    if manuscript["originYear"] != {"early": 400, "late": 499, "content": "V"}:
        raise ValueError("Original manuscript catalogue date changed")
    for page_id, folio, content in [(1280, "64v Suppl", "John 4:53-54; John 5:1-11"),
                                    (1290, "65r", "John 5:11-22")]:
        pages = [page for page in manuscript["pages"]["page"] if page["pageID"] == page_id]
        if len(pages) != 1 or pages[0]["folio"] != folio or pages[0]["indexContent"] != content:
            raise ValueError("Metadata boundary page/folio changed")
    pairs = set(parse_coverage(checked_capture(index, "biblicalcontent/get", "long", 20032), 20032))
    if [(row["osis_ref"], row["page_id"], row["unit_id"], row["anchor"], row["line"], row["status"])
            for row in review["coverage_reviews"]] != ROWS:
        raise ValueError("Reviewed boundary coverage/layer assignments changed")
    for row in review["coverage_reviews"]:
        if ((row["osis_ref"], row["page_id"]) not in pairs or
                row["folio"] != ("64v" if row["page_id"] == 1280 else "65r")):
            raise ValueError("Reviewed boundary index link changed")
        for key in ("reason", "citation", "source_locator"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"Coverage review requires {key}")
    units = review["units"]
    expected_units = [(SUPPLEMENT, "supplement", "032S", "64v", 1280),
                      (ORIGINAL, "original", "032", "65r", 1290)]
    if [(u["unit_id"], u["kind"], u["siglum"], u["folio"], u["page_id"])
            for u in units] != expected_units:
        raise ValueError("Reviewed boundary writing layers changed")
    for unit, dates in zip(units, [("valid", 601, 800, "perhaps to the seventh or eighth century"),
                                  ("valid", 400, 499, "V")]):
        if unit["transcription_fixture"] != f"tests/fixtures/washingtonianus-john5-{unit['siglum'].lower()}-transcription.json":
            raise ValueError("Boundary transcription fixture changed")
        checked_transcription(read_json(ROOT / unit["transcription_fixture"]), unit["siglum"])
        for key in ("label", "reason", "citation"):
            if not isinstance(unit.get(key), str) or not unit[key].strip():
                raise ValueError(f"Writing unit requires {key}")
        if ([(a["status"], a["date_min"], a["date_max"], a["original_notation"])
             for a in unit["assessments"]] != [dates] or
                any(not a["citation"].strip() for a in unit["assessments"])):
            raise ValueError("Date assessment differs from reviewed writing layer")
    source = read_json(ROOT / review["date_source_fixture"])
    if (source["source_url"] != DATE_URL or source["source_text"] != DATE_TEXT or
            source["source_text_sha256"] != hashlib.sha256(DATE_TEXT.encode()).hexdigest() or
            source["source_locator"] != "p. 233, The Freer Gospels, first paragraph" or
            source["applies_to"] != "Washingtonianus replacement quire, John 1:1-5:11a"):
        raise ValueError("Supplement date source changed")
    date.fromisoformat(source["consulted_on"])
    return review, inventory, metadata, index


def apply(db_path, review_path=REVIEW):
    review, inventory, metadata, index = load_inputs(review_path)
    if Path(db_path).exists():
        raise ValueError("Boundary replay requires a fresh database path")
    with closing(connect(db_path)) as con:
        import_edition_inventory(con, inventory)
        with con:
            cursor = con.execute("""INSERT INTO source_response(endpoint,url,params_json,
                status_code,headers_json,body,body_sha256,retrieved_at,origin)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                ("metadata/manuscript/get", metadata["source_url"], encoded(metadata["params"]),
                 200, "{}", metadata["raw_body"], metadata["body_sha256"],
                 metadata["retrieved_at"], "fixture"))
            metadata_id = cursor.lastrowid
        index_id = import_coverage_fixture(con, index)
        for fixture, endpoint, stage in ((metadata, "metadata/manuscript/get", "metadata"),
                                          (index, "biblicalcontent/get", "coverage")):
            client = Client(con, review["review_id"], offline=True,
                            base_url=fixture["source_url"].removesuffix(f"/{endpoint}/"))
            if collect_stage(client, 20032, stage) != "success" or client.attempts:
                raise ValueError("Washingtonianus cached collection did not complete offline")
        reviewer = review["reviewer"]
        record_candidate_review(con, 20032, metadata_id, "retain", "greek_manuscript",
                                "Both transcriptions identify the same Greek codex",
                                review["classification_citation"], reviewer)
        record_witness_assignment(con, 20032, metadata_id, review["witness_id"],
                                  review["witness_label"], "032S and 032 are layers of one codex",
                                  review["identity_citation"], reviewer)
        units = {unit["unit_id"]: unit for unit in review["units"]}
        for unit in units.values():
            create_writing_unit(con, unit["unit_id"], review["witness_id"], unit["label"],
                                unit["kind"], unit["reason"], unit["citation"], reviewer)
            for assessment in unit["assessments"]:
                record_date_assessment(con, unit["unit_id"], assessment["status"], assessment["date_min"],
                                       assessment["date_max"], assessment["original_notation"],
                                       assessment["citation"], review["reviewed_on"], reviewer)
            select_date_assessment(con, unit["unit_id"], None, review["policy_id"],
                                   review["consensus_note"], reviewer)
        for row in review["coverage_reviews"]:
            coverage_id = record_coverage_review(
                con, review["inventory_id"], row["osis_ref"], row["osis_ref"], 20032,
                row["page_id"], index_id, row["status"], "reviewed_transcription",
                row["reason"], row["citation"], reviewer)
            if row["unit_id"] is not None:
                unit = units[row["unit_id"]]
                assign_coverage_unit(con, coverage_id, unit["unit_id"], unit["reason"],
                                     unit["citation"], reviewer)
        verified = coverage_review_report(con, review["inventory_id"])["verified_witnesses"]
        if verified != {ref: [review["witness_id"]] for ref in REFS if ref != "John.5.12"}:
            raise ValueError("Replay did not yield four declared positive witness/verse pairs")
        return {"review_id": review["review_id"], "inventory_id": review["inventory_id"],
                "policy_id": review["policy_id"], "reviewed_witnesses": 1,
                "mapped_coordinates": 5, "page_coverage_reviews": 6,
                "positive_witness_verse_pairs": sum(map(len, verified.values())),
                "uncertain_witness_verse_pairs": 1, "writing_units": len(units),
                "date_assessments": 2,
                "network_attempts": con.execute("SELECT count(*) FROM request_attempt").fetchone()[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        review, _, _, _ = load_inputs(args.review)
        result = ({"planned_review_id": review["review_id"], "planned_inventory_id": review["inventory_id"],
                   "planned_witnesses": 1, "planned_positive_pairs": 4,
                   "planned_uncertain_pairs": 1, "network_attempts": 0}
                  if args.dry_run else apply(args.db, args.review))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, sqlite3.Error) as error:
        print(f"John 5 boundary replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
