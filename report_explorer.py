"""Prepare data for the single New Testament explorer app.

Only coordinate metadata is read from the full inventory. Coverage, dates and
rankings always come from the supplied scholarly-report export.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "data" / "reference" / "na28.json"

# These fields repeat across claims from the same reported source and indexing
# tier. Their exact values are retained once; no provenance is reconstructed.
CLAIM_CONTEXT_FIELDS = frozenset((
    "assertion", "citation", "doc_id", "extent", "indexing_metadata_sha256",
    "provider", "qualifications", "reported_indexing_tier", "retrieved_at",
    "source_response_id", "source_sha256", "witness_id",
))


def build_explorer_data(graph, inventory=None):
    """Adapt an export without ranking again or inventing reports for empty slots.

    Dates and contents claims are interned once by their export identifiers. The
    browser selects existing per-verse combinations on demand; it never expands
    a corpus-wide Cartesian product of date alternatives.
    """
    if (graph.get("format_version") != 3 or graph.get("kind") != "graph_input"
            or graph.get("evidence_policy") != "scholarly_reports_only"):
        raise ValueError("Expected a version 3 scholarly-report graph input")
    if graph["counts"]["verse_count"] != len(graph["verses"]):
        raise ValueError("Graph verse count does not match its rows")
    if inventory is None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    coordinates = [[v["osis_ref"], v["editorial_status"]] for v in inventory["verses"]]
    refs = {ref for ref, _ in coordinates}
    if len(refs) != len(coordinates):
        raise ValueError("Duplicate display coordinate")
    claims, dates, observations = {}, {}, {}

    def intern(table, record, key):
        identifier = str(record[key])
        if identifier in table and table[identifier] != record:
            raise ValueError(f"Conflicting {key}: {identifier}")
        table[identifier] = record
        return identifier

    for verse in graph["verses"]:
        ref = verse["osis_ref"]
        if ref not in refs or ref in observations:
            raise ValueError(f"Unknown or duplicate graph coordinate: {ref}")
        pairs = []
        for pair in verse["reported_coverage"]:
            pairs.append({**pair,
                "claims": [intern(claims, c, "claim_id") for c in pair["claims"]],
                "date_assessments": [intern(dates, d, "assessment_id")
                                     for d in pair["date_assessments"]]})
        alternatives = verse["dating_alternatives"]
        combinations = []
        for combination in alternatives["combinations"]:
            combinations.append({
                "assessments": [intern(dates, d, "assessment_id")
                                for d in combination["assessments"]],
                "scenarios": {side: [{key: event[key] for key in (
                    "witness_id", "assessment_id", "rank", "event_year", "coverage_claim_ids")}
                    for event in entries] for side, entries in combination["scenarios"].items()},
            })
        observations[ref] = {
            "editorial_status": verse["editorial_status"],
            "editorial_note": verse.get("editorial_note"),
            "mapping_note": verse.get("mapping_note"),
            "passage_citation": verse.get("passage_citation"),
            "ranking_state": verse["ranking_state"],
            "discovery": verse.get("discovery", {"state": "not_searched", "ranking_scope": "collected_witnesses_only"}),
            "reported_coverage": pairs,
            "dating_alternatives": {**{k: v for k, v in alternatives.items()
                                       if k not in ("combinations", "unrankable_assessments")},
                                    "combinations": combinations},
        }
    return {
        "format_version": 1,
        "coordinates": coordinates,
        "coordinate_inventory": {k: inventory[k] for k in ("inventory_id", "scope", "source_citation")},
        "metadata": {k: v for k, v in graph.items() if k not in ("verses", "sources", "documents")},
        "documents": graph["documents"], "sources": graph["sources"],
        "claims": claims, "dates": dates, "observations": observations,
    }


def pack_explorer_data(data):
    """Store repeated records once in the version 2 browser transfer format.

    Normalized observations remain version 1 in Python and in the chart model.
    This lossless storage step neither removes unknown pairs nor computes claims,
    dates, discovery states, or rankings.
    """
    if data.get("format_version") != 1:
        raise ValueError("Expected normalized version 1 explorer data")
    tables = {name: [] for name in ("claim_contexts", "coverage_records", "discovery_records")}
    indices = {name: {} for name in tables}

    def intern(name, record):
        key = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key not in indices[name]:
            indices[name][key] = len(tables[name])
            tables[name].append(record)
        return indices[name][key]

    claims = {}
    for identifier, claim in data["claims"].items():
        context = {k: v for k, v in claim.items() if k in CLAIM_CONTEXT_FIELDS}
        details = {k: v for k, v in claim.items() if k not in CLAIM_CONTEXT_FIELDS}
        claims[identifier] = [intern("claim_contexts", context), details]
    observations = {ref: {
        **row,
        "reported_coverage": [intern("coverage_records", pair) for pair in row["reported_coverage"]],
        "discovery": intern("discovery_records", row["discovery"]),
    } for ref, row in data["observations"].items()}
    return {**data, "format_version": 2, **tables, "claims": claims, "observations": observations}


def expand_explorer_data(data):
    """Restore the transfer format exactly; also accept previous version 1 files."""
    if data.get("format_version") == 1:
        return data
    if data.get("format_version") != 2:
        raise ValueError("Unsupported explorer data")
    names = ("claim_contexts", "coverage_records", "discovery_records")
    if any(not isinstance(data.get(name), list) for name in names):
        raise ValueError("Missing explorer record tables")

    def record(name, index):
        if type(index) is not int or not 0 <= index < len(data[name]) or not isinstance(data[name][index], dict):
            raise ValueError(f"Invalid {name} reference")
        return deepcopy(data[name][index])

    claims = {}
    for identifier, packed in data["claims"].items():
        if not isinstance(packed, list) or len(packed) != 2 or not isinstance(packed[1], dict):
            raise ValueError("Invalid packed claim")
        context = record("claim_contexts", packed[0])
        if context.keys() & packed[1].keys():
            raise ValueError("Packed claim overrides its context")
        claims[identifier] = {**context, **deepcopy(packed[1])}
    observations = {ref: {
        **row,
        "reported_coverage": [record("coverage_records", index) for index in row["reported_coverage"]],
        "discovery": record("discovery_records", row["discovery"]),
    } for ref, row in data["observations"].items()}
    return {**{k: v for k, v in data.items() if k not in names},
            "format_version": 1, "claims": claims, "observations": observations}
