"""Version 5 browser projection and relational transfer tables.

The source registers/captures retain full scholarly and collection evidence.
The browser keeps content claims, dates, coverage and rankings. Discovery uses
per-book summaries; single-choice date constraints and audit bookkeeping are
omitted. Coordinates are reference strings, with non-main statuses in
coordinate_statuses. observation_defaults supplies omitted context fields.

NTVMR claims use numeric (ID, context, reference, page, locator) columns; each
shared reference records the exact coordinate and reported indexContent.
Integer columns choose arrays, {"runs": [start, step, count, ...]},
{"varints": [count, base64_zigzag_32bit_values]}, or {"deltas": array_runs_or_varints}.
Coverage claims may use {"context_deltas": integer_column}: differences from the
last claim ID in the same exact coverage context, initially zero. These are
reversible integer encodings, never scholarly verse ranges or inferred contents.
String/noncanonical keys retain literal arrays. Ranking events and templates are
shared; observations use exact dense vectors or sparse overrides. Versions 4
and 5 can be expanded offline without changing the browser projection's meaning.
"""

from copy import deepcopy
from collections import Counter
from array import array
import base64
import json


def _key(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def pack_integers(values, *, allow_deltas=True):
    # Millions of integer objects, alternate encodings and their JSON strings
    # used to coexist here. Keep candidates in native buffers and measure JSON
    # lengths without serializing them; materialize only the winning encoding.
    source = iter(values)
    numbers = array("q")
    for value in source:
        if type(value) is not int or abs(value) > 2**53 - 1:
            return [*numbers, value, *source]
        numbers.append(value)
    if not numbers:
        return []
    packed, _ = _pack_integer_buffer(numbers, allow_deltas=allow_deltas)

    def materialize(value):
        if isinstance(value, array):
            return list(value)
        if isinstance(value, dict):
            return {key: materialize(item) for key, item in value.items()}
        return value

    return materialize(packed)


def _integer_json_size(values):
    return 2 + max(0, len(values) - 1) + sum(len(str(v)) for v in values)


def _pack_integer_buffer(values, *, allow_deltas):
    runs = array("q")
    start = 0
    while start < len(values):
        step = values[start + 1] - values[start] if start + 1 < len(values) else 0
        end = start + 1
        while end < len(values) and values[end] - values[end - 1] == step:
            end += 1
        runs.extend((values[start], step, end - start))
        start = end
    best, size = values, _integer_json_size(values)
    if all(abs(v) <= 2**53 - 1 for v in runs):
        run_size = len('{"runs":}') + _integer_json_size(runs)
        if run_size < size:
            best, size = {"runs": runs}, run_size
    del runs
    if allow_deltas:
        deltas = array("q", (values[i] - values[i - 1] if i else values[0]
                             for i in range(len(values))))
        if all(abs(v) <= 2**53 - 1 for v in deltas):
            candidate, delta_size = _pack_integer_buffer(deltas, allow_deltas=False)
            delta_size += len('{"deltas":}')
            if delta_size < size:
                best, size = {"deltas": candidate}, delta_size
            del candidate
        del deltas
    # Signed 32-bit varints are an additional lossless choice, not a replacement
    # for readable short arrays/runs. Larger safe integers retain the old forms.
    if all(-2**31 <= v < 2**31 for v in values):
        body = bytearray()
        for value in values:
            value = value * 2 if value >= 0 else -value * 2 - 1
            while value >= 128:
                body.append((value % 128) | 128)
                value //= 128
            body.append(value)
        varint_size = len('{"varints":[,""]}') + len(str(len(values))) + 4 * ((len(body) + 2) // 3)
        if varint_size < size:
            best, size = {"varints": [len(values), base64.b64encode(body).decode("ascii")]}, varint_size
    return best, size


def unpack_integers(value):
    if isinstance(value, list):
        return value.copy()
    if isinstance(value, dict) and set(value) == {"varints"}:
        spec = value["varints"]
        if (not isinstance(spec, list) or len(spec) != 2 or type(spec[0]) is not int
                or not 0 <= spec[0] <= 50_000_000 or not isinstance(spec[1], str)):
            raise ValueError("Invalid varint column")
        try:
            body = base64.b64decode(spec[1], validate=True)
        except (ValueError, base64.binascii.Error) as error:
            raise ValueError("Invalid varint base64") from error
        if base64.b64encode(body).decode("ascii") != spec[1]:
            raise ValueError("Invalid varint base64")
        result, total, multiplier = [], 0, 1
        for byte in body:
            total += (byte & 127) * multiplier
            if total > 2**32 - 1 or multiplier > 128**4:
                raise ValueError("Invalid varint bounds")
            if byte & 128:
                multiplier *= 128
            else:
                if multiplier > 1 and byte == 0:
                    raise ValueError("Noncanonical varint")
                result.append(total // 2 if total % 2 == 0 else -(total // 2) - 1)
                total, multiplier = 0, 1
        if multiplier != 1 or len(result) != spec[0]:
            raise ValueError("Mismatched varint column")
        return result
    if isinstance(value, dict) and set(value) == {"deltas"}:
        encoded = value["deltas"]
        if isinstance(encoded, dict) and set(encoded) not in ({"runs"}, {"varints"}):
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
                          if k not in ("batch_id", "batch_sha256", "contract_id", "kind", "collection_cost")}
    discovery = result["metadata"].pop("discovery", None)
    if discovery:
        summaries = {}
        scopes = discovery.get("scopes", [discovery])
        books = dict.fromkeys(c[0].split(".")[0] for c in data["coordinates"])
        for book in books:
            selected = [s for s in scopes if s.get("definition", {}).get("book") == book
                        or book in s.get("definition", {}).get("books", [])]
            if not selected:
                continue
            union = lambda field, fallback=None: len(set(value for scope in selected
                for value in scope.get(field, scope.get(fallback, []) if fallback else [])))
            incomplete = next((s for s in selected if s.get("search_state") != "complete"), None)
            summaries[book] = {
                "state": "search_incomplete" if incomplete else "candidate_collection_incomplete"
                    if any(s.get("candidate_collection_state") != "complete" for s in selected)
                    else "bounded_search_complete",
                "search_state": incomplete.get("search_state", "incomplete") if incomplete else "complete",
                "candidate_count": union("candidate_ids"),
                "pending_count": union("pending_candidate_ids"),
                "eligible_count": union("eligible_candidate_ids", "candidate_ids"),
                "excluded_count": union("date_excluded_candidate_ids"),
                "cutoffs": list(dict.fromkeys(s["definition"]["earliest_date_before"] for s in selected
                    if s.get("definition", {}).get("earliest_date_before") is not None)),
                "catalogue": any(s.get("definition", {}).get("scope_type") == "catalogue_range" for s in selected),
            }
        result["metadata"]["discovery_summary"] = summaries
    # Only witnesses with alternatives constrain the date selector. Keep every
    # complete date record and the eligible count; remove tautological choices.
    choices = Counter(d["witness_id"] for d in data["dates"].values() if d.get("status") == "valid")
    def ranking(value):
        value = deepcopy(value)
        for combo in value["combinations"]:
            combo["assessments"] = [identifier for identifier in unpack_integers(combo["assessments"])
                if str(identifier) not in data["dates"]
                or data["dates"][str(identifier)].get("status") != "valid"
                or choices[data["dates"][str(identifier)]["witness_id"]] != 1]
        return value
    def discovery_state(value):
        return {k: deepcopy(v) for k, v in value.items() if k in ("state", "corpus_complete", "ranking_scope")}
    if data.get("format_version") == 1:
        result["observations"] = {ref: {**row, "dating_alternatives": ranking(row["dating_alternatives"]),
            "discovery": discovery_state(row["discovery"])} for ref, row in data["observations"].items()}
    else:
        result["ranking_templates"] = [ranking(r) for r in data["ranking_templates"]]
        result["discovery_records"] = [discovery_state(r) for r in data["discovery_records"]]

    return result


def pack_browser_data(data, *, consume=False, progress=None):
    """Build the browser file; consume=True releases owned intermediate tables.

    Ordinary callers retain their input. The production writer transfers its
    disposable v3 input so its caller cannot keep obsolete tables alive during
    column compression.
    """
    if data.get("format_version") == 4:
        return upgrade_browser_data(data, progress=progress)
    if data.get("format_version") == 1:
        from pipeline.report_explorer import pack_explorer_data
        data = pack_explorer_data(data)
    if data.get("format_version") != 3:
        raise ValueError("Expected normalized v1 or packed v3 explorer data")
    projected = project_browser_data(data)
    if consume:
        data.clear()
    data = projected
    del projected
    result = dict(data)
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
    # Release the sparse pair lists before sorting millions of claim IDs. In
    # owned builds these lists are the largest avoidable overlap at this stage.
    if progress:
        progress("Encoding observation columns")
    observations = {}
    for ref, (context, encoding) in data["observations"].items():
        if encoding[0] == "dense":
            value = [context, 0, pack_integers(encoding[1])]
        else:
            value = [context, 1, encoding[1], pack_integers(p[0] for p in encoding[2]),
                     pack_integers(p[1] for p in encoding[2])]
        observations[str(coordinates[ref])] = value
    result["observations"] = observations
    data.pop("observations")
    references, reference_ids = [], {}
    columns = {name: array("q") for name in ("ids", "contexts", "references", "pages", "locators")}
    literals = {}
    if progress:
        progress("Encoding index claim columns")
    # IDs sort numerically so lookup uses binary search without a 2.5M-entry Map.
    indexed = sorted((key for key, claim in data["claims"].items()
                      if claim[0] == "ntvmr_index_v1" and claim[2][1] in coordinates), key=int)
    for key in indexed:
        identifier = int(key)
        _, context, (content, osis, page, locator) = data["claims"][key]
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
    result["claims"] = literals
    data.pop("claims")  # project_browser_data returned a private top-level copy.
    result["index_claims"] = {name: pack_integers(values) for name, values in columns.items()}
    result["claim_references"] = references
    del columns
    if progress:
        progress("Encoding coverage claim columns")
    records = data["coverage_records"]
    result["coverage_records"] = {
        "contexts": pack_integers(r[0] for r in records),
        "lengths": pack_integers(len(r[1]) for r in records),
        "claims": pack_integers(_numeric_key(key) for r in records for key in r[1]),
    }
    del records
    data.pop("coverage_records")
    if progress:
        progress("Encoding ranking references")
    result["coverage_defaults"] = [pack_integers(v) for v in data["coverage_defaults"]]
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
    # Do not hold the millions of v3 claim/coverage records or uncompressed
    # columns across the final v5 upgrade. result now owns their replacements.
    del data
    return upgrade_browser_data(result, progress=progress)


def upgrade_browser_data(data, *, progress=None):
    """Project/repack v4 directly, without materializing millions of claim objects."""
    result = project_browser_data(data)
    result["format_version"] = 5
    result["coordinates"] = [c[0] for c in data["coordinates"]]
    result["coordinate_statuses"] = {str(i): c[1] for i, c in enumerate(data["coordinates"]) if c[1] != "main"}
    if progress:
        progress("Finalizing browser column compression")
    result["index_claims"] = {k: pack_integers(unpack_integers(v)) for k, v in data["index_claims"].items()}
    coverage = {k: unpack_integers(v) for k, v in data["coverage_records"].items()}
    packed = {k: pack_integers(v) for k, v in coverage.items()}
    if all(type(v) is int for v in coverage["claims"]):
        # Predict only from earlier stored IDs with the same exact coverage
        # context. This is reversible integer compression, never coverage inference.
        previous, deltas, offset = {}, [], 0
        for context, length in zip(coverage["contexts"], coverage["lengths"]):
            for value in coverage["claims"][offset:offset + length]:
                deltas.append(value - previous.get(context, 0))
                previous[context] = value
            offset += length
        candidate = {"context_deltas": pack_integers(deltas)}
        if all(abs(v) <= 2**53 - 1 for v in deltas) and len(_key(candidate)) < len(_key(packed["claims"])):
            packed["claims"] = candidate
    result["coverage_records"] = packed
    del coverage
    if progress:
        progress("Finalizing browser observations and shared defaults")
    result["coverage_defaults"] = [pack_integers(unpack_integers(v)) for v in data["coverage_defaults"]]
    result["observations"] = {}
    for coordinate, original in data["observations"].items():
        row = original.copy()
        for index in ([2] if row[1] == 0 else [3, 4]):
            row[index] = pack_integers(unpack_integers(row[index]))
        result["observations"][coordinate] = row
    for template in result["ranking_templates"]:
        for combo in template["combinations"]:
            combo["assessments"] = pack_integers(combo["assessments"])
    # Projection makes many formerly different templates and discovery records
    # identical. Intern them again and update their observation references.
    result["observation_contexts"] = deepcopy(data["observation_contexts"])
    for table, field in (("ranking_templates", "dating_alternatives"), ("discovery_records", "discovery")):
        rows, ids, remap = [], {}, []
        for value in result[table]:
            key = _key(value)
            if key not in ids:
                ids[key] = len(rows)
                rows.append(value)
            remap.append(ids[key])
        result[table] = rows
        for context in result["observation_contexts"]:
            context[field] = remap[context[field]]
    contexts = result["observation_contexts"]
    defaults = {}
    if contexts:
        for field in contexts[0]:
            if not all(field in c for c in contexts):
                continue
            counts = Counter(_key(c[field]) for c in contexts)
            key, count = counts.most_common(1)[0]
            if count > len(contexts) / 2:
                defaults[field] = json.loads(key)
    result["observation_defaults"] = defaults
    result["observation_contexts"] = [{k: v for k, v in c.items()
        if k not in defaults or _key(v) != _key(defaults[k])} for c in contexts]
    return result


def restore_format4(data):
    """Restore v5 structural defaults/predictors for offline compatibility."""
    result = dict(data)
    result["format_version"] = 4
    statuses = result.pop("coordinate_statuses")
    result["coordinates"] = [[ref, statuses.get(str(i), "main")] for i, ref in enumerate(data["coordinates"])]
    defaults = result.pop("observation_defaults")
    result["observation_contexts"] = [{**defaults, **c} for c in data["observation_contexts"]]
    coverage = data["coverage_records"]
    if isinstance(coverage["claims"], dict) and "context_deltas" in coverage["claims"]:
        contexts, lengths = (unpack_integers(coverage[k]) for k in ("contexts", "lengths"))
        claims = unpack_integers(coverage["claims"]["context_deltas"])
        if len(contexts) != len(lengths) or sum(lengths) != len(claims):
            raise ValueError("Mismatched coverage columns")
        previous, offset = {}, 0
        for context, length in zip(contexts, lengths):
            for i in range(offset, offset + length):
                claims[i] += previous.get(context, 0)
                if abs(claims[i]) > 2**53 - 1:
                    raise ValueError("Invalid contextual delta bounds")
                previous[context] = claims[i]
            offset += length
        result["coverage_records"] = {**coverage, "claims": claims}
    return result


def unpack_browser_data(data):
    """Explicit offline expansion to projected v3; the browser uses columns directly."""
    if data.get("format_version") not in (4, 5):
        raise ValueError("Expected browser format 4 or 5")
    if data["format_version"] == 5:
        data = restore_format4(data)
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
