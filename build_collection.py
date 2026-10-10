#!/usr/bin/env python3
"""Refresh the explorer's central data file from captured scholarly reports, offline."""

import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import sys
import time
import sqlite3

from pipeline.controlled_ntvmr import connect, encoded, validate_inventory
from pipeline.report_explorer import build_explorer_data, ExplorerPacker
from pipeline.browser_format import pack_browser_data
from pipeline.source_reports import CONTRACT, build_report_exports, digest, import_batch, prepare_batch
from pipeline.build_storage import check_expansion, record_store
from pipeline.build_memory import DEFAULT_MEMORY_LIMIT_MB, memory_budget


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value, *, compact=False):
    """Replace one current file atomically; a failed write preserves its predecessor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    formatting = {"separators": (",", ":")} if compact else {"indent": 2}
    body = json.dumps(value, ensure_ascii=False, **formatting) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == body:
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, suffix=".tmp", delete=False) as output:
        temporary = Path(output.name)
        output.write(body)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def data_path(data_dir, relative):
    path = (data_dir / relative).resolve()
    if not path.is_relative_to(data_dir.resolve()):
        raise ValueError("Collection inputs must stay inside the central data directory")
    return path


def load_additional_reports(collection, data_dir):
    reports = []
    for entry in collection.get("additional_reports", []):
        if "capture_file" in entry:
            if set(entry) - {"capture_file", "admission"}:
                raise ValueError("A referenced additional report cannot override captured evidence")
            report = read_json(data_path(data_dir, entry["capture_file"]))
            if (not isinstance(report.get("raw_body"), str)
                    or report.get("body_sha256") != digest(report["raw_body"])):
                raise ValueError("Referenced additional-report capture hash does not match retained material")
            report = {**report, "capture_file": entry["capture_file"],
                      "admission": entry.get("admission", "active")}
        else:
            report = deepcopy(entry)
        if report.get("admission", "active") not in ("active", "pending_contract_review"):
            raise ValueError("Unsupported additional-report admission state")
        reports.append(report)
    return reports


def prepare_collection(collection, data_dir=DATA, *, discovery_records=None):
    """Derive reference mappings in memory; never write a book-specific manifest."""
    if collection.get("format_version") != 1:
        raise ValueError("Unsupported collection format")
    publisher = read_json(data_path(data_dir, collection["coordinate_inventory"]))
    validate_inventory(publisher)
    available = list(dict.fromkeys(v["osis_ref"].split(".")[0] for v in publisher["verses"]))
    books = collection["books"]
    if not books or len(set(books)) != len(books) or set(books) - set(available):
        raise ValueError("Choose distinct book codes present in the coordinate inventory")
    books = [book for book in available if book in books]
    documents = deepcopy(collection["documents"])
    for document in documents:
        for field in ("metadata_fixture", "coverage_fixture"):
            if document.get(field):
                data_path(data_dir, document[field])
    if discovery_records is None:
        discovery_records = read_json(data_path(data_dir, collection["discovery"])) if collection.get("discovery") else []
    if not isinstance(discovery_records, list):
        raise ValueError("The discovery register must be a list of bounded search records")
    # Coordinates alone make no claims. Ignore any old source-reference mapping.
    inventory = {**publisher, "inventory_id": "collected-coordinates", "verses": []}
    for source in publisher["verses"]:
        if source["osis_ref"].split(".")[0] in books:
            inventory["verses"].append({
                **{k: source[k] for k in ("osis_ref", "editorial_status", "editorial_note", "passage_citation") if k in source},
                "ntvmr_refs": [], "mapping_note": "No explicit coordinate match established."})
    manifest = {
        "format_version": 1, "contract_id": CONTRACT, "batch_id": "collection",
        "scope": (f"Collected scholarly reports for {', '.join(books)}. Rankings compare collected witnesses only. "
                  "Discovery coverage is recorded separately for each declared book and catalogue range."),
        "inventory": inventory, "catalogue_citation": collection.get("catalogue_citation"),
        "documents": documents, "additional_reports": load_additional_reports(collection, data_dir),
        "discovery_records": discovery_records,
    }
    with record_store(data_dir) as factory:
        _, snapshots, claims, _, _ = prepare_batch(manifest, data_dir, record_factory=factory)
        observed = {claim["source_ref"] for claim in claims}
        source_hashes = [s["body_sha256"] for s in snapshots]
    for coordinate in inventory["verses"]:
        ref = coordinate["osis_ref"]
        if ref in observed:
            coordinate["ntvmr_refs"] = [ref]
            coordinate.pop("mapping_note")
        else:
            coordinate["mapping_note"] = "No exact OSIS coordinate in collected reports; unresolved, with no absence inference."
    inventory.update(
        scope=f"{', '.join(books)}; {len(inventory['verses'])} collected reference coordinates.",
        mapping_citation="Exact OSIS matches in explicit scholarly reports; see docs/NTVMR_SOURCE_REPORT_CONTRACT.md. No neighboring-verse inference.",
        reviewer="Automated faithful reference extraction")
    manifest["coordinate_derivation"] = {
        "publisher_inventory_sha256": digest(encoded(publisher)),
        "rule": "Copy reference/editorial metadata; map exact OSIS matches in explicit reports only.",
        "source_hashes": source_hashes,
    }
    if collection.get("source_checks"):
        from source_checks import prepare_checks
        prepare_checks(read_json(data_path(data_dir, collection["source_checks"])), manifest, data_dir)
    return manifest, publisher


def build_data(collection=None, data_dir=DATA, *, discovery_records=None, packed=False, progress=None):
    """Normalized data for bounded callers; packed=True streams production rows."""
    collection = read_json(data_dir / "collection.json") if collection is None else collection
    if not packed:
        inventory = read_json(data_path(data_dir, collection["coordinate_inventory"]))
        coordinate_count = sum(v["osis_ref"].split(".")[0] in collection["books"] for v in inventory["verses"])
        check_expansion(len(collection["documents"]), coordinate_count)
    if progress:
        progress("Validating retained reports and reference mappings")
    manifest, publisher = prepare_collection(collection, data_dir, discovery_records=discovery_records)
    # The normalization database is a disposable build intermediate, never another collection.
    cache = data_dir / ".cache"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="attestation-", dir=cache) as temporary:
        with closing(connect(Path(temporary) / "normalize.sqlite")) as con:
            if progress:
                progress("Importing reports into the temporary normalization database")
            batch = import_batch(con, manifest, data_dir)
            packer = ExplorerPacker() if packed else None
            def consume(verse):
                graph = {"format_version": 3, "kind": "graph_input", "evidence_policy": "scholarly_reports_only",
                         "counts": {"verse_count": 1}, "verses": [verse], "documents": [], "sources": []}
                packer.add(build_explorer_data(graph, {**publisher, "verses": [verse]}))
                if progress and len(packer.observations) % 1000 == 0:
                    progress(f"Packed coverage for {len(packer.observations):,} verses")
            if progress:
                progress("Validating normalized evidence and packing coverage")
            _, graph = build_report_exports(con, batch,
                include_omitted=collection.get("include_omitted", False),
                include_bracketed=collection.get("include_bracketed", True),
                consume_verse=consume if packed else None)
            if con.execute("PRAGMA foreign_key_check").fetchall() or con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Collection integrity check failed")
    if packed:
        if progress:
            progress("Compressing shared coverage vectors")
        base = build_explorer_data({**graph, "counts": {**graph["counts"], "verse_count": 0}}, publisher)
        base["metadata"]["counts"] = graph["counts"]
        result = packer.finish(base)
    else:
        result = build_explorer_data(graph, publisher)
    # Link each document's raw source in the same central directory.
    captures = {}
    for document in collection["documents"]:
        for field in ("metadata_fixture", "coverage_fixture"):
            if document.get(field):
                capture = read_json(data_path(data_dir, document[field]))
                captures[(capture["body_sha256"], capture["retrieved_at"], capture["source_url"])] = document[field]
    for report in manifest["additional_reports"]:
        if report.get("capture_file") and report.get("admission", "active") == "active":
            captures[(digest(report["raw_body"]), report["retrieved_at"], report["citation"])] = report["capture_file"]
    for source in result["sources"]:
        key = (source["body_sha256"], source["retrieved_at"], source["url"])
        if key in captures:
            source["capture_file"] = captures[key]
    if packed and progress:
        progress("Encoding the browser transfer columns")
    return result


def build_browser_data(collection=None, data_dir=DATA, *, discovery_records=None,
                       memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB, stats=None):
    """Build the browser projection without any complete expanded coverage matrix."""
    with memory_budget(memory_limit_mb) as usage:
        result = _build_browser_data(collection, data_dir, discovery_records=discovery_records)
    if stats is not None:
        stats.update(usage)
    return result


def _build_browser_data(collection=None, data_dir=DATA, *, discovery_records=None, progress=None):
    # Call only inside a budget: refresh keeps the limit through comparison/write.
    return pack_browser_data(build_data(collection, data_dir, discovery_records=discovery_records,
                                        packed=True, progress=progress), consume=True, progress=progress)


def refresh(data_dir=DATA, *, check=False, memory_limit_mb=DEFAULT_MEMORY_LIMIT_MB, stats=None, progress=None):
    with memory_budget(memory_limit_mb) as usage:
        packed = _build_browser_data(data_dir=data_dir, progress=progress)
        output = data_dir / "attestations.json"
        if progress:
            progress("Comparing current browser data" if check else "Writing current browser data")
        if check:
            if not output.exists() or read_json(output) != packed:
                raise ValueError("Explorer data is out of date; run python build_collection.py")
        else:
            write_json(output, packed, compact=True)
    if stats is not None:
        stats.update(usage)
    return packed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--check", action="store_true", help="Verify the current data without writing")
    parser.add_argument("--memory-limit-mb", type=int, default=DEFAULT_MEMORY_LIMIT_MB,
                        help="OS memory ceiling in MiB (default: 2048); stop if exceeded")
    args = parser.parse_args(argv)
    if args.memory_limit_mb <= 0:
        parser.error("--memory-limit-mb must be positive")
    stats, started = {}, time.monotonic()
    last_stage = ["Initializing"]
    def progress(message):
        last_stage[0] = message
        print(message, file=sys.stderr, flush=True)
    try:
        data = refresh(args.data_dir.resolve(), check=args.check, memory_limit_mb=args.memory_limit_mb, stats=stats, progress=progress)
    except (MemoryError, sqlite3.Error, OSError, ValueError) as error:
        message = str(error) or "memory allocation failed"
        print(f"Build stopped during {last_stage[0].lower()}: {message}. Memory ceiling: {args.memory_limit_mb} MiB. "
              "The previous data file is preserved.", file=sys.stderr)
        return 1
    print(json.dumps({**data["metadata"]["counts"], **stats, "elapsed_seconds": round(time.monotonic() - started, 2), "network_requests": 0,
                      "data_file": str(args.data_dir / "attestations.json"),
                      "data_bytes": (args.data_dir / "attestations.json").stat().st_size,
                      "checked": args.check}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
