"""Offline checks of documented search continuation; synthetic pages are discovery only."""

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from controlled_ntvmr import (
    API_BASE, AccessBlocked, Client, ContractError, RunStopped, catalogue_report,
    collect_catalogue_scope, collect_search, connect, discovery_report,
    import_search_fixture, main, parse_search, search_continuation,
)

ROOT = Path(__file__).resolve().parent.parent


def page(ids, *, partial=None, cursor=None, count=None):
    root = {"count": len(ids) if count is None else count, "pagecount": len(ids),
            "manuscript": [{"docID": doc_id, "gaNum": f"Synthetic {doc_id}", "lang": "g"}
                           for doc_id in ids]}
    if partial is not None:
        root["partial"] = partial
    if cursor is not None:
        root["nextAfterDocID"] = cursor
    return {"status": "success", "data": {"manuscripts": root}}


class SearchContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "new.sqlite"
        self.con = connect(self.path)
        self.addCleanup(self.con.close)

    def client(self, pages, *, budget=10, run_id="test"):
        calls, waits = [], []

        def send(url, params, timeout):
            calls.append(dict(params))
            response = pages[len(calls)-1]
            return response if isinstance(response, tuple) else (200, json.dumps(response), {})

        return Client(self.con, run_id, budget=budget, send=send,
                      sleep=waits.append, clock=lambda: 0, jitter=0), calls, waits

    def test_captured_help_and_bounded_terminal_search(self):
        fixtures = ROOT / "data/reference/contracts"
        help_record = json.loads((fixtures / "metadata_liste_search_help.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(help_record["raw_body"].encode()).hexdigest(), help_record["body_sha256"])
        self.assertIn("nextAfterDocID", help_record["raw_body"])
        record = json.loads((fixtures / "search_bounded_terminal.json").read_text(encoding="utf-8"))
        import_search_fixture(self.con, record)
        offline = Client(self.con, "capture", offline=True)
        self.assertEqual(collect_catalogue_scope(offline, [10066, 10075], index_ref="John.1.1", page_limit=1), "success")
        self.assertEqual(offline.attempts, 0)
        self.assertFalse(catalogue_report(self.con, "capture")["corpus_complete"])

    def test_named_lookup_follows_cursor_and_preserves_each_source_page(self):
        client, calls, waits = self.client([
            page([10046], partial="true", cursor="10046"),
            page([10047], partial=False),
        ])
        self.assertEqual(collect_search(client, "Gal.1.1", "P*", lang="grc"), "success")
        self.assertEqual(calls[1], {**calls[0], "afterDocID": "10046"})
        self.assertEqual(waits, [5])
        rows = self.con.execute("SELECT doc_id,response_id FROM discovery_candidate ORDER BY doc_id").fetchall()
        self.assertEqual(rows, [(10046, 1), (10047, 2)])
        report = discovery_report(self.con, "test")
        self.assertEqual(report["jobs"][0]["returned_count"], 2)
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(self.con.execute("SELECT count(*) FROM coverage_index").fetchone()[0], 0)

    def test_budget_pause_and_resume_replays_first_page_without_another_request(self):
        client, calls, _ = self.client([page([10046], partial=True, cursor=10046)], budget=1)
        with self.assertRaises(RunStopped):
            collect_catalogue_scope(client, [10046, 10047], page_limit=1)
        self.assertEqual(len(calls), 1)
        report = catalogue_report(self.con, "test")
        self.assertEqual(report["state"], "pending")
        self.assertTrue(report["candidate_snapshot_stale"])
        self.assertEqual(report["candidates"], [])
        resumed, calls, _ = self.client([page([10047])], budget=2)
        self.assertEqual(collect_catalogue_scope(resumed, [10046, 10047], page_limit=1), "success")
        self.assertEqual([call["afterDocID"] for call in calls], ["10046"])
        self.assertEqual(resumed.attempts, 2)
        self.assertTrue(catalogue_report(self.con, "test")["catalogue_lookup_complete"])
        offline = Client(self.con, "offline", offline=True)
        self.assertEqual(collect_catalogue_scope(offline, [10046, 10047], page_limit=1), "success")
        self.assertEqual(offline.attempts, 0)

    def test_interrupted_refresh_retains_snapshot_and_avoids_old_continuation_cache(self):
        client, _, _ = self.client([page([10046], partial=True, cursor=10046), page([10047])])
        collect_catalogue_scope(client, [10046, 10047], page_limit=1)
        old = self.con.execute("SELECT doc_id,response_id FROM catalogue_candidate ORDER BY doc_id").fetchall()
        refreshing, _, _ = self.client([page([10046], partial=True, cursor=10046)], budget=3)
        with self.assertRaises(RunStopped):
            collect_catalogue_scope(refreshing, [10046, 10047], page_limit=1, refresh=True)
        self.assertEqual(self.con.execute("SELECT doc_id,response_id FROM catalogue_candidate ORDER BY doc_id").fetchall(), old)
        offline = Client(self.con, "test", offline=True)
        with self.assertRaisesRegex(RunStopped, "Offline cache miss"):
            collect_catalogue_scope(offline, [10046, 10047], page_limit=1)
        resumed, calls, _ = self.client([page([10047])], budget=4)
        self.assertEqual(collect_catalogue_scope(resumed, [10046, 10047], page_limit=1), "success")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.con.execute("SELECT response_id FROM catalogue_candidate ORDER BY doc_id").fetchall(), [(3,), (4,)])

    def test_header_only_continuation_survives_fixture_import_and_offline_replay(self):
        params = {"docID": "10046|10047", "detail": "document", "format": "json", "limit": "1"}
        for response, query, headers in [
            (page([10046]), params, {"X-VMR-Partial": "true", "X-VMR-Next-AfterDocID": "10046"}),
            (page([10047]), {**params, "afterDocID": "10046"}, {"X-VMR-Partial": "false"}),
        ]:
            body = json.dumps(response)
            import_search_fixture(self.con, {"source_url": API_BASE + "/metadata/liste/search/",
                "params": query, "raw_body": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "http_status": 200, "retrieved_at": "2026-10-06T12:00:00+00:00", "headers": headers})
        self.assertEqual(collect_catalogue_scope(Client(self.con, "test", offline=True), [10046, 10047], page_limit=1), "success")

    def test_invalid_continuation_is_a_contract_error(self):
        for payload in [page([10046], partial=True), page([], partial=True, cursor=10046),
                        page([10046], partial="yes", cursor=10046),
                        page([10046], partial=True, cursor=True),
                        page([10046], partial=True, cursor=10047),
                        page([10046], partial=False, cursor=10046)]:
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                search_continuation(payload, parse_search(payload)[0])
        good = page([10046], partial=True, cursor=10046)
        malformed = page([10046])
        malformed["data"]["manuscripts"]["partial"] = None
        with self.assertRaises(ContractError):
            search_continuation(malformed, parse_search(malformed)[0])
        with self.assertRaises(ContractError):
            search_continuation(good, parse_search(good)[0], {"X-VMR-Partial": "false"})
        with self.assertRaises(ContractError):
            search_continuation(good, parse_search(good)[0], {"X-VMR-Next-AfterDocID": "10047"})
        with self.assertRaises(ContractError):
            search_continuation(good, parse_search(good)[0], after_doc_id=10046)

    def test_header_changes_are_distinct_immutable_snapshots(self):
        body = json.dumps(page([10046]))
        record = {"source_url": API_BASE + "/metadata/liste/search/", "params": {},
                  "raw_body": body, "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                  "http_status": 200, "retrieved_at": "2026-10-06T12:00:00+00:00",
                  "headers": {"X-VMR-Partial": "false"}}
        terminal = import_search_fixture(self.con, record)
        self.assertEqual(import_search_fixture(self.con, record), terminal)
        record["headers"] = {"X-VMR-Partial": "true", "X-VMR-Next-AfterDocID": "10046"}
        partial = import_search_fixture(self.con, record)
        self.assertNotEqual(terminal, partial)
        self.assertEqual(json.loads(self.con.execute("SELECT headers_json FROM source_response WHERE id=?",
                                                    (terminal,)).fetchone()[0]), {"X-VMR-Partial": "false"})

    def test_overlapping_pages_fail_without_publishing_duplicate_candidates(self):
        client, calls, _ = self.client([page([10046], partial=True, cursor=10046), page([10046, 10047])])
        with self.assertRaises(ContractError):
            collect_search(client, "Gal.1.1", "P*")
        self.assertEqual(len(calls), 2)
        self.assertEqual(discovery_report(self.con, "test")["jobs"][0]["state"], "failed")
        self.assertEqual(self.con.execute("SELECT count(*) FROM discovery_candidate").fetchone()[0], 0)

    def test_count_mismatches_remain_incomplete_even_when_aggregate_counts_match(self):
        client, _, _ = self.client([page([10046], partial=True, cursor=10046, count=2), page([10047], count=0)])
        self.assertEqual(collect_catalogue_scope(client, [10046, 10047], page_limit=1), "incomplete")
        report = catalogue_report(self.con, "test")
        self.assertEqual(report["returned_count"], report["reported_count"])
        self.assertFalse(report["catalogue_lookup_complete"])

    def test_unexpected_partial_document_stops_before_followup_request(self):
        client, calls, _ = self.client([page([10048], partial=True, cursor=10048)])
        with self.assertRaisesRegex(ContractError, "outside the declared scope"):
            collect_catalogue_scope(client, [10046, 10047], page_limit=1)
        self.assertEqual(len(calls), 1)

    def test_block_on_continuation_is_preserved_until_explicit_refresh(self):
        client, _, _ = self.client([page([10046], partial=True, cursor=10046), (403, "Blocked", {})])
        with self.assertRaises(AccessBlocked):
            collect_catalogue_scope(client, [10046, 10047], page_limit=1)
        self.assertEqual(catalogue_report(self.con, "test")["state"], "blocked")
        resumed, calls, _ = self.client([])
        with self.assertRaises(AccessBlocked):
            collect_catalogue_scope(resumed, [10046, 10047], page_limit=1)
        self.assertEqual(calls, [])

    def test_dry_run_accounts_for_uncached_continuations(self):
        client, _, _ = self.client([page([10046], partial=True, cursor=10046)], budget=1)
        with self.assertRaises(RunStopped):
            collect_catalogue_scope(client, [10046, 10047], page_limit=1)
        stdout = StringIO()
        with redirect_stdout(stdout):
            self.assertEqual(main(["--db", str(self.path), "--run-id", "test", "--request-budget", "4",
                "--catalogue-doc-id", "10046", "--catalogue-doc-id", "10047", "--catalogue-limit", "1", "--dry-run"]), 0)
        report = json.loads(stdout.getvalue())
        self.assertEqual(report["maximum_network_attempts"], 3)
        self.assertTrue(report["catalogue_cached"])


if __name__ == "__main__":
    unittest.main()
