import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from controlled_ntvmr import (
    AccessBlocked, Client, ContractError, RunStopped, collect_stage, connect,
    export_p52, import_p52, main, parse_coverage, retry_after,
)

FIXTURE = Path(__file__).parent / "fixtures" / "p52_coverage_probe.json"
P52 = json.loads(FIXTURE.read_text(encoding="utf-8"))["response"]
PARAMS = {"docID": "10052", "detail": "long", "format": "json"}


class FakeTime:
    def __init__(self):
        self.value = 0

    def clock(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "v2.sqlite"
        self.con = connect(self.path)
        self.addCleanup(self.con.close)

    def client(self, responses, **options):
        clock = FakeTime()
        calls = []

        def send(url, params, timeout):
            calls.append((clock.value, url, dict(params)))
            item = responses[len(calls) - 1]
            if isinstance(item, Exception):
                raise item
            return item

        client = Client(self.con, options.pop("run_id", "test"), budget=options.pop("budget", 10),
                        interval=options.pop("interval", 5), jitter=0,
                        send=send, clock=clock.clock, sleep=clock.sleep,
                        rng=lambda: 0, **options)
        return client, clock, calls

    def test_p52_individual_entries_and_no_inferred_neighbors(self):
        self.assertEqual(parse_coverage(P52, 10052), [
            ("John.18.31", 10), ("John.18.32", 10), ("John.18.33", 10),
            ("John.18.37", 20), ("John.18.38", 20)])
        for bad in [
            {"status": "error", "data": P52["data"]},
            {"status": "success", "data": {}},
            {"status": "success", "data": {"indexContents": {"docID": 10052, "indexContent": [{}]}}},
        ]:
            with self.assertRaises(ContractError):
                parse_coverage(bad, 10052)
        altered = json.loads(json.dumps(P52))
        altered["data"]["indexContents"]["indexContent"][1]["osisID"] = "John.18.31-John.18.33"
        with self.assertRaises(ContractError):
            parse_coverage(altered, 10052)

    def test_success_and_exception_both_space_attempts(self):
        client, clock, calls = self.client([
            (200, json.dumps(P52), {"Content-Type": "application/json"}),
            TimeoutError("timeout"),
            (200, json.dumps(P52), {}),
        ])
        client.get_json("biblicalcontent/get", PARAMS)
        client.get_json("biblicalcontent/get", {**PARAMS, "pageID": "10"})
        self.assertEqual([call[0] for call in calls], [0, 5, 10])
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 3)
        self.assertEqual(self.con.execute("SELECT count(*) FROM source_response").fetchone()[0], 2)

    def test_retry_after_and_budgeted_stop(self):
        self.assertEqual(retry_after("12"), 12)
        self.assertEqual(retry_after("Thu, 01 Jan 1970 00:01:00 GMT", lambda: 30), 30)
        client, clock, calls = self.client([
            (429, "busy", {"Retry-After": "8"}),
            (200, json.dumps(P52), {}),
        ])
        client.get_json("biblicalcontent/get", PARAMS)
        self.assertEqual([call[0] for call in calls], [0, 8])
        limited, _, limited_calls = self.client([(429, "busy", {"Retry-After": "100"})], duration=10)
        with self.assertRaises(RunStopped):
            limited.get_json("biblicalcontent/get", {**PARAMS, "pageID": "20"})
        self.assertEqual(len(limited_calls), 1)

    def test_block_and_retry_limits(self):
        client, _, calls = self.client([(403, "denied", {})])
        with self.assertRaises(AccessBlocked):
            collect_stage(client, 10052, "coverage")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.con.execute("SELECT state FROM collection_job").fetchone()[0], "blocked")
        other, _, calls = self.client([(429, "busy", {}), (429, "busy", {}), (429, "busy", {})])
        with self.assertRaises(AccessBlocked):
            other.get_json("biblicalcontent/get", {**PARAMS, "pageID": "20"})
        self.assertEqual(len(calls), 3)

    def test_offline_fixture_resume_and_atomic_replacement(self):
        import_p52(self.con, FIXTURE)
        client = Client(self.con, "sample", offline=True)
        self.assertEqual(collect_stage(client, 10052, "coverage"), "success")
        self.assertEqual(client.attempts, 0)
        self.assertEqual(collect_stage(client, 10052, "coverage"), "success")
        self.assertEqual(self.con.execute("SELECT count(*) FROM coverage_index").fetchone()[0], 5)
        output = Path(self.temp.name) / "sample.json"
        export_p52(self.con, output)
        sample = json.loads(output.read_text())
        self.assertFalse(sample["corpus_complete"])
        self.assertEqual([x["osis_ref"] for x in sample["verses"]],
                         ["John.18.31", "John.18.32", "John.18.33", "John.18.37", "John.18.38"])
        bad = json.loads(json.dumps(P52))
        bad["data"]["indexContents"]["indexContent"][2]["pageID"] = None
        with self.assertRaises(ContractError):
            parse_coverage(bad, 10052)
        self.assertEqual(self.con.execute("SELECT count(*) FROM coverage_index").fetchone()[0], 5)

        # A valid empty refresh withdraws old index rows. A bad refresh retains them.
        empty = {"status": "success", "data": {"indexContents": {"docID": 10052, "indexContent": []}}}
        refreshed, _, calls = self.client([(200, json.dumps(empty), {})])
        self.assertEqual(collect_stage(refreshed, 10052, "coverage", refresh=True), "empty")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.con.execute("SELECT count(*) FROM coverage_index").fetchone()[0], 0)
        again, _, _ = self.client([(200, json.dumps(P52), {})])
        collect_stage(again, 10052, "coverage", refresh=True)
        malformed, _, _ = self.client([(200, json.dumps(bad), {})])
        with self.assertRaises(ContractError):
            collect_stage(malformed, 10052, "coverage", refresh=True)
        self.assertEqual(self.con.execute("SELECT count(*) FROM coverage_index").fetchone()[0], 5)
        self.assertEqual(self.con.execute("SELECT state FROM collection_job WHERE run_id='test'").fetchone()[0], "failed")

    def test_completed_stage_is_skipped_after_resume(self):
        import_p52(self.con, FIXTURE)
        first = Client(self.con, "resume", offline=True)
        collect_stage(first, 10052, "coverage")
        resumed, _, calls = self.client([], budget=0)
        resumed.run_id = "resume"
        self.assertEqual(collect_stage(resumed, 10052, "coverage"), "success")
        self.assertEqual(calls, [])
        with self.assertRaises(RunStopped):
            collect_stage(first, 10052, "metadata")
        self.assertEqual(self.con.execute("SELECT state FROM collection_job WHERE run_id='resume' AND stage='coverage'").fetchone()[0], "success")

    def test_fixture_cache_is_not_used_for_live_mode(self):
        import_p52(self.con, FIXTURE)
        live, _, calls = self.client([(200, json.dumps(P52), {})], run_id="live")
        live.get_json("biblicalcontent/get", PARAMS)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.con.execute("SELECT count(*) FROM source_response").fetchone()[0], 2)

    def test_html_block_and_budget_count(self):
        html, _, calls = self.client([(200, "<html>challenge</html>", {"content-type": "text/html"})])
        with self.assertRaises(AccessBlocked):
            html.get_json("biblicalcontent/get", PARAMS)
        self.assertEqual(len(calls), 1)
        limited, _, calls = self.client([(503, "unavailable", {})], budget=1, run_id="limited")
        with self.assertRaises(RunStopped):
            limited.get_json("biblicalcontent/get", {**PARAMS, "pageID": "20"})
        self.assertEqual(len(calls), 1)
        resumed, _, calls = self.client([], budget=1, run_id="limited")
        with self.assertRaises(RunStopped):
            resumed.get_json("biblicalcontent/get", {**PARAMS, "pageID": "30"})
        self.assertEqual(calls, [])

    def test_cli_offline_sample_and_zero_network_budget(self):
        output = Path(self.temp.name) / "p52.json"
        self.assertEqual(main(["--db", str(self.path), "--offline", "--fixture-p52",
                               "--run-id", "p52", "--export-p52", str(output)]), 0)
        self.assertTrue(output.exists())
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        self.assertEqual(main(["--db", str(self.path), "--offline", "--doc-id", "10052",
                               "--run-id", "missing-metadata"]), 1)


if __name__ == "__main__":
    unittest.main()
