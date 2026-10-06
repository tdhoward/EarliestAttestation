#!/usr/bin/env python3
"""Collect a budgeted discovery scope into the central collection and refresh its data."""

import argparse
from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from build_collection import DATA, build_data, data_path, prepare_collection, read_json, write_json
from controlled_ntvmr import (Client, ContractError, JobFailure, RunStopped,
                              collect_stage, connect, encoded, import_search_fixture)
from source_discovery import (captured_chain, collect_book_range, prepare_discovery,
                              range_params, response_capture, sha)
from source_reports import capture, prepare_batch


def https_proxy_transport(proxy_url):
    """Route official HTTPS through CONNECT, preserving certificate verification."""
    proxy = urlsplit(proxy_url)
    if proxy.scheme not in ("http", "https") or not proxy.hostname or proxy.username or proxy.password:
        raise ValueError("Use a configured HTTP(S) CONNECT proxy without credentials in its URL")
    opener = build_opener(ProxyHandler({"https": proxy_url}))

    def send(url, params, timeout):
        if not url.startswith("https://ntvmr.uni-muenster.de/community/vmr/api/"):
            raise ValueError("Proxy transport accepts only the canonical HTTPS NTVMR API")
        request = Request(url + "?" + urlencode(params),
                          headers={"User-Agent": "EarliestAttestation/0.2 (research collector; project repository)",
                                   "Accept": "application/json"})
        try:
            with opener.open(request, timeout=timeout) as response:
                return response.status, response.read().decode("utf-8", "replace"), dict(response.headers.items())
        except HTTPError as error:
            return error.code, error.read().decode("utf-8", "replace"), dict(error.headers.items())
    return send


def collect(data_dir, definition, run_id, *, offline=False, https_proxy=None, base_url=None):
    range_params(definition)
    if https_proxy != definition.get("https_connect_proxy"):
        raise ValueError("The network route must match the declared discovery definition")
    if base_url != definition.get("transport_base_url") or (base_url and https_proxy):
        raise ValueError("Use the single network route recorded in the discovery definition")
    config_path = data_dir / "collection.json"
    original = read_json(config_path)
    prepare_collection(original, data_dir)  # Validate reused reports before requests.
    config = deepcopy(original)
    documents = config["documents"]
    known = {doc["doc_id"]: doc for doc in documents}
    discovery_path = data_path(data_dir, config.get("discovery", "discovery.json"))
    records = read_json(discovery_path) if discovery_path.exists() else []
    original_records = deepcopy(records)
    errors = []
    with closing(connect(data_dir / ".cache" / "collection.sqlite")) as con:
        if offline:
            for previous in records:
                if previous["definition"] == definition:
                    for record in previous["search_captures"]:
                        import_search_fixture(con, record)
        transport_options = {"send": https_proxy_transport(https_proxy)} if https_proxy else {}
        if base_url:
            transport_options["base_url"] = base_url
        client = Client(con, run_id, offline=offline, budget=definition["request_budget"],
                        interval=definition["minimum_interval_seconds"],
                        duration=definition["maximum_run_seconds"], **transport_options)
        try:
            collect_book_range(client, definition)
        except (ContractError, RunStopped, JobFailure) as error:
            errors.append(str(error))
        state, error = con.execute("SELECT state,error FROM scholarly_discovery_run WHERE run_id=?", (run_id,)).fetchone()
        record = {"format_version": 1, "definition": definition, "run_state": state,
                  "run_error": error, "search_captures": captured_chain(con, definition, client.base_url, offline=offline)}
        summary, _ = prepare_discovery(record, [])
        for doc_id in summary["candidate_ids"] if state in ("complete", "incomplete") else []:
            item = deepcopy(known.get(doc_id, {"doc_id": doc_id, "corpus": "greek_nt_manuscript"}))
            stopped = False
            for stage in ("metadata", "coverage"):
                if item.get(f"{stage}_fixture"):
                    continue
                try:
                    collect_stage(client, doc_id, stage)
                    response_id = con.execute("SELECT response_id FROM collection_job WHERE run_id=? AND doc_id=? AND stage=?",
                                              (run_id, doc_id, stage)).fetchone()[0]
                    saved = response_capture(con, response_id)
                    if base_url:
                        saved["transport_qualification"] = definition["transport_qualification"]
                    target = data_dir / "sources" / f"ntvmr-{doc_id}-{stage}-{sha(encoded(saved))[:12]}.json"
                    write_json(target, saved)
                    _, _, parsed = capture(target, doc_id, stage)
                    if stage == "metadata" and (parsed["source_lang"] not in ("g", "grc", "grc_lat") or not parsed["ga_num"]):
                        errors.append(f"Candidate {doc_id} outside supported Greek GA contract; uncollected")
                        break
                    item[f"{stage}_fixture"] = target.relative_to(data_dir).as_posix()
                except (ContractError, RunStopped, JobFailure) as error:
                    errors.append(f"{doc_id} {stage}: {error}")
                    stopped = isinstance(error, RunStopped)
                    break
            if item.get("metadata_fixture"):
                if doc_id in known:
                    known[doc_id].update(item)
                else:
                    documents.append(item)
                    known[doc_id] = item
            if stopped:
                break
        record["collection_cost"] = {
            "request_attempts": client.attempts,
            "http_responses_recorded": con.execute("SELECT count(*) FROM request_attempt WHERE run_id=? AND response_id IS NOT NULL", (run_id,)).fetchone()[0],
            "reused_seed_document_responses": sum(bool(d.get(f)) for d in original["documents"] for f in ("metadata_fixture", "coverage_fixture")),
            "request_budget": definition["request_budget"], "collection_errors": errors,
        }
    # One current record per declared scope, including failures and pending candidates.
    records = [r for r in records if r["definition"]["scope_id"] != definition["scope_id"]]
    records.append(record)
    config["discovery"] = discovery_path.relative_to(data_dir).as_posix()
    if definition["book"] not in config["books"]:
        config["books"].append(definition["book"])
    manifest, _ = prepare_collection(config, data_dir, discovery_records=records)
    ready = prepare_batch(manifest, data_dir)[4]
    for scope in records:
        prepare_discovery(scope, ready)
    app_data = build_data(config, data_dir, discovery_records=records)
    if read_json(config_path) != original or (read_json(discovery_path) if discovery_path.exists() else []) != original_records:
        raise ValueError("Collection changed during discovery; captures are retained in data/sources for recovery")
    write_json(discovery_path, records)
    write_json(config_path, config)
    write_json(data_dir / "attestations.json", app_data, compact=True)
    summary, _ = prepare_discovery(record, ready)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definition", type=Path, required=True)
    parser.add_argument("--run-id", required=True, help="Stable identifier for budgeted resume")
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--https-proxy", help="Configured HTTPS CONNECT proxy; canonical TLS remains verified")
    parser.add_argument("--base-url", help="Explicit configured relay, qualified in the definition")
    args = parser.parse_args(argv)
    summary = collect(args.data_dir.resolve(), read_json(args.definition), args.run_id,
                      offline=args.offline, https_proxy=args.https_proxy, base_url=args.base_url)
    print(json.dumps({k: summary[k] for k in ("scope_id", "search_state", "candidate_ids", "pending_candidate_ids",
                                             "corpus_complete", "collection_cost")}, sort_keys=True))
    return 0 if summary["search_state"] == "complete" and not summary["pending_candidate_ids"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
