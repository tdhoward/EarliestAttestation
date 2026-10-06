#!/usr/bin/env python3
"""Replay five John 1:1-5 witnesses, dating Washingtonianus's later quire separately."""

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
    create_writing_unit, encoded, import_coverage_fixture, parse_coverage,
    parse_metadata, record_candidate_review, record_coverage_review,
    record_date_assessment, record_witness_assignment, select_date_assessment,
)
from replay_gal1_p46 import NS, checked_capture, read_json
from replay_john1_prototype import REFS, ROOT, apply as replay_original, load_inputs as load_original

REVIEW = ROOT / "benchmarks/john1-supplement-reviewed-v1.json"
BASE_REVIEW = ROOT / "benchmarks/john1-reviewed-v3.json"
XML_URL = "https://itseeweb.cal.bham.ac.uk/iohannes/transcriptions/greek/NT_GRC_032S_John.xml"
DATE_URL = "https://www.galaxie.com/article/bbr11-2-05"
DATE_TEXT = "which dates perhaps to the seventh or eighth century."
ANCHORS = dict(zip(REFS, ["αρχη", "ουτος", "παντα", "αυτω", "κατελαβεν"]))
LINES = dict(zip(REFS, [2, 3, 4, 6, 8]))


def checked_transcription(fixture):
    """Guard reviewed supplement anchors, not arbitrary TEI survival claims."""
    if fixture["source_url"] != XML_URL:
        raise ValueError("Unexpected supplement transcription source")
    for part in ("header", "excerpt"):
        if hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest() != fixture[f"{part}_sha256"]:
            raise ValueError("Transcription hash mismatch")
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0">' +
                        fixture["raw_header"] + '<text><body>' +
                        fixture["raw_excerpt"] + '</body></text></TEI>')
    title = root.find(".//t:title[@type='document']", NS)
    shelfmark = root.find(".//t:msIdentifier/t:idno", NS)
    if (title is None or title.get("key") != "20032" or title.get("n") != "032S" or
            shelfmark is None or shelfmark.text != "06.274"):
        raise ValueError("Transcription supplement identity mismatch")
    pages, columns = root.findall(".//t:pb", NS), root.findall(".//t:cb", NS)
    if (len(pages) != 1 or pages[0].get("n") != "57r" or
            len(columns) != 1 or columns[0].get("n") != "1"):
        raise ValueError("Transcription page/column differs from reviewed supplement")
    verses = root.findall(".//t:div[@type='chapter']/t:ab", NS)
    if [verse.get("n") for verse in verses] != REFS:
        raise ValueError("Transcription differs from the five-verse review scope")
    parents = {child: parent for parent in root.iter() for child in parent}
    # Resolve physical line markers through the inscription and verse boundaries.
    line = None
    anchor_lines = {}
    for node in root.iter():
        if node.tag == f"{{{NS['t']}}}lb":
            line = node.get("n")
        if node.tag == f"{{{NS['t']}}}w":
            anchor_lines[node] = line
    for verse in verses:
        ref = verse.get("n")
        if verse.attrib != {"n": ref} or verse.findall(".//t:app", NS):
            raise ValueError("Writing-layer change needs a new source review")
        ancestor = parents[verse]
        while ancestor is not None:
            if "hand" in ancestor.attrib:
                raise ValueError("Writing-layer change needs a new source review")
            ancestor = parents.get(ancestor)
        words = [word for word in verse.findall("t:w", NS)
                 if not len(word) and not word.attrib and word.text == ANCHORS[ref]]
        if len(words) != 1:
            raise ValueError("Reviewed surviving supplement anchor missing or ambiguous")
        if anchor_lines[words[0]] != f"P57rC1L{LINES[ref]}-032S":
            raise ValueError("Reviewed supplement line anchor changed")
    return verses


def load_inputs(review_path=REVIEW):
    review = read_json(review_path)
    base, inventory, _ = load_original(BASE_REVIEW)
    date.fromisoformat(review["reviewed_on"])
    expected = {
        "format_version": 1, "review_id": "john1-supplement-reviewed-v1",
        "base_review": "benchmarks/john1-reviewed-v3.json",
        "inventory_id": inventory["inventory_id"], "policy_id": "john1-supplement-conditional-v1",
        "doc_id": 20032, "ga_num": "032", "witness_id": "032-washingtonianus",
        "unit_id": "032-john-opening-supplement", "unit_kind": "supplement",
        "consensus_status": "unknown",
        "metadata_fixture": "tests/fixtures/washingtonianus_metadata_probe.json",
        "index_fixture": "tests/fixtures/washingtonianus_coverage_probe.json",
        "transcription_fixture": "tests/fixtures/washingtonianus-john1-transcription.json",
        "date_source_fixture": "tests/fixtures/washingtonianus-supplement-date-source.json",
    }
    if (any(review.get(key) != value for key, value in expected.items()) or
            review.get("independent_human_validation") is not False or
            [row["osis_ref"] for row in review["positive_reviews"]] != REFS):
        raise ValueError("Unsupported Washingtonianus supplement review scope")
    for key in ("reviewer", "witness_label", "classification_citation", "identity_citation",
                "unit_label", "unit_reason", "unit_citation", "coverage_citation",
                "consensus_note", "discovery_note", "catalogue_date_exclusion"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Review requires {key}")
    metadata, index = (read_json(ROOT / review[key]) for key in ("metadata_fixture", "index_fixture"))
    payload = checked_capture(metadata, "metadata/manuscript/get", "10", 20032)
    if parse_metadata(payload, 20032)["ga_num"] not in ("032", "32"):
        raise ValueError("Metadata manuscript identity mismatch")
    manuscript = payload["data"]["manuscript"]
    pages = [page for page in manuscript["pages"]["page"] if page["pageID"] == 1130]
    if (len(pages) != 1 or pages[0]["folio"] != "57r Suppl" or
            pages[0]["indexContent"] != "John 1:1-15"):
        raise ValueError("Metadata does not identify reviewed supplement page/folio")
    pairs = set(parse_coverage(checked_capture(index, "biblicalcontent/get", "long", 20032), 20032))
    checked_transcription(read_json(ROOT / review["transcription_fixture"]))
    for row in review["positive_reviews"]:
        ref = row["osis_ref"]
        if (row["page_id"] != 1130 or row["folio"] != "57r" or
                row["anchor"] != ANCHORS[ref] or row["line"] != LINES[ref] or
                (ref, row["page_id"]) not in pairs):
            raise ValueError("Reviewed anchor does not match indexed supplement page/folio")
        if not row["source_locator"].strip() or not row["reason"].strip():
            raise ValueError("Review requires source locations and reasons")
    source = read_json(ROOT / review["date_source_fixture"])
    if (source["source_url"] != DATE_URL or source["source_text"] != DATE_TEXT or
            source["source_text_sha256"] != hashlib.sha256(DATE_TEXT.encode()).hexdigest() or
            source["source_locator"] != "p. 233, The Freer Gospels, first paragraph" or
            source["applies_to"] != "Washingtonianus replacement quire, John 1:1-5:11a"):
        raise ValueError("Supplement date source changed")
    date.fromisoformat(source["consulted_on"])
    assessments = review["assessments"]
    if ([(a["status"], a["date_min"], a["date_max"], a["original_notation"])
         for a in assessments] != [("valid", 601, 800, "perhaps to the seventh or eighth century")] or
            any(not a["citation"].strip() for a in assessments)):
        raise ValueError("Date assessment differs from reviewed supplement source")
    # Preserve these original catalogue fields without applying them to this quire.
    if manuscript["originYear"] != {"early": 400, "late": 499, "content": "V"}:
        raise ValueError("Manuscript catalogue date changed; supplement applicability needs review")
    return review, base, metadata, index


def apply(db_path, review_path=REVIEW):
    review, base, metadata, index = load_inputs(review_path)
    if Path(db_path).exists():
        raise ValueError("Supplement replay requires a fresh database path")
    replay_original(db_path, BASE_REVIEW)
    with closing(connect(db_path)) as con:
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
                                "Catalogue and supplement transcription identify a Greek codex",
                                review["classification_citation"], reviewer)
        record_witness_assignment(con, 20032, metadata_id, review["witness_id"],
                                  review["witness_label"], "032S is a writing layer of physical codex 032",
                                  review["identity_citation"], reviewer)
        create_writing_unit(con, review["unit_id"], review["witness_id"], review["unit_label"],
                            "supplement", review["unit_reason"], review["unit_citation"], reviewer)
        for assessment in review["assessments"]:
            record_date_assessment(con, review["unit_id"], assessment["status"], assessment["date_min"],
                                   assessment["date_max"], assessment["original_notation"],
                                   assessment["citation"], review["reviewed_on"], reviewer)
        for unit in [witness["unit_id"] for witness in base["witnesses"]] + [review["unit_id"]]:
            select_date_assessment(con, unit, None, review["policy_id"], review["consensus_note"], reviewer)
        for row in review["positive_reviews"]:
            coverage_id = record_coverage_review(
                con, review["inventory_id"], row["osis_ref"], row["osis_ref"], 20032,
                row["page_id"], index_id, "partial", "reviewed_transcription", row["reason"],
                review["coverage_citation"] + " Location: " + row["source_locator"], reviewer)
            assign_coverage_unit(con, coverage_id, review["unit_id"], review["unit_reason"],
                                 review["unit_citation"], reviewer)
        verified = coverage_review_report(con, review["inventory_id"])["verified_witnesses"]
        witnesses = {witness["witness_id"] for witness in base["witnesses"]} | {review["witness_id"]}
        if set(verified) != set(REFS) or any(set(ids) != witnesses for ids in verified.values()):
            raise ValueError("Replay did not yield five declared physical witnesses per verse")
        return {"review_id": review["review_id"], "inventory_id": review["inventory_id"],
                "policy_id": review["policy_id"], "reviewed_witnesses": 5,
                "positive_witness_verse_pairs": sum(map(len, verified.values())),
                "date_assessments": con.execute("SELECT count(*) FROM date_assessment").fetchone()[0],
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
                   "planned_witnesses": 5, "planned_positive_pairs": 25, "network_attempts": 0}
                  if args.dry_run else apply(args.db, args.review))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, sqlite3.Error) as error:
        print(f"John 1 supplement replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
