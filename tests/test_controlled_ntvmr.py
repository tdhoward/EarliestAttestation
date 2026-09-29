import json
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from controlled_ntvmr import (
    AccessBlocked, Client, ContractError, RunStopped, collect_stage, connect,
    catalogue_params, catalogue_report, collect_catalogue_scope, collect_search,
    discovery_report, export_p52, import_language_probe, import_p52,
    import_search_fixture, main, parse_coverage, parse_search, retry_after,
    scoped_index_report,
)

FIXTURE = Path(__file__).parent / "fixtures" / "p52_coverage_probe.json"
P52 = json.loads(FIXTURE.read_text(encoding="utf-8"))["response"]
LANGUAGE_FIXTURE = Path(__file__).parent / "fixtures" / "p52_language_probe.json"
LANGUAGE = json.loads(LANGUAGE_FIXTURE.read_text(encoding="utf-8"))
NAMED = json.loads((Path(__file__).parent / "fixtures" / "john_named_probe.json").read_text(encoding="utf-8"))
LIST = json.loads((Path(__file__).parent / "fixtures" / "john_list_probe.json").read_text(encoding="utf-8"))
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

    def test_transport_failure_is_visible_when_budget_stops_retry(self):
        client, _, _ = self.client([TimeoutError("connection timed out")], budget=1)
        with self.assertRaisesRegex(RunStopped, "connection timed out"):
            client.get_json("metadata/liste/search", {"docID": "10052"})
        self.assertIn("connection timed out", self.con.execute(
            "SELECT failure FROM request_attempt").fetchone()[0])

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

    def test_named_discovery_reproduces_language_exclusion(self):
        import_language_probe(self.con, LANGUAGE_FIXTURE)
        import_p52(self.con, FIXTURE)
        client = Client(self.con, "language", offline=True)
        collect_stage(client, 10052, "coverage")
        self.assertEqual(collect_search(client, "John.18.31", "P52", lang="gr"), "empty")
        self.assertEqual(collect_search(client, "John.18.31", "P52", lang="grc"), "success")
        self.assertEqual(collect_search(client, "John.18.31", "P52"), "success")
        self.assertEqual(client.attempts, 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM discovery_candidate").fetchone()[0], 2)
        self.assertEqual(self.con.execute("SELECT DISTINCT source_lang FROM discovery_candidate").fetchone()[0], "g")
        report = discovery_report(self.con, "language")
        self.assertFalse(report["discovery_complete"])
        self.assertEqual(report["indexed_coverage_search_omissions"],
                         [{"osis_ref": "John.18.31", "query_ga_num": "P52",
                           "lang_filter": "gr", "doc_id": 10052}])
        self.assertEqual(collect_search(client, "John.18.31", "P52", lang="grc"), "success")
        self.assertEqual(self.con.execute("SELECT count(*) FROM discovery_candidate").fetchone()[0], 2)

    def test_search_contract_and_incomplete_result(self):
        singleton = LANGUAGE["cases"][1]["response"]
        empty = LANGUAGE["cases"][0]["response"]
        self.assertEqual(len(parse_search(singleton)[0]), 1)
        self.assertEqual(parse_search(empty), ([], 0))
        numeric_name = json.loads(json.dumps(singleton))
        numeric_name["data"]["manuscripts"]["manuscript"]["gaNum"] = 1
        numeric_name["data"]["manuscripts"]["manuscript"]["primaryName"] = 1
        self.assertEqual(len(parse_search(numeric_name)[0]), 1)
        for payload in [
            {"status": "error", "data": empty["data"]},
            {"status": "success", "data": {"manuscripts": {"count": 1, "pagecount": 1}}},
            {"status": "success", "data": {"manuscripts": {"count": 0, "pagecount": 0,
                                                             "manuscript": [None]}}},
        ]:
            with self.assertRaises(ContractError):
                parse_search(payload)
        truncated = json.loads(json.dumps(singleton))
        truncated["data"]["manuscripts"]["count"] = 2
        client, _, calls = self.client([(200, json.dumps(truncated), {})])
        self.assertEqual(collect_search(client, "John.18.31", "P52"), "incomplete")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.con.execute("SELECT count(*) FROM discovery_candidate").fetchone()[0], 1)
        self.assertEqual(discovery_report(self.con, "test")["jobs"][0]["state"], "incomplete")

    def test_captured_named_john_searches(self):
        expected = {"01": (20001, 1), "02": (20002, 2),
                    "P66": (10066, "P66"), "P75": (10075, "P75")}
        for case in NAMED["cases"]:
            name = case["params"]["gaNum"]
            self.assertEqual(hashlib.sha256(case["raw_body"].encode()).hexdigest(),
                             case["body_sha256"])
            rows, count = parse_search(json.loads(case["raw_body"]))
            self.assertEqual(count, 1)
            self.assertEqual((rows[0]["docID"], rows[0]["gaNum"]), expected[name])
            self.assertEqual(rows[0]["lang"], "g")

    def test_captured_document_set_search_is_a_list(self):
        self.assertEqual(hashlib.sha256(LIST["raw_body"].encode()).hexdigest(),
                         LIST["body_sha256"])
        payload = json.loads(LIST["raw_body"])
        self.assertIsInstance(payload["data"]["manuscripts"]["manuscript"], list)
        rows, count = parse_search(payload)
        self.assertEqual(count, 2)
        self.assertEqual([row["docID"] for row in rows], [10066, 10075])

    def test_search_failed_refresh_retains_previous_candidates(self):
        good = LANGUAGE["cases"][1]["response"]
        client, _, _ = self.client([(200, json.dumps(good), {})])
        collect_search(client, "John.18.31", "P52", lang="grc")
        bad, _, _ = self.client([(200, '{"status":"success","data":{}}', {})])
        with self.assertRaises(ContractError):
            collect_search(bad, "John.18.31", "P52", lang="grc", refresh=True)
        self.assertEqual(self.con.execute("SELECT count(*) FROM discovery_candidate").fetchone()[0], 1)
        self.assertEqual(discovery_report(self.con, "test")["jobs"][0]["state"], "failed")

    def test_cli_offline_named_search_uses_fixture_without_requests(self):
        self.assertEqual(main(["--db", str(self.path), "--offline", "--fixture-language-probe",
                               "--run-id", "named", "--search-ref", "John.18.31",
                               "--search-ga-num", "P52"]), 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        self.assertEqual(discovery_report(self.con, "named")["candidates"][0]["source_lang"], "g")

    def test_offline_bounded_catalogue_scope_and_resume(self):
        import_search_fixture(self.con, Path(__file__).parent / "fixtures" / "john_list_probe.json")
        client = Client(self.con, "batch", offline=True)
        self.assertEqual(collect_catalogue_scope(client, [10075, 10066],
                         index_ref="John.1.1", page_limit=10), "success")
        report = catalogue_report(self.con, "batch")
        self.assertEqual(report["requested_doc_ids"], [10066, 10075])
        self.assertEqual([row["doc_id"] for row in report["candidates"]], [10066, 10075])
        self.assertFalse(report["catalogue_lookup_complete"])
        self.assertEqual(client.attempts, 0)
        self.assertEqual(collect_catalogue_scope(client, [10066, 10075],
                         index_ref="John.1.1", page_limit=10), "success")
        self.assertEqual(self.con.execute("SELECT count(*) FROM catalogue_candidate").fetchone()[0], 2)
        with self.assertRaises(ValueError):
            collect_catalogue_scope(client, [10066], index_ref="John.1.1", page_limit=10)

    def test_catalogue_scope_requires_all_ids_without_passage_filter(self):
        payload = json.loads(LIST["raw_body"])
        client, _, _ = self.client([(200, json.dumps(payload), {})])
        self.assertEqual(collect_catalogue_scope(client, [10066, 10075], page_limit=10), "success")
        self.assertTrue(catalogue_report(self.con, "test")["catalogue_lookup_complete"])
        self.assertEqual(catalogue_params([10075, 10066], page_limit=10)[1]["docID"], "10066|10075")
        with self.assertRaises(ValueError):
            catalogue_params(list(range(1, 22)))
        with self.assertRaises(ValueError):
            catalogue_params([10052], page_limit=201)

    def test_catalogue_incomplete_and_failed_refresh_keep_distinct_states(self):
        payload = json.loads(LIST["raw_body"])
        one = json.loads(json.dumps(payload))
        one["data"]["manuscripts"]["manuscript"].pop()
        client, _, _ = self.client([(200, json.dumps(one), {})])
        self.assertEqual(collect_catalogue_scope(client, [10066, 10075], page_limit=10), "incomplete")
        report = catalogue_report(self.con, "test")
        self.assertEqual(report["not_returned_doc_ids"], [10075])
        self.assertEqual(report["returned_count"], 1)
        self.assertFalse(report["catalogue_lookup_complete"])
        good, _, _ = self.client([(200, json.dumps(payload), {})])
        self.assertEqual(collect_catalogue_scope(good, [10066, 10075],
                         page_limit=10, refresh=True), "success")
        malformed, _, _ = self.client([(200, '{"status":"success","data":{}}', {})])
        with self.assertRaises(ContractError):
            collect_catalogue_scope(malformed, [10066, 10075], page_limit=10, refresh=True)
        report = catalogue_report(self.con, "test")
        self.assertEqual(report["state"], "failed")
        self.assertEqual(len(report["candidates"]), 2)
        self.assertFalse(report["catalogue_lookup_complete"])

    def test_cli_offline_catalogue_fixture(self):
        self.assertEqual(main(["--db", str(self.path), "--offline", "--fixture-john-list",
                               "--run-id", "fixture-batch", "--catalogue-doc-id", "10066",
                               "--catalogue-doc-id", "10075", "--catalogue-index-ref", "John.1.1",
                               "--catalogue-limit", "10"]), 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        self.assertEqual(catalogue_report(self.con, "fixture-batch")["state"], "success")

    def test_filtered_scope_stops_before_document_collection(self):
        result = main(["--db", str(self.path), "--offline", "--fixture-john-list",
                       "--run-id", "filtered", "--catalogue-doc-id", "10066",
                       "--catalogue-doc-id", "10075", "--catalogue-index-ref", "John.1.1",
                       "--catalogue-limit", "10", "--scope-check-ref", "John.1.1",
                       "--doc-id", "10066"])
        self.assertEqual(result, 1)
        self.assertEqual(self.con.execute("SELECT count(*) FROM collection_job").fetchone()[0], 0)

    def test_scoped_index_inversion_flags_search_omission_and_stale_refresh(self):
        p52_search = LANGUAGE["cases"][1]["response"]
        catalogue, _, _ = self.client([(200, json.dumps(p52_search), {})], run_id="scope")
        collect_catalogue_scope(catalogue, [10052], page_limit=10)
        import_p52(self.con, FIXTURE)
        import_language_probe(self.con, LANGUAGE_FIXTURE)
        offline = Client(self.con, "scope", offline=True)
        collect_stage(offline, 10052, "coverage")
        collect_search(offline, "John.18.31", "P52", lang="gr")
        collect_search(offline, "John.18.31", "P52", lang="grc")
        report = scoped_index_report(self.con, "scope", ["John.18.31", "John.18.34"])
        self.assertEqual(report["state"], "incomplete")
        self.assertEqual(report["unready_doc_ids"], [])
        self.assertEqual(report["candidates"]["John.18.31"],
                         [{"doc_id": 10052, "page_ids": [10]}])
        self.assertEqual(report["candidates"]["John.18.34"], [])
        self.assertEqual(report["named_search_omissions"],
                         [{"osis_ref": "John.18.31", "query_ga_num": "P52",
                           "lang_filter": "gr", "doc_id": 10052}])
        empty = {"status": "success", "data": {"indexContents": {"docID": 10052,
                 "indexContent": []}}}
        later, _, _ = self.client([(200, json.dumps(empty), {})], run_id="later")
        collect_stage(later, 10052, "coverage", refresh=True)
        stale = scoped_index_report(self.con, "scope", ["John.18.31"])
        self.assertEqual(stale["state"], "incomplete")
        self.assertEqual(stale["unready_doc_ids"], [10052])


if __name__ == "__main__":
    unittest.main()
