#!/usr/bin/env python3
"""Refresh the explorer's central data file from captured scholarly reports, offline."""

import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import tempfile

from controlled_ntvmr import connect, encoded, validate_inventory
from report_explorer import build_explorer_data
from browser_format import pack_browser_data
from source_reports import CONTRACT, build_report_exports, digest, import_batch, prepare_batch


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
        "documents": documents, "additional_reports": deepcopy(collection.get("additional_reports", [])),
        "discovery_records": discovery_records,
    }
    _, snapshots, claims, _, _ = prepare_batch(manifest, data_dir)
    observed = {claim["source_ref"] for claim in claims}
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
        "source_hashes": [s["body_sha256"] for s in snapshots],
    }
    return manifest, publisher


def build_data(collection=None, data_dir=DATA, *, discovery_records=None):
    collection = read_json(data_dir / "collection.json") if collection is None else collection
    manifest, publisher = prepare_collection(collection, data_dir, discovery_records=discovery_records)
    # The normalization database is a disposable build intermediate, never another collection.
    with tempfile.TemporaryDirectory(prefix="attestation-") as temporary:
        with closing(connect(Path(temporary) / "normalize.sqlite")) as con:
            batch = import_batch(con, manifest, data_dir)
            _, graph = build_report_exports(con, batch,
                include_omitted=collection.get("include_omitted", False),
                include_bracketed=collection.get("include_bracketed", True))
            if con.execute("PRAGMA foreign_key_check").fetchall() or con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Collection integrity check failed")
    result = build_explorer_data(graph, publisher)
    # Link each document's raw source in the same central directory.
    captures = {}
    for document in collection["documents"]:
        for field in ("metadata_fixture", "coverage_fixture"):
            if document.get(field):
                capture = read_json(data_path(data_dir, document[field]))
                captures[capture["body_sha256"]] = document[field]
    for source in result["sources"]:
        if source["body_sha256"] in captures:
            source["capture_file"] = captures[source["body_sha256"]]
    return result


def refresh(data_dir=DATA, *, check=False):
    result = build_data(data_dir=data_dir)
    packed = pack_browser_data(result)
    output = data_dir / "attestations.json"
    if check:
        if not output.exists() or read_json(output) != packed:
            raise ValueError("Explorer data is out of date; run python build_collection.py")
    else:
        write_json(output, packed, compact=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--check", action="store_true", help="Verify the current data without writing")
    args = parser.parse_args(argv)
    data = refresh(args.data_dir.resolve(), check=args.check)
    print(json.dumps({**data["metadata"]["counts"], "network_requests": 0,
                      "data_file": str(args.data_dir / "attestations.json"),
                      "data_bytes": (args.data_dir / "attestations.json").stat().st_size,
                      "checked": args.check}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
