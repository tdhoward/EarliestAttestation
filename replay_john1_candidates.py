#!/usr/bin/env python3
"""Replay the captured John 1 named searches as candidates, offline."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from controlled_ntvmr import (Client, collect_search, connect,
                              import_edition_inventory, import_search_fixture,
                              search_params, validate_inventory)


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "benchmarks" / "john1-na28-subset-v1.json"
PARENT = ROOT / "benchmarks" / "na28-nt-reference-provisional-v3.json"
PROBE = ROOT / "tests" / "fixtures" / "john_named_probe.json"


def load_inputs():
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    validate_inventory(inventory)
    expected_refs = [f"John.1.{n}" for n in range(1, 6)]
    if [v["osis_ref"] for v in inventory["verses"]] != expected_refs:
        raise ValueError("John 1 prototype inventory must contain verses 1–5")
    parent_rows = {v["osis_ref"]: v for v in parent["verses"]}
    if any(v["editorial_status"] != parent_rows[v["osis_ref"]]["editorial_status"]
           or v["ntvmr_refs"] for v in inventory["verses"]):
        raise ValueError("Subset editorial statuses differ from the pinned parent")
    if (len(probe["cases"]) != 4 or
            {case["params"]["gaNum"] for case in probe["cases"]} !=
            {"P66", "P75", "01", "02"}):
        raise ValueError("Expected four captured named manuscript searches")
    for case in probe["cases"]:
        if (case["params"] != search_params("John.1.1", case["params"]["gaNum"])
                or case["source_url"] !=
                "https://ntvmr.uni-muenster.de/community/vmr/api/metadata/liste/search/"):
            raise ValueError("Captured search has an unexpected source or scope")
        datetime.fromisoformat(case["retrieved_at"])
    return inventory, probe


def apply(db_path):
    inventory, probe = load_inputs()
    con = connect(db_path)
    try:
        import_edition_inventory(con, inventory)
        client = Client(con, probe["run_id"], offline=True)
        results = []
        for case in probe["cases"]:
            import_search_fixture(con, {**case, "http_status": 200})
            name = case["params"]["gaNum"]
            state = collect_search(client, "John.1.1", name)
            if state != "success":
                raise ValueError(f"Captured {name} search is {state}")
            row = con.execute("""SELECT doc_id,ga_num,review_state FROM discovery_candidate
                WHERE run_id=? AND osis_ref='John.1.1' AND ga_num_query=?""",
                (probe["run_id"], name)).fetchone()
            if row is None or row[2] != "unreviewed":
                raise ValueError(f"Captured {name} candidate was not retained")
            results.append({"query": name, "doc_id": row[0], "ga_num": row[1],
                            "state": row[2]})
        if client.attempts:
            raise AssertionError("Candidate replay made a network request")
        return {"inventory_id": inventory["inventory_id"],
                "verse_count": len(inventory["verses"]),
                "candidates": results, "positive_coverage_reviews": 0,
                "network_attempts": client.attempts}
    finally:
        con.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    inventory, probe = load_inputs()
    result = ({"planned_inventory_id": inventory["inventory_id"],
               "planned_candidate_queries": [case["params"]["gaNum"]
                                             for case in probe["cases"]],
               "network_attempts": 0} if args.dry_run else apply(args.db))
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
