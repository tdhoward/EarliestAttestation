"""Offline scholarly-report normalization, with no historical review inputs.

The additive tables belong to this report path; the legacy v12 schema is unchanged.
Each batch is immutable and selects its own source snapshots and declared scope.
"""

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
from itertools import product
import json
from pathlib import Path
from urllib.parse import urlencode

from controlled_ntvmr import (API_BASE, encoded, edition_inventory_report,
                              import_edition_inventory, inventory_ref_parts,
                              parse_coverage, parse_metadata, rank_candidates,
                              validate_inventory)


CONTRACT = "ntvmr-source-reports-v1"
PROVIDER = "INTF / New Testament Virtual Manuscript Room (NTVMR)"
SCHEMA = """
CREATE TABLE IF NOT EXISTS scholarly_report_batch (
 batch_id TEXT PRIMARY KEY, manifest_sha256 TEXT NOT NULL,
 manifest_json TEXT NOT NULL, inventory_id TEXT NOT NULL REFERENCES edition_inventory(inventory_id));
CREATE TABLE IF NOT EXISTS scholarly_coverage_claim (
 id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES scholarly_report_batch(batch_id),
 witness_id TEXT NOT NULL, source_ref TEXT NOT NULL,
 assertion TEXT NOT NULL CHECK(assertion IN ('present','absent','unknown')),
 response_id INTEGER NOT NULL REFERENCES source_response(id), claim_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS scholarly_date_claim (
 id INTEGER PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES scholarly_report_batch(batch_id),
 witness_id TEXT NOT NULL, response_id INTEGER NOT NULL REFERENCES source_response(id),
 claim_json TEXT NOT NULL);
"""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def required_text(record, field):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"A nonempty {field} is required")
    return value


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Source retrieval timestamp must include a timezone")
    return value


def capture(path, doc_id, stage):
    record = json.loads(path.read_text(encoding="utf-8"))
    endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
    params = {"docID": str(doc_id), "detail": "10" if stage == "metadata" else "long",
              "format": "json"}
    body = required_text(record, "raw_body")
    if (record.get("body_sha256") != digest(body) or record.get("http_status") != 200
            or record.get("params") != params
            or not required_text(record, "source_url").endswith("/" + endpoint + "/")):
        raise ValueError(f"Invalid {stage} capture for {doc_id}")
    payload = json.loads(body)
    parsed = (parse_metadata(payload, doc_id) if stage == "metadata"
              else parse_coverage(payload, doc_id))
    result = {"endpoint": endpoint, "url": record["source_url"], "params": params,
              "body": body, "body_sha256": record["body_sha256"],
              "retrieved_at": timestamp(required_text(record, "retrieved_at")),
              "provider": PROVIDER, "capture_path": path.as_posix(),
              "citation": API_BASE + "/" + endpoint + "/?" + urlencode(params)}
    return result, payload, parsed


def provenance(snapshot, locator, reported, qualifications=""):
    return {"provider": snapshot["provider"], "citation": snapshot["citation"],
            "retrieved_at": snapshot["retrieved_at"], "source_locator": locator,
            "reported": reported, "qualifications": qualifications,
            "source_sha256": snapshot["body_sha256"]}


def date_bounds(record):
    low, high = record.get("date_min"), record.get("date_max")
    if low is None and high is None:
        return "unknown"
    if type(low) is not int or type(high) is not int or not 0 < low <= high:
        raise ValueError("A reported date needs a complete positive interval or null bounds")
    return "valid"


def prepare_batch(manifest, root):
    """Read only metadata/contents captures and explicitly supplied published claims."""
    if manifest.get("format_version") != 1 or manifest.get("contract_id") != CONTRACT:
        raise ValueError("Unsupported source-report manifest contract")
    required_text(manifest, "batch_id")
    required_text(manifest, "scope")
    inventory = json.loads((root / manifest["inventory"]).read_text(encoding="utf-8"))
    validate_inventory(inventory)
    for coordinate in inventory["verses"]:
        if coordinate["ntvmr_refs"] not in ([], [coordinate["osis_ref"]]):
            raise ValueError("This source contract supports explicit direct coordinate matches only")
    snapshots, coverage, dates, documents = [], [], [], []
    seen = set()
    for document in manifest["documents"]:
        doc_id = document["doc_id"]
        if type(doc_id) is not int or doc_id <= 0 or doc_id in seen:
            raise ValueError("Document IDs must be distinct positive integers")
        seen.add(doc_id)
        witness = document.get("witness_id", f"ntvmr:{doc_id}")
        if not isinstance(witness, str) or not witness.strip():
            raise ValueError("Invalid witness ID")
        identity = document.get("identity_report")
        if witness != f"ntvmr:{doc_id}":
            # A join/alias must be explicitly reported, never inferred by the collector.
            for key in ("provider", "citation", "consulted_on", "source_locator", "statement"):
                required_text(identity or {}, key)
        item = {"doc_id": doc_id, "witness_id": witness, "identity_report": identity,
                "label": str(doc_id), "metadata_state": "missing", "coverage_state": "missing"}
        metadata = None
        if document.get("metadata_fixture"):
            snap, payload, metadata = capture(root / document["metadata_fixture"], doc_id, "metadata")
            snapshots.append(snap)
            item.update(label=metadata["ga_num"] or metadata["primary_name"],
                        metadata_state="success", metadata_sha256=snap["body_sha256"],
                        reported_language=metadata["source_lang"],
                        identity=provenance(snap, "data.manuscript.{docID,gaNum,primaryName,lang}",
                            {k: payload["data"]["manuscript"].get(k)
                             for k in ("docID", "gaNum", "primaryName", "lang")}))
            if metadata["source_lang"] not in ("g", "grc", "grc_lat"):
                raise ValueError("This bounded contract supports only reported Greek language codes")
            # GA catalogue membership must be declared from the source scope, not a name guess.
            if document.get("corpus") != "greek_nt_manuscript":
                raise ValueError("Declare the Greek NT manuscript catalogue scope")
            dates.append({"witness_id": witness, "snapshot": len(snapshots)-1,
                          "status": metadata["date_status"],
                          "date_min": metadata["date_min"], "date_max": metadata["date_max"],
                          "original_notation": metadata["origin_notation"],
                          "applicability": "catalogue_document", "doc_id": doc_id,
                          **provenance(snap, "data.manuscript.originYear",
                                       payload["data"]["manuscript"].get("originYear"),
                                       "Catalogue document estimate; no independently assigned portions.")})
        if document.get("coverage_fixture"):
            if metadata is None:
                raise ValueError("A contents capture needs metadata establishing the scoped witness")
            snap, payload, entries = capture(root / document["coverage_fixture"], doc_id, "coverage")
            snapshots.append(snap)
            item.update(coverage_state="success" if entries else "empty",
                        coverage_sha256=snap["body_sha256"])
            pages = payload["data"]["indexContents"]["indexContent"]
            page_metadata = json.loads(snapshots[-2]["body"])["data"]["manuscript"].get("pages", {}).get("page", [])
            if isinstance(page_metadata, dict):
                page_metadata = [page_metadata]
            tiers = {p.get("pageID"): p.get("indexTier") for p in page_metadata}
            allowed = set(entries)
            for index, entry in enumerate(pages):
                if not isinstance(entry, dict) or (entry.get("osisID"), entry.get("pageID")) not in allowed:
                    continue
                tier = tiers.get(entry["pageID"])
                qualification = (f"Catalogue indexing tier {tier}. " if tier is not None
                                 else "Indexing tier not supplied. ")
                if type(tier) is int and tier >= 4:
                    qualification += "Provider labels tier 4+ as AI indexing awaiting human confirmation. "
                qualification += "Reported verse-range entry; extent unspecified. Missing entries establish no absence."
                coverage.append({"witness_id": witness, "source_ref": entry["osisID"],
                                 "assertion": "unknown" if type(tier) is int and tier >= 4 else "present",
                                 "extent": "unspecified", "doc_id": doc_id,
                                 "page_id": entry["pageID"], "snapshot": len(snapshots)-1,
                                 "indexing_metadata_sha256": item["metadata_sha256"],
                                 "reported_indexing_tier": tier,
                                 **provenance(snap, f"data.indexContents.indexContent[{index}]",
                                              entry, qualification)})
        documents.append(item)
    if not documents:
        raise ValueError("A bounded document scope is required")
    witnesses = {d["witness_id"] for d in documents}
    for report in manifest.get("additional_reports", []):
        body = required_text(report, "raw_body")
        snap = {"endpoint": "scholarly/report", "url": required_text(report, "citation"),
                "params": {}, "body": body, "body_sha256": digest(body),
                "retrieved_at": timestamp(required_text(report, "retrieved_at")),
                "provider": required_text(report, "provider"), "citation": report["citation"]}
        snapshots.append(snap)
        for claim in report.get("coverage", []) + report.get("dates", []):
            if claim["witness_id"] not in witnesses:
                raise ValueError("Additional claims must identify a witness in the declared scope")
            if required_text(claim, "statement") not in body:
                raise ValueError("The exact reported statement must be retained in the source snapshot")
            required_text(claim, "source_locator")
        for claim in report.get("coverage", []):
            if set(claim) - {"witness_id", "source_ref", "assertion", "extent", "source_locator", "statement", "qualifications"}:
                raise ValueError("Additional coverage reports must apply to the witness/verse, without independently inferred portions")
            inventory_ref_parts(claim["source_ref"])
            if claim["assertion"] not in ("present", "absent", "unknown"):
                raise ValueError("Invalid explicit source assertion")
            if claim.get("extent", "unspecified") not in ("partial", "full", "unspecified"):
                raise ValueError("Invalid reported extent")
            coverage.append({**claim, "snapshot": len(snapshots)-1,
                             **provenance(snap, claim["source_locator"], claim["statement"],
                                          claim.get("qualifications", ""))})
        for claim in report.get("dates", []):
            if set(claim) - {"witness_id", "date_min", "date_max", "original_notation", "source_locator", "statement", "qualifications"}:
                raise ValueError("This bounded contract supports whole-witness date reports only")
            required_text(claim, "original_notation")
            dates.append({**claim, "status": date_bounds(claim), "snapshot": len(snapshots)-1,
                          "applicability": "catalogue_document",
                          **provenance(snap, claim["source_locator"], claim["statement"],
                                       claim.get("qualifications", ""))})
    return inventory, snapshots, coverage, dates, documents


def import_batch(con, manifest, root=Path(".")):
    inventory, snapshots, coverage, dates, documents = prepare_batch(manifest, root)
    con.executescript(SCHEMA)
    batch_id = manifest["batch_id"]
    # Hash actual captures as well as the manifest, so changed files cannot replay as the same batch.
    normalized = {"manifest": manifest, "documents": documents,
                  "inventory_sha256": digest(encoded(inventory)),
                  "source_hashes": [s["body_sha256"] for s in snapshots],
                  "coverage_sha256": digest(encoded([{k: v for k, v in c.items() if k != "snapshot"}
                                                      for c in coverage])),
                  "dates_sha256": digest(encoded([{k: v for k, v in d.items() if k != "snapshot"}
                                                   for d in dates]))}
    body = encoded(normalized)
    existing = con.execute("SELECT manifest_sha256 FROM scholarly_report_batch WHERE batch_id=?", (batch_id,)).fetchone()
    if existing:
        if existing[0] != digest(body):
            raise ValueError("Report batches are immutable; use a new batch ID for changed sources")
        return batch_id
    import_edition_inventory(con, inventory)
    with con:
        con.execute("INSERT INTO scholarly_report_batch VALUES (?,?,?,?)",
                    (batch_id, digest(body), body, inventory["inventory_id"]))
        response_ids = []
        for snap in snapshots:
            row = con.execute("SELECT id FROM source_response WHERE url=? AND params_json=? AND body_sha256=? AND retrieved_at=?",
                              (snap["url"], encoded(snap["params"]), snap["body_sha256"], snap["retrieved_at"])).fetchone()
            if row:
                response_ids.append(row[0])
            else:
                cur = con.execute("""INSERT INTO source_response
                    (endpoint,url,params_json,status_code,headers_json,body,body_sha256,retrieved_at,origin)
                    VALUES (?,?,?,200,'{}',?,?,?,'fixture')""",
                    (snap["endpoint"], snap["url"], encoded(snap["params"]), snap["body"], snap["body_sha256"], snap["retrieved_at"]))
                response_ids.append(cur.lastrowid)
        for table, claims in (("scholarly_coverage_claim", coverage), ("scholarly_date_claim", dates)):
            for claim in claims:
                record = dict(claim)
                record["source_response_id"] = response_ids[record.pop("snapshot")]
                if table == "scholarly_coverage_claim":
                    con.execute("INSERT INTO scholarly_coverage_claim (batch_id,witness_id,source_ref,assertion,response_id,claim_json) VALUES (?,?,?,?,?,?)",
                                (batch_id, record["witness_id"], record["source_ref"], record["assertion"], record["source_response_id"], encoded(record)))
                else:
                    con.execute("INSERT INTO scholarly_date_claim (batch_id,witness_id,response_id,claim_json) VALUES (?,?,?,?)",
                                (batch_id, record["witness_id"], record["source_response_id"], encoded(record)))
    return batch_id


def coverage_state(claims):
    assertions = {c["assertion"] for c in claims}
    if {"present", "absent"} <= assertions:
        return "contested"
    return "present" if "present" in assertions else "absent" if "absent" in assertions else "unknown"


def alternatives(pairs, dates, max_combinations=256):
    choices, unknown = {}, []
    for pair in pairs:
        if pair["state"] != "present":
            continue
        witness = pair["witness_id"]
        usable = [d for d in dates[witness] if d["status"] == "valid"]
        unknown.extend(d for d in dates[witness] if d["status"] != "valid")
        if usable:
            choices[witness] = usable
    count = 1
    for rows in choices.values():
        count *= len(rows)
    result = {"state": "complete" if choices else "no_rankable_dates",
              "combination_count": count if choices else 0, "max_combinations": max_combinations,
              "eligible_witness_count": len(choices), "unrankable_assessments": unknown,
              "combinations": []}
    if count > max_combinations:
        result["state"] = "too_many_combinations"
        return result
    if not choices:
        return result
    pair_by_id = {p["witness_id"]: p for p in pairs}
    for selection in product(*(choices[w] for w in sorted(choices))):
        candidates = []
        for date in selection:
            pair = pair_by_id[date["witness_id"]]
            candidates.append({**date, "coverage_claim_ids": [c["claim_id"] for c in pair["claims"]
                                                             if c["assertion"] == "present"]})
        result["combinations"].append({"assessments": list(selection),
            "scenarios": {s: rank_candidates(candidates, s)[:5] for s in ("optimistic", "pessimistic")}})
    return result


def build_report_exports(con, batch_id, *, include_omitted=False, include_bracketed=True):
    row = con.execute("SELECT manifest_json,inventory_id,manifest_sha256 FROM scholarly_report_batch WHERE batch_id=?", (batch_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown scholarly-report batch")
    batch, inventory_id, batch_sha = json.loads(row[0]), row[1], row[2]
    if digest(row[0]) != batch_sha:
        raise ValueError("Report batch manifest checksum mismatch")
    inventory = edition_inventory_report(con, inventory_id)
    inventory_body = con.execute("SELECT manifest_json FROM edition_inventory WHERE inventory_id=?", (inventory_id,)).fetchone()[0]
    if digest(inventory_body) != batch["inventory_sha256"]:
        raise ValueError("Report inventory changed; use a new inventory and batch")
    expected_coordinates = json.loads(inventory_body)["verses"]
    if len(inventory["verses"]) != len(expected_coordinates):
        raise ValueError("Stored inventory coordinates disagree with their source manifest")
    for ordinal, (actual, expected) in enumerate(zip(inventory["verses"], expected_coordinates), 1):
        for key in ("osis_ref", "editorial_status", "editorial_note", "mapping_note", "ntvmr_refs", "passage_citation"):
            if actual.get(key) != expected.get(key):
                raise ValueError("Stored inventory coordinates disagree with their source manifest")
        book, chapter, verse = inventory_ref_parts(expected["osis_ref"])
        if (actual["ordinal"], actual["book"], actual["chapter"], actual["verse"]) != (ordinal, book, chapter, verse):
            raise ValueError("Stored coordinate order differs from the source manifest")
    claims = []
    dates = defaultdict(list)
    for claim_id, body, witness, ref, assertion, response_id in con.execute(
            "SELECT id,claim_json,witness_id,source_ref,assertion,response_id FROM scholarly_coverage_claim WHERE batch_id=? ORDER BY id", (batch_id,)):
        claim = json.loads(body)
        if (claim["witness_id"], claim["source_ref"], claim["assertion"], claim["source_response_id"]) != (witness, ref, assertion, response_id):
            raise ValueError("Stored coverage claim columns disagree with their provenance")
        claims.append({**claim, "claim_id": claim_id})
    all_dates = []
    for assessment_id, body, witness, response_id in con.execute(
            "SELECT id,claim_json,witness_id,response_id FROM scholarly_date_claim WHERE batch_id=? ORDER BY id", (batch_id,)):
        date = {**json.loads(body), "assessment_id": assessment_id}
        if (date["witness_id"], date["source_response_id"]) != (witness, response_id):
            raise ValueError("Stored date claim columns disagree with their provenance")
        dates[date["witness_id"]].append(date)
        all_dates.append(date)
    for records, checksum, id_field in ((claims, "coverage_sha256", "claim_id"),
                                        (all_dates, "dates_sha256", "assessment_id")):
        normalized_claims = [{k: v for k, v in c.items() if k not in (id_field, "source_response_id")}
                             for c in records]
        if digest(encoded(normalized_claims)) != batch[checksum]:
            raise ValueError("Stored scholarly claims changed; preserve history with a new batch")
    by_ref = defaultdict(list)
    for claim in claims:
        by_ref[claim["source_ref"]].append(claim)
    witnesses = sorted({d["witness_id"] for d in batch["documents"]})
    verses = []
    for coordinate in inventory["verses"]:
        relevant = [c for ref in coordinate["ntvmr_refs"] for c in by_ref[ref]]
        pairs = []
        for witness in witnesses:
            reports = [c for c in relevant if c["witness_id"] == witness]
            pairs.append({"witness_id": witness, "state": coverage_state(reports), "claims": reports,
                          "unknown_reason": ("no_explicit_mapped_report" if coordinate["ntvmr_refs"]
                                             else "unresolved_reference_mapping") if not reports else None,
                          "date_assessments": dates[witness]})
        alt = alternatives(pairs, dates)
        verses.append({**coordinate, "reported_coverage": pairs, "dating_alternatives": alt,
                       "ranking_state": alt["state"], "scenarios": None})
    response_ids = sorted({c["source_response_id"] for c in claims} |
                          {d["source_response_id"] for values in dates.values() for d in values})
    sources = []
    source_hashes = {}
    for response_id in response_ids:
        s = con.execute("SELECT endpoint,url,params_json,body,body_sha256,retrieved_at FROM source_response WHERE id=?", (response_id,)).fetchone()
        if s is None or digest(s[3]) != s[4]:
            raise ValueError("Source response missing or corrupt")
        source_hashes[response_id] = (s[4], s[5])
        sources.append({"source_response_id": response_id, "endpoint": s[0], "url": s[1],
                        "canonical_url": API_BASE + "/" + s[0] + "/" if s[0] != "scholarly/report" else s[1],
                        "params": json.loads(s[2]), "raw_body": s[3], "body_sha256": s[4], "retrieved_at": s[5]})
    if any(source_hashes[c["source_response_id"]] != (c["source_sha256"], c["retrieved_at"]) for c in claims + all_dates):
        raise ValueError("Source claim points to a different captured response")
    # Counts refer to the declared inventory, not all entries in document-wide captures.
    def counts(rows):
        states = Counter(p["state"] for v in rows for p in v["reported_coverage"])
        return {"verse_count": len(rows), "document_count": len(batch["documents"]),
                "witness_count": len(witnesses),
                "witness_verse_pairs": {state: states[state] for state in ("present", "absent", "unknown", "contested")},
                "graphable_coordinates": sum(v["dating_alternatives"]["state"] == "complete" for v in rows),
                "mapping_gaps": sum(not v["ntvmr_refs"] for v in rows),
                "by_ranking_state": dict(sorted(Counter(v["ranking_state"] for v in rows).items()))}
    common = {"format_version": 3, "evidence_policy": "scholarly_reports_only",
              "batch_id": batch_id, "batch_sha256": batch_sha, "contract_id": CONTRACT,
              "inventory_id": inventory_id, "inventory_scope": inventory["scope"],
              "inventory_source_citation": inventory["source_citation"],
              "mapping_citation": inventory["mapping_citation"],
              "collection_scope": batch["manifest"]["scope"], "documents": batch["documents"],
              "catalogue_citation": batch["manifest"].get("catalogue_citation"),
              "dating_policy_id": "all_complete_reported_intervals_equally",
              "collection_cost": {"replay_network_requests": 0, "reused_response_count": len(sources),
                                  "document_response_count": sum(s["endpoint"] != "scholarly/report" for s in sources),
                                  "historical_request_attempts": "not measured by this replay"}}
    dataset = {**common, "kind": "complete_dataset", "filters": None,
               "sources": sources, "source_claims": claims,
               "date_assessments": [d for values in dates.values() for d in values],
               "verses": verses, "counts": counts(verses)}
    selected = [v for v in verses if (include_omitted or v["editorial_status"] != "omitted")
                and (include_bracketed or v["editorial_status"] != "bracketed")]
    graph = {**common, "kind": "graph_input",
             "filters": {"include_omitted": include_omitted, "include_bracketed": include_bracketed},
             "sources": [{k: value for k, value in s.items() if k != "raw_body"} for s in sources],
             "verses": selected, "counts": counts(selected)}
    return dataset, graph
