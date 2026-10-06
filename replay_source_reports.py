#!/usr/bin/env python3
"""Replay captured scholarly reports into a fresh database, export, and render offline."""

import argparse
from contextlib import closing
import json
from pathlib import Path

from controlled_ntvmr import connect
from render_attestation import render
from source_reports import import_batch, build_report_exports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("benchmarks/gal1-source-reports-v1.json"))
    parser.add_argument("--db", type=Path, required=True, help="Must be a new database path")
    parser.add_argument("--dataset-output", type=Path, required=True)
    parser.add_argument("--graph-output", type=Path, required=True)
    parser.add_argument("--html-output", type=Path, required=True)
    parser.add_argument("--include-omitted", action="store_true")
    parser.add_argument("--exclude-bracketed", action="store_true")
    args = parser.parse_args(argv)
    outputs = [args.db, args.dataset_output, args.graph_output, args.html_output]
    if len({p.resolve() for p in outputs}) != len(outputs):
        parser.error("Database and output paths must all differ")
    if args.db.exists():
        parser.error("Replay requires a fresh database; existing source and decision history is preserved")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    # Manifest paths are relative to the repository root, regardless of caller cwd.
    root = Path(__file__).resolve().parent
    with closing(connect(args.db)) as con:
        batch_id = import_batch(con, manifest, root)
        dataset, graph = build_report_exports(con, batch_id, include_omitted=args.include_omitted,
                                             include_bracketed=not args.exclude_bracketed)
        html = render(graph)
        if con.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Source-report database failed foreign-key verification")
        if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Source-report database failed integrity verification")
    for path, value in ((args.dataset_output, json.dumps(dataset, ensure_ascii=False, indent=2) + "\n"),
                        (args.graph_output, json.dumps(graph, ensure_ascii=False, indent=2) + "\n"),
                        (args.html_output, html)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
    print(json.dumps({"batch_id": batch_id, **graph["counts"], "collection_cost": graph["collection_cost"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
