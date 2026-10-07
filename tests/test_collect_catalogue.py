"""Entirely fictional HTTP responses and clocks; no live collection."""

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_collection import build_data, read_json, write_json
from collect_catalogue import (CATEGORIES, collect, import_captures, main, queue_connection,
                               scope_definition, single_worker, summary)
from controlled_ntvmr import API_BASE, NT_BOOKS, AccessBlocked
from source_discovery import prepare_discovery, range_params, sha, verse_discovery


def page(ids, *, cursor=None, count=None):
    root = {"count": len(ids) if count is None else count, "pagecount": len(ids),
            "manuscript": [{"docID": doc, "gaNum": f"Fictional {doc}", "lang": "g"} for doc in ids]}
    if cursor:
        root.update(partial="true", nextAfterDocID=str(cursor))
    return {"status": "success", "data": {"manuscripts": root}}


def report(doc, stage, *, empty=False):
    if stage == "metadata":
        return {"status": "success", "data": {"manuscript": {"docID": doc,
            "gaNum": f"Fictional {doc}", "lang": "g",
            "originYear": {"early": 200, "late": 399, "content": "Fictional competing-century notation"},
            "pages": {"page": [{"pageID": 1, "indexTier": 3}, {"pageID": 2, "indexTier": 3}]}}}}
    return {"status": "success", "data": {"indexContents": {"docID": doc, "indexContent": [] if empty else [
        {"docID": doc, "osisID": "Gal.1.1", "pageID": 1},
        {"docID": doc, "osisID": "Gal.1.1", "pageID": 2},
        {"docID": doc, "osisID": "Heb.1.1", "pageID": 2}]}}}


class Clock:
    def __init__(self):
        self.elapsed, self.wall, self.waits = 0.0, 1000.0, []

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.advance(seconds)

    def advance(self, seconds):
        self.elapsed += seconds
        self.wall += seconds


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.connection = queue_connection(self.root, create=True)
        self.con = self.connection.__enter__()
        self.addCleanup(self.connection.__exit__, None, None, None)
        self.clock, self.calls = Clock(), []
        self.config = {"run_id": "fictional", "hours": 8, "interval": 5, "max_requests": None,
                       "page_limit": 200, "base_url": API_BASE, "https_proxy": None}
        write_json(self.root / "inventory.json", {"format_version": 1, "inventory_id": "fictional",
            "edition": "NA28", "scope": "Software fixture", "source_citation": "Fictional publisher",
            "reuse_terms": "Fictional", "mapping_citation": "Fictional", "reviewer": "Software fixture",
            "verses": [{"osis_ref": ref, "editorial_status": "main", "ntvmr_refs": [ref]}
                       for ref in ("Gal.1.1", "Gal.1.2", "Heb.1.1")]})
        write_json(self.root / "collection.json", {"format_version": 1, "coordinate_inventory": "inventory.json",
            "books": ["Gal", "Heb"], "documents": [], "additional_reports": [],
            "include_bracketed": True, "include_omitted": False})

    def run_collect(self, handler, **kwargs):
        def send(url, params, timeout):
            self.calls.append((url, dict(params), self.clock.wall))
            self.clock.advance(.25)
            result = handler(url, params)
            return result if isinstance(result, tuple) else (200, json.dumps(result),
                {"Set-Cookie": "private", "Link": API_BASE + "/metadata/liste/search/"})

        return collect(self.con, self.config, self.root, send=send, sleep=self.clock.sleep,
                       clock=lambda: self.clock.elapsed, wall_clock=lambda: self.clock.wall, **kwargs)

    def handler(self, ids, *, empty=()):
        def respond(url, params):
            if url.endswith("/metadata/liste/search/"):
                low, high = map(int, params["docID"].split("-"))
                return page([doc for doc in ids if low <= doc <= high])
            stage = "metadata" if url.endswith("/metadata/manuscript/get/") else "coverage"
            doc = int(params["docID"])
            return report(doc, stage, empty=doc in empty)
        return respond

    def assert_spacing(self):
        self.assertTrue(all(b[2] - a[2] >= 5 for a, b in zip(self.calls, self.calls[1:])))

    def test_all_categories_uncapped_reports_once_and_offline_import(self):
        ids = [10000 + n for n in range(1, 26)] + [20001, 30001, 40001]
        original = (self.root / "collection.json").read_bytes()
        result = self.run_collect(self.handler(ids, empty=[40001]))
        self.assertEqual(result["state"], "complete")
        self.assertEqual(result["request_attempts"], 60)
        self.assertGreater(result["request_attempts"], 50)
        self.assertEqual([c["documents"] for c in result["categories"]], [25, 1, 1, 1])
        self.assertEqual((self.root / "collection.json").read_bytes(), original)
        self.assertFalse((self.root / "attestations.json").exists())
        self.assertTrue(all(read_json(p)["headers"]["Link"].startswith(API_BASE)
                            for p in (self.root / "sources").glob("*.json")))
        searches = [params for url, params, _ in self.calls if url.endswith("/metadata/liste/search/")]
        self.assertEqual(len(searches), 4)
        self.assertTrue(all(set(p) == {"docID", "detail", "format", "limit"} for p in searches))
        self.assert_spacing()
        calls = len(self.calls)
        self.assertEqual(self.run_collect(self.handler(ids))["state"], "complete")
        self.assertEqual(len(self.calls), calls)
        with patch("collect_catalogue.transport", side_effect=AssertionError("No network")):
            result = import_captures(self.con, self.root, "fictional")
            data = build_data(data_dir=self.root)
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(result["import_errors"], [])
        self.assertEqual(result["documents_added"], 28)
        self.assertEqual(data["metadata"]["counts"]["witness_verse_pairs"],
                         {"present": 54, "unknown": 30, "absent": 0, "contested": 0})
        for ref in ("Gal.1.1", "Gal.1.2", "Heb.1.1"):
            self.assertEqual(data["observations"][ref]["discovery"]["state"], "bounded_search_complete")
        self.assertFalse(data["metadata"]["discovery"]["corpus_complete"])
        # Two page reports count once; dates and original notation are copied intact.
        self.assertEqual(len(data["observations"]["Gal.1.1"]["reported_coverage"][0]["claims"]), 2)
        self.assertTrue(all((d["date_min"], d["date_max"]) == (200, 399) for d in data["dates"].values()))
        self.assertTrue(all(d["original_notation"] == "Fictional competing-century notation" for d in data["dates"].values()))
        before = (self.root / "collection.json").read_bytes(), (self.root / "discovery.json").read_bytes()
        self.assertEqual(import_captures(self.con, self.root, "fictional")["documents_added"], 0)
        self.assertEqual(before, ((self.root / "collection.json").read_bytes(), (self.root / "discovery.json").read_bytes()))

    def test_pagination_resume_reuses_seeds_and_keeps_first_request_spacing(self):
        metadata = json.dumps(report(10001, "metadata"))
        write_json(self.root / "sources" / "seed.json", {"source_url": API_BASE + "/metadata/manuscript/get/",
            "params": {"docID": "10001", "detail": "10", "format": "json"}, "http_status": 200,
            "raw_body": metadata, "body_sha256": sha(metadata), "retrieved_at": "2026-10-06T12:00:00Z"})
        config = read_json(self.root / "collection.json")
        config["documents"] = [{"doc_id": 10001, "corpus": "greek_nt_manuscript",
                                "metadata_fixture": "sources/seed.json", "note": "Keep this annotation"}]
        write_json(self.root / "collection.json", config)

        def handler(url, params):
            if url.endswith("/metadata/liste/search/") and params["docID"] == "10000-19999":
                return page([10002]) if "afterDocID" in params else page([10001], cursor=10001)
            return self.handler([10001, 10002])(url, params)

        self.config["max_requests"] = 1
        self.assertEqual(self.run_collect(handler)["state"], "paused")
        self.config["max_requests"] = 1000
        result = self.run_collect(handler)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(self.calls[1][1]["afterDocID"], "10001")
        self.assertEqual(len(self.calls), 8)  # Two inventory pages, three empty categories, three new reports.
        self.assertFalse(any(url.endswith("/metadata/manuscript/get/") and p["docID"] == "10001"
                             for url, p, _ in self.calls))
        self.assert_spacing()
        imported = import_captures(self.con, self.root, "fictional")
        self.assertFalse(imported["import_errors"])
        preserved = read_json(self.root / "collection.json")["documents"][0]
        self.assertEqual(preserved["metadata_fixture"], "sources/seed.json")
        self.assertEqual(preserved["note"], "Keep this annotation")

    def test_retry_after_survives_a_deadline_and_restart(self):
        self.config["hours"] = 20 / 3600
        result = self.run_collect(lambda *args: (429, "Slow down", {"Retry-After": "60"}))
        self.assertEqual(result["state"], "paused")
        self.assertEqual(len(self.calls), 1)
        self.config["hours"] = 8
        self.assertEqual(self.run_collect(self.handler([]))["state"], "complete")
        self.assertGreaterEqual(self.calls[1][2] - self.calls[0][2], 60)
        captures = [read_json(p) for p in (self.root / "sources").glob("*.json")]
        self.assertIn(429, [c["http_status"] for c in captures])
        self.assert_spacing()

    def test_provider_block_stops_every_category_and_new_campaign_until_explicit_resolution(self):
        result = self.run_collect(lambda *args: (200, "<!doctype html><html>Challenge</html>", {"Content-Type": "text/html"}))
        self.assertEqual(result["state"], "blocked")
        for name in ("fictional", "different-campaign"):
            self.config["run_id"] = name
            with self.assertRaises(AccessBlocked):
                self.run_collect(self.handler([]))
        self.assertEqual(len(self.calls), 1)
        self.config["run_id"] = "fictional"
        self.assertEqual(self.run_collect(self.handler([]), access_restored_reason="Fictional provider restored access")["state"], "complete")
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(self.con.execute("SELECT count(*) FROM access_resolution").fetchone()[0], 1)
        self.assertEqual(self.con.execute("SELECT origin FROM source_response WHERE id=1").fetchone()[0], "blocked")
        self.assert_spacing()

    def test_response_committed_before_queue_update_is_recovered_without_a_request(self):
        original_write = write_json
        interrupted = False

        def interrupt(path, value, **kwargs):
            nonlocal interrupted
            if path.parent.name == "sources" and not interrupted:
                interrupted = True
                raise KeyboardInterrupt
            return original_write(path, value, **kwargs)

        with patch("collect_catalogue.write_json", side_effect=interrupt):
            self.assertEqual(self.run_collect(self.handler([]))["state"], "paused")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.run_collect(self.handler([]))["state"], "complete")
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.con.execute("SELECT count(*) FROM archive").fetchone()[0], 4)
        self.assert_spacing()

    def test_interrupt_after_a_blocking_response_cannot_retry_it(self):
        with patch("collect_catalogue.write_json", side_effect=KeyboardInterrupt):
            result = self.run_collect(lambda *args: (403, "Fictional block", {}))
        self.assertEqual(result["state"], "blocked")
        with self.assertRaises(AccessBlocked):
            self.run_collect(self.handler([]))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(list((self.root / "sources").glob("*.json"))), 1)

    def test_three_throttled_responses_latch_a_persistent_block(self):
        result = self.run_collect(lambda *args: (429, "Fictional quota", {"Retry-After": "10"}))
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(len(self.calls), 3)
        with self.assertRaises(AccessBlocked):
            self.run_collect(self.handler([]))
        self.assertEqual(len(self.calls), 3)
        self.assert_spacing()

    def test_clock_adjustment_does_not_remove_restart_spacing(self):
        self.config["max_requests"] = 1
        self.assertEqual(self.run_collect(self.handler([]))["state"], "paused")
        self.clock.wall += 3600  # Wall-clock correction, without elapsed monotonic time.
        elapsed = self.clock.elapsed
        self.config["max_requests"] = 100
        self.assertEqual(self.run_collect(self.handler([]))["state"], "complete")
        self.assertGreaterEqual(self.clock.elapsed - elapsed, 15)

    def test_contract_failures_are_visible_and_do_not_promote_discovery(self):
        def bad_inventory(url, params):
            if url.endswith("/metadata/liste/search/") and params["docID"] == "10000-19999":
                return page([10001], count=2)
            return self.handler([10001])(url, params)

        self.assertEqual(self.run_collect(bad_inventory)["state"], "incomplete")
        import_captures(self.con, self.root, "fictional")
        record = read_json(self.root / "discovery.json")[0]
        assessed, _ = prepare_discovery(record, [{"doc_id": 10001, "metadata_state": "success", "coverage_state": "success"}])
        self.assertEqual(assessed["search_state"], "failed")
        self.assertEqual(verse_discovery(assessed, "Gal.1.1")["state"], "search_incomplete")
        self.assertEqual(verse_discovery(assessed, "Rev.1.1")["state"], "search_incomplete")
        self.assertFalse(assessed["corpus_complete"])

    def test_out_of_range_rows_are_not_queued(self):
        def bad_inventory(url, params):
            if url.endswith("/metadata/liste/search/") and params["docID"] == "10000-19999":
                return page([20001])
            return page([])

        self.assertEqual(self.run_collect(bad_inventory)["state"], "incomplete")
        self.assertEqual(self.con.execute("SELECT count(*) FROM job").fetchone()[0], 0)

    def test_proxy_captures_are_canonical_redacted_and_preserve_raw_bodies(self):
        self.config["base_url"] = "http://fictional.proxy:8889/community/vmr/api"
        self.assertEqual(self.run_collect(self.handler([10001]))["state"], "complete")
        for p in (self.root / "sources").glob("*.json"):
            record = read_json(p)
            self.assertNotIn("fictional.proxy", p.read_text(encoding="utf-8"))
            self.assertTrue(record["source_url"].startswith(API_BASE))
            self.assertTrue(record["transport_url"].startswith("<local proxy>"))
            self.assertEqual(record["body_sha256"], sha(record["raw_body"]))
            self.assertNotIn("Set-Cookie", record["headers"])
        self.assertFalse(import_captures(self.con, self.root, "fictional")["import_errors"])
        self.assertNotIn("fictional.proxy", (self.root / "discovery.json").read_text())
        data = build_data(data_dir=self.root)
        self.assertTrue(all(d["citation"].startswith(API_BASE) for d in data["dates"].values()))

    def test_unusable_reports_stay_captured_and_unknown_without_blocking_other_witnesses(self):
        def handler(url, params):
            value = self.handler([10001, 10002])(url, params)
            if url.endswith("/metadata/manuscript/get/") and params["docID"] == "10001":
                value["data"]["manuscript"]["lang"] = "unsupported"
            return value

        self.assertEqual(self.run_collect(handler)["state"], "complete")
        result = import_captures(self.con, self.root, "fictional")
        self.assertEqual(result["documents_added"], 1)
        self.assertTrue(result["import_errors"])
        data = build_data(data_dir=self.root)
        self.assertEqual(data["metadata"]["discovery"]["scopes"][0]["pending_candidate_ids"], [10001])
        self.assertEqual(data["observations"]["Gal.1.1"]["discovery"]["state"], "candidate_collection_incomplete")

    def test_transient_failures_count_all_retries_and_need_explicit_retry(self):
        def handler(url, params):
            if url.endswith("/metadata/manuscript/get/"):
                return 503, "Fictional temporary failure", {}
            return self.handler([10001])(url, params)

        result = self.run_collect(handler)
        self.assertEqual(result["state"], "incomplete")
        self.assertEqual(len(result["failed_reports"]), 1)
        self.assertEqual(len(self.calls), 8)  # Four inventories, three metadata attempts, one contents.
        self.assertEqual(self.run_collect(self.handler([10001]))["state"], "incomplete")
        self.assertEqual(len(self.calls), 8)
        self.assertEqual(self.run_collect(self.handler([10001]), retry_failed=True)["state"], "complete")
        self.assertEqual(len(self.calls), 9)
        self.assert_spacing()

    def test_invalid_settings_never_make_requests_and_worker_lock_is_exclusive(self):
        for key, value in (("interval", 4.999), ("interval", float("nan")), ("hours", 0),
                           ("max_requests", -1), ("page_limit", 201)):
            bad = deepcopy(self.config)
            bad[key] = value
            with self.assertRaises(ValueError):
                collect(self.con, bad, self.root, send=lambda *args: self.fail("No requests"))
        with single_worker(self.root):
            with self.assertRaisesRegex(ValueError, "already running"):
                with single_worker(self.root):
                    self.fail("Second worker acquired the lock")
        self.assertEqual(self.calls, [])
        plan = scope_definition(self.config, *CATEGORIES[0])
        self.assertEqual(plan["books"], list(NT_BOOKS))
        self.assertNotIn("indexContent", range_params(plan))
        self.assertNotIn("indexContent", range_params({**plan, "request_budget": 10000}))

    def test_status_and_import_commands_are_offline(self):
        self.run_collect(self.handler([]))
        with patch("collect_catalogue.transport", side_effect=AssertionError("No network")), redirect_stdout(StringIO()):
            with single_worker(self.root):
                self.assertEqual(main(["status", "--data-dir", str(self.root), "--run-id", "fictional"]), 0)
            self.assertEqual(main(["import", "--data-dir", str(self.root), "--run-id", "fictional"]), 0)
        self.assertEqual(summary(self.con, "fictional")["request_attempts"], 4)


if __name__ == "__main__":
    unittest.main()
