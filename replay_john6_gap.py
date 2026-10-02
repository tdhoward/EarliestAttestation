#!/usr/bin/env python3
"""Replay the cited John 6:49-53 survival boundary, using existing review APIs."""

from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

from controlled_ntvmr import (
    assign_coverage_unit, connect, create_writing_unit, import_edition_inventory,
    parse_coverage, record_coverage_review, record_date_assessment,
    record_physical_absence_review, select_date_assessment, validate_inventory,
)
from replay_john1_prototype import ROOT, apply as replay_john1, load_inputs as load_john1


REVIEW = ROOT / "benchmarks/john6-gap-reviewed-v2.json"
INVENTORY = ROOT / "benchmarks/john6-na28-subset-v1.json"
BASE_REVIEW = ROOT / "benchmarks/john1-reviewed-v3.json"
REFS = [f"John.6.{verse}" for verse in range(49, 54)]
NS = {"t": "http://www.tei-c.org/ns/1.0"}
SOURCE_NAMES = {"P66": "p66", "P75": "p75", "02": "alexandrinus"}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def checked_transcription(fixture, ga_num):
    """Check pinned review anchors, not a general automated survival classifier."""
    if ga_num not in SOURCE_NAMES:
        raise ValueError("Unsupported transcription witness")
    excerpt = fixture["raw_excerpt"]
    if (hashlib.sha256(excerpt.encode("utf-8")).hexdigest() != fixture["excerpt_sha256"]
            or fixture["source_url"] !=
            f"https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_{ga_num}_John.xml"):
        raise ValueError("Transcription excerpt source or hash mismatch")
    # The contiguous excerpt can cross a chapter boundary; restore only its
    # surrounding TEI namespace and chapter containers for XML parsing.
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0"><div>' +
                         excerpt + '</div></TEI>')
    verses = root.findall(".//t:ab", NS)
    expected = {
        "P66": ["John.6.48", *REFS],
        "P75": ["John.6.47", "John.6.48", *REFS],
        "02": ["John.6.48", "John.6.49", "John.6.50", "John.8.52", "John.8.53"],
    }[ga_num]
    if [verse.get("n") for verse in verses] != expected:
        raise ValueError("Transcription does not match the reviewed boundary sequence")
    by_ref = {verse.get("n"): verse for verse in verses}
    positive = REFS[:2] if ga_num == "02" else REFS
    for ref in positive:
        # Direct words outside an apparatus/supplied span establish the bounded
        # source anchor. Human/agent review supplies the actual historical claim.
        if not any(word.text and word.text.strip() for word in
                   by_ref[ref].findall("t:w", NS)):
            raise ValueError("Reviewed verse lacks a surviving base-text anchor")
    if ga_num == "P75":
        # All reviewed portions are on 52r; supplied letters do not establish
        # survival. Keep the exact line anchors used in this bounded review.
        lines = [node.get("n") for node in root.findall(".//t:lb", NS)]
        if (lines != [f"P52rC1L{line}-P75" for line in range(26, 44)] or
                root.findall(".//t:pb", NS)):
            raise ValueError("P75 transcription differs from the reviewed page/line anchors")
    if ga_num == "02":
        for ref in ("John.6.50", "John.8.52"):
            if by_ref[ref].find("t:gap[@reason='lacuna'][@extent='rest']", NS) is None:
                raise ValueError("Physical gap requires explicit transcription lacuna anchors")
        if by_ref["John.6.50"].find("t:pb[@n='73r']", NS) is None:
            raise ValueError("Physical gap requires the reviewed folio transition")
    return by_ref


def load_inputs(review_path=REVIEW):
    review, inventory = read_json(review_path), read_json(INVENTORY)
    base, _, indexes = load_john1(BASE_REVIEW)
    validate_inventory(inventory)
    expected_witnesses = {
        "john6-gap-reviewed-v1": ["P66", "02"],
        "john6-gap-reviewed-v2": ["P66", "02", "P75"],
    }.get(review.get("review_id"))
    if (review.get("format_version") != 1 or
            review.get("inventory_id") != inventory["inventory_id"] or
            review.get("base_review") != "benchmarks/john1-reviewed-v3.json" or
            review.get("independent_human_validation") is not False or
            [v["osis_ref"] for v in inventory["verses"]] != REFS or
            any(v["ntvmr_refs"] != [v["osis_ref"]] for v in inventory["verses"]) or
            [w["ga_num"] for w in review["witnesses"]] != expected_witnesses):
        raise ValueError("Unsupported John 6 review scope")
    corpus = read_json(ROOT / "benchmarks/na28-nt-reference-provisional-v3.json")
    corpus_refs = {v["osis_ref"]: v["editorial_status"] for v in corpus["verses"]}
    if any(corpus_refs.get(ref) != "main" for ref in REFS):
        raise ValueError("John 6 coordinates differ from the pinned inventory")
    for witness in review["witnesses"]:
        ga_num = witness["ga_num"]
        original = next(w for w in base["witnesses"] if w["ga_num"] == ga_num)
        name = SOURCE_NAMES[ga_num]
        if (witness["doc_id"] != original["doc_id"] or
                witness["witness_id"] != original["witness_id"] or
                witness["index_fixture"] != original["index_fixture"] or
                witness["metadata_fixture"] != f"tests/fixtures/{name}_metadata_probe.json" or
                witness["transcription_fixture"] != f"tests/fixtures/{name}-john6-transcription.json"):
            raise ValueError("John 6 witness differs from its pinned sources")
        checked_transcription(read_json(ROOT / witness["transcription_fixture"]), ga_num)
        positives = REFS[:2] if ga_num == "02" else REFS
        absences = REFS[2:] if ga_num == "02" else []
        if ([r["osis_ref"] for r in witness["positive_reviews"]] != positives or
                [r["osis_ref"] for r in witness["absence_reviews"]] != absences):
            raise ValueError("John 6 decisions differ from the reviewed survival boundary")
        fixture = indexes[witness["doc_id"]][1]
        pairs = set(parse_coverage(json.loads(fixture["raw_body"]), witness["doc_id"]))
        metadata = read_json(ROOT / witness["metadata_fixture"])
        if (metadata["params"] != {"detail": "10", "docID": str(witness["doc_id"]), "format": "json"}
                or metadata.get("canonical_source_url", metadata["source_url"]) !=
                "https://ntvmr.uni-muenster.de/community/vmr/api/metadata/manuscript/get/"
                or metadata["http_status"] != 200
                or hashlib.sha256(metadata["raw_body"].encode("utf-8")).hexdigest()
                != metadata["body_sha256"]):
            raise ValueError("Page metadata source or hash mismatch")
        payload = json.loads(metadata["raw_body"])
        manuscript = payload["data"]["manuscript"]
        if payload["status"] != "success" or manuscript["docID"] != witness["doc_id"]:
            raise ValueError("Page metadata manuscript identity mismatch")
        pages = manuscript["pages"]["page"]
        for row in witness["positive_reviews"]:
            page_id, folio = {
                "P66": (360, "40") if row["osis_ref"] in REFS[:3] else (370, "41"),
                "02": (531, "70v"),
                "P75": (790, "52r"),
            }[ga_num]
            linked = [page for page in pages if page["pageID"] == page_id]
            if (row["page_id"] != page_id or row["folio"] != folio or
                    (row["osis_ref"], page_id) not in pairs or len(linked) != 1 or
                    str(linked[0]["folio"]) != folio):
                raise ValueError("Reviewed portion does not match the indexed page/folio")
    return review, inventory, base


def apply(db_path, review_path=REVIEW):
    review, inventory, base = load_inputs(review_path)
    if Path(db_path).exists():
        raise ValueError("John 6 gap replay requires a fresh database path")
    # Reuse the fixed, reviewed identity/date provenance and cached indexes.
    # Existing John 1 data stays in its own inventory in this new database.
    replay_john1(db_path, BASE_REVIEW)
    with closing(connect(db_path)) as con:
        import_edition_inventory(con, inventory)
        for witness in review["witnesses"]:
            original = next(w for w in base["witnesses"] if w["ga_num"] == witness["ga_num"])
            create_writing_unit(con, witness["unit_id"], witness["witness_id"],
                                witness["unit_label"], "original", witness["unit_reason"],
                                witness["unit_citation"], review["reviewer"])
            for assessment in original["assessments"]:
                record_date_assessment(
                    con, witness["unit_id"], assessment["status"], assessment["date_min"],
                    assessment["date_max"], assessment["original_notation"],
                    assessment["citation"], base["reviewed_on"], review["reviewer"])
            select_date_assessment(con, witness["unit_id"], None, review["policy_id"],
                                   "Stored source dates remain conditional; consensus unknown",
                                   review["reviewer"])
            for row in witness["positive_reviews"]:
                response_id = con.execute("""SELECT response_id FROM coverage_index
                    WHERE doc_id=? AND osis_ref=? AND page_id=?""",
                    (witness["doc_id"], row["osis_ref"], row["page_id"])).fetchone()[0]
                citation = witness["coverage_citation"] + " Location: " + row["source_locator"]
                coverage_id = record_coverage_review(
                    con, inventory["inventory_id"], row["osis_ref"], row["osis_ref"],
                    witness["doc_id"], row["page_id"], response_id, "partial",
                    "reviewed_transcription", row["reason"], citation, review["reviewer"])
                assign_coverage_unit(con, coverage_id, witness["unit_id"], witness["unit_reason"],
                                     witness["unit_citation"], review["reviewer"])
            for row in witness["absence_reviews"]:
                record_physical_absence_review(
                    con, inventory["inventory_id"], row["osis_ref"], witness["witness_id"],
                    "absent", "reviewed_transcription", row["source_locator"], row["reason"],
                    witness["coverage_citation"] + " Location: " + row["source_locator"],
                    review["reviewer"])
        return {"review_id": review["review_id"], "inventory_id": inventory["inventory_id"],
                "policy_id": review["policy_id"], "reviewed_witnesses": len(review["witnesses"]),
                "positive_witness_verse_pairs": sum(len(w["positive_reviews"]) for w in review["witnesses"]),
                "absent_witness_verse_pairs": sum(len(w["absence_reviews"]) for w in review["witnesses"]),
                "network_attempts": con.execute("SELECT count(*) FROM request_attempt").fetchone()[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=REVIEW,
                        help="Pinned review manifest (defaults to the three-witness v2 review)")
    args = parser.parse_args(argv)
    try:
        result = apply(args.db, args.review)
    except (OSError, ValueError, KeyError, sqlite3.Error, ET.ParseError) as error:
        print(f"John 6 gap replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
