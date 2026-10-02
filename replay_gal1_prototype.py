#!/usr/bin/env python3
"""Replay P46 and Alexandrinus at Galatians 1:1-5 from pinned sources offline."""

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
from replay_gal1_p46 import (
    NS, REFS, ROOT, apply as replay_p46, checked_capture,
    load_inputs as load_p46, read_json,
)

REVIEW = ROOT / "benchmarks/gal1-overlap-reviewed-v1.json"
BASE_REVIEW = ROOT / "benchmarks/gal1-p46-reviewed-v1.json"
XML_URL = "https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_02_Gal.xml"
ANCHORS = dict(zip(REFS, ["νεκρων", "παντες", "ειρηνη", "εαυτον", "δοξα"]))
LINES = dict(zip(REFS, [4, 5, 7, 9, 14]))


def checked_transcription(fixture):
    """Guard the reviewed anchors, not a general survival or writing-layer classifier."""
    if fixture["source_url"] != XML_URL:
        raise ValueError("Unexpected Alexandrinus transcription source")
    for part in ("header", "excerpt"):
        if hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest() != fixture[f"{part}_sha256"]:
            raise ValueError("Transcription hash mismatch")
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0">' +
                        fixture["raw_header"] + '<text><body>' +
                        fixture["raw_excerpt"] + '</body></text></TEI>')
    title = root.find(".//t:title[@type='document']", NS)
    if title is None or title.get("key") != "20002" or title.get("n") != "02":
        raise ValueError("Transcription identity mismatch")
    pages, columns = root.findall(".//t:pb", NS), root.findall(".//t:cb", NS)
    if (len(pages) != 1 or pages[0].get("n") != "127v" or
            len(columns) != 1 or columns[0].get("n") != "2"):
        raise ValueError("Transcription page/column differs from reviewed location")
    verses = root.findall(".//t:div[@type='chapter']/t:ab", NS)
    if [v.get("n") for v in verses] != REFS:
        raise ValueError("Transcription differs from the five-verse review scope")
    line = 1
    for verse in verses:
        ref = verse.get("n")
        words = [w for w in verse.findall("t:w", NS) if not len(w) and w.text == ANCHORS[ref]]
        if len(words) != 1:
            raise ValueError("Reviewed surviving base-text anchor missing or ambiguous")
        if verse.findall(".//t:app", NS):
            raise ValueError("Writing-layer change needs a new source review")
        for node in verse.iter():
            if node.tag == f"{{{NS['t']}}}lb":
                line += 1
            elif node is words[0] and line != LINES[ref]:
                raise ValueError("Reviewed relative line anchor changed")
    return verses


def load_inputs(review_path=REVIEW):
    review = read_json(review_path)
    base, inventory, _, _ = load_p46(BASE_REVIEW)
    date.fromisoformat(review["reviewed_on"])
    expected = {
        "format_version": 1, "review_id": "gal1-overlap-reviewed-v1",
        "base_review": "benchmarks/gal1-p46-reviewed-v1.json",
        "inventory_id": inventory["inventory_id"], "policy_id": "gal1-overlap-conditional-v1",
        "doc_id": 20002, "ga_num": "02", "witness_id": "02-alexandrinus",
        "unit_id": "02-alexandrinus-gal1-original", "consensus_status": "unknown",
        "metadata_fixture": "tests/fixtures/alexandrinus_metadata_probe.json",
        "index_fixture": "tests/fixtures/alexandrinus_coverage_probe.json",
        "transcription_fixture": "tests/fixtures/alexandrinus-gal1-transcription.json",
    }
    if (any(review.get(key) != value for key, value in expected.items()) or
            review.get("independent_human_validation") is not False or
            [r["osis_ref"] for r in review["positive_reviews"]] != REFS):
        raise ValueError("Unsupported Galatians overlap review scope")
    for key in ("reviewer", "witness_label", "classification_citation", "identity_citation",
                "unit_label", "unit_reason", "unit_citation", "coverage_citation",
                "consensus_note", "discovery_note"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Review requires {key}")
    metadata, index = (read_json(ROOT / review[key]) for key in ("metadata_fixture", "index_fixture"))
    payload = checked_capture(metadata, "metadata/manuscript/get", "10", 20002)
    normalized = parse_metadata(payload, 20002)
    if normalized["ga_num"] not in ("02", "2"):
        raise ValueError("Metadata manuscript identity mismatch")
    manuscript = payload["data"]["manuscript"]
    pages = [p for p in manuscript["pages"]["page"] if p["pageID"] == 1081]
    if (len(pages) != 1 or pages[0]["folio"] != "127v" or pages[0]["indexContent"] !=
            "2Cor 13:9-14; 2Cor subscriptio; Gal inscriptio; Gal 1:1-14"):
        raise ValueError("Metadata does not identify reviewed page/folio")
    pairs = set(parse_coverage(checked_capture(index, "biblicalcontent/get", "long", 20002), 20002))
    checked_transcription(read_json(ROOT / review["transcription_fixture"]))
    for row in review["positive_reviews"]:
        if (row["page_id"] != 1081 or row["folio"] != "127v" or
                row["anchor"] != ANCHORS[row["osis_ref"]] or
                (row["osis_ref"], row["page_id"]) not in pairs):
            raise ValueError("Reviewed anchor does not match indexed page/folio")
        if not row["source_locator"].strip() or not row["reason"].strip():
            raise ValueError("Review requires source locations and reasons")
    assessments = review["assessments"]
    if (len(assessments) != 1 or
            [(a["status"], a["date_min"], a["date_max"], a["original_notation"])
             for a in assessments] != [("valid", 400, 499, "V")] or
            not assessments[0]["citation"].strip() or
            manuscript["originYear"] != {"early": 400, "late": 499, "content": "V"}):
        raise ValueError("Date assessment differs from reviewed source bounds")
    return review, base, metadata, index


def apply(db_path, review_path=REVIEW):
    review, base, metadata, index = load_inputs(review_path)
    if Path(db_path).exists():
        raise ValueError("Galatians overlap replay requires a fresh database path")
    replay_p46(db_path, BASE_REVIEW)
    with closing(connect(db_path)) as con:
        # Cache immutable raw metadata; ordinary collector/review interfaces
        # normalize it and create every historical decision.
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
            if collect_stage(client, 20002, stage) != "success" or client.attempts:
                raise ValueError("Alexandrinus cached collection did not complete offline")
        reviewer = review["reviewer"]
        record_candidate_review(con, 20002, metadata_id, "retain", "greek_manuscript",
                                "Catalogue and transcription identify a Greek codex",
                                review["classification_citation"], reviewer)
        record_witness_assignment(con, 20002, metadata_id, review["witness_id"],
                                  review["witness_label"], "Matching GA number and library shelfmark",
                                  review["identity_citation"], reviewer)
        create_writing_unit(con, review["unit_id"], review["witness_id"], review["unit_label"],
                            "original", review["unit_reason"], review["unit_citation"], reviewer)
        for a in review["assessments"]:
            record_date_assessment(con, review["unit_id"], a["status"], a["date_min"],
                                   a["date_max"], a["original_notation"], a["citation"],
                                   review["reviewed_on"], reviewer)
        for unit in (base["unit_id"], review["unit_id"]):
            select_date_assessment(con, unit, None, review["policy_id"], review["consensus_note"], reviewer)
        for row in review["positive_reviews"]:
            coverage_id = record_coverage_review(
                con, review["inventory_id"], row["osis_ref"], row["osis_ref"], 20002,
                row["page_id"], index_id, "partial", "reviewed_transcription", row["reason"],
                review["coverage_citation"] + " Location: " + row["source_locator"], reviewer)
            assign_coverage_unit(con, coverage_id, review["unit_id"], review["unit_reason"],
                                 review["unit_citation"], reviewer)
        verified = coverage_review_report(con, review["inventory_id"])["verified_witnesses"]
        if (set(verified) != set(REFS) or
                any(set(ids) != {base["witness_id"], review["witness_id"]} for ids in verified.values())):
            raise ValueError("Replay did not yield both declared witnesses per verse")
        return {"review_id": review["review_id"], "inventory_id": review["inventory_id"],
                "policy_id": review["policy_id"], "reviewed_witnesses": 2,
                "positive_witness_verse_pairs": sum(map(len, verified.values())),
                "date_assessments": len(base["assessments"]) + len(review["assessments"]),
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
                   "planned_witnesses": 2, "planned_positive_pairs": 10, "network_attempts": 0}
                  if args.dry_run else apply(args.db, args.review))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, sqlite3.Error) as error:
        print(f"Galatians overlap replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
