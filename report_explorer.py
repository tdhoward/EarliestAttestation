"""Prepare data for the single New Testament explorer app.

Only coordinate metadata is read from the full inventory. Coverage, dates and
rankings always come from the supplied scholarly-report export.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
INVENTORY = ROOT / "data" / "reference" / "na28.json"

# These fields repeat across claims from the same reported source and indexing
# tier. Their exact values are retained once; no provenance is reconstructed.
CLAIM_CONTEXT_FIELDS = frozenset((
    "assertion", "citation", "doc_id", "extent", "indexing_metadata_sha256",
    "provider", "qualifications", "reported_indexing_tier", "retrieved_at",
    "source_response_id", "source_sha256", "witness_id",
))

# Private intermediate codecs retained for offline compatibility checks.
# Numeric version 3 is the complete production browser transfer schema.
PHASE1_FORMAT_VERSION = "3-phase1"
PHASE2_FORMAT_VERSION = "3-phase2"
PHASE3_FORMAT_VERSION = "3-phase3"
JS_SAFE_INTEGER = 2**53 - 1
CANONICAL_INTEGER = re.compile(r"(?:0|-?[1-9][0-9]*)")
INDEX_LOCATOR = re.compile(r"data\.indexContents\.indexContent\[(0|[1-9][0-9]*)\]")


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
    """Write the complete version 3 browser transfer format.

    Normalized observations remain version 1 in Python and in the chart model.
    This lossless storage step neither removes unknown pairs nor computes claims,
    dates, discovery states, or rankings. The Phase 3 schema's tagged claims,
    shared contexts/rankings, and dense/sparse coverage are now production.
    """
    return {**pack_explorer_data_phase3(data), "format_version": 3}


def _pack_explorer_data_v2(data):
    """Retain the original dense layout as an intermediate for the codecs."""
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


def _json_key(value):
    """Intern/compare JSON values without Python's True == 1 equivalence."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _ranking_events(alternatives):
    if not isinstance(alternatives, dict) or not isinstance(alternatives.get("combinations"), list):
        raise ValueError("Invalid ranking template")
    for combination in alternatives["combinations"]:
        if not isinstance(combination, dict) or not isinstance(combination.get("scenarios"), dict):
            raise ValueError("Invalid ranking combination")
        for events in combination["scenarios"].values():
            if not isinstance(events, list):
                raise ValueError("Invalid ranking scenario")
            for event in events:
                if not isinstance(event, dict) or "witness_id" not in event:
                    raise ValueError("Invalid ranking event")
                yield event


def _present_claim_ids(pair, claims):
    """Mechanically copy stored present assertions in the pair's claim order."""
    if not isinstance(pair, dict) or not isinstance(pair.get("claims"), list):
        raise ValueError("Invalid coverage record")
    result = []
    for identifier in pair["claims"]:
        if not isinstance(identifier, str) or identifier not in claims:
            raise ValueError("Dangling coverage claim reference")
        claim = claims[identifier]
        if claim.get("assertion") == "present":
            if "claim_id" not in claim:
                raise ValueError("Missing coverage claim identifier")
            result.append(claim["claim_id"])
    return result


def _pair_claim_ids(pairs, witness, claims):
    matches = [pair for pair in pairs if "witness_id" in pair
               and _json_key(pair["witness_id"]) == _json_key(witness)]
    return _present_claim_ids(matches[0], claims) if len(matches) == 1 else None


def _validate_event_ids(identifiers, claim_ids):
    if not isinstance(identifiers, list):
        raise ValueError("Invalid event claim references")
    if any(_json_key(identifier) not in claim_ids for identifier in identifiers):
        raise ValueError("Dangling event claim reference")


def pack_explorer_data_phase1(data):
    """Build the retained private Phase 1 representation.

    Claims and coverage records retain v2 shapes. New observations are
    [contextIndex, ["dense", coverageRecordIndices]]. Contexts contain every
    other observation field, with discovery and dating_alternatives as indices.
    Ranking event coverage_claim_ids become ["pair"] or ["literal", ids].
    These tuple positions/tags also appear beside the JavaScript decoder.
    """
    packed = deepcopy(_pack_explorer_data_v2(data))
    tables = {name: [] for name in ("ranking_templates", "observation_contexts")}
    indices = {name: {} for name in tables}
    claim_ids = {_json_key(claim["claim_id"]) for claim in data["claims"].values()
                 if "claim_id" in claim}

    def intern(name, value):
        key = _json_key(value)
        if key not in indices[name]:
            indices[name][key] = len(tables[name])
            tables[name].append(value)
        return indices[name][key]

    observations = {}
    for ref, row in packed["observations"].items():
        pairs = [packed["coverage_records"][index] for index in row["reported_coverage"]]
        for pair in pairs:
            _present_claim_ids(pair, data["claims"])
        alternatives = deepcopy(row["dating_alternatives"])
        for event in _ranking_events(alternatives):
            identifiers = event.get("coverage_claim_ids")
            _validate_event_ids(identifiers, claim_ids)
            recovered = _pair_claim_ids(pairs, event["witness_id"], data["claims"])
            event["coverage_claim_ids"] = (["pair"] if recovered is not None
                and _json_key(identifiers) == _json_key(recovered) else ["literal", identifiers])
        context = {k: v for k, v in row.items() if k != "reported_coverage"}
        context["dating_alternatives"] = intern("ranking_templates", alternatives)
        observations[ref] = [intern("observation_contexts", context), ["dense", row["reported_coverage"]]]
    return {**packed, "format_version": PHASE1_FORMAT_VERSION, **tables, "observations": observations}


def _safe_integer(value):
    return type(value) is int and abs(value) <= JS_SAFE_INTEGER


def _compact_index_values(identifier, context, details):
    """Return mechanically reversible index fields, or choose literal storage."""
    if set(details) != {"claim_id", "source_ref", "page_id", "reported", "source_locator"}:
        return None
    reported = details["reported"]
    if (not isinstance(reported, dict)
            or set(reported) != {"docID", "indexContent", "osisID", "pageID"}
            or not isinstance(identifier, str) or not CANONICAL_INTEGER.fullmatch(identifier)
            or not _safe_integer(details["claim_id"]) or str(details["claim_id"]) != identifier
            or "doc_id" not in context
            or _json_key(details["source_ref"]) != _json_key(reported["osisID"])
            or _json_key(details["page_id"]) != _json_key(reported["pageID"])
            or _json_key(context["doc_id"]) != _json_key(reported["docID"])):
        return None
    # Keep noninteger and unsafe document/page IDs literal rather than converting
    # them. The same conservative eligibility rules are checked by both decoders.
    if not _safe_integer(context["doc_id"]) or not _safe_integer(details["page_id"]):
        return None
    locator = details["source_locator"]
    match = INDEX_LOCATOR.fullmatch(locator) if isinstance(locator, str) else None
    if not match or len(match[1]) > 16 or not _safe_integer(int(match[1])):
        return None
    return [reported["indexContent"], reported["osisID"], reported["pageID"], int(match[1])]


def pack_explorer_data_phase2(data):
    """Offline candidate: compact claims and coverage, retaining dense vectors.

    Claims: ["ntvmr_index_v1", contextIndex, [indexContent, osisID, pageID,
    locatorIndex]] or ["literal", contextIndex, completeDetails]. Coverage:
    [coverageContextIndex, orderedClaimIdStrings]; contexts retain every other
    field. This private marker is retained for offline compatibility checks.
    """
    packed = pack_explorer_data_phase1(data)
    claims = {}
    for identifier, (index, details) in packed["claims"].items():
        values = _compact_index_values(identifier, packed["claim_contexts"][index], details)
        claims[identifier] = (["ntvmr_index_v1", index, values] if values is not None
                              else ["literal", index, details])
    contexts, records, context_indices, record_indices, remap = [], [], {}, {}, []
    for pair in packed["coverage_records"]:
        context = {k: v for k, v in pair.items() if k != "claims"}
        key = _json_key(context)
        if key not in context_indices:
            context_indices[key] = len(contexts)
            contexts.append(context)
        record = [context_indices[key], pair["claims"]]
        key = _json_key(record)
        if key not in record_indices:
            record_indices[key] = len(records)
            records.append(record)
        remap.append(record_indices[key])
    for row in packed["observations"].values():
        row[1][1] = [remap[index] for index in row[1][1]]
    return {**packed, "format_version": PHASE2_FORMAT_VERSION, "claims": claims,
            "coverage_contexts": contexts, "coverage_records": records}


def pack_explorer_data_phase3(data):
    """Build exact coverage defaults using the complete version 3 schema.

    Coverage is ["dense", indices] or ["sparse", defaultsIndex, overrides],
    where overrides are increasing [position, coverageRecordIndex] pairs.
    Defaults group only nonempty vectors with the same ordered, unique witness
    identities. Each position uses its modal exact record, with the lowest
    record index (first encounter) breaking ties. No coverage is inferred.
    """
    packed = pack_explorer_data_phase2(data)
    groups = {}
    for row in packed["observations"].values():
        vector = row[1][1]
        contexts = [packed["coverage_contexts"][packed["coverage_records"][index][0]]
                    for index in vector]
        if not vector or any("witness_id" not in context for context in contexts):
            continue
        witnesses = [context["witness_id"] for context in contexts]
        if len({_json_key(witness) for witness in witnesses}) != len(witnesses):
            continue
        groups.setdefault(_json_key(witnesses), []).append(row)

    defaults = []
    size = lambda value: len(_json_key(value).encode("utf-8"))
    for rows in groups.values():
        vectors = [row[1][1] for row in rows]
        default = [min(Counter(values).items(), key=lambda item: (-item[1], item[0]))[0]
                   for values in zip(*vectors)]
        candidates = []
        for row, vector in zip(rows, vectors):
            overrides = [[position, index] for position, index in enumerate(vector)
                         if index != default[position]]
            encoding = ["sparse", len(defaults), overrides]
            saving = size(row[1]) - size(encoding)
            if saving > 0:
                candidates.append((row, encoding, saving))
        # Count the vector, its table separator, and the initial field/table
        # overhead. Rows whose sparse form costs more retain their dense form.
        overhead = size(default) + (1 if defaults else len(',"coverage_defaults":[]'))
        if sum(saving for _, _, saving in candidates) <= overhead:
            continue
        defaults.append(default)
        for row, encoding, _ in candidates:
            restored = default.copy()
            for position, index in encoding[2]:
                restored[position] = index
            if restored != row[1][1]:
                raise ValueError("Sparse coverage does not restore its dense vector")
            row[1] = encoding
    return {**packed, "format_version": PHASE3_FORMAT_VERSION, "coverage_defaults": defaults}


def expand_explorer_data(data):
    """Restore the transfer format exactly; also accept previous version 1 files."""
    if data.get("format_version") == 1:
        return data
    phase3 = data.get("format_version") in (3, PHASE3_FORMAT_VERSION)
    phase2 = data.get("format_version") == PHASE2_FORMAT_VERSION or phase3
    shared_observations = data.get("format_version") == PHASE1_FORMAT_VERSION or phase2
    if data.get("format_version") != 2 and not shared_observations:
        raise ValueError("Unsupported explorer data")
    names = ("claim_contexts", "coverage_records", "discovery_records")
    if shared_observations:
        names += ("ranking_templates", "observation_contexts")
    if phase2:
        names += ("coverage_contexts",)
    if phase3:
        names += ("coverage_defaults",)
    if (any(not isinstance(data.get(name), list) for name in names)
            or not isinstance(data.get("claims"), dict)):
        raise ValueError("Missing explorer record tables")

    def record(name, index):
        if type(index) is not int or not 0 <= index < len(data[name]) or not isinstance(data[name][index], dict):
            raise ValueError(f"Invalid {name} reference")
        return deepcopy(data[name][index])

    claims = {}
    for identifier, packed in data["claims"].items():
        if phase2:
            if not isinstance(packed, list) or len(packed) != 3:
                raise ValueError("Invalid packed claim")
            tag, index, values = packed
            context = record("claim_contexts", index)
            if tag == "literal" and isinstance(values, dict):
                details = deepcopy(values)
            elif tag == "ntvmr_index_v1":
                if (not isinstance(values, list) or len(values) != 4
                        or not _safe_integer(values[3]) or values[3] < 0
                        or not isinstance(identifier, str) or len(identifier) > 17
                        or not CANONICAL_INTEGER.fullmatch(identifier)
                        or not _safe_integer(int(identifier)) or "doc_id" not in context):
                    raise ValueError("Invalid compact index claim")
                content, osis, page, locator = deepcopy(values)
                details = {"claim_id": int(identifier), "source_ref": osis, "page_id": page,
                           "reported": {"docID": deepcopy(context["doc_id"]), "indexContent": content,
                                        "osisID": deepcopy(osis), "pageID": page},
                           "source_locator": f"data.indexContents.indexContent[{locator}]"}
                if _compact_index_values(identifier, context, details) is None:
                    raise ValueError("Invalid compact index claim")
            else:
                raise ValueError("Invalid claim encoding")
            if context.keys() & details.keys():
                raise ValueError("Packed claim overrides its context")
            claims[identifier] = {**context, **details}
            continue
        if not isinstance(packed, list) or len(packed) != 2 or not isinstance(packed[1], dict):
            raise ValueError("Invalid packed claim")
        context = record("claim_contexts", packed[0])
        if context.keys() & packed[1].keys():
            raise ValueError("Packed claim overrides its context")
        claims[identifier] = {**context, **deepcopy(packed[1])}
    if shared_observations:
        claim_ids = {_json_key(claim["claim_id"]) for claim in claims.values() if "claim_id" in claim}
        coverage_records = []
        for pair in data["coverage_records"]:
            if phase2:
                if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[1], list):
                    raise ValueError("Invalid packed coverage record")
                context = record("coverage_contexts", pair[0])
                if "claims" in context:
                    raise ValueError("Coverage context contains claims")
                pair = {**context, "claims": deepcopy(pair[1])}
            _present_claim_ids(pair, claims)
            coverage_records.append(pair)

        def validate_coverage_index(index):
            if type(index) is not int or not 0 <= index < len(coverage_records):
                raise ValueError("Invalid coverage_records reference")

        def coverage_record(index):
            validate_coverage_index(index)
            return deepcopy(coverage_records[index])

        if phase3:
            # Validate even unused default vectors; they must not hide dangling
            # records. A default is an ordered storage value, never a new row.
            for vector in data["coverage_defaults"]:
                if not isinstance(vector, list):
                    raise ValueError("Invalid coverage default vector")
                for index in vector:
                    validate_coverage_index(index)

        observations = {}
        for ref, packed in data["observations"].items():
            if not isinstance(packed, list) or len(packed) != 2:
                raise ValueError("Invalid packed observation")
            row = record("observation_contexts", packed[0])
            if "reported_coverage" in row:
                raise ValueError("Observation context contains coverage")
            encoding = packed[1]
            if (isinstance(encoding, list) and len(encoding) == 2
                    and encoding[0] == "dense" and isinstance(encoding[1], list)):
                vector = encoding[1]
            elif (phase3 and isinstance(encoding, list) and len(encoding) == 3
                    and encoding[0] == "sparse" and isinstance(encoding[2], list)):
                default_index = encoding[1]
                if type(default_index) is not int or not 0 <= default_index < len(data["coverage_defaults"]):
                    raise ValueError("Invalid coverage_defaults reference")
                vector = data["coverage_defaults"][default_index].copy()
                previous = -1
                for override in encoding[2]:
                    if not isinstance(override, list) or len(override) != 2:
                        raise ValueError("Invalid coverage override")
                    position, index = override
                    if type(position) is not int or not previous < position < len(vector):
                        raise ValueError("Invalid coverage override position")
                    validate_coverage_index(index)
                    vector[position] = index
                    previous = position
            else:
                raise ValueError("Invalid coverage encoding")
            pairs = [coverage_record(index) for index in vector]
            row["discovery"] = record("discovery_records", row.get("discovery"))
            alternatives = record("ranking_templates", row.get("dating_alternatives"))
            for event in _ranking_events(alternatives):
                tag = event.get("coverage_claim_ids")
                if isinstance(tag, list) and tag == ["pair"]:
                    identifiers = _pair_claim_ids(pairs, event["witness_id"], claims)
                    if identifiers is None:
                        raise ValueError("Missing or ambiguous coverage pair reference")
                elif isinstance(tag, list) and len(tag) == 2 and tag[0] == "literal":
                    identifiers = tag[1]
                else:
                    raise ValueError("Invalid event claim encoding")
                _validate_event_ids(identifiers, claim_ids)
                event["coverage_claim_ids"] = deepcopy(identifiers)
            observations[ref] = {**row, "reported_coverage": pairs, "dating_alternatives": alternatives}
        # Copy all remaining values as well, so no expanded nested object aliases
        # its packed input, another observation, or a shared ranking template.
        return {**deepcopy({k: v for k, v in data.items()
                           if k not in (*names, "claims", "observations")}),
                "format_version": 1, "claims": claims, "observations": observations}
    observations = {ref: {
        **row,
        "reported_coverage": [record("coverage_records", index) for index in row["reported_coverage"]],
        "discovery": record("discovery_records", row["discovery"]),
    } for ref, row in data["observations"].items()}
    return {**{k: v for k, v in data.items() if k not in names},
            "format_version": 1, "claims": claims, "observations": observations}
