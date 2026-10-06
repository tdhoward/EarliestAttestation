#!/usr/bin/env python3
"""Replay three Galatians 1:1-5 witnesses with explicit Sinaiticus layer review."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date
import hashlib
from pathlib import Path
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET

from controlled_ntvmr import (
    Client, assign_coverage_unit, collect_stage, connect, coverage_review_report,
    create_writing_unit, encoded, import_coverage_fixture, parse_coverage,
    parse_metadata, record_candidate_review, record_coverage_review,
    record_date_assessment, record_witness_assignment, select_date_assessment,
)
from replay_gal1_p46 import NS, REFS, ROOT, checked_capture, read_json
from replay_gal1_prototype import apply as replay_overlap, load_inputs as load_overlap

REVIEW = ROOT / "benchmarks/gal1-sinaiticus-reviewed-v1.json"
BASE_REVIEW = ROOT / "benchmarks/gal1-overlap-reviewed-v1.json"
XML_URL = "https://itseeweb.cal.bham.ac.uk/epistulae/transcriptions/greek/Gal/NT_GRC_01_Gal.xml"
DATE_URL = "https://www.codexsinaiticus.org/en/codex/date.aspx"
DATE_TEXT = ("Codex Sinaiticus is generally dated to the fourth century, and sometimes "
             "more precisely to the middle of that century.")
ANCHORS = dict(zip(REFS, ["παυλος", "αδελφοι", "ειρηνη", "αμαρτιων", "δοξα"]))
LINES = dict(zip(REFS, [1, 8, 11, 15, 21]))
# Each tuple records type, hand, rendition and transcribed words. These are
# bounded review guards, not a general TEI survival or corrector classifier.
APPARATUS = {
    "Gal.1.1": [(("orig", "firsthand", None, ("αυτων",)),
                 ("corr", "corrector1", "strikethrough", ("αυτον",)))],
    "Gal.1.2": [], "Gal.1.3": [],
    "Gal.1.4": [(("orig", "firsthand", None, ("περι",)),
                 ("corr", "corrector2", "strikethrough", ("υπερ",))),
                (("orig", "firsthand", None, ("αιωνος", "του", "ενεστωτος")),
                 ("corr", "corrector2", "transposition_marks", ("ενεστωτος", "αιωνος"))),
                (("orig", "firsthand", None, ()),
                 ("corr", "corrector2", None, ("το",)))],
    "Gal.1.5": [],
}


def checked_transcription(fixture):
    """Require reviewed direct anchors and preserve the known correction layers."""
    if fixture["source_url"] != XML_URL:
        raise ValueError("Unexpected Sinaiticus transcription source")
    for part in ("header", "excerpt"):
        if hashlib.sha256(fixture[f"raw_{part}"].encode()).hexdigest() != fixture[f"{part}_sha256"]:
            raise ValueError("Transcription hash mismatch")
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0">' +
                        fixture["raw_header"] + '<text><body>' +
                        fixture["raw_excerpt"] + '</body></text></TEI>')
    title = root.find(".//t:title[@type='document']", NS)
    shelfmark = root.find(".//t:msIdentifier/t:idno", NS)
    if (title is None or title.get("key") != "20001" or title.get("n") != "01" or
            shelfmark is None or shelfmark.text != "Add. 43725"):
        raise ValueError("Transcription identity mismatch")
    pages, columns = root.findall(".//t:pb", NS), root.findall(".//t:cb", NS)
    if (len(pages) != 1 or pages[0].get("n") != "278v" or
            len(columns) != 1 or columns[0].get("n") != "3"):
        raise ValueError("Transcription page/column differs from reviewed location")
    verses = root.findall(".//t:div[@type='chapter']/t:ab", NS)
    if [v.get("n") for v in verses] != REFS:
        raise ValueError("Transcription differs from the five-verse review scope")
    line = 1
    for verse in verses:
        ref = verse.get("n")
        if verse.attrib != {"n": ref}:
            raise ValueError("Writing-layer change needs a new source review")
        words = [w for w in verse.findall("t:w", NS)
                 if not len(w) and not w.attrib and w.text == ANCHORS[ref]]
        if len(words) != 1:
            raise ValueError("Reviewed surviving base-text anchor missing or ambiguous")
        apparatus = [tuple((r.get("type"), r.get("hand"), r.get("rend"),
                            tuple("".join(w.itertext()) for w in r.findall(".//t:w", NS)))
                           for r in app.findall("t:rdg", NS))
                     for app in verse.findall(".//t:app", NS)]
        if apparatus != APPARATUS[ref]:
            raise ValueError("Writing-layer apparatus needs a new source review")
        for node in verse.iter():
            if node.tag == f"{{{NS['t']}}}lb":
                line += 1
            elif node is words[0] and line != LINES[ref]:
                raise ValueError("Reviewed relative line anchor changed")
    return verses


def load_inputs(review_path=REVIEW):
    review = read_json(review_path)
    overlap, p46, _, _ = load_overlap(BASE_REVIEW)
    date.fromisoformat(review["reviewed_on"])
    expected = {
        "format_version": 1, "review_id": "gal1-sinaiticus-reviewed-v1",
        "base_review": "benchmarks/gal1-overlap-reviewed-v1.json",
        "inventory_id": overlap["inventory_id"], "policy_id": "gal1-three-witness-conditional-v1",
        "doc_id": 20001, "ga_num": "01", "witness_id": "01-sinaiticus",
        "unit_id": "01-sinaiticus-gal1-original", "consensus_status": "unknown",
        "metadata_fixture": "tests/fixtures/sinaiticus_metadata_probe.json",
        "index_fixture": "tests/fixtures/sinaiticus_coverage_probe.json",
        "transcription_fixture": "tests/fixtures/sinaiticus-gal1-transcription.json",
        "date_source_fixture": "tests/fixtures/sinaiticus-date-source.json",
    }
    if (any(review.get(key) != value for key, value in expected.items()) or
            review.get("independent_human_validation") is not False or
            [r["osis_ref"] for r in review["positive_reviews"]] != REFS):
        raise ValueError("Unsupported Sinaiticus review scope")
    for key in ("reviewer", "witness_label", "classification_citation", "identity_citation",
                "unit_label", "unit_reason", "unit_citation", "coverage_citation",
                "consensus_note", "discovery_note"):
        if not isinstance(review.get(key), str) or not review[key].strip():
            raise ValueError(f"Review requires {key}")
    metadata, index = (read_json(ROOT / review[key]) for key in ("metadata_fixture", "index_fixture"))
    payload = checked_capture(metadata, "metadata/manuscript/get", "10", 20001)
    if parse_metadata(payload, 20001)["ga_num"] not in ("01", "1"):
        raise ValueError("Metadata manuscript identity mismatch")
    manuscript = payload["data"]["manuscript"]
    pages = [p for p in manuscript["pages"]["page"] if p["pageID"] == 1580]
    if (len(pages) != 1 or pages[0]["folio"] != "278v" or pages[0]["indexContent"] !=
            "2Cor 13:5-13; 2Cor subscriptio; Gal inscriptio; Gal 1:1-17"):
        raise ValueError("Metadata does not identify reviewed page/folio")
    pairs = set(parse_coverage(checked_capture(index, "biblicalcontent/get", "long", 20001), 20001))
    checked_transcription(read_json(ROOT / review["transcription_fixture"]))
    for row in review["positive_reviews"]:
        ref = row["osis_ref"]
        if (row["page_id"] != 1580 or row["folio"] != "278v" or
                row["anchor"] != ANCHORS[ref] or row["relative_line"] != LINES[ref] or
                (ref, row["page_id"]) not in pairs):
            raise ValueError("Reviewed anchor does not match indexed page/folio")
        if not row["source_locator"].strip() or not row["reason"].strip():
            raise ValueError("Review requires source locations and reasons")
    source = read_json(ROOT / review["date_source_fixture"])
    if (source["source_url"] != DATE_URL or source["source_text"] != DATE_TEXT or
            source["source_text_sha256"] != hashlib.sha256(DATE_TEXT.encode()).hexdigest()):
        raise ValueError("Project date source changed")
    date.fromisoformat(source["consulted_on"])
    assessments = review["assessments"]
    if ([(a["status"], a["date_min"], a["date_max"], a["original_notation"])
         for a in assessments] != [("valid", 300, 399, "IV"),
                                   ("valid", 301, 400, "fourth century"),
                                   ("unknown", None, None, "middle of that century")] or
            any(not a["citation"].strip() for a in assessments) or
            manuscript["originYear"] != {"early": 300, "late": 399, "content": "IV"}):
        raise ValueError("Date assessment differs from reviewed source bounds")
    return review, overlap, p46, metadata, index


def apply(db_path, review_path=REVIEW):
    review, overlap, p46, metadata, index = load_inputs(review_path)
    if Path(db_path).exists():
        raise ValueError("Sinaiticus replay requires a fresh database path")
    replay_overlap(db_path, BASE_REVIEW)
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
            if collect_stage(client, 20001, stage) != "success" or client.attempts:
                raise ValueError("Sinaiticus cached collection did not complete offline")
        reviewer = review["reviewer"]
        record_candidate_review(con, 20001, metadata_id, "retain", "greek_manuscript",
                                "Catalogue and transcription identify a Greek codex",
                                review["classification_citation"], reviewer)
        record_witness_assignment(con, 20001, metadata_id, review["witness_id"],
                                  review["witness_label"], "Matching GA number and library shelfmark",
                                  review["identity_citation"], reviewer)
        create_writing_unit(con, review["unit_id"], review["witness_id"], review["unit_label"],
                            "original", review["unit_reason"], review["unit_citation"], reviewer)
        for a in review["assessments"]:
            record_date_assessment(con, review["unit_id"], a["status"], a["date_min"],
                                   a["date_max"], a["original_notation"], a["citation"],
                                   review["reviewed_on"], reviewer)
        for unit in (p46["unit_id"], overlap["unit_id"], review["unit_id"]):
            select_date_assessment(con, unit, None, review["policy_id"], review["consensus_note"], reviewer)
        for row in review["positive_reviews"]:
            coverage_id = record_coverage_review(
                con, review["inventory_id"], row["osis_ref"], row["osis_ref"], 20001,
                row["page_id"], index_id, "partial", "reviewed_transcription", row["reason"],
                review["coverage_citation"] + " Location: " + row["source_locator"], reviewer)
            assign_coverage_unit(con, coverage_id, review["unit_id"], review["unit_reason"],
                                 review["unit_citation"], reviewer)
        verified = coverage_review_report(con, review["inventory_id"])["verified_witnesses"]
        witnesses = {p46["witness_id"], overlap["witness_id"], review["witness_id"]}
        if set(verified) != set(REFS) or any(set(ids) != witnesses for ids in verified.values()):
            raise ValueError("Replay did not yield three declared witnesses per verse")
        return {"review_id": review["review_id"], "inventory_id": review["inventory_id"],
                "policy_id": review["policy_id"], "reviewed_witnesses": 3,
                "positive_witness_verse_pairs": sum(map(len, verified.values())),
                "date_assessments": sum(len(r["assessments"]) for r in (p46, overlap, review)),
                "network_attempts": con.execute("SELECT count(*) FROM request_attempt").fetchone()[0]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=REVIEW)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        review, _, _, _, _ = load_inputs(args.review)
        result = ({"planned_review_id": review["review_id"], "planned_inventory_id": review["inventory_id"],
                   "planned_witnesses": 3, "planned_positive_pairs": 15, "network_attempts": 0}
                  if args.dry_run else apply(args.db, args.review))
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, sqlite3.Error) as error:
        print(f"Sinaiticus replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
