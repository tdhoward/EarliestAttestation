#!/usr/bin/env python3
"""Export complete reviewed inventory data and a filtered graph input, offline."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from controlled_ntvmr import (dating_alternatives_report, edition_inventory_report,
                              ranking_report)


def build_exports(con, inventory_id, policy_id, *, include_omitted=False,
                  include_bracketed=True):
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise ValueError("A dating policy ID is required")
    inventory = edition_inventory_report(con, inventory_id)
    ranked_refs = {row[0] for row in con.execute(
        "SELECT osis_ref FROM ranking_snapshot WHERE inventory_id=? AND policy_id=?",
        (inventory_id, policy_id))}
    reviewed_refs = {row[0] for row in con.execute(
        "SELECT DISTINCT osis_ref FROM coverage_review WHERE inventory_id=?",
        (inventory_id,))}
    rows = []
    for verse in inventory["verses"]:
        ref = verse["osis_ref"]
        ranking = (ranking_report(con, inventory_id, ref, policy_id)
                   if ref in ranked_refs else None)
        alternatives = (dating_alternatives_report(con, inventory_id, ref, policy_id)
                        if ref in reviewed_refs else None)
        rows.append({**verse,
                     "ranking_state": ranking["state"] if ranking else "uncomputed",
                     "scenarios": ranking["scenarios"] if ranking else
                     {"optimistic": [], "pessimistic": []},
                     "scenarios_basis": "selected_policy_assessments",
                     "dating_alternatives": alternatives})
    filters = {"include_omitted": include_omitted,
               "include_bracketed": include_bracketed}
    shown = [{**row, "scenarios": row["scenarios"] if
              row["ranking_state"] in ("success", "empty") and
              row["dating_alternatives"] is None else None}
             for row in rows
             if (include_omitted or row["editorial_status"] != "omitted")
             and (include_bracketed or row["editorial_status"] != "bracketed")]

    def counts(items):
        return {"verse_count": len(items),
                "verses_with_complete_date_alternatives": sum(
                    row["dating_alternatives"] is not None and
                    row["dating_alternatives"]["state"] == "complete"
                    for row in items),
                "by_editorial_status": {status: sum(row["editorial_status"] == status
                                                   for row in items)
                                        for status in ("main", "bracketed", "omitted", "uncertain")},
                "by_ranking_state": {state: sum(row["ranking_state"] == state
                                                 for row in items)
                                     for state in ("uncomputed", "success", "empty",
                                                   "stale", "incomplete", "failed")}}

    common = {"format_version": 2, "inventory_id": inventory_id,
              "edition": inventory["edition"], "inventory_scope": inventory["scope"],
              "inventory_source_citation": inventory["source_citation"],
              "inventory_mapping_citation": inventory["mapping_citation"],
              "inventory_reviewer": inventory["reviewer"],
              "inventory_sha256": inventory["manifest_sha256"],
              "dating_policy_id": policy_id, "whole_nt_complete": False,
              "dating_alternatives_complete": False}
    dataset = {**common, "kind": "complete_inventory", "counts": counts(rows),
               "verses": rows}
    graph = {**common, "kind": "graph_input", "filters": filters,
             "counts": counts(shown), "verses": shown}
    return dataset, graph


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--dataset-output", type=Path, required=True)
    parser.add_argument("--graph-output", type=Path, required=True)
    parser.add_argument("--include-omitted", action="store_true")
    parser.add_argument("--exclude-bracketed", action="store_true")
    args = parser.parse_args(argv)
    if args.dataset_output.resolve() == args.graph_output.resolve():
        parser.error("Dataset and graph output paths must differ")
    with closing(sqlite3.connect(f"file:{args.db.resolve().as_posix()}?mode=ro", uri=True)) as con:
        dataset, graph = build_exports(
            con, args.inventory, args.policy,
            include_omitted=args.include_omitted,
            include_bracketed=not args.exclude_bracketed)
    for path, data in ((args.dataset_output, dataset), (args.graph_output, graph)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"dataset_verses": dataset["counts"]["verse_count"],
                      "graph_verses": graph["counts"]["verse_count"],
                      "filters": graph["filters"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
