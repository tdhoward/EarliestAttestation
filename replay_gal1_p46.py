#!/usr/bin/env python3
"""Replay the source-reviewed P46 Galatians 1:1-5 increment offline."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

from controlled_ntvmr import (
    API_BASE, Client, assign_coverage_unit, collect_stage, connect,
    create_writing_unit, encoded, import_coverage_fixture, import_edition_inventory,
    parse_coverage, parse_metadata, record_candidate_review, record_coverage_review,
    record_date_assessment, record_witness_assignment, select_date_assessment,
    validate_inventory,
)

ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "benchmarks/gal1-p46-reviewed-v1.json"
INVENTORY = ROOT / "benchmarks/gal1-na28-subset-v1.json"
REFS = [f"Gal.1.{verse}" for verse in range(1, 6)]
XML_URL = "https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_P46_Gal.xml"
NS = {"t": "http://www.tei-c.org/ns/1.0"}
ANCHORS = dict(zip(REFS, ["παυλος", "παντες", "χαρις", "αμαρτιων", "δοξα"]))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def checked_transcription(fixture):
    """Guard this reviewed excerpt; this is not an automated survival classifier."""
    if fixture["source_url"] != XML_URL:
        raise ValueError("Unexpected transcription source")
    for part in ("header", "excerpt"):
        if hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest() != fixture[f"{part}_sha256"]:
            raise ValueError("Transcription hash mismatch")
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0">' +
                         fixture["raw_header"] + '<text><body>' +
                         fixture["raw_excerpt"] + '</body></text></TEI>')
    title = root.find(".//t:title[@type='document']", NS)
    if title is None or title.get("key") != "10046" or title.get("n") != "P46":
        raise ValueError("Transcription identity mismatch")
    pages = root.findall(".//t:pb", NS)
    if len(pages) != 1 or pages[0].get("n") != "81r":
        raise ValueError("Transcription page differs from reviewed folio 81r")
    verses = root.findall(".//t:div[@type='chapter']/t:ab", NS)
    if [v.get("n") for v in verses] != REFS:
        raise ValueError("Transcription differs from the five-verse review scope")
    for verse in verses:
        # Entire direct words only: no supplied/unclear letters or apparatus.
        words = [w.text for w in verse.findall("t:w", NS) if not len(w)]
        if ANCHORS[verse.get("n")] not in words:
            raise ValueError("Reviewed surviving base-text anchor missing")
        if verse.findall(".//t:app", NS):
            raise ValueError("Writing-layer change needs a new source review")
    return verses


def checked_capture(fixture, endpoint, detail, doc_id=10046):
    if (fixture.get("canonical_source_url", fixture["source_url"]) !=
            f"{API_BASE}/{endpoint}/" or
            not fixture["source_url"].endswith(f"/{endpoint}/") or
            fixture["http_status"] != 200 or
            fixture["params"] != {"docID": str(doc_id), "detail": detail, "format": "json"} or
            hashlib.sha256(fixture["raw_body"].encode()).hexdigest() != fixture["body_sha256"]):
        raise ValueError("Captured source, scope, or hash mismatch")
    datetime.fromisoformat(fixture["retrieved_at"])
    return json.loads(fixture["raw_body"])


def load_inputs(review_path=REVIEW):
    review, inventory = read_json(review_path), read_json(INVENTORY)
    validate_inventory(inventory)
    date.fromisoformat(review["reviewed_on"])
    if (review.get("format_version") != 1 or review.get("review_id") != "gal1-p46-reviewed-v1" or
            review.get("inventory_id") != inventory["inventory_id"] or
            review.get("independent_human_validation") is not False or
            review.get("consensus_status") != "unknown" or
            review.get("doc_id") != 10046 or review.get("ga_num") != "P46" or
            review.get("witness_id") != "p46-chester-beatty-michigan" or
            review.get("unit_id") != "p46-gal1-original" or
            [v["osis_ref"] for v in inventory["verses"]] != REFS or
            any(v["ntvmr_refs"] != [v["osis_ref"]] for v in inventory["verses"]) or
            [r["osis_ref"] for r in review["positive_reviews"]] != REFS):
        raise ValueError("Unsupported P46 review scope")
    parent = read_json(ROOT / "benchmarks/na28-nt-reference-provisional-v3.json")
    statuses = {v["osis_ref"]: v["editorial_status"] for v in parent["verses"]}
    if any(v["editorial_status"] != statuses[v["osis_ref"]] for v in inventory["verses"]):
        raise ValueError("Subset differs from the pinned edition inventory")
    for field, name in (("metadata_fixture", "p46_metadata_probe.json"),
                        ("index_fixture", "p46_coverage_probe.json"),
                        ("transcription_fixture", "p46-gal1-transcription.json")):
        if review[field] != f"tests/fixtures/{name}":
            raise ValueError("Unexpected P46 fixture path")
    metadata = read_json(ROOT / review["metadata_fixture"])
    index = read_json(ROOT / review["index_fixture"])
    payload = checked_capture(metadata, "metadata/manuscript/get", "10")
    normalized = parse_metadata(payload, 10046)
    manuscript = payload["data"]["manuscript"]
    if normalized["ga_num"] != "P46":
        raise ValueError("Metadata manuscript identity mismatch")
    pages = [p for p in manuscript["pages"]["page"] if p["pageID"] == 1421]
    if (len(pages) != 1 or pages[0]["folio"] != "81r" or
            pages[0]["indexContent"] != "Eph 6:20-24; Gal inscriptio; Gal 1:1-8"):
        raise ValueError("Metadata does not identify reviewed page/folio")
    pairs = set(parse_coverage(checked_capture(index, "biblicalcontent/get", "long"), 10046))
    checked_transcription(read_json(ROOT / review["transcription_fixture"]))
    for row in review["positive_reviews"]:
        if (row["page_id"] != 1421 or row["folio"] != "81r" or
                row["anchor"] != ANCHORS[row["osis_ref"]] or
                (row["osis_ref"], row["page_id"]) not in pairs):
            raise ValueError("Reviewed anchor does not match indexed page/folio")
        if not row["source_locator"].strip() or not row["reason"].strip():
            raise ValueError("Review requires source locations and reasons")
    assessments = review["assessments"]
    expected = [(200, 225, "III (A)"), (201, 300, "third century AD")]
    if ([(a["date_min"], a["date_max"], a["original_notation"]) for a in assessments] != expected or
            any(a["status"] != "valid" or not a["citation"].strip() for a in assessments) or
            manuscript["originYear"] != {"early": 200, "late": 225, "content": "III (A)"}):
        raise ValueError("Date assessments differ from reviewed source bounds")
    for key in ("policy_id", "reviewer", "witness_label", "classification_citation",
                "identity_citation", "unit_label", "unit_reason", "unit_citation",
                "coverage_citation", "discovery_note"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Review requires {key}")
    return review, inventory, metadata, index


def apply(db_path, review_path=REVIEW):
    review, inventory, metadata, index = load_inputs(review_path)
    if Path(db_path).exists():
        raise ValueError("P46 replay requires a fresh database path")
    with closing(connect(db_path)) as con:
        import_edition_inventory(con, inventory)
        # Cache the captured metadata only. All normalization and historical
        # decisions below go through the ordinary collection/review APIs.
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
            if collect_stage(client, 10046, stage) != "success" or client.attempts:
                raise ValueError("P46 cached collection did not complete offline")
        reviewer = review["reviewer"]
        record_candidate_review(con, 10046, metadata_id, "retain", "greek_manuscript",
                                "Catalogue and transcription identify a Greek papyrus codex",
                                review["classification_citation"], reviewer)
        record_witness_assignment(con, 10046, metadata_id, review["witness_id"],
                                  review["witness_label"], "Two holding institutions share one codex",
                                  review["identity_citation"], reviewer)
        create_writing_unit(con, review["unit_id"], review["witness_id"], review["unit_label"],
                            "original", review["unit_reason"], review["unit_citation"], reviewer)
        for a in review["assessments"]:
            record_date_assessment(con, review["unit_id"], a["status"], a["date_min"],
                                   a["date_max"], a["original_notation"], a["citation"],
                                   review["reviewed_on"], reviewer)
        select_date_assessment(con, review["unit_id"], None, review["policy_id"],
                               review["consensus_note"], reviewer)
        for row in review["positive_reviews"]:
            coverage_id = record_coverage_review(
                con, inventory["inventory_id"], row["osis_ref"], row["osis_ref"], 10046,
                row["page_id"], index_id, "partial", "reviewed_transcription", row["reason"],
                review["coverage_citation"] + " Location: " + row["source_locator"], reviewer)
            assign_coverage_unit(con, coverage_id, review["unit_id"], review["unit_reason"],
                                 review["unit_citation"], reviewer)
        return {"review_id": review["review_id"], "inventory_id": inventory["inventory_id"],
                "policy_id": review["policy_id"], "reviewed_witnesses": 1,
                "positive_witness_verse_pairs": len(review["positive_reviews"]),
                "date_assessments": len(review["assessments"]),
                "network_attempts": con.execute("SELECT count(*) FROM request_attempt").fetchone()[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        review, inventory, _, _ = load_inputs(args.review)
        result = ({"planned_review_id": review["review_id"],
                   "planned_inventory_id": inventory["inventory_id"],
                   "planned_positive_pairs": 5, "network_attempts": 0}
                  if args.dry_run else apply(args.db, args.review))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, sqlite3.Error) as error:
        print(f"P46 replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
