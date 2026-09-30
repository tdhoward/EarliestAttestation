#!/usr/bin/env python3
"""Replay the bounded, cited P52 coverage review without network requests."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

from audit_reviewed import (date_source_report, load_date_source, load_source_controls,
                            source_control_report)
from controlled_ntvmr import (Client, collect_search, collect_stage, connect,
                              coverage_review_report, create_writing_unit,
                              import_edition_inventory, record_date_assessment,
                              import_language_probe, import_p52, record_candidate_review,
                              record_coverage_review, record_witness_assignment,
                              select_date_assessment,
                              validate_inventory)

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "benchmarks" / "p52-reviewed-v1.json"
INVENTORY = ROOT / "benchmarks" / "p52-na28-john18-subset-v1.json"
COVERAGE_FIXTURE = ROOT / "tests" / "fixtures" / "p52_coverage_probe.json"
LANGUAGE_FIXTURE = ROOT / "tests" / "fixtures" / "p52_language_probe.json"
SOURCE_CONTROLS = ROOT / "benchmarks" / "p52-source-controls-v1.json"
DATE_SOURCE = ROOT / "benchmarks" / "p52-date-source-v1.json"
DATING_REVIEW = ROOT / "benchmarks" / "p52-dating-review-v1.json"
RUN_ID = "p52-reviewed-v1"


def load_review():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    required = {"format_version", "benchmark_id", "inventory_id", "policy_id", "doc_id",
                "witness_id", "witness_label", "reviewer", "reviewed_on",
                "classification_citation", "identity_citation", "coverage_citation",
                "coverage_reason", "coverage"}
    if not isinstance(config, dict) or set(config) != required or \
            type(config["format_version"]) is not int or config["format_version"] != 1:
        raise ValueError("P52 review configuration has an unsupported shape")
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    validate_inventory(inventory)
    controls = load_source_controls(SOURCE_CONTROLS)
    load_date_source(DATE_SOURCE)
    if (config["inventory_id"] != inventory["inventory_id"] or
            type(config["doc_id"]) is not int or config["doc_id"] != controls["doc_id"] or
            not isinstance(config["coverage"], list) or len(config["coverage"]) != 5):
        raise ValueError("P52 review does not match its inventory or source controls")
    if any(not isinstance(row, dict) or set(row) !=
           {"osis_ref", "ntvmr_ref", "page_id", "status"} or
           type(row["page_id"]) is not int for row in config["coverage"]):
        raise ValueError("P52 review has an invalid coverage entry")
    expected = {(row["osis_ref"], row["page_id"])
                for row in controls["indexed_refs_expected"]}
    mapped = {(row["osis_ref"], row["page_id"]) for row in config["coverage"]}
    if mapped != expected or any(row["ntvmr_ref"] != row["osis_ref"] or
                                 row["status"] != "partial" for row in config["coverage"]):
        raise ValueError("P52 review coverage differs from the pinned source controls")
    for key in ("benchmark_id", "policy_id", "witness_id", "witness_label", "reviewer",
                "classification_citation", "identity_citation", "coverage_citation",
                "coverage_reason"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(f"P52 review requires {key}")
    if not isinstance(config["reviewed_on"], str):
        raise ValueError("P52 review requires a review date")
    date.fromisoformat(config["reviewed_on"])
    return config, inventory


def load_dating_review(witness_id):
    review = json.loads(DATING_REVIEW.read_text(encoding="utf-8"))
    if (not isinstance(review, dict) or set(review) !=
            {"format_version", "review_id", "reviewer", "reviewed_on",
             "witness_id", "unit", "assessments", "selection"} or
            type(review["format_version"]) is not int or
            review["format_version"] != 1 or review["witness_id"] != witness_id or
            not isinstance(review["unit"], dict) or
            set(review["unit"]) != {"unit_id", "label", "kind", "reason", "citation"} or
            review["unit"]["kind"] != "original" or
            not isinstance(review["assessments"], list) or
            len(review["assessments"]) != 3 or
            not isinstance(review["selection"], dict) or
            set(review["selection"]) != {"policy_id", "assessment_id", "reason"} or
            review["selection"]["assessment_id"] is not None):
        raise ValueError("P52 dating review has an unsupported shape")
    if not isinstance(review["reviewed_on"], str):
        raise ValueError("P52 dating review requires an ISO review date")
    date.fromisoformat(review["reviewed_on"])
    required_text = [review["review_id"], review["reviewer"],
                     review["unit"]["unit_id"], review["unit"]["label"],
                     review["unit"]["reason"], review["unit"]["citation"],
                     review["selection"]["policy_id"],
                     review["selection"]["reason"]]
    for assessment in review["assessments"]:
        if not isinstance(assessment, dict) or set(assessment) != {
                "status", "date_min", "date_max", "original_notation", "citation"}:
            raise ValueError("P52 dating assessment has an unsupported shape")
        required_text.extend((assessment["original_notation"], assessment["citation"]))
    if any(not isinstance(value, str) or not value.strip()
           for value in required_text):
        raise ValueError("P52 dating review requires source and policy text")
    if (review["assessments"][0]["status"] != "valid" or
            (review["assessments"][0]["date_min"],
             review["assessments"][0]["date_max"],
             review["assessments"][0]["original_notation"]) != (125, 175, "II (M)") or
            any(a["status"] != "unknown" or a["date_min"] is not None or
                a["date_max"] is not None for a in review["assessments"][1:])):
        raise ValueError("P52 dating review differs from the bounded source claims")
    return review


def apply_dating_review(con, review):
    unit = review["unit"]
    unit_id = unit["unit_id"]
    expected_unit = (review["witness_id"], unit["label"], unit["kind"],
                     unit["reason"], unit["citation"], review["reviewer"])
    prior = con.execute("""SELECT witness_id,label,kind,reason,citation,reviewer
        FROM writing_unit WHERE unit_id=?""", (unit_id,)).fetchone()
    if prior is not None and prior != expected_unit:
        raise ValueError("Existing P52 writing unit differs; review it manually")
    if prior is None:
        create_writing_unit(con, unit_id, review["witness_id"], unit["label"],
                            unit["kind"], unit["reason"], unit["citation"],
                            review["reviewer"])
    expected_assessments = [
        (a["status"], a["date_min"], a["date_max"], a["original_notation"],
         a["citation"], review["reviewed_on"], review["reviewer"])
        for a in review["assessments"]]
    existing = con.execute("""SELECT status,date_min,date_max,original_notation,
        citation,consulted_on,reviewer FROM date_assessment WHERE unit_id=? ORDER BY id""",
        (unit_id,)).fetchall()
    if existing and existing != expected_assessments:
        raise ValueError("Existing P52 date assessments differ; review them manually")
    if not existing:
        for a in review["assessments"]:
            record_date_assessment(con, unit_id, a["status"], a["date_min"],
                                   a["date_max"], a["original_notation"],
                                   a["citation"], review["reviewed_on"],
                                   review["reviewer"])
    selection = review["selection"]
    expected_selection = (selection["policy_id"], None, selection["reason"],
                          review["reviewer"])
    prior = con.execute("""SELECT policy_id,assessment_id,reason,reviewer
        FROM date_selection WHERE unit_id=? AND policy_id=? ORDER BY id DESC LIMIT 1""",
        (unit_id, selection["policy_id"])).fetchone()
    if prior is not None and prior != expected_selection:
        raise ValueError("Existing P52 date selection differs; review it manually")
    if prior is None:
        select_date_assessment(con, unit_id, None, selection["policy_id"],
                               selection["reason"], review["reviewer"])


def apply_review(db_path):
    config, inventory = load_review()
    dating_review = load_dating_review(config["witness_id"])
    con = connect(Path(db_path))
    try:
        import_p52(con, COVERAGE_FIXTURE)
        import_language_probe(con, LANGUAGE_FIXTURE)
        client = Client(con, RUN_ID, offline=True)
        if collect_stage(client, config["doc_id"], "coverage") != "success":
            raise ValueError("P52 coverage fixture did not complete")
        if collect_search(client, "John.18.31", "P52", lang="grc") != "success":
            raise ValueError("P52 named search fixture did not complete")
        source = source_control_report(con, load_source_controls(SOURCE_CONTROLS))
        dating = date_source_report(con, load_date_source(DATE_SOURCE))
        if source["state"] != "pass" or dating["state"] != "pass":
            raise ValueError(f"Pinned source checks failed: {source['findings'] + dating['findings']}")
        doc_id = config["doc_id"]
        response_id = con.execute("""SELECT response_id FROM discovery_candidate
            WHERE run_id=? AND osis_ref='John.18.31' AND ga_num_query='P52'
            AND lang_filter='grc' AND doc_id=?""", (RUN_ID, doc_id)).fetchone()[0]
        index_response_id = con.execute("""SELECT response_id FROM coverage_index
            WHERE doc_id=? LIMIT 1""", (doc_id,)).fetchone()[0]
        citation = config["classification_citation"]
        review = con.execute("""SELECT source_response_id,decision,source_type,reason,citation
            FROM candidate_review WHERE doc_id=? ORDER BY id DESC LIMIT 1""",
            (doc_id,)).fetchone()
        expected_review = (response_id, "retain", "greek_manuscript",
                           "Greek papyrus manuscript identified by CSNTM", citation)
        if review is not None and review != expected_review:
            raise ValueError("Existing P52 classification differs; review it manually")
        identity = con.execute("""SELECT witness_id,source_response_id,reason,citation
            FROM witness_assignment WHERE doc_id=? ORDER BY id DESC LIMIT 1""",
            (doc_id,)).fetchone()
        expected_identity = (config["witness_id"], response_id,
                             "P52 and P. Rylands Gk. 457 are the same physical fragment",
                             config["identity_citation"])
        if identity is not None and identity != expected_identity:
            raise ValueError("Existing P52 physical identity differs; review it manually")
        coverage_plan = []
        for row in config["coverage"]:
            prior = con.execute("""SELECT status,evidence_type,reason,citation,
                index_response_id,witness_id FROM coverage_review WHERE inventory_id=?
                AND osis_ref=? AND ntvmr_ref=? AND doc_id=? AND page_id=?
                ORDER BY id DESC LIMIT 1""",
                (config["inventory_id"], row["osis_ref"], row["ntvmr_ref"],
                 doc_id, row["page_id"])).fetchone()
            expected_coverage = ("partial", "catalogue_content_statement",
                                 config["coverage_reason"], config["coverage_citation"],
                                 index_response_id, config["witness_id"])
            if prior is not None and prior != expected_coverage:
                raise ValueError(f"Existing P52 review differs at {row['osis_ref']}")
            coverage_plan.append((row, prior is None))
        import_edition_inventory(con, inventory)
        if review is None:
            record_candidate_review(con, doc_id, *expected_review, config["reviewer"])
        if identity is None:
            record_witness_assignment(con, doc_id, response_id,
                                      config["witness_id"], config["witness_label"],
                                      expected_identity[2], expected_identity[3],
                                      config["reviewer"])
        for row, needed in coverage_plan:
            if needed:
                record_coverage_review(
                    con, config["inventory_id"], row["osis_ref"], row["ntvmr_ref"],
                    doc_id, row["page_id"], index_response_id,
                    "partial", "catalogue_content_statement",
                    config["coverage_reason"], config["coverage_citation"],
                    config["reviewer"])
        report = coverage_review_report(con, config["inventory_id"])
        verified = report["verified_witnesses"]
        expected_refs = {row["osis_ref"] for row in config["coverage"]}
        if set(verified) != expected_refs or any(
                ids != [config["witness_id"]] for ids in verified.values()):
            raise ValueError("P52 review did not yield the five expected partial attestations")
        apply_dating_review(con, dating_review)
        return {"benchmark_id": config["benchmark_id"],
                "inventory_id": config["inventory_id"], "witness_id": config["witness_id"],
                "reviewed_verses": sorted(verified), "selected_date": False,
                "dating_review_id": dating_review["review_id"],
                "dating_policy_id": dating_review["selection"]["policy_id"],
                "whole_nt_complete": False, "network_attempts": client.attempts}
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        config, _ = load_review()
        dating_review = load_dating_review(config["witness_id"])
        if args.dry_run:
            result = {"planned_benchmark_id": config["benchmark_id"],
                      "planned_review_count": len(config["coverage"]),
                      "planned_date_assessment_count": len(dating_review["assessments"]),
                      "network_attempts": 0}
        else:
            result = apply_review(args.db)
    except (OSError, ValueError) as error:
        print(f"P52 benchmark replay failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
