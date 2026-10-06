"""Package version 3 reports as an offline, reusable New Testament explorer.

Only coordinate metadata is read from the full inventory. Coverage, dates and
rankings always come from the supplied scholarly-report export.
"""

from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "web" / "attestation-explorer"
INVENTORY = ROOT / "benchmarks" / "na28-nt-reference-provisional-v3.json"


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


def render_report_explorer(graph):
    data = build_explorer_data(graph)
    # Escape HTML delimiters even inside application/json script elements.
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":"))
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    template = (ASSETS / "index.html").read_text(encoding="utf-8")
    replacements = {
        "/* EXPLORER_STYLES */": (ASSETS / "explorer.css").read_text(encoding="utf-8"),
        "/* EXPLORER_SCRIPT */": (ASSETS / "explorer.js").read_text(encoding="utf-8"),
        "EXPLORER_DATA": payload,
    }
    # One pass: source strings cannot be interpreted as template placeholders.
    return re.sub("|".join(re.escape(k) for k in replacements),
                  lambda match: replacements[match.group()], template)
