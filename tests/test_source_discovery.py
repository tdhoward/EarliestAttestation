"""Bounded candidate discovery and uncertainty, using fictional offline reports."""

from contextlib import closing
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from controlled_ntvmr import AccessBlocked, Client, ContractError, RunStopped, connect
from source_discovery import (captured_chain, collect_book_range, prepare_discovery,
                              range_params, sha, verse_discovery)
from source_reports import build_report_exports, import_batch
from report_explorer import build_explorer_data, expand_explorer_data
from browser_format import pack_browser_data
from collect_source_discovery import main as collect_main, https_proxy_transport


def definition():
    return {"format_version": 1, "scope_id": "synthetic-range", "book": "Gal",
            "doc_id_min": 10000, "doc_id_max": 10100, "page_limit": 1,
            "catalogue_citation": "Synthetic catalogue", "access_expectations": "Fictional offline test only",
            "request_budget": 12, "minimum_interval_seconds": 5, "maximum_run_seconds": 180}


def page(ids, partial=False, cursor=None, count=None):
    root = {"count": len(ids) if count is None else count, "pagecount": len(ids),
            "manuscript": [{"docID": i, "gaNum": f"Synthetic {i}", "lang": "g"} for i in ids]}
    if partial:
        root.update(partial=True, nextAfterDocID=cursor)
    return {"status": "success", "data": {"manuscripts": root}}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.con = connect(self.root / "new.sqlite")
        self.addCleanup(self.con.close)

    def client(self, pages, budget=12):
        calls, waits = [], []

        def send(url, params, timeout):
            calls.append(dict(params))
            response = pages[len(calls)-1]
            return response if isinstance(response, tuple) else (200, json.dumps(response), {})

        return Client(self.con, "test", budget=budget, send=send, sleep=waits.append,
                      clock=lambda: 0, jitter=0), calls, waits

    def test_budget_resume_preserves_filters_and_unobserved_candidates(self):
        plan = definition()
        first, calls, _ = self.client([page([10046], True, 10046)], budget=1)
        with self.assertRaises(RunStopped):
            collect_book_range(first, plan)
        self.assertEqual(len(calls), 1)
        captured = captured_chain(self.con, plan)
        summary, _ = prepare_discovery({"definition": plan, "search_captures": captured, "run_state": "pending"}, [])
        self.assertEqual(summary["search_state"], "pending")
        self.assertEqual(summary["pending_candidate_ids"], [10046])
        self.assertEqual(verse_discovery(summary, "Gal.1.1")["state"], "search_incomplete")
        resumed, calls, _ = self.client([page([10051])], budget=2)
        self.assertEqual(collect_book_range(resumed, plan), "complete")
        self.assertEqual(calls, [{**range_params(plan), "afterDocID": "10046"}])
        self.assertEqual(resumed.attempts, 2)
        records = {"definition": plan, "search_captures": captured_chain(self.con, plan)}
        ready = [{"doc_id": doc, "metadata_state": "success", "coverage_state": "success"} for doc in (10046, 10051)]
        summary, _ = prepare_discovery(records, ready)
        self.assertEqual(summary["candidate_ids"], [10046, 10051])
        self.assertEqual(summary["search_state"], "complete")
        self.assertEqual(verse_discovery(summary, "Gal.1.1")["state"], "bounded_search_complete")
        self.assertEqual(verse_discovery(summary, "Heb.1.1")["state"], "not_searched")
        self.assertFalse(summary["corpus_complete"])
        offline = Client(self.con, "offline", offline=True)
        self.assertEqual(collect_book_range(offline, plan), "complete")
        self.assertEqual(offline.attempts, 0)
        changed = {**plan, "book": "Heb"}
        with self.assertRaisesRegex(ValueError, "different discovery definition"):
            collect_book_range(resumed, changed)

    def test_blocks_count_mismatches_and_outside_range_never_become_complete(self):
        blocked, calls, _ = self.client([(403, "Blocked", {})])
        with self.assertRaises(AccessBlocked):
            collect_book_range(blocked, definition())
        with self.assertRaises(AccessBlocked):
            collect_book_range(blocked, definition())
        self.assertEqual(len(calls), 1)
        self.assertEqual(captured_chain(self.con, definition()), [])
        with tempfile.TemporaryDirectory() as tmp, closing(connect(Path(tmp) / "new.sqlite")) as con:
            client = Client(con, "mismatch", budget=1, send=lambda *args: (200, json.dumps(page([10046], count=2)), {}))
            self.assertEqual(collect_book_range(client, definition()), "incomplete")
            summary, _ = prepare_discovery({"definition": definition(), "search_captures": captured_chain(con, definition())}, [])
            self.assertEqual(summary["search_state"], "incomplete")
        with tempfile.TemporaryDirectory() as tmp, closing(connect(Path(tmp) / "new.sqlite")) as con:
            client = Client(con, "outside", budget=1, send=lambda *args: (200, json.dumps(page([20001])), {}))
            with self.assertRaisesRegex(ContractError, "outside"):
                collect_book_range(client, definition())

    def test_header_only_continuation_is_retained_and_tampering_fails(self):
        client, _, _ = self.client([(200, json.dumps(page([10046])),
                                   {"X-VMR-Partial": "true", "X-VMR-Next-AfterDocID": "10046", "Set-Cookie": "secret"}),
                                  page([10051])])
        collect_book_range(client, definition())
        captures = captured_chain(self.con, definition())
        self.assertNotIn("Set-Cookie", captures[0]["headers"])
        summary, snapshots = prepare_discovery({"definition": definition(), "search_captures": captures}, [])
        self.assertEqual(summary["candidate_ids"], [10046, 10051])
        self.assertEqual(snapshots[0]["headers"]["X-VMR-Partial"], "true")
        captures[1]["params"]["indexContent"] = "Heb"
        with self.assertRaisesRegex(ValueError, "Invalid bounded discovery capture"):
            prepare_discovery({"definition": definition(), "search_captures": captures}, [])

    def write(self, name, record):
        (self.root / name).write_text(json.dumps(record), encoding="utf-8")

    def capture(self, name, doc, stage, payload):
        body = json.dumps({"status": "success", "data": payload})
        endpoint = "metadata/manuscript/get" if stage == "metadata" else "biblicalcontent/get"
        self.write(name, {"source_url": f"https://example.org/{endpoint}/", "http_status": 200,
                          "params": {"docID": str(doc), "detail": "10" if stage == "metadata" else "long", "format": "json"},
                          "raw_body": body, "body_sha256": sha(body), "retrieved_at": "2026-10-06T12:00:00Z"})

    def manifest(self):
        self.write("inventory.json", {"format_version": 1, "inventory_id": "synthetic", "edition": "NA28",
            "scope": "Fictional coordinates", "source_citation": "Synthetic publisher", "reuse_terms": "Synthetic",
            "mapping_citation": "Synthetic", "reviewer": "Software test",
            "verses": [{"osis_ref": ref, "editorial_status": "main", "ntvmr_refs": [ref]}
                       for ref in ("Gal.1.1", "Heb.1.1")]})
        for doc in (10046, 10051):
            self.capture(f"meta-{doc}.json", doc, "metadata", {"manuscript": {"docID": doc, "lang": "g",
                "gaNum": f"Synthetic {doc}", "originYear": {"early": 100, "late": 300, "content": "Fictional estimate"}}})
        self.capture("contents.json", 10046, "coverage", {"indexContents": {"docID": 10046,
            "indexContent": [{"docID": 10046, "pageID": 1, "osisID": "Gal.1.1"}]}})
        return {"format_version": 1, "contract_id": "ntvmr-source-reports-v1", "batch_id": "synthetic",
                "scope": "Fictional software reports", "inventory": "inventory.json", "additional_reports": [],
                "discovery_fixture": "discovery.json", "documents": [
                    {"doc_id": 10046, "corpus": "greek_nt_manuscript", "metadata_fixture": "meta-10046.json", "coverage_fixture": "contents.json"},
                    {"doc_id": 10051, "corpus": "greek_nt_manuscript", "metadata_fixture": "meta-10051.json"}]}

    def test_search_candidates_do_not_create_presence_and_pending_collection_is_visible(self):
        client, _, _ = self.client([page([10046, 10051])])
        collect_book_range(client, definition())
        self.write("discovery.json", {"definition": definition(), "search_captures": captured_chain(self.con, definition())})
        manifest = self.manifest()
        import_batch(self.con, manifest, self.root)
        dataset, graph = build_report_exports(self.con, "synthetic")
        self.assertEqual(graph["discovery"]["pending_candidate_ids"], [10051])
        self.assertEqual(graph["counts"]["witness_verse_pairs"], {"present": 1, "unknown": 3, "absent": 0, "contested": 0})
        self.assertEqual(graph["verses"][0]["discovery"]["state"], "candidate_collection_incomplete")
        self.assertEqual(graph["verses"][1]["discovery"]["state"], "not_searched")
        self.assertEqual(graph["verses"][0]["reported_coverage"][1]["state"], "unknown")
        self.assertEqual(len(dataset["source_claims"]), 1)
        self.assertEqual(graph["collection_cost"]["document_response_count"], 3)
        self.assertEqual(graph["collection_cost"]["discovery_response_count"], 1)
        payload = build_explorer_data(graph)
        self.assertEqual(payload["observations"]["Gal.1.1"]["discovery"]["state"], "candidate_collection_incomplete")
        self.assertFalse(payload["metadata"]["discovery"]["corpus_complete"])
        search_id = graph["discovery"]["sources"][0]["source_response_id"]
        self.con.execute("UPDATE source_response SET headers_json='{}' WHERE id=?", (search_id,))
        # Body integrity remains enforced even without contents claims pointing at this response.
        self.con.execute("UPDATE source_response SET body='changed' WHERE id=?", (search_id,))
        with self.assertRaisesRegex(ValueError, "Discovery source response"):
            build_report_exports(self.con, "synthetic")

    def test_collection_cli_discovers_an_unnamed_witness_and_collects_it_once(self):
        seed = self.manifest()
        seed["documents"] = seed["documents"][:1]
        self.write("collection.json", {"format_version": 1, "coordinate_inventory": "inventory.json",
            "books": ["Gal", "Heb"], "documents": seed["documents"], "additional_reports": []})
        plan = {**definition(), "transport_base_url": "http://proxy.example/community/vmr/api"}
        self.write("definition.json", plan)
        calls = []

        def send(url, params, timeout):
            calls.append((url, dict(params)))
            if url.endswith("/metadata/liste/search/"):
                response = page([10046, 10051])
            elif url.endswith("/metadata/manuscript/get/"):
                response = {"status": "success", "data": {"manuscript": {"docID": 10051,
                    "gaNum": "Synthetic newly discovered witness", "lang": "g",
                    "originYear": {"early": 150, "late": 250, "content": "Fictional catalogue estimate"}}}}
            else:
                response = {"status": "success", "data": {"indexContents": {"docID": 10051,
                    "indexContent": [{"docID": 10051, "pageID": 1, "osisID": "Gal.1.1"}]}}}
            return 200, json.dumps(response), {}

        def client(con, run_id, **kwargs):
            return Client(con, run_id, send=send, sleep=lambda seconds: None, clock=lambda: 0, jitter=0, **kwargs)

        args = ["--definition", str(self.root / "definition.json"), "--data-dir", str(self.root),
                "--run-id", "synthetic-cli", "--base-url", plan["transport_base_url"]]
        with patch("collect_source_discovery.Client", side_effect=client), redirect_stdout(StringIO()):
            self.assertEqual(collect_main(args), 0)
            # Repeating this scope uses existing captures and leaves one central record.
            self.assertEqual(collect_main(args), 0)
        self.assertEqual(len(json.loads((self.root / "discovery.json").read_text())), 1)
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(url.startswith(plan["transport_base_url"]) for url, _ in calls))
        self.assertNotIn("gaNum", calls[0][1])
        self.assertNotIn("lang", calls[0][1])
        self.assertNotIn("dateMax", calls[0][1])
        self.assertEqual([p["docID"] for _, p in calls[1:]], ["10051", "10051"])
        packed = json.loads((self.root / "attestations.json").read_text(encoding="utf-8"))
        self.assertEqual(packed["format_version"], 4)
        data = expand_explorer_data(packed)
        self.assertEqual(data, expand_explorer_data(pack_browser_data(data)))
        self.assertEqual(data["metadata"]["discovery"]["candidate_ids"], [10046, 10051])
        self.assertEqual(data["metadata"]["discovery"]["pending_candidate_ids"], [])
        self.assertEqual(data["metadata"]["counts"]["witness_verse_pairs"]["present"], 2)
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertFalse(list(self.root.glob("*.html")))
        record = json.loads((self.root / "discovery.json").read_text())[-1]
        self.assertEqual(record["definition"]["transport_base_url"], "<local proxy>/community/vmr/api")
        self.assertTrue(record["search_captures"][0]["source_url"].startswith("<local proxy>/"))
        for path in [self.root / "discovery.json", self.root / "attestations.json", *self.root.glob("sources/*.json")]:
            self.assertNotIn("http://proxy.example", path.read_text(encoding="utf-8"))
        for path in self.root.glob("sources/*.json"):
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(sha(saved["raw_body"]), saved["body_sha256"])
        # A fresh ignored cache can replay redacted search captures using the configured route.
        with patch("collect_source_discovery.Client", side_effect=client), \
                patch("collect_source_discovery.connect", side_effect=lambda path: connect(self.root / "offline.sqlite")), \
                redirect_stdout(StringIO()):
            self.assertEqual(collect_main([*args, "--offline"]), 0)
        self.assertEqual(len(calls), 3)
        replayed = json.loads((self.root / "attestations.json").read_text(encoding="utf-8"))
        self.assertEqual(replayed["format_version"], 4)
        self.assertEqual(expand_explorer_data(replayed), expand_explorer_data(pack_browser_data(expand_explorer_data(replayed))))
        for claim in [*data["claims"].values(), *data["dates"].values()]:
            self.assertTrue(claim["citation"].startswith("https://ntvmr.uni-muenster.de/"))
        self.assertTrue(data["metadata"]["discovery"]["sources"][0]["citation"].startswith("https://ntvmr.uni-muenster.de/"))

    def test_metadata_only_candidate_resumes_contents_into_existing_collection(self):
        seed = self.manifest()
        self.write("collection.json", {"format_version": 1, "coordinate_inventory": "inventory.json",
            "books": ["Gal", "Heb"], "documents": seed["documents"], "additional_reports": []})
        self.write("definition.json", definition())
        calls = []

        def send(url, params, timeout):
            calls.append((url, dict(params)))
            if url.endswith("/metadata/liste/search/"):
                response = page([10046, 10051])
            else:
                self.assertTrue(url.endswith("/biblicalcontent/get/"))
                self.assertEqual(params["docID"], "10051")
                response = {"status": "success", "data": {"indexContents": {"docID": 10051,
                    "indexContent": [{"docID": 10051, "pageID": 1, "osisID": "Gal.1.1"}]}}}
            return 200, json.dumps(response), {}

        def client(con, run_id, **kwargs):
            return Client(con, run_id, send=send, sleep=lambda seconds: None, clock=lambda: 0, jitter=0, **kwargs)

        args = ["--definition", str(self.root / "definition.json"), "--data-dir", str(self.root),
                "--run-id", "synthetic-resume"]
        with patch("collect_source_discovery.Client", side_effect=client), redirect_stdout(StringIO()):
            self.assertEqual(collect_main(args), 0)
        self.assertEqual(len(calls), 2)
        updated = json.loads((self.root / "collection.json").read_text())
        self.assertEqual(updated["books"], ["Gal", "Heb"])
        self.assertEqual(len(updated["documents"]), 2)
        self.assertEqual(updated["documents"][1]["metadata_fixture"], "meta-10051.json")
        self.assertIn("coverage_fixture", updated["documents"][1])
        data = expand_explorer_data(json.loads((self.root / "attestations.json").read_text()))
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "bounded_search_complete")
        self.assertEqual(data["observations"]["Heb.1.1"]["discovery"]["state"], "not_searched")

    def test_collection_cli_preserves_candidate_block_on_resume(self):
        seed = self.manifest()
        self.write("collection.json", {"format_version": 1, "coordinate_inventory": "inventory.json",
            "books": ["Gal", "Heb"], "documents": seed["documents"], "additional_reports": []})
        self.write("definition.json", definition())
        calls = []

        def send(url, params, timeout):
            calls.append((url, dict(params)))
            if url.endswith("/metadata/liste/search/"):
                return 200, json.dumps(page([10046, 10051, 10052])), {}
            self.assertTrue(url.endswith("/biblicalcontent/get/"))
            self.assertEqual(params["docID"], "10051")
            return 403, "Synthetic provider access block", {}

        def client(con, run_id, **kwargs):
            return Client(con, run_id, send=send, sleep=lambda seconds: None, clock=lambda: 0, jitter=0, **kwargs)

        args = ["--definition", str(self.root / "definition.json"), "--data-dir", str(self.root),
                "--run-id", "synthetic-blocked-candidate"]
        with patch("collect_source_discovery.Client", side_effect=client), redirect_stdout(StringIO()):
            self.assertEqual(collect_main(args), 2)
            self.assertEqual(collect_main(args), 2)
        self.assertEqual(len(calls), 2)
        record = json.loads((self.root / "discovery.json").read_text())[0]
        self.assertEqual(record["collection_cost"]["request_attempts"], 2)
        self.assertIn("Prior document access block", record["collection_cost"]["collection_errors"][0])
        data = expand_explorer_data(json.loads((self.root / "attestations.json").read_text()))
        self.assertEqual(data["metadata"]["discovery"]["pending_candidate_ids"], [10051, 10052])
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "candidate_collection_incomplete")
        self.assertEqual(data["metadata"]["counts"]["witness_verse_pairs"]["present"], 1)
        with closing(connect(self.root / ".cache" / "collection.sqlite")) as con:
            self.assertEqual(con.execute("SELECT doc_id,state,attempts FROM collection_job").fetchall(),
                             [(10051, "blocked", 1)])

    def test_proxy_keeps_canonical_https_requests_and_rejects_credentials(self):
        with self.assertRaises(ValueError):
            https_proxy_transport("http://user:password@example.org:8889")
        with patch("collect_source_discovery.build_opener") as opener:
            send = https_proxy_transport("http://example.org:8889")
            response = opener.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b'{"status":"success"}'
            response.headers = {}
            self.assertEqual(send("https://ntvmr.uni-muenster.de/community/vmr/api/metadata/liste/search/", {"indexContent": "Gal"}, 30)[0], 200)
            request = opener.return_value.open.call_args.args[0]
            self.assertTrue(request.full_url.startswith("https://ntvmr.uni-muenster.de/"))
            self.assertIn("EarliestAttestation", request.get_header("User-agent"))
            with self.assertRaises(ValueError):
                send("http://example.org/", {}, 30)



if __name__ == "__main__":
    unittest.main()
