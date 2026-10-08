"""Version 4 browser projection and relational transfer tables.

The source register/captures remain the collection of record. The browser keeps
all claims, dates, coverage and rankings, but omits unused document identity and
build/transport bookkeeping. Providers are interned. NTVMR claims are columns
(ID, context, reference, page, locator), with one shared reference record per
exact (coordinate ID, reported indexContent) pair. Other claim shapes stay literal.

Integer columns are JSON arrays, {"runs": [start, step, count, ...]}, or
{"deltas": array_or_runs} (cumulative sum), whichever is smallest. These encode
*existing ordered integers*, never scholarly verse ranges. Ranking events are
interned once and scenarios contain their numeric table IDs.
Coverage columns retain context IDs, claim counts, and ordered claim IDs. Numeric
claim references decode to string lookup keys; noncanonical keys stay strings.
Observations use coordinate IDs and exact dense vectors or sparse overrides.
No missing observation, claim, date alternative or unknown pair is synthesized.
"""

from copy import deepcopy
import json


def _key(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def pack_integers(values, *, allow_deltas=True):
    values = list(values)
    if not values or any(type(v) is not int or abs(v) > 2**53 - 1 for v in values):
        return values
    runs = []
    start = 0
    while start < len(values):
        step = values[start + 1] - values[start] if start + 1 < len(values) else 0
        end = start + 1
        while end < len(values) and values[end] - values[end - 1] == step:
            end += 1
        runs.extend((values[start], step, end - start))
        start = end
    candidates = [values]
    if all(abs(v) <= 2**53 - 1 for v in runs):
        candidates.append({"runs": runs})
    if allow_deltas:
        deltas = [values[0], *(values[i] - values[i - 1] for i in range(1, len(values)))]
        if all(abs(v) <= 2**53 - 1 for v in deltas):
            candidates.append({"deltas": pack_integers(deltas, allow_deltas=False)})
    return min(candidates, key=lambda value: len(_key(value)))


def unpack_integers(value):
    if isinstance(value, list):
        return value.copy()
    if isinstance(value, dict) and set(value) == {"deltas"}:
        encoded = value["deltas"]
        if isinstance(encoded, dict) and set(encoded) != {"runs"}:
            raise ValueError("Invalid nested delta column")
        result, total = [], 0
        for delta in unpack_integers(encoded):
            if type(delta) is not int:
                raise ValueError("Invalid delta column bounds")
            total += delta
            if abs(total) > 2**53 - 1:
                raise ValueError("Invalid delta column bounds")
            result.append(total)
        return result
    if not isinstance(value, dict) or set(value) != {"runs"}:
        raise ValueError("Invalid integer column")
    runs = value["runs"]
    if not isinstance(runs, list) or len(runs) % 3:
        raise ValueError("Invalid integer runs")
    result = []
    for i in range(0, len(runs), 3):
        start, step, count = runs[i:i + 3]
        if (any(type(v) is not int or abs(v) > 2**53 - 1 for v in (start, step, count))
                or count <= 0 or len(result) + count > 50_000_000
                or abs(start + step * (count - 1)) > 2**53 - 1):
            raise ValueError("Invalid integer run bounds")
        result.extend(start + step * n for n in range(count))
    return result


def _numeric_key(value):
    try:
        number = int(value)
        if str(number) == value and abs(number) <= 2**53 - 1:
            return number
    except (ValueError, TypeError):
        pass
    return value


def project_browser_data(data):
    """Keep display data; full identity/capture/discovery evidence stays in data/."""
    result = dict(data)
    result["documents"] = [{k: d[k] for k in ("witness_id", "label")} for d in data["documents"]]
    source_fields = ("source_response_id", "canonical_url", "params", "retrieved_at", "body_sha256")
    result["sources"] = [{k: s[k] for k in source_fields if k in s} |
                         ({"url": s["url"]} if not s.get("canonical_url") and "url" in s else {})
                         for s in data["sources"]]
    result["metadata"] = {k: v for k, v in data["metadata"].items()
                          if k not in ("batch_id", "batch_sha256", "contract_id", "kind")}
    # These are catalogue audit records, not inputs to any app control/display.
    discovery = result["metadata"].get("discovery")
    if discovery:
        discovery = deepcopy(discovery)
        for scope in discovery.get("scopes", [discovery]):
            for field in ("candidates", "collected_candidate_ids", "additional_collected_doc_ids"):
                scope.pop(field, None)
        result["metadata"]["discovery"] = discovery
    return result


def pack_browser_data(data):
    """Build the production browser file from normalized data or an existing v3."""
    if data.get("format_version") == 1:
        from report_explorer import pack_explorer_data
        data = pack_explorer_data(data)
    if data.get("format_version") != 3:
        raise ValueError("Expected normalized v1 or packed v3 explorer data")
    result = project_browser_data(data)
    result["format_version"] = 4
    providers, provider_ids = [], {}

    def provider(record):
        record = dict(record)
        if "provider" in record:
            value = record.pop("provider")
            key = _key(value)
            if key not in provider_ids:
                provider_ids[key] = len(providers)
                providers.append(value)
            record["provider_id"] = provider_ids[key]
        return record

    result["claim_contexts"] = [provider(c) for c in data["claim_contexts"]]
    result["dates"] = {key: provider(d) for key, d in data["dates"].items()}
    result["providers"] = providers
    coordinates = {c[0]: i for i, c in enumerate(data["coordinates"])}
    references, reference_ids = [], {}
    columns = {name: [] for name in ("ids", "contexts", "references", "pages", "locators")}
    literals = {}
    # IDs sort numerically so lookup uses binary search without a 2.5M-entry Map.
    indexed = sorted((int(key), claim) for key, claim in data["claims"].items()
                     if claim[0] == "ntvmr_index_v1" and claim[2][1] in coordinates)
    for identifier, (_, context, (content, osis, page, locator)) in indexed:
        ref = [coordinates[osis], content]
        key = _key(ref)
        if key not in reference_ids:
            reference_ids[key] = len(references)
            references.append(ref)
        for name, value in zip(columns, (identifier, context, reference_ids[key], page, locator)):
            columns[name].append(value)
    del indexed
    for identifier, claim in data["claims"].items():
        if claim[0] != "ntvmr_index_v1" or claim[2][1] not in coordinates:
            literals[identifier] = claim
    result["index_claims"] = {name: pack_integers(values) for name, values in columns.items()}
    result["claim_references"] = references
    result["claims"] = literals
    records = data["coverage_records"]
    result["coverage_records"] = {
        "contexts": pack_integers(r[0] for r in records),
        "lengths": pack_integers(len(r[1]) for r in records),
        "claims": pack_integers(_numeric_key(key) for r in records for key in r[1]),
    }
    result["coverage_defaults"] = [pack_integers(v) for v in data["coverage_defaults"]]
    observations = {}
    for ref, (context, encoding) in data["observations"].items():
        if encoding[0] == "dense":
            value = [context, 0, pack_integers(encoding[1])]
        else:
            value = [context, 1, encoding[1], pack_integers(p[0] for p in encoding[2]),
                     pack_integers(p[1] for p in encoding[2])]
        observations[str(coordinates[ref])] = value
    result["observations"] = observations
    result["ranking_templates"] = deepcopy(data["ranking_templates"])
    events, event_ids = [], {}
    for template in result["ranking_templates"]:
        for combo in template["combinations"]:
            combo["assessments"] = pack_integers(_numeric_key(key) for key in combo["assessments"])
            for side, scenario in combo["scenarios"].items():
                ids = []
                for event in scenario:
                    key = _key(event)
                    if key not in event_ids:
                        event_ids[key] = len(events)
                        events.append(event)
                    ids.append(event_ids[key])
                combo["scenarios"][side] = ids
    result["ranking_events"] = events
    return result


def unpack_browser_data(data):
    """Explicit offline expansion to projected v3; the browser uses columns directly."""
    if data.get("format_version") != 4:
        raise ValueError("Expected browser format 4")
    result = {k: deepcopy(v) for k, v in data.items()
              if k not in ("providers", "index_claims", "claim_references", "coverage_records", "ranking_events")}
    result["format_version"] = 3
    for record in [*result["claim_contexts"], *result["dates"].values()]:
        if "provider_id" in record:
            record["provider"] = data["providers"][record.pop("provider_id")]
    columns = {k: unpack_integers(v) for k, v in data["index_claims"].items()}
    if len({len(v) for v in columns.values()}) != 1:
        raise ValueError("Mismatched claim columns")
    for identifier, context, reference, page, locator in zip(*(columns[k] for k in
            ("ids", "contexts", "references", "pages", "locators"))):
        coordinate, content = data["claim_references"][reference]
        result["claims"][str(identifier)] = ["ntvmr_index_v1", context,
            [content, data["coordinates"][coordinate][0], page, locator]]
    records = data["coverage_records"]
    contexts, lengths, claims = (unpack_integers(records[k]) for k in ("contexts", "lengths", "claims"))
    if len(contexts) != len(lengths) or sum(lengths) != len(claims):
        raise ValueError("Mismatched coverage columns")
    result["coverage_records"] = []
    offset = 0
    for context, length in zip(contexts, lengths):
        result["coverage_records"].append([context, [str(v) for v in claims[offset:offset + length]]])
        offset += length
    result["coverage_defaults"] = [unpack_integers(v) for v in data["coverage_defaults"]]
    result["observations"] = {}
    for coordinate, row in data["observations"].items():
        if row[1] == 0:
            encoding = ["dense", unpack_integers(row[2])]
        else:
            positions, records = unpack_integers(row[3]), unpack_integers(row[4])
            if len(positions) != len(records):
                raise ValueError("Mismatched override columns")
            encoding = ["sparse", row[2], [list(p) for p in zip(positions, records)]]
        result["observations"][data["coordinates"][int(coordinate)][0]] = [row[0], encoding]
    for template in result["ranking_templates"]:
        for combo in template["combinations"]:
            combo["assessments"] = [str(v) for v in unpack_integers(combo["assessments"])]
            combo["scenarios"] = {side: [deepcopy(data["ranking_events"][i]) for i in ids]
                                  for side, ids in combo["scenarios"].items()}
    return result
