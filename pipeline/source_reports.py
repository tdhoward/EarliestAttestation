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

from pipeline.controlled_ntvmr import (API_BASE, NT_BOOKS, encoded, edition_inventory_report,
                              import_edition_inventory, inventory_ref_parts,
                              parse_coverage, parse_metadata, rank_candidates,
                              validate_inventory)
from pipeline.source_discovery import prepare_discovery, verse_discovery
from pipeline.build_storage import check_expansion, record_store, records_digest


CONTRACT = "ntvmr-source-reports-v1"
PROVIDER = "INTF / New Testament Virtual Manuscript Room (NTVMR)"
# Exact Greek and multilingual catalogue codes observed in retained GA reports.
GREEK_LANGUAGE_CODES = frozenset(("g", "grc", "grc_lat", "g-k", "g-l", "g-arb",
                                  "g-arm", "g-l-arb", "g-sl", "g-t"))
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
CREATE INDEX IF NOT EXISTS scholarly_coverage_by_ref
 ON scholarly_coverage_claim(batch_id,source_ref,id);
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
    return parse_capture(record, doc_id, stage, capture_path=path.as_posix())


def parse_capture(record, doc_id, stage, *, capture_path):
    """Validate a retained capture, whether standalone or embedded in discovery evidence."""
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
              else parse_coverage(payload, doc_id, books=NT_BOOKS))
    result = {"endpoint": endpoint, "url": record["source_url"], "params": params,
              "body": body, "body_sha256": record["body_sha256"],
              "retrieved_at": timestamp(required_text(record, "retrieved_at")),
              "provider": PROVIDER, "capture_path": capture_path,
              "citation": API_BASE + "/" + endpoint + "/?" + urlencode(params)}
    if record.get("transport_qualification"):
        result["transport_qualification"] = record["transport_qualification"]
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


def metadata_date_claim(document, snapshot, payload, metadata):
    doc_id = document["doc_id"]
    return {"witness_id": document.get("witness_id", f"ntvmr:{doc_id}"),
            "status": metadata["date_status"],
            "date_min": metadata["date_min"], "date_max": metadata["date_max"],
            "original_notation": metadata["origin_notation"],
            "applicability": "catalogue_document", "doc_id": doc_id,
            **provenance(snapshot, "data.manuscript.originYear",
                         payload["data"]["manuscript"].get("originYear"),
                         "Catalogue document estimate; no independently assigned portions.")}


def published_claims(report, field):
    """Resolve optional character spans in retained scholarly prose, not manuscript text."""
    body = required_text(report, "raw_body")
    result = []
    for original in report.get(field, []):
        claim = dict(original)
        if "statement_span" in claim:
            span = claim.pop("statement_span")
            if ("statement" in claim or not isinstance(span, list) or len(span) != 2
                    or any(type(i) is not int for i in span) or not 0 <= span[0] < span[1] <= len(body)):
                raise ValueError("A scholarly statement span must select retained material without overriding text")
            claim["statement"] = body[span[0]:span[1]]
        result.append(claim)
    return result


def additional_date_claims(report, witnesses):
    """Validate explicit published date reports for both collection and normalization."""
    body = required_text(report, "raw_body")
    snapshot = {"provider": required_text(report, "provider"), "citation": required_text(report, "citation"),
                "retrieved_at": timestamp(required_text(report, "retrieved_at")), "body_sha256": digest(body)}
    dates = []
    for claim in published_claims(report, "dates"):
        if set(claim) - {"witness_id", "date_min", "date_max", "original_notation", "source_locator", "statement", "qualifications"}:
            raise ValueError("This bounded contract supports whole-witness date reports only")
        if claim["witness_id"] not in witnesses:
            raise ValueError("Additional claims must identify a witness in the declared scope")
        if required_text(claim, "statement") not in body:
            raise ValueError("The exact reported statement must be retained in the source snapshot")
        required_text(claim, "source_locator")
        required_text(claim, "original_notation")
        dates.append({**claim, "status": date_bounds(claim), "applicability": "catalogue_document",
                      **provenance(snapshot, claim["source_locator"], claim["statement"], claim.get("qualifications", ""))})
    return dates


def discovery_date_overrides(record, documents):
    """Retained metadata can qualify collection even when it is not the primary report."""
    known = {d["doc_id"]: d for d in documents}
    dates = []
    for item in record.get("date_filter_metadata_captures", []):
        doc = item["doc_id"]
        snap, payload, metadata = parse_capture(item["capture"], doc, "metadata", capture_path=item["capture_file"])
        dates.append({**metadata_date_claim(known.get(doc, {"doc_id": doc}), snap, payload, metadata),
                      "capture_file": item["capture_file"]})
    return dates


def index_limitations(document, root, metadata_sha256, coverage_sha256, coordinates):
    """Qualify only pinned index entries; this is admission, not a source assertion."""
    result, identifiers = {}, set()
    supplied = document.get("index_limitations", [])
    if not isinstance(supplied, list):
        raise ValueError("Index limitations must be a list")
    for limitation in supplied:
        identifier = required_text(limitation, "limitation_id")
        if identifier in identifiers:
            raise ValueError("Index limitation IDs must be distinct within a document")
        identifiers.add(identifier)
        refs = limitation.get("verses")
        if (not isinstance(refs, list) or not refs or any(not isinstance(v, str) for v in refs)
                or len(set(refs)) != len(refs) or set(refs) - coordinates or set(refs) & result.keys()):
            raise ValueError("Index limitations need exact, distinct, nonoverlapping collection verses")
        if (limitation.get("metadata_sha256") != metadata_sha256
                or limitation.get("coverage_sha256") != coverage_sha256):
            raise ValueError("Index limitation source changed; review the scoped admission before rebuilding")
        required_text(limitation, "reason")
        evidence = limitation.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("Index limitations need retained evidence")
        retained_evidence = []
        for pin in evidence:
            relative = required_text(pin, "capture_file")
            path = (root / relative).resolve()
            if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
                raise ValueError("Index limitation evidence must stay inside the data directory")
            raw = json.loads(path.read_text(encoding="utf-8"))
            body = required_text(raw, "raw_body")
            if raw.get("body_sha256") != digest(body) or pin.get("body_sha256") != digest(body):
                raise ValueError("Index limitation evidence hash does not match its capture")
            required_text(pin, "source_locator")
            if required_text(pin, "statement") not in body:
                raise ValueError("Index limitation statement must occur in retained evidence")
            retained_evidence.append({**pin, "citation": raw.get("citation", raw.get("source_url")),
                                      "source_url": required_text(raw, "source_url"),
                                      "retrieved_at": timestamp(required_text(raw, "retrieved_at"))})
        result.update((ref, {**limitation, "evidence": retained_evidence}) for ref in refs)
    return result


def prepare_batch(manifest, root, *, include_pending=False, record_factory=None):
    """Read only metadata/contents captures and explicitly supplied published claims."""
    if manifest.get("format_version") != 1 or manifest.get("contract_id") != CONTRACT:
        raise ValueError("Unsupported source-report manifest contract")
    required_text(manifest, "batch_id")
    required_text(manifest, "scope")
    inventory = manifest["inventory"]
    if not isinstance(inventory, dict):
        inventory = json.loads((root / inventory).read_text(encoding="utf-8"))
    validate_inventory(inventory)
    for coordinate in inventory["verses"]:
        if coordinate["ntvmr_refs"] not in ([], [coordinate["osis_ref"]]):
            raise ValueError("This source contract supports explicit direct coordinate matches only")
    snapshots, coverage, dates, documents = [], [], [], []
    if record_factory is not None:
        snapshots, coverage = record_factory("snapshots"), record_factory("coverage")
    seen = set()
    coordinates = {v["osis_ref"] for v in inventory["verses"]}
    for document in manifest["documents"]:
        if document.get("index_limitations") and not all(document.get(k) for k in ("metadata_fixture", "coverage_fixture")):
            raise ValueError("Index limitations require both metadata and contents captures")
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
            if metadata["source_lang"] not in GREEK_LANGUAGE_CODES:
                raise ValueError("This bounded contract supports only reported Greek language codes")
            # GA catalogue membership must be declared from the source scope, not a name guess.
            if document.get("corpus") != "greek_nt_manuscript":
                raise ValueError("Declare the Greek NT manuscript catalogue scope")
            dates.append({**metadata_date_claim(document, snap, payload, metadata), "snapshot": len(snapshots)-1})
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
            limitations = index_limitations(document, root, item["metadata_sha256"],
                                            snap["body_sha256"], coordinates)
            for index, entry in enumerate(pages):
                if not isinstance(entry, dict) or (entry.get("osisID"), entry.get("pageID")) not in allowed:
                    continue
                tier = tiers.get(entry["pageID"])
                qualification = (f"Catalogue indexing tier {tier}. " if tier is not None
                                 else "Indexing tier not supplied. ")
                if type(tier) is int and tier >= 4:
                    qualification += "Provider labels tier 4+ as AI indexing awaiting human confirmation. "
                qualification += "Reported verse-range entry; extent unspecified. Missing entries establish no absence."
                limitation = limitations.get(entry["osisID"])
                if limitation:
                    qualification += (f" Scoped index admission limitation ({limitation['limitation_id']}): "
                                      f"{limitation['reason']} This index contribution is unknown; "
                                      "it is not an explicit absence or an opposing scholarly assertion.")
                coverage.append({"witness_id": witness, "source_ref": entry["osisID"],
                                 "assertion": "unknown" if limitation or type(tier) is int and tier >= 4 else "present",
                                 "extent": "unspecified", "doc_id": doc_id,
                                 "page_id": entry["pageID"], "snapshot": len(snapshots)-1,
                                 "indexing_metadata_sha256": item["metadata_sha256"],
                                 "reported_indexing_tier": tier,
                                 **({"index_limitation": limitation} if limitation else {}),
                                 **provenance(snap, f"data.indexContents.indexContent[{index}]",
                                              entry, qualification)})
        documents.append(item)
    if not documents:
        raise ValueError("A bounded document scope is required")
    witnesses = {d["witness_id"] for d in documents}
    for report in manifest.get("additional_reports", []):
        admission = report.get("admission", "active")
        if admission not in ("active", "pending_contract_review"):
            raise ValueError("Unsupported additional-report admission state")
        body = required_text(report, "raw_body")
        if report.get("body_sha256", digest(body)) != digest(body):
            raise ValueError("Additional-report capture hash does not match its retained material")
        snap = {"endpoint": "scholarly/report", "url": required_text(report, "citation"),
                "params": {}, "body": body, "body_sha256": digest(body),
                "retrieved_at": timestamp(required_text(report, "retrieved_at")),
                "provider": required_text(report, "provider"), "citation": report["citation"]}
        report_coverage = []
        supplied_coverage = published_claims(report, "coverage")
        for claim in supplied_coverage + published_claims(report, "dates"):
            if claim["witness_id"] not in witnesses:
                raise ValueError("Additional claims must identify a witness in the declared scope")
            if required_text(claim, "statement") not in body:
                raise ValueError("The exact reported statement must be retained in the source snapshot")
            required_text(claim, "source_locator")
        for claim in supplied_coverage:
            if set(claim) - {"witness_id", "source_ref", "assertion", "extent", "source_locator", "statement", "qualifications"}:
                raise ValueError("Additional coverage reports must apply to the witness/verse, without independently inferred portions")
            inventory_ref_parts(claim["source_ref"])
            if claim["assertion"] not in ("present", "absent", "unknown"):
                raise ValueError("Invalid explicit source assertion")
            if claim.get("extent", "unspecified") not in ("partial", "full", "unspecified"):
                raise ValueError("Invalid reported extent")
            report_coverage.append({**claim,
                                    **provenance(snap, claim["source_locator"], claim["statement"],
                                                 claim.get("qualifications", ""))})
        report_dates = additional_date_claims(report, witnesses)
        # Retain and validate proposed extractions at the evidence-review checkpoint.
        # Only admitted reports enter ordinary coverage, dates, or rankings.
        if admission == "active" or include_pending:
            snapshots.append(snap)
            coverage.extend({**claim, "snapshot": len(snapshots)-1} for claim in report_coverage)
            dates.extend({**claim, "snapshot": len(snapshots)-1} for claim in report_dates)
    return inventory, snapshots, coverage, dates, documents


def import_batch(con, manifest, root=Path(".")):
    with record_store(root) as factory:
        prepared = prepare_batch(manifest, root, record_factory=factory)
        return _import_batch(con, manifest, root, prepared)


def _import_batch(con, manifest, root, prepared):
    inventory, snapshots, coverage, dates, documents = prepared
    discovery = None
    discoveries = []
    for record in manifest.get("discovery_records", []):
        summary, search_snapshots = prepare_discovery(record, documents, dates + discovery_date_overrides(record, documents))
        if any(item["scope_id"] == summary["scope_id"] for item in discoveries):
            raise ValueError("Duplicate discovery scope")
        discoveries.append(summary)
        snapshots.extend(search_snapshots)
    if manifest.get("discovery_fixture"):
        record = json.loads((root / manifest["discovery_fixture"]).read_text(encoding="utf-8"))
        discovery, search_snapshots = prepare_discovery(record, documents, dates + discovery_date_overrides(record, documents))
        snapshots.extend(search_snapshots)
    con.executescript(SCHEMA)
    batch_id = manifest["batch_id"]
    # Hash actual captures as well as the manifest, so changed files cannot replay as the same batch.
    normalized = {"manifest": manifest, "documents": documents,
                  "inventory_sha256": digest(encoded(inventory)),
                  "source_hashes": [s["body_sha256"] for s in snapshots],
                  "coverage_sha256": records_digest(coverage, omit=("snapshot",)),
                  "dates_sha256": records_digest(dates, omit=("snapshot",))}
    if discovery is not None:
        normalized["discovery"] = discovery
    if discoveries:
        normalized["discoveries"] = discoveries
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
            headers = encoded(snap.get("headers", {}))
            # Include endpoint to use response_lookup rather than repeatedly
            # scanning the entire table of retained raw source bodies.
            row = con.execute("SELECT id FROM source_response WHERE endpoint=? AND url=? AND params_json=? AND body_sha256=? AND retrieved_at=? AND headers_json=?",
                              (snap["endpoint"], snap["url"], encoded(snap["params"]), snap["body_sha256"], snap["retrieved_at"], headers)).fetchone()
            if row:
                response_ids.append(row[0])
            else:
                cur = con.execute("""INSERT INTO source_response
                    (endpoint,url,params_json,status_code,headers_json,body,body_sha256,retrieved_at,origin)
                    VALUES (?,?,?,200,?,?,?,?,'fixture')""",
                    (snap["endpoint"], snap["url"], encoded(snap["params"]), headers, snap["body"], snap["body_sha256"], snap["retrieved_at"]))
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


def export_discovery(con, discovery):
    discovery_sources = []
    for snap in discovery.get("source_snapshots", []):
        source = con.execute("""SELECT id,body,headers_json FROM source_response WHERE endpoint=? AND url=?
          AND params_json=? AND body_sha256=? AND retrieved_at=? AND headers_json=?""",
          (snap["endpoint"], snap["url"], encoded(snap["params"]), snap["body_sha256"], snap["retrieved_at"], encoded(snap.get("headers", {})))).fetchone()
        if source is None or digest(source[1]) != snap["body_sha256"]:
            raise ValueError("Discovery source response missing or changed")
        discovery_sources.append({"source_response_id": source[0],
                                  **{k: v for k, v in snap.items() if k not in ("body", "headers")}})
    discovery = {k: v for k, v in discovery.items() if k != "source_snapshots"}
    cost = dict(discovery.get("collection_cost", {}))
    if "request_attempts" in cost:
        cost["prior_pilot_attempts"] = discovery["definition"].get("prior_pilot_attempts", 0)
        cost["increment_attempts_to_date"] = cost["prior_pilot_attempts"] + cost["request_attempts"]
        discovery["collection_cost"] = cost
    discovery["sources"] = discovery_sources
    discovery["candidates"] = [{**{k: v for k, v in candidate.items() if k != "snapshot"},
                                 "source_response_id": discovery_sources[candidate["snapshot"]]["source_response_id"]}
                                for candidate in discovery.get("candidates", [])]
    return discovery


def build_report_exports(con, batch_id, *, include_omitted=False, include_bracketed=True,
                         consume_verse=None):
    """Validate all evidence; optionally hand off one graph verse at a time.

    A consumer receives only selected graph rows. In that mode no complete
    dataset or coverage matrix is retained; the returned graph has metadata
    and counts, with an empty verses list.
    """
    row = con.execute("SELECT manifest_json,inventory_id,manifest_sha256 FROM scholarly_report_batch WHERE batch_id=?", (batch_id,)).fetchone()
    if row is None:
        raise ValueError("Unknown scholarly-report batch")
    batch, inventory_id, batch_sha = json.loads(row[0]), row[1], row[2]
    witnesses = sorted({d["witness_id"] for d in batch["documents"]})
    if digest(row[0]) != batch_sha:
        raise ValueError("Report batch manifest checksum mismatch")
    discoveries = batch.get("discoveries", [batch.get("discovery") or prepare_discovery(None, [])[0]])
    discoveries = [export_discovery(con, item) for item in discoveries]
    discovery = discoveries[0] if len(discoveries) == 1 else {"scopes": discoveries, "corpus_complete": False,
                                                            "ranking_scope": "collected_witnesses_only"}
    discovery_sources = [source for item in discoveries for source in item["sources"]]
    inventory = edition_inventory_report(con, inventory_id)
    inventory_body = con.execute("SELECT manifest_json FROM edition_inventory WHERE inventory_id=?", (inventory_id,)).fetchone()[0]
    if digest(inventory_body) != batch["inventory_sha256"]:
        raise ValueError("Report inventory changed; use a new inventory and batch")
    expected_coordinates = json.loads(inventory_body)["verses"]
    if consume_verse is None:
        check_expansion(len(witnesses), len(expected_coordinates))
    if len(inventory["verses"]) != len(expected_coordinates):
        raise ValueError("Stored inventory coordinates disagree with their source manifest")
    for ordinal, (actual, expected) in enumerate(zip(inventory["verses"], expected_coordinates), 1):
        for key in ("osis_ref", "editorial_status", "editorial_note", "mapping_note", "ntvmr_refs", "passage_citation"):
            if actual.get(key) != expected.get(key):
                raise ValueError("Stored inventory coordinates disagree with their source manifest")
        book, chapter, verse = inventory_ref_parts(expected["osis_ref"])
        if (actual["ordinal"], actual["book"], actual["chapter"], actual["verse"]) != (ordinal, book, chapter, verse):
            raise ValueError("Stored coordinate order differs from the source manifest")
    claim_sources = {}
    def read_claims(ref=None):
        query = "SELECT id,claim_json,witness_id,source_ref,assertion,response_id FROM scholarly_coverage_claim WHERE batch_id=?"
        params = (batch_id,)
        if ref is not None:
            query += " AND source_ref=?"
            params += (ref,)
        for claim_id, body, witness, source_ref, assertion, response_id in con.execute(query + " ORDER BY id", params):
            claim = json.loads(body)
            if (claim["witness_id"], claim["source_ref"], claim["assertion"], claim["source_response_id"]) != (witness, source_ref, assertion, response_id):
                raise ValueError("Stored coverage claim columns disagree with their provenance")
            identity = (claim["source_sha256"], claim["retrieved_at"])
            if response_id in claim_sources and claim_sources[response_id] != identity:
                raise ValueError("Source claim points to a different captured response")
            claim_sources[response_id] = identity
            yield {**claim, "claim_id": claim_id}
    claims = list(read_claims()) if consume_verse is None else None
    dates = defaultdict(list)
    all_dates = []
    for assessment_id, body, witness, response_id in con.execute(
            "SELECT id,claim_json,witness_id,response_id FROM scholarly_date_claim WHERE batch_id=? ORDER BY id", (batch_id,)):
        date = {**json.loads(body), "assessment_id": assessment_id}
        if (date["witness_id"], date["source_response_id"]) != (witness, response_id):
            raise ValueError("Stored date claim columns disagree with their provenance")
        dates[date["witness_id"]].append(date)
        all_dates.append(date)
    for records, checksum, id_field in ((claims if claims is not None else read_claims(), "coverage_sha256", "claim_id"),
                                        (all_dates, "dates_sha256", "assessment_id")):
        if records_digest(records, omit=(id_field, "source_response_id")) != batch[checksum]:
            raise ValueError("Stored scholarly claims changed; preserve history with a new batch")
    by_ref = defaultdict(list)
    for claim in claims or ():
        by_ref[claim["source_ref"]].append(claim)
    verses = []
    totals, selected_totals = Counter(), Counter()
    def count_verse(total, verse):
        total["verse_count"] += 1
        total["graphable_coordinates"] += verse["dating_alternatives"]["state"] == "complete"
        total["mapping_gaps"] += not verse["ntvmr_refs"]
        total.update(("coverage", p["state"]) for p in verse["reported_coverage"])
        total[("discovery", verse["discovery"]["state"])] += 1
        total[("ranking", verse["ranking_state"])] += 1
    for coordinate in inventory["verses"]:
        relevant = [c for ref in coordinate["ntvmr_refs"]
                    for c in (by_ref[ref] if claims is not None else read_claims(ref))]
        reports_by_witness = defaultdict(list)
        for claim in relevant:
            reports_by_witness[claim["witness_id"]].append(claim)
        pairs = []
        for witness in witnesses:
            reports = reports_by_witness.get(witness, [])
            pairs.append({"witness_id": witness, "state": coverage_state(reports), "claims": reports,
                          "unknown_reason": ("no_explicit_mapped_report" if coordinate["ntvmr_refs"]
                                             else "unresolved_reference_mapping") if not reports else None,
                          "date_assessments": dates[witness]})
        alt = alternatives(pairs, dates)
        verse = {**coordinate, "discovery": verse_discovery(discovery, coordinate["osis_ref"]),
                       "reported_coverage": pairs, "dating_alternatives": alt,
                       "ranking_state": alt["state"], "scenarios": None}
        count_verse(totals, verse)
        selected = ((include_omitted or verse["editorial_status"] != "omitted")
                    and (include_bracketed or verse["editorial_status"] != "bracketed"))
        if selected:
            count_verse(selected_totals, verse)
            if consume_verse is not None:
                consume_verse(verse)
        if consume_verse is None:
            verses.append(verse)
    response_ids = sorted(set(claim_sources) |
                          {d["source_response_id"] for values in dates.values() for d in values} |
                          {s["source_response_id"] for s in discovery_sources})
    sources = []
    source_hashes = {}
    for response_id in response_ids:
        s = con.execute("SELECT endpoint,url,params_json,body,body_sha256,retrieved_at FROM source_response WHERE id=?", (response_id,)).fetchone()
        if s is None or digest(s[3]) != s[4]:
            raise ValueError("Source response missing or corrupt")
        source_hashes[response_id] = (s[4], s[5])
        sources.append({"source_response_id": response_id, "endpoint": s[0], "url": s[1],
                        "canonical_url": API_BASE + "/" + s[0] + "/" if s[0] != "scholarly/report" else s[1],
                        "params": json.loads(s[2]), "body_sha256": s[4], "retrieved_at": s[5],
                        **({"raw_body": s[3]} if consume_verse is None else {})})
    if (any(source_hashes[key] != identity for key, identity in claim_sources.items())
            or any(source_hashes[d["source_response_id"]] != (d["source_sha256"], d["retrieved_at"]) for d in all_dates)):
        raise ValueError("Source claim points to a different captured response")
    # Counts refer to the declared inventory, not all entries in document-wide captures.
    def counts(total):
        return {"verse_count": total["verse_count"], "document_count": len(batch["documents"]),
                "witness_count": len(witnesses),
                "witness_verse_pairs": {state: total[("coverage", state)] for state in ("present", "absent", "unknown", "contested")},
                "graphable_coordinates": total["graphable_coordinates"],
                "mapping_gaps": total["mapping_gaps"],
                "by_discovery_state": dict(sorted((key[1], value) for key, value in total.items() if isinstance(key, tuple) and key[0] == "discovery")),
                "by_ranking_state": dict(sorted((key[1], value) for key, value in total.items() if isinstance(key, tuple) and key[0] == "ranking"))}
    common = {"format_version": 3, "evidence_policy": "scholarly_reports_only",
              "batch_id": batch_id, "batch_sha256": batch_sha, "contract_id": CONTRACT,
              "inventory_id": inventory_id, "inventory_scope": inventory["scope"],
              "inventory_source_citation": inventory["source_citation"],
              "mapping_citation": inventory["mapping_citation"],
              "collection_scope": batch["manifest"]["scope"], "documents": batch["documents"],
              "discovery": discovery,
              "catalogue_citation": batch["manifest"].get("catalogue_citation"),
              "dating_policy_id": "all_complete_reported_intervals_equally",
              "collection_cost": {"replay_network_requests": 0, "reused_response_count": len(sources),
                                  "document_response_count": sum(s["endpoint"] in ("metadata/manuscript/get", "biblicalcontent/get") for s in sources),
                                  "discovery_response_count": len(discovery_sources),
                                  "historical_request_attempts": "not measured by this replay"}}
    dataset = {**common, "kind": "complete_dataset", "filters": None,
               "sources": sources, "source_claims": claims,
               "date_assessments": [d for values in dates.values() for d in values],
               "verses": verses, "counts": counts(totals)} if consume_verse is None else None
    selected = [v for v in verses if (include_omitted or v["editorial_status"] != "omitted")
                and (include_bracketed or v["editorial_status"] != "bracketed")]
    graph = {**common, "kind": "graph_input",
             "filters": {"include_omitted": include_omitted, "include_bracketed": include_bracketed},
             "sources": [{k: value for k, value in s.items() if k != "raw_body"} for s in sources],
             "verses": selected, "counts": counts(selected_totals)}
    return dataset, graph
