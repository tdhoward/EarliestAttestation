#!/usr/bin/env python3
"""Replay the cited John 1:1-5 four-witness prototype offline."""

from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from controlled_ntvmr import (
    Client, assign_coverage_unit, collect_stage, connect, coverage_review_report,
    create_writing_unit, import_coverage_fixture, import_edition_inventory,
    parse_coverage, record_candidate_review, record_coverage_review,
    record_date_assessment, record_witness_assignment, select_date_assessment,
    validate_inventory,
)
from replay_john1_candidates import apply as replay_candidates


ROOT = Path(__file__).resolve().parent
REVIEW = ROOT / "benchmarks" / "john1-reviewed-v3.json"
INVENTORY = ROOT / "benchmarks" / "john1-na28-subset-v2.json"
SEARCHES = ROOT / "tests" / "fixtures" / "john_named_probe.json"
REFS = [f"John.1.{verse}" for verse in range(1, 6)]


def load_inputs(review_path=REVIEW):
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    searches = json.loads(SEARCHES.read_text(encoding="utf-8"))
    validate_inventory(inventory)
    if ([row["osis_ref"] for row in inventory["verses"]] != REFS or
            any(row["ntvmr_refs"] != [row["osis_ref"]] for row in inventory["verses"])):
        raise ValueError("John 1 review requires five direct inventory mappings")
    if (review.get("format_version") != 1 or
            review.get("inventory_id") != inventory["inventory_id"] or
            not review.get("review_id") or not review.get("policy_id") or
            not review.get("reviewer") or not review.get("discovery_note") or
            len(review.get("witnesses", [])) not in (3, 4)):
        raise ValueError("John 1 review manifest has an unsupported shape")
    date.fromisoformat(review["reviewed_on"])
    expected = {"P66": 10066, "P75": 10075, "01": 20001, "02": 20002}
    discovered = {case["params"]["gaNum"]: json.loads(case["raw_body"])
                  ["data"]["manuscripts"]["manuscript"]["docID"]
                  for case in searches["cases"]}
    if any(discovered.get(name) != doc_id for name, doc_id in expected.items()):
        raise ValueError("Reviewed documents differ from captured named searches")
    identity_only = review.get("identity_only_candidates", [])
    records = review["witnesses"] + identity_only
    names = [w.get("ga_num") for w in records]
    if (len(names) != len(set(names)) or set(names) != set(expected) or
            any(expected.get(w.get("ga_num")) != w.get("doc_id") for w in records) or
            len({w.get("witness_id") for w in records}) != len(records) or
            len({w.get("unit_id") for w in review["witnesses"]}) != len(review["witnesses"])):
        raise ValueError("John 1 review must identify each captured witness exactly once")
    if identity_only and (len(identity_only) != 1 or identity_only[0]["ga_num"] != "02"):
        raise ValueError("Only captured 02 may remain an identity-only review")
    for candidate in identity_only:
        for key in ("witness_id", "witness_label", "classification_citation",
                    "identity_citation", "review_limit"):
            if not isinstance(candidate.get(key), str) or not candidate[key].strip():
                raise ValueError(f"02 identity-only review requires {key}")
    fixtures = {}
    for witness in review["witnesses"]:
        if expected.get(witness["ga_num"]) != witness["doc_id"]:
            raise ValueError("Unexpected John 1 witness or document ID")
        if witness["consensus_status"] != "unknown":
            raise ValueError("Consensus requires an independently cited review")
        for key in ("witness_id", "witness_label", "classification_citation",
                    "identity_citation", "coverage_citation", "coverage_reason",
                    "unit_id", "unit_label", "unit_citation", "unit_reason"):
            if not isinstance(witness.get(key), str) or not witness[key].strip():
                raise ValueError(f"John 1 review requires {key}")
        fixture_path = ROOT / witness["index_fixture"]
        if fixture_path.parent != ROOT / "tests" / "fixtures":
            raise ValueError("Coverage fixture must be checked in under tests/fixtures")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        if fixture["params"] != {"docID": str(witness["doc_id"]),
                                  "detail": "long", "format": "json"}:
            raise ValueError("Coverage fixture request differs from review")
        if hashlib.sha256(fixture["raw_body"].encode("utf-8")).hexdigest() != fixture["body_sha256"]:
            raise ValueError("Coverage fixture body hash mismatch")
        pairs = set(parse_coverage(json.loads(fixture["raw_body"]), witness["doc_id"]))
        if any((ref, witness["page_id"]) not in pairs for ref in REFS):
            raise ValueError("Coverage fixture lacks a reviewed verse/page pair")
        if witness["ga_num"] in ("P66", "02"):
            name = witness["ga_num"]
            metadata_file, folio, content = {
                "P66": ("p66_metadata_probe.json", 1, "John 1:1-14"),
                "02": ("alexandrinus_metadata_probe.json", "66r",
                       "John inscriptio; John 1:1-18"),
            }[name]
            metadata_path = ROOT / witness.get("page_metadata_fixture", "")
            if metadata_path != ROOT / "tests" / "fixtures" / metadata_file:
                raise ValueError(f"{name} page link requires the checked-in metadata fixture")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if (metadata["params"] != {"detail": "10", "docID": str(witness["doc_id"]), "format": "json"}
                    or metadata.get("canonical_source_url", metadata["source_url"]) !=
                    "https://ntvmr.uni-muenster.de/community/vmr/api/metadata/manuscript/get/"
                    or metadata["http_status"] != 200
                    or hashlib.sha256(metadata["raw_body"].encode("utf-8")).hexdigest()
                    != metadata["body_sha256"]):
                raise ValueError(f"{name} page metadata source or hash mismatch")
            manuscript = json.loads(metadata["raw_body"])["data"]["manuscript"]
            pages = manuscript["pages"]["page"]
            linked = [page for page in pages if page["pageID"] == witness["page_id"]]
            if (manuscript["docID"] != witness["doc_id"] or len(linked) != 1
                    or linked[0]["folio"] != folio
                    or linked[0]["indexContent"] != content):
                raise ValueError(f"{name} indexed page is not the first John folio")
            if name == "02":
                image_check = witness["image_check"]
                if (witness["coverage_evidence_type"] != "checked_image" or
                        image_check["source_url"] != linked[0]["images"]["image"]["uri"] or
                        image_check["reviewer"] != review["reviewer"] or
                        image_check["independent_human_validation"] is not False or
                        len(image_check["image_sha256"]) != 64 or
                        any(c not in "0123456789abcdef" for c in image_check["image_sha256"])):
                    raise ValueError("02 image review does not match the indexed public image")
        if not witness.get("assessments") or not any(
                item["status"] == "valid" for item in witness["assessments"]):
            raise ValueError("Each reviewed witness requires a usable assessment")
        fixtures[witness["doc_id"]] = (fixture_path, fixture)
    return review, inventory, fixtures


def apply(db_path, review_path=REVIEW):
    review, inventory, fixtures = load_inputs(review_path)
    # Refuse an existing destination before candidate replay can append anything.
    # A separate database preserves earlier manifests and manual reviews.
    if Path(db_path).exists():
        raise ValueError("John 1 review replay requires a fresh database path")
    replay_candidates(db_path)
    con = connect(db_path)
    try:
        if con.execute("SELECT 1 FROM coverage_review WHERE inventory_id=? LIMIT 1",
                       (inventory["inventory_id"],)).fetchone():
            raise ValueError("John 1 review replay requires a fresh database")
        import_edition_inventory(con, inventory)
        for identity_only in review.get("identity_only_candidates", []):
            source = con.execute("""SELECT response_id FROM discovery_candidate
                WHERE run_id=? AND osis_ref='John.1.1' AND ga_num_query='02'
                AND doc_id=20002""", ("john-four-named-20260929",)).fetchone()
            if source is None:
                raise ValueError("Named search candidate missing for 02")
            search_response_id = source[0]
            record_candidate_review(
                con, 20002, search_response_id, "retain", "greek_manuscript",
                "The cited British Library catalogue identifies GA 02 as a Greek manuscript",
                identity_only["classification_citation"], review["reviewer"])
            record_witness_assignment(
                con, 20002, search_response_id, identity_only["witness_id"],
                identity_only["witness_label"],
                "The cited British Library shelfmark and GA number identify the physical volume",
                identity_only["identity_citation"], review["reviewer"])
        for witness in review["witnesses"]:
            doc_id = witness["doc_id"]
            fixture_path, fixture = fixtures[doc_id]
            index_response_id = import_coverage_fixture(con, fixture_path)
            base_url = fixture["source_url"].removesuffix("/biblicalcontent/get/")
            client = Client(con, f"{review['review_id']}-{doc_id}",
                            base_url=base_url, offline=True)
            if collect_stage(client, doc_id, "coverage") != "success" or client.attempts:
                raise ValueError(f"Offline index replay failed for {doc_id}")
            source = con.execute("""SELECT response_id FROM discovery_candidate
                WHERE run_id=? AND osis_ref='John.1.1' AND ga_num_query=?
                AND doc_id=?""", ("john-four-named-20260929",
                                  witness["ga_num"], doc_id)).fetchone()
            if source is None:
                raise ValueError(f"Named search candidate missing for {doc_id}")
            search_response_id = source[0]
            record_candidate_review(
                con, doc_id, search_response_id, "retain", "greek_manuscript",
                "The cited source identifies this candidate as a Greek manuscript",
                witness["classification_citation"], review["reviewer"])
            record_witness_assignment(
                con, doc_id, search_response_id, witness["witness_id"],
                witness["witness_label"],
                "The cited manuscript identity matches the captured catalogue candidate",
                witness["identity_citation"], review["reviewer"])
            create_writing_unit(
                con, witness["unit_id"], witness["witness_id"],
                witness["unit_label"], "original", witness["unit_reason"],
                witness["unit_citation"], review["reviewer"])
            for assessment in witness["assessments"]:
                record_date_assessment(
                    con, witness["unit_id"], assessment["status"],
                    assessment["date_min"], assessment["date_max"],
                    assessment["original_notation"], assessment["citation"],
                    review["reviewed_on"], review["reviewer"])
            select_date_assessment(
                con, witness["unit_id"], None, review["policy_id"],
                "No scholar is preferred: consensus status is unknown; dated graph results are conditional on the cited assessment",
                review["reviewer"])
            for ref in REFS:
                review_id = record_coverage_review(
                    con, inventory["inventory_id"], ref, ref, doc_id,
                    witness["page_id"], index_response_id, "partial",
                    witness["coverage_evidence_type"],
                    witness["coverage_reason"], witness["coverage_citation"],
                    review["reviewer"])
                assign_coverage_unit(
                    con, review_id, witness["unit_id"],
                    witness["unit_reason"], witness["unit_citation"],
                    review["reviewer"])
        verified = coverage_review_report(con, inventory["inventory_id"])["verified_witnesses"]
        expected_ids = {w["witness_id"] for w in review["witnesses"]}
        if set(verified) != set(REFS) or any(set(ids) != expected_ids for ids in verified.values()):
            raise ValueError("John 1 replay did not yield the declared witnesses per verse")
        return {"review_id": review["review_id"],
                "inventory_id": inventory["inventory_id"],
                "policy_id": review["policy_id"],
                "reviewed_witnesses": len(expected_ids),
                "positive_witness_verse_pairs": sum(map(len, verified.values())),
                "coverage_pending_candidates": [w["ga_num"] for w in
                                                review.get("identity_only_candidates", [])],
                "network_attempts": 0}
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--review", type=Path, default=REVIEW,
                        help="Cited review manifest (defaults to the current four-witness review)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        review, inventory, _ = load_inputs(args.review)
        result = ({"planned_review_id": review["review_id"],
                   "planned_inventory_id": inventory["inventory_id"],
                   "planned_witnesses": len(review["witnesses"]),
                   "planned_positive_pairs": len(REFS) * len(review["witnesses"]),
                   "network_attempts": 0} if args.dry_run else apply(args.db, args.review))
    except (OSError, ValueError, KeyError, sqlite3.Error) as error:
        print(f"John 1 prototype replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
