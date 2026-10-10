"""Scoped comparisons of retained scholarly reports; never coverage overrides.

Pinned captures and content-derived claim IDs survive database rebuilds. Current
inputs are compared with the pins, without overwriting an earlier result. This
module performs no requests and supplies no manuscript coverage assertions.
"""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import date
import json
from pathlib import Path

from pipeline.controlled_ntvmr import encoded
from pipeline.source_reports import CONTRACT, digest, parse_capture, prepare_batch, required_text, timestamp


METHOD = {"id": "scoped-source-comparison", "version": 1, "source_contract": CONTRACT}
OUTCOMES = {"not_yet_checked", "agreement", "disagreement", "insufficient_detail"}
INTERPRETATIONS = {"explicit", "ambiguous_index", "missing_entries", "context"}


def stable_claim_id(kind, claim):
    """Fingerprint the full extraction, independent of temporary SQLite row IDs."""
    if kind not in ("content", "date"):
        raise ValueError("Unsupported comparison kind")
    retained = {key: value for key, value in claim.items()
                if key not in ("snapshot", "claim_id", "assessment_id", "source_response_id")}
    return f"{kind}:" + digest(encoded(retained))


def read_capture(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError("A capture file is required")
    path = Path(relative)
    target = (root / path).resolve()
    if path.is_absolute() or not target.is_relative_to(root.resolve()):
        raise ValueError("Check captures must stay inside the central data directory")
    record = json.loads(target.read_text(encoding="utf-8"))
    body = required_text(record, "raw_body")
    if record.get("body_sha256") != digest(body):
        raise ValueError("Check capture hash does not match retained material")
    timestamp(required_text(record, "retrieved_at"))
    return record


def comparison_outcome(kind, scope, sides):
    """Compare explicit assertions only; missing/ambiguous reports cannot agree."""
    claims = {role: [claim for e, records in side if e["interpretation"] == "explicit"
                     for claim in records] for role, side in sides.items()}
    if kind == "date":
        intervals = {role: {(c["date_min"], c["date_max"], c["applicability"])
                            for c in records if c["status"] == "valid"}
                     for role, records in claims.items()}
        if not all(intervals.values()):
            return "insufficient_detail"
        return "agreement" if intervals["ntvmr"] == intervals["comparison"] else "disagreement"
    incomplete = False
    for ref in scope["verses"]:
        assertions = {role: {c["assertion"] for c in records if c["source_ref"] == ref
                             and c["assertion"] in ("present", "absent")}
                      for role, records in claims.items()}
        left, right = assertions["ntvmr"], assertions["comparison"]
        if ("present" in left and "absent" in right) or ("absent" in left and "present" in right):
            return "disagreement"
        if not left or not right:
            incomplete = True
    return "insufficient_detail" if incomplete else "agreement"


def first_five_targets(data):
    """Read compact ranking tables only, without decoding any coverage vectors."""
    if data.get("format_version") not in (4, 5):
        raise ValueError("First-five selection requires compact browser format 4 or 5")
    selected, limitations = {}, []
    defaults = data.get("observation_defaults", {})
    filters = data.get("metadata", {}).get("filters", {})
    for coordinate, value in enumerate(data["coordinates"]):
        ref = value if isinstance(value, str) else value[0]
        observation = data["observations"].get(str(coordinate))
        if observation is None:
            status = data.get("coordinate_statuses", {}).get(str(coordinate), "main") if isinstance(value, str) else value[1]
            filtered = status == "omitted" and not filters.get("include_omitted", False) or status == "bracketed" and not filters.get("include_bracketed", True)
            limitations.append({"verse": ref, "state": "filtered" if filtered else "uncollected"})
            continue
        context = {**defaults, **data["observation_contexts"][observation[0]]}
        ranking = data["ranking_templates"][context["dating_alternatives"]]
        if ranking["state"] == "too_many_combinations":
            limitations.append({"verse": ref, "state": ranking["state"],
                                "combination_count": ranking["combination_count"],
                                "max_combinations": ranking["max_combinations"]})
            continue
        if ranking["state"] == "no_rankable_dates":
            limitations.append({"verse": ref, "state": ranking["state"]})
            continue
        if ranking["state"] != "complete":
            raise ValueError("Unknown ranking state; cannot select a first-five scope")
        for combination in ranking["combinations"]:
            for side in ("optimistic", "pessimistic"):
                for identifier in combination["scenarios"][side][:5]:
                    event = data["ranking_events"][identifier]
                    witness = event["witness_id"]
                    date_report = data["dates"][str(event["assessment_id"])]
                    if date_report["witness_id"] != witness or date_report["status"] != "valid":
                        raise ValueError("Ranked event must link to its witness's complete date report")
                    selected.setdefault(witness, set()).add(ref)
    targets = [{"witness_id": witness, "verses": sorted(refs),
                "date_reports": [deepcopy(d) for d in data["dates"].values() if d["witness_id"] == witness]}
               for witness, refs in sorted(selected.items())]
    return {"format_version": 1, "selection": "first-five-both-endpoints-all-retained-combinations",
            "targets": targets, "limitations": limitations,
            "summary": {"witness_count": len(targets), "witness_verse_count": sum(len(t["verses"]) for t in targets),
                        "date_report_count": sum(len(t["date_reports"]) for t in targets),
                        "unavailable_verse_count": len(limitations)}}


def queue_first_five(register, selection, documents):
    """Refresh unreviewed selected work; preserve recorded evidence and outcomes."""
    result = deepcopy(register)
    result["selection_limitations"] = deepcopy(selection["limitations"])
    result["checks"] = [c for c in result["checks"] if not (
        c["check_id"].startswith("first-five-") and c["outcome"] == "not_yet_checked" and not c["evidence"])]
    identities = {}
    for document in documents:
        identities.setdefault(document.get("witness_id", f"ntvmr:{document['doc_id']}"), []).append(document["doc_id"])
    latest = [c for c in result["checks"] if "superseded_by" not in c]
    for target in selection["targets"]:
        witness = target["witness_id"]
        if witness not in identities:
            raise ValueError("Selected witnesses must resolve to the central collection")
        existing = [c for c in latest if c["witness_id"] == witness]
        covered = {v for c in existing if c["kind"] == "content" for v in c["scope"]["verses"]}
        missing = sorted(set(target["verses"]) - covered)
        scopes = [("content", {"verses": missing})] if missing else []
        if not any(c["kind"] == "date" for c in existing):
            scopes.append(("date", {"applicability": "catalogue_document"}))
        for kind, scope in scopes:
            identifier = digest(encoded({"witness_id": witness, "kind": kind, "scope": scope}))[:20]
            result["checks"].append({
                "check_id": f"first-five-{kind}-{identifier}", "witness_id": witness,
                "doc_ids": sorted(identities[witness]), "kind": kind, "scope": scope,
                "method": deepcopy(METHOD), "checked_on": None, "outcome": "not_yet_checked",
                "explanation": "Selected from the first five across both date endpoints and every exported date combination. Only the listed content scope and complete applicable date reports are queued.",
                "evidence": [], "follow_up": {"state": "open", "reason": "Scoped source review pending; selection does not negate a usable report.", "evidence": []}})
    return result


def prepare_checks(register, manifest, data_dir):
    """Validate archived links and return current/stale scoped comparison summaries."""
    if register.get("format_version") != 1 or not isinstance(register.get("checks"), list):
        raise ValueError("Unsupported source-check register format")
    data_dir = Path(data_dir)
    documents = {d["doc_id"]: d for d in manifest["documents"]}
    inventory = manifest["inventory"]
    if not isinstance(inventory, dict):
        inventory = json.loads((data_dir / inventory).read_text(encoding="utf-8"))
    coordinates = {v["osis_ref"] for v in inventory["verses"]}
    selection_limitations = register.get("selection_limitations", [])
    if not isinstance(selection_limitations, list):
        raise ValueError("First-five ranking limitations must be a list")
    for limitation in selection_limitations:
        if (limitation.get("verse") not in coordinates
                or limitation.get("state") not in ("too_many_combinations", "no_rankable_dates", "filtered", "uncollected")):
            raise ValueError("First-five ranking limitations need an exact collection scope and unavailable state")
    reports = {}
    for report in manifest.get("additional_reports", []):
        if report.get("report_id"):
            if report["report_id"] in reports:
                raise ValueError("Additional report IDs must be distinct")
            reports[report["report_id"]] = report
    prepared, seen, capture_cache = [], set(), {}

    def retained(relative):
        if relative not in capture_cache:
            capture_cache[relative] = read_capture(data_dir, relative)
        return capture_cache[relative]

    for check in register["checks"]:
        check_id = required_text(check, "check_id")
        if check_id in seen:
            raise ValueError("Source-check IDs must be distinct")
        seen.add(check_id)
        witness = required_text(check, "witness_id")
        doc_ids = check.get("doc_ids")
        if (not isinstance(doc_ids, list) or not doc_ids or len(set(doc_ids)) != len(doc_ids)
                or any(type(doc) is not int or doc not in documents for doc in doc_ids)):
            raise ValueError("Checks must name distinct canonical collection documents")
        if any(documents[doc].get("witness_id", f"ntvmr:{doc}") != witness for doc in doc_ids):
            raise ValueError("Check documents do not identify the canonical witness")
        kind, scope = check.get("kind"), check.get("scope")
        if kind == "content":
            if (not isinstance(scope, dict) or set(scope) != {"verses"}
                    or not isinstance(scope["verses"], list) or not scope["verses"]
                    or any(not isinstance(v, str) for v in scope["verses"])
                    or len(set(scope["verses"])) != len(scope["verses"])
                    or set(scope["verses"]) - coordinates):
                raise ValueError("Content checks need exact distinct collection verse coordinates")
        elif kind != "date" or scope != {"applicability": "catalogue_document"}:
            raise ValueError("Date checks support whole catalogue-document applicability only")
        outcome = check.get("outcome")
        if outcome not in OUTCOMES:
            raise ValueError("Unsupported comparison outcome")
        required_text(check, "explanation")
        method = check.get("method")
        if (not isinstance(method, dict) or set(method) != set(METHOD)
                or type(method["version"]) is not int or method["version"] <= 0):
            raise ValueError("A versioned comparison method and extraction contract are required")
        required_text(method, "id")
        required_text(method, "source_contract")
        checked_on = check.get("checked_on")
        if outcome == "not_yet_checked":
            if checked_on is not None:
                raise ValueError("Queued checks cannot have a completed comparison date")
        elif not isinstance(checked_on, str) or date.fromisoformat(checked_on).isoformat() != checked_on:
            raise ValueError("Completed checks need an ISO comparison date")
        follow_up = check.get("follow_up", {})
        if follow_up.get("state") not in ("open", "deferred", "resolved"):
            raise ValueError("Unsupported follow-up state")
        required_text(follow_up, "reason")
        resolutions = follow_up.get("evidence", [])
        if not isinstance(resolutions, list) or (follow_up["state"] == "resolved" and not resolutions):
            raise ValueError("Resolved follow-up needs attributable correction or clarification evidence")
        for resolution in resolutions:
            raw = retained(resolution.get("capture_file"))
            if raw["body_sha256"] != resolution.get("body_sha256"):
                raise ValueError("Resolution evidence hash does not match its capture")
            required_text(resolution, "source_locator")
            if required_text(resolution, "statement") not in raw["raw_body"]:
                raise ValueError("Resolution statement must occur in the retained capture")
        attempts = check.get("access_attempts", [])
        if not isinstance(attempts, list):
            raise ValueError("Access attempts must be separate from evidence outcomes")
        for attempt in attempts:
            timestamp(required_text(attempt, "attempted_at"))
            required_text(attempt, "source_url")
            if attempt.get("state") not in ("success", "failed", "blocked"):
                raise ValueError("Unsupported source-access state")
            if attempt["state"] != "success":
                required_text(attempt, "reason")

        evidence = check.get("evidence")
        if not isinstance(evidence, list) or (outcome != "not_yet_checked" and not evidence):
            raise ValueError("Completed checks need pinned source evidence")
        pins = {doc: deepcopy(documents[doc]) for doc in doc_ids}
        pinned_reports, changes, entries, used = [], [], [], set()
        for entry in evidence:
            role, stage = entry.get("role"), entry.get("stage")
            if role not in ("ntvmr", "comparison", "context") or stage not in ("metadata", "coverage", "scholarly", "contract"):
                raise ValueError("Unsupported evidence role or capture stage")
            if ((role == "ntvmr" and stage not in ("metadata", "coverage"))
                    or (role == "comparison" and stage != "scholarly")):
                raise ValueError("Evidence stage does not match its comparison role")
            raw = retained(entry.get("capture_file"))
            if raw["body_sha256"] != entry.get("body_sha256"):
                raise ValueError("Pinned evidence hash does not match its capture")
            required_text(entry, "source_locator")
            if (entry.get("interpretation") not in INTERPRETATIONS
                    or not isinstance(entry.get("claim_ids"), list)
                    or any(not isinstance(c, str) for c in entry["claim_ids"])
                    or len(set(entry["claim_ids"])) != len(entry["claim_ids"])):
                raise ValueError("Evidence needs an interpretation and distinct stable claim IDs")
            identity = (role, stage, entry.get("doc_id"), entry["capture_file"])
            if identity in used:
                raise ValueError("Duplicate check evidence")
            used.add(identity)
            if stage in ("metadata", "coverage"):
                doc = entry.get("doc_id")
                if doc not in pins:
                    raise ValueError("Evidence must belong to a declared check document")
                field = "metadata_fixture" if stage == "metadata" else "coverage_fixture"
                # Two competing snapshots are separate checks, not arbitrary pin overrides.
                if any(e.get("doc_id") == doc and e["stage"] == stage for e, _ in entries):
                    raise ValueError("Each check pins one NTVMR snapshot per document and stage")
                pins[doc][field] = entry["capture_file"]
                if stage == "coverage":
                    pinned_limitations = entry.get("index_limitations", [])
                    if not isinstance(pinned_limitations, list):
                        raise ValueError("Pin index admission limitations as a list")
                    pins[doc]["index_limitations"] = deepcopy(pinned_limitations)
                    if documents[doc].get("index_limitations", []) != pinned_limitations:
                        changes.append(f"{doc} scoped index admission changed")
                current_path = documents[doc].get(field)
                if not current_path or retained(current_path) != raw:
                    changes.append(f"{doc} {stage} snapshot changed")
            elif stage == "scholarly":
                report_id = required_text(raw, "report_id")
                if report_id != entry.get("report_id"):
                    raise ValueError("Evidence report ID does not match its capture")
                admission = entry.get("admission")
                if admission not in ("active", "pending_contract_review"):
                    raise ValueError("Pin the additional report's admission state")
                pinned_reports.append({**raw, "admission": admission,
                                       "coverage": [c for c in raw.get("coverage", []) if c["witness_id"] == witness],
                                       "dates": [c for c in raw.get("dates", []) if c["witness_id"] == witness]})
                current = reports.get(report_id)
                if (current is None or digest(current["raw_body"]) != raw["body_sha256"]
                        or current.get("admission", "active") != admission
                        or {k: v for k, v in current.items() if k not in ("capture_file", "admission")} != raw):
                    changes.append(f"{report_id} source or extraction changed")
            entries.append((entry, raw))
        for entry, _ in entries:
            if entry["stage"] == "coverage" and not any(e["stage"] == "metadata" and e.get("doc_id") == entry["doc_id"] for e, _ in entries):
                raise ValueError("Contents evidence must pin its indexing metadata too")
        observations = check.get("index_observations")
        if observations is not None:
            if kind != "content" or len(doc_ids) != 1:
                raise ValueError("Index observations require one exact content-check document")
            captured = {e["stage"]: json.loads(raw["raw_body"]) for e, raw in entries
                        if e["role"] == "ntvmr" and e["stage"] in ("metadata", "coverage")}
            if set(captured) != {"metadata", "coverage"}:
                raise ValueError("Index observations require pinned metadata and contents")
            rows = captured["coverage"]["data"]["indexContents"]["indexContent"]
            rows = rows if isinstance(rows, list) else [rows]
            indexed = [r for r in rows if isinstance(r, dict) and r.get("osisID") in scope["verses"]]
            pages = captured["metadata"]["data"]["manuscript"].get("pages", {}).get("page", [])
            pages = pages if isinstance(pages, list) else [pages]
            expected = {"expanded_entries": indexed, "metadata_pages": [
                {k: p.get(k) for k in ("pageID", "indexTier", "indexedBy", "indexContent", "biblicalContent")}
                for p in pages if p.get("pageID") in {r["pageID"] for r in indexed}]}
            if observations != expected:
                raise ValueError("Index observations must match exact pinned fields and scoped entries")
        pinned_report_ids = {entry.get("report_id") for entry, _ in entries if entry["stage"] == "scholarly"}
        if outcome != "not_yet_checked":
            for report_id, report in reports.items():
                field = "coverage" if kind == "content" else "dates"
                if report_id not in pinned_report_ids and any(
                        c["witness_id"] == witness and (kind == "date" or c["source_ref"] in scope["verses"])
                        for c in report.get(field, [])):
                    changes.append(f"{report_id} additional scoped report added")
        if entries:
            pinned_manifest = {**manifest, "documents": list(pins.values()),
                               "additional_reports": pinned_reports}
            _, _, contents, dates, _ = prepare_batch(pinned_manifest, data_dir, include_pending=True)
            relevant = [c for c in (contents if kind == "content" else dates)
                        if c["witness_id"] == witness and (kind == "date" or c["source_ref"] in scope["verses"])]
            by_id = {stable_claim_id(kind, c): c for c in relevant}
        else:
            by_id = {}
        sides, evidence_summary = {"ntvmr": [], "comparison": []}, []
        for entry, raw in entries:
            if entry["stage"] in ("metadata", "coverage"):
                snap, _, _ = parse_capture(raw, entry["doc_id"], entry["stage"], capture_path=entry["capture_file"])
                citation = snap["citation"]
            else:
                citation = raw.get("citation")
            matching = {c for c, claim in by_id.items()
                        if claim["source_sha256"] == entry["body_sha256"]
                        and claim["retrieved_at"] == raw["retrieved_at"] and claim["citation"] == citation}
            selected = entry["claim_ids"]
            if set(selected) - matching:
                raise ValueError("Stable claim links must resolve to the pinned witness, scope, and capture")
            if entry["interpretation"] == "context":
                if selected:
                    raise ValueError("Context evidence cannot supply comparison assertions")
            else:
                if set(selected) != matching:
                    raise ValueError("Comparison evidence must include all scoped claims in its capture")
                if entry["interpretation"] == "missing_entries" and selected:
                    raise ValueError("A missing-entry observation cannot contain source claims")
            if entry["role"] in sides:
                sides[entry["role"]].append((entry, [by_id[c] for c in selected]))
            evidence_summary.append({key: deepcopy(entry[key]) for key in (
                "role", "stage", "capture_file", "body_sha256", "source_locator", "interpretation",
                "report_id", "admission") if key in entry} | {
                    "citation": citation or raw.get("source_url"), "retrieved_at": raw["retrieved_at"],
                    "claim_count": len(selected)})
        if outcome != "not_yet_checked" and method == METHOD:
            actual = comparison_outcome(kind, scope, sides)
            if outcome != actual:
                raise ValueError(f"Check {check_id}: outcome must be {actual} for the pinned evidence")
        if method != METHOD:
            changes.append("comparison method or extraction contract changed")
        status = ("not_yet_checked" if outcome == "not_yet_checked" else
                  "needs_recheck" if changes else "current")
        prepared.append({"check_id": check_id, "witness_id": witness, "doc_ids": doc_ids,
                         "kind": kind, "scope": deepcopy(scope), "outcome": outcome,
                         "checked_on": checked_on, "status": status,
                         "recheck_reasons": sorted(set(changes)), "explanation": check["explanation"],
                         "follow_up": deepcopy(follow_up),
                         "evidence": evidence_summary,
                         "evidence_claim_count": sum(len(e["claim_ids"]) for e in evidence),
                         **({"index_observations": deepcopy(observations)} if observations is not None else {}),
                         **({"superseded_by": check["superseded_by"]} if "superseded_by" in check else {})})
    by_check = {c["check_id"]: c for c in prepared}
    for check in prepared:
        chain, current = {check["check_id"]}, check
        while "superseded_by" in current:
            required_text(current, "superseded_by")
            successor = by_check.get(current["superseded_by"])
            if successor is None or successor["check_id"] in chain:
                raise ValueError("Source-check supersession must resolve without cycles")
            if (any(successor[k] != current[k] for k in ("witness_id", "doc_ids", "kind", "scope"))
                    or successor["outcome"] == "not_yet_checked"):
                raise ValueError("A completed recheck must preserve the superseded witness and scope")
            chain.add(successor["check_id"])
            current = successor
        if len(chain) > 1 and current["status"] == "current":
            check["status"] = "superseded"
    return {"format_version": 1, "method": METHOD, "checks": prepared,
            "selection_limitations": deepcopy(selection_limitations),
            "summary": {"check_count": len(prepared),
                        "by_status": dict(Counter(c["status"] for c in prepared)),
                        "recorded_outcomes": dict(Counter(c["outcome"] for c in prepared)),
                        "current_outcomes": dict(Counter(c["outcome"] for c in prepared if c["status"] == "current")),
                        "by_follow_up": dict(Counter(c["follow_up"]["state"] for c in prepared))}}


def main(argv=None):
    from build_collection import DATA, data_path, load_additional_reports, read_json, write_json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--details", action="store_true", help="Show exact checked scopes and follow-up")
    parser.add_argument("--pending", action="store_true", help="List queued, stale, or open follow-up work")
    parser.add_argument("--check", action="store_true", help="Exit unsuccessfully if a completed check needs rechecking")
    selection_mode = parser.add_mutually_exclusive_group()
    selection_mode.add_argument("--first-five", action="store_true", help="Show deduplicated compact-ranking targets without rebuilding")
    selection_mode.add_argument("--queue-first-five", action="store_true", help="Append uncovered first-five scopes to the checking register")
    args = parser.parse_args(argv)
    data_dir = args.data_dir.resolve()
    collection = read_json(data_dir / "collection.json")
    register = read_json(data_path(data_dir, collection["source_checks"]))
    selection = None
    if args.first_five or args.queue_first_five:
        selection = first_five_targets(read_json(data_dir / "attestations.json"))
        if args.first_five:
            print(json.dumps(selection, ensure_ascii=False, indent=2))
            return 0
        register = queue_first_five(register, selection, collection["documents"])
    # Checking a small scope does not require normalizing the full witness pool.
    inventory = read_json(data_path(data_dir, collection["coordinate_inventory"]))
    inventory["verses"] = [{**v, "ntvmr_refs": [], "mapping_note": "Check scope only; no coverage mapping derived here."}
                           for v in inventory["verses"]
                           if v["osis_ref"].split(".")[0] in collection["books"]]
    manifest = {"format_version": 1, "contract_id": CONTRACT, "batch_id": "source-checks",
                "scope": "Scoped offline source comparisons", "inventory": inventory,
                "documents": collection["documents"],
                "additional_reports": load_additional_reports(collection, data_dir)}
    result = prepare_checks(register, manifest, data_dir)
    if args.queue_first_five:
        write_json(data_path(data_dir, collection["source_checks"]), register)
        result["selection_summary"] = selection["summary"]
        result["selection_limitations"] = selection["limitations"]
    if args.pending:
        result["checks"] = [c for c in result["checks"] if c["status"] != "superseded"
                            and (c["status"] != "current" or c["follow_up"]["state"] != "resolved")]
    summary = {"summary": result["summary"], "selection_summary": selection["summary"],
               "selection_limitations": selection["limitations"]} if args.queue_first_five else result["summary"]
    print(json.dumps(result if args.details or args.pending else summary, ensure_ascii=False, indent=2))
    return 1 if args.check and result["summary"]["by_status"].get("needs_recheck", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
