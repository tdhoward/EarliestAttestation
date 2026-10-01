import json
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest

from audit_reviewed import (audit_database as audit_reviewed_database, load_benchmark,
                            load_date_source, load_source_controls)

from controlled_ntvmr import (
    AccessBlocked, Client, ContractError, RunStopped, collect_stage, connect,
    catalogue_params, catalogue_report, collect_catalogue_scope, collect_search,
    discovery_report, export_p52, import_language_probe, import_p52,
    import_search_fixture, main, parse_coverage, parse_metadata, parse_search, retry_after,
    record_candidate_review, scoped_index_report,
    record_witness_assignment, witness_identity_report,
    edition_inventory_report, import_edition_inventory,
    coverage_review_report, record_coverage_review,
    apply_dating_action, assign_coverage_unit, create_writing_unit,
    record_date_assessment, select_date_assessment, writing_unit_report,
    compute_ranking, rank_candidates, ranking_report, dating_alternatives_report,
)

FIXTURE = Path(__file__).parent / "fixtures" / "p52_coverage_probe.json"
P52 = json.loads(FIXTURE.read_text(encoding="utf-8"))["response"]
LANGUAGE_FIXTURE = Path(__file__).parent / "fixtures" / "p52_language_probe.json"
LANGUAGE = json.loads(LANGUAGE_FIXTURE.read_text(encoding="utf-8"))
NAMED = json.loads((Path(__file__).parent / "fixtures" / "john_named_probe.json").read_text(encoding="utf-8"))
LIST = json.loads((Path(__file__).parent / "fixtures" / "john_list_probe.json").read_text(encoding="utf-8"))
P134_METADATA = json.loads((Path(__file__).parent / "fixtures" / "p134_metadata_cache.json").read_text(encoding="utf-8"))
P52_CONTROLS = Path(__file__).parent.parent / "benchmarks" / "p52-source-controls-v1.json"
P52_DATE_SOURCE = Path(__file__).parent.parent / "benchmarks" / "p52-date-source-v1.json"
PARAMS = {"docID": "10052", "detail": "long", "format": "json"}
METADATA = {"status": "success", "data": {"manuscript": {
    "docID": 10052, "gaNum": "P52", "primaryName": "P52", "lang": "grc",
    "originYear": {"early": 125, "late": 175, "content": "II (M)"}}}}


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

    def test_metadata_contract_and_date_status(self):
        self.assertEqual(hashlib.sha256(P134_METADATA["raw_body"].encode()).hexdigest(),
                         P134_METADATA["body_sha256"])
        captured = parse_metadata(json.loads(P134_METADATA["raw_body"]), 10134)
        self.assertEqual((captured["ga_num"], captured["source_lang"], captured["date_status"]),
                         ("P134", "grc", "valid"))
        parsed = parse_metadata(METADATA, 10052)
        self.assertEqual((parsed["source_lang"], parsed["origin_notation"],
                          parsed["date_status"], parsed["date_min"], parsed["date_max"]),
                         ("grc", "II (M)", "valid", 125, 175))
        numeric = json.loads(json.dumps(METADATA))
        numeric["data"]["manuscript"]["gaNum"] = 1
        self.assertEqual(parse_metadata(numeric, 10052)["ga_num"], "1")
        unknown = json.loads(json.dumps(METADATA))
        unknown["data"]["manuscript"]["originYear"] = {"early": 0, "late": 0}
        self.assertEqual(parse_metadata(unknown, 10052)["date_status"], "unknown")
        invalid = json.loads(json.dumps(METADATA))
        invalid["data"]["manuscript"]["originYear"] = {"early": 200, "late": 100,
                                                            "content": "disputed"}
        self.assertEqual(parse_metadata(invalid, 10052)["date_status"], "invalid")
        self.assertIsNone(parse_metadata(invalid, 10052)["date_min"])
        for bad in [
            {"status": "success", "data": {}},
            {"status": "error", "data": METADATA["data"]},
            {"status": "success", "data": {"manuscript": {"docID": 10053,
                "gaNum": "P52", "lang": "grc"}}},
            {"status": "success", "data": {"manuscript": {"docID": 10052,
                "gaNum": "P52"}}},
        ]:
            with self.assertRaises(ContractError):
                parse_metadata(bad, 10052)

    def test_metadata_snapshot_refresh_failure_and_offline_replay(self):
        first, _, _ = self.client([(200, json.dumps(METADATA), {})], run_id="metadata")
        self.assertEqual(collect_stage(first, 10052, "metadata"), "success")
        initial = self.con.execute("SELECT response_id,date_status,date_min,date_max,source_lang "
                                   "FROM document_metadata WHERE doc_id=10052").fetchone()
        self.assertEqual(initial[1:], ("valid", 125, 175, "grc"))
        self.con.execute("DELETE FROM document_metadata WHERE doc_id=10052")
        self.con.commit()
        offline = Client(self.con, "metadata", offline=True)
        self.assertEqual(collect_stage(offline, 10052, "metadata"), "success")
        self.assertEqual(offline.attempts, 1)
        self.assertEqual(self.con.execute("SELECT date_status FROM document_metadata").fetchone()[0], "valid")
        malformed, _, _ = self.client([(200, '{"status":"success","data":{}}', {})], run_id="metadata")
        with self.assertRaises(ContractError):
            collect_stage(malformed, 10052, "metadata", refresh=True)
        self.assertEqual(self.con.execute("SELECT response_id,date_status FROM document_metadata").fetchone(),
                         initial[:2])
        self.assertEqual(self.con.execute("SELECT state FROM collection_job WHERE run_id='metadata'").fetchone()[0],
                         "failed")

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

    def test_document_review_survives_refresh_and_keeps_history(self):
        printed = {"status": "success", "data": {"manuscripts": {
            "count": 1, "pagecount": 1,
            "manuscript": {"docID": 90000, "gaNum": "NA27",
                           "primaryName": "NA27", "lang": "grc"}}}}
        changed = json.loads(json.dumps(printed))
        changed["data"]["manuscripts"]["manuscript"]["lang"] = "g"
        empty = {"status": "success", "data": {"manuscripts": {
            "count": 0, "pagecount": 0}}}
        client, _, _ = self.client([(200, json.dumps(printed), {}),
                                    (200, json.dumps(changed), {}),
                                    (200, json.dumps(empty), {})])
        self.assertEqual(collect_catalogue_scope(client, [90000], page_limit=10), "success")
        response_id = catalogue_report(self.con, "test")["candidates"][0]["response_id"]
        with self.assertRaises(ValueError):
            record_candidate_review(self.con, 90001, response_id, "exclude",
                                    "printed_edition", "Printed edition", "test source", "reviewer")
        with self.assertRaises(ValueError):
            record_candidate_review(self.con, 90000, response_id, "retain",
                                    "printed_edition", "Wrong pairing", "test source", "reviewer")
        first_id = record_candidate_review(self.con, 90000, response_id, "exclude",
                                           "printed_edition", "Named printed edition",
                                           "catalogue response", "test reviewer")
        self.assertEqual(collect_catalogue_scope(client, [90000], page_limit=10,
                                                refresh=True), "success")
        reviewed = catalogue_report(self.con, "test")["candidates"][0]
        self.assertEqual((reviewed["review_decision"], reviewed["source_type"],
                          reviewed["review_source_response_id"]),
                         ("exclude", "printed_edition", response_id))
        self.assertEqual(reviewed["review_reason"], "Named printed edition")
        self.assertTrue(reviewed["review_source_changed"])
        second_id = record_candidate_review(self.con, 90000, reviewed["response_id"],
                                            "uncertain", "uncertain", "Needs recheck",
                                            "new catalogue response", "test reviewer")
        self.assertGreater(second_id, first_id)
        self.assertEqual(self.con.execute("SELECT count(*) FROM candidate_review").fetchone()[0], 2)
        self.assertEqual(catalogue_report(self.con, "test")["candidates"][0]["review_decision"],
                         "uncertain")
        self.assertFalse(catalogue_report(self.con, "test")["candidates"][0]["review_source_changed"])
        self.assertEqual(collect_catalogue_scope(client, [90000], page_limit=10,
                                                refresh=True), "incomplete")
        self.assertEqual(catalogue_report(self.con, "test")["candidates"], [])
        self.assertEqual(self.con.execute("SELECT count(*) FROM candidate_review").fetchone()[0], 2)
        reopened = connect(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.execute("PRAGMA user_version").fetchone()[0], 12)
        self.assertEqual(reopened.execute("SELECT count(*) FROM candidate_review").fetchone()[0], 2)

    def test_cli_review_is_offline_and_visible_in_named_report(self):
        self.assertEqual(main(["--db", str(self.path), "--offline", "--fixture-language-probe",
                               "--run-id", "named", "--search-ref", "John.18.31",
                               "--search-ga-num", "P52"]), 0)
        response_id = discovery_report(self.con, "named")["candidates"][0]["response_id"]
        self.assertEqual(main(["--db", str(self.path), "--review-doc-id", "10052",
                               "--review-response-id", str(response_id),
                               "--review-decision", "uncertain", "--review-source-type", "uncertain",
                               "--review-reason", "Source category needs review",
                               "--review-citation", "captured P52 search response",
                               "--reviewer", "fixture test"]), 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        self.assertEqual(discovery_report(self.con, "named")["candidates"][0]["review_decision"],
                         "uncertain")

    def test_identity_links_join_documents_and_keep_corrections(self):
        payload = {"status": "success", "data": {"manuscripts": {
            "count": 2, "pagecount": 1, "manuscript": [
                {"docID": 90001, "gaNum": "A", "lang": "g"},
                {"docID": 90002, "gaNum": "B", "lang": "g"}]}}}
        client, _, _ = self.client([(200, json.dumps(payload), {})], run_id="identity")
        collect_catalogue_scope(client, [90001, 90002], page_limit=10)
        candidates = catalogue_report(self.con, "identity")["candidates"]
        response_id = candidates[0]["response_id"]
        for doc_id in (90001, 90002):
            record_candidate_review(self.con, doc_id, response_id, "retain",
                                    "greek_manuscript", "Catalogue candidate",
                                    "captured list response", "fixture reviewer")
            record_witness_assignment(self.con, doc_id, response_id, "physical-1",
                                      "One physical object", "Joined pieces reviewed",
                                      "identity source", "fixture reviewer")
        report = witness_identity_report(self.con)
        self.assertEqual([row["witness_id"] for row in report["assignments"]],
                         ["physical-1", "physical-1"])
        self.assertEqual(report["witnesses"][0]["current_doc_ids"], [90001, 90002])
        self.assertEqual([row["witness_id"] for row in catalogue_report(self.con, "identity")["candidates"]],
                         ["physical-1", "physical-1"])
        self.assertEqual(self.con.execute("SELECT count(*) FROM physical_witness").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            record_witness_assignment(self.con, 90001, response_id, "physical-1",
                                      "Conflicting label", "reason", "source", "reviewer")
        record_witness_assignment(self.con, 90002, response_id, None, None,
                                  "The join was mistaken", "corrected source", "fixture reviewer")
        self.assertIsNone(witness_identity_report(self.con)["assignments"][1]["witness_id"])
        self.assertEqual(witness_identity_report(self.con)["witnesses"][0]["current_doc_ids"], [90001])
        self.assertEqual(self.con.execute("SELECT count(*) FROM witness_assignment").fetchone()[0], 3)
        record_candidate_review(self.con, 90001, response_id, "exclude", "other",
                                "Reclassified", "corrected source", "fixture reviewer")
        self.assertTrue(witness_identity_report(self.con)["assignments"][0]["identity_review_needed"])
        record_witness_assignment(self.con, 90001, response_id, None, None,
                                  "Excluded document", "corrected source", "fixture reviewer")
        self.assertIsNone(witness_identity_report(self.con)["assignments"][0]["witness_id"])
        self.assertEqual(client.attempts, 1)

    def test_identity_requires_current_retained_source_and_cli_is_offline(self):
        import_language_probe(self.con, LANGUAGE_FIXTURE)
        client = Client(self.con, "named", offline=True)
        collect_search(client, "John.18.31", "P52")
        response_id = discovery_report(self.con, "named")["candidates"][0]["response_id"]
        with self.assertRaises(ValueError):
            record_witness_assignment(self.con, 10052, response_id, "p52", "P52",
                                      "reason", "source", "reviewer")
        record_candidate_review(self.con, 10052, response_id, "retain",
                                "greek_manuscript", "Candidate", "captured search", "fixture reviewer")
        self.assertEqual(main(["--db", str(self.path), "--identity-doc-id", "10052",
                               "--identity-response-id", str(response_id),
                               "--witness-id", "p52", "--witness-label", "P52",
                               "--identity-reason", "Physical witness review",
                               "--identity-citation", "identity source",
                               "--identity-reviewer", "fixture reviewer"]), 0)
        self.assertEqual(discovery_report(self.con, "named")["candidates"][0]["witness_id"], "p52")
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)

    def test_identity_flags_changed_source_and_v6_database_upgrades(self):
        original = {"status": "success", "data": {"manuscripts": {
            "count": 1, "pagecount": 1,
            "manuscript": {"docID": 90001, "gaNum": "A", "lang": "g"}}}}
        changed = json.loads(json.dumps(original))
        changed["data"]["manuscripts"]["manuscript"]["lang"] = "grc"
        client, _, _ = self.client([(200, json.dumps(original), {}),
                                    (200, json.dumps(changed), {})], run_id="identity")
        collect_catalogue_scope(client, [90001], page_limit=10)
        response_id = catalogue_report(self.con, "identity")["candidates"][0]["response_id"]
        record_candidate_review(self.con, 90001, response_id, "retain",
                                "greek_manuscript", "Candidate", "first response", "reviewer")
        record_witness_assignment(self.con, 90001, response_id, "physical-1", "Object",
                                  "Identity reviewed", "identity source", "reviewer")
        collect_catalogue_scope(client, [90001], page_limit=10, refresh=True)
        self.assertTrue(witness_identity_report(self.con)["assignments"][0]["identity_review_needed"])
        with self.assertRaises(ValueError):
            record_witness_assignment(self.con, 90001, response_id, "physical-1", None,
                                      "Old source", "identity source", "reviewer")
        new_response_id = catalogue_report(self.con, "identity")["candidates"][0]["response_id"]
        record_candidate_review(self.con, 90001, new_response_id, "retain",
                                "greek_manuscript", "Rechecked", "second response", "reviewer")
        self.assertTrue(witness_identity_report(self.con)["assignments"][0]["identity_review_needed"])
        record_witness_assignment(self.con, 90001, new_response_id, "physical-1", None,
                                  "Identity rechecked", "second identity source", "reviewer")
        self.assertFalse(witness_identity_report(self.con)["assignments"][0]["identity_review_needed"])

        self.con.execute("DROP TABLE witness_assignment")
        self.con.execute("DROP TABLE physical_witness")
        self.con.execute("PRAGMA user_version=6")
        self.con.commit()
        upgraded = connect(self.path)
        self.addCleanup(upgraded.close)
        self.assertEqual(upgraded.execute("PRAGMA user_version").fetchone()[0], 12)
        self.assertEqual(upgraded.execute("SELECT count(*) FROM candidate_review").fetchone()[0], 2)
        self.assertEqual(upgraded.execute("SELECT count(*) FROM witness_assignment").fetchone()[0], 0)

    def test_cited_inventory_import_and_subset_before_limit(self):
        manifest = {"format_version": 1, "inventory_id": "synthetic-1",
                    "edition": "TEST", "scope": "synthetic selected coordinates",
                    "source_citation": "Synthetic test inventory", "reuse_terms": "Test data",
                    "mapping_citation": "Synthetic mapping review", "reviewer": "fixture reviewer",
                    "verses": [
                        {"osis_ref": "Matt.1.1", "editorial_status": "main",
                         "ntvmr_refs": ["Matt.1.1"]},
                        {"osis_ref": "John.18.2", "editorial_status": "main",
                         "ntvmr_refs": ["John.18.2"]},
                        {"osis_ref": "John.18.10", "editorial_status": "bracketed",
                         "editorial_note": "Synthetic bracket example",
                         "ntvmr_refs": ["John.18.10", "John.18.11"],
                         "mapping_note": "Synthetic boundary difference"},
                        {"osis_ref": "Rev.1.1", "editorial_status": "omitted",
                         "editorial_note": "Synthetic omission example",
                         "ntvmr_refs": [], "mapping_note": "No mapping reviewed"}]}
        self.assertEqual(import_edition_inventory(self.con, manifest), 4)
        self.assertEqual(import_edition_inventory(self.con, manifest), 4)
        report = edition_inventory_report(self.con, "synthetic-1", books=["John"], limit=1)
        self.assertEqual([row["osis_ref"] for row in report["verses"]], ["John.18.2"])
        self.assertFalse(report["whole_nt_complete"])
        self.assertEqual(edition_inventory_report(self.con, "synthetic-1")["verses"][2]["ntvmr_refs"],
                         ["John.18.10", "John.18.11"])
        self.assertEqual(edition_inventory_report(self.con, "synthetic-1")["verses"][-1]["ntvmr_refs"], [])
        self.assertEqual(self.con.execute("SELECT count(*) FROM edition_verse").fetchone()[0], 4)
        changed = json.loads(json.dumps(manifest))
        changed["verses"][0]["editorial_status"] = "uncertain"
        changed["verses"][0]["editorial_note"] = "Correction"
        with self.assertRaises(ValueError):
            import_edition_inventory(self.con, changed)
        changed["inventory_id"] = "synthetic-2"
        changed["edition"] = "OTHER"
        import_edition_inventory(self.con, changed)
        self.assertEqual(edition_inventory_report(self.con, "synthetic-1")["edition"], "TEST")
        self.assertEqual(self.con.execute("SELECT count(*) FROM edition_verse").fetchone()[0], 8)

    def test_inventory_rejects_ranges_unordered_and_unsourced_mapping(self):
        base = {"format_version": 1, "inventory_id": "bad", "edition": "TEST",
                "scope": "synthetic", "source_citation": "fixture",
                "reuse_terms": "test", "mapping_citation": "fixture mapping", "reviewer": "tester",
                "verses": [{"osis_ref": "John.18.2", "editorial_status": "main",
                            "ntvmr_refs": ["John.18.2"]}]}
        changes = []
        for ref in ("John.18.2-John.18.3", "John.18.2a", "Unknown.1.1"):
            case = json.loads(json.dumps(base))
            case["verses"][0]["osis_ref"] = ref
            changes.append(case)
        case = json.loads(json.dumps(base))
        case["verses"].append({"osis_ref": "John.18.1", "editorial_status": "main",
                               "ntvmr_refs": ["John.18.1"]})
        changes.append(case)
        case = json.loads(json.dumps(base))
        case["mapping_citation"] = None
        changes.append(case)
        case = json.loads(json.dumps(base))
        case["verses"][0]["ntvmr_refs"] = []
        changes.append(case)
        for case in changes:
            with self.assertRaises(ValueError):
                import_edition_inventory(self.con, case)
        self.assertEqual(self.con.execute("SELECT count(*) FROM edition_inventory").fetchone()[0], 0)

    def test_inventory_cli_import_and_report_have_no_network(self):
        manifest = {"format_version": 1, "inventory_id": "cli-sample", "edition": "TEST",
                    "scope": "synthetic", "source_citation": "fixture", "reuse_terms": "test",
                    "mapping_citation": None, "reviewer": "tester",
                    "verses": [{"osis_ref": "John.18.31", "editorial_status": "uncertain",
                                "editorial_note": "Synthetic example", "ntvmr_refs": [],
                                "mapping_note": "Unresolved"}]}
        source = Path(self.temp.name) / "inventory.json"
        source.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(main(["--db", str(self.path), "--import-inventory", str(source),
                               "--dry-run"]), 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM edition_inventory").fetchone()[0], 0)
        self.assertEqual(main(["--db", str(self.path), "--import-inventory", str(source)]), 0)
        self.assertEqual(main(["--db", str(self.path), "--inventory-report", "cli-sample",
                               "--inventory-book", "John", "--inventory-limit", "1"]), 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)

    def test_reviewed_coverage_requires_mapping_identity_and_current_index(self):
        manifest = {"format_version": 1, "inventory_id": "evidence-test",
                    "edition": "TEST", "scope": "synthetic", "source_citation": "fixture",
                    "reuse_terms": "test", "mapping_citation": "synthetic mapping",
                    "reviewer": "tester", "verses": [{
                        "osis_ref": "John.18.31", "editorial_status": "main",
                        "ntvmr_refs": ["John.18.31", "John.18.32"],
                        "mapping_note": "Synthetic merged boundary"}]}
        import_edition_inventory(self.con, manifest)
        import_language_probe(self.con, LANGUAGE_FIXTURE)
        collect_search(Client(self.con, "evidence", offline=True), "John.18.31", "P52")
        source_id = discovery_report(self.con, "evidence")["candidates"][0]["response_id"]
        record_candidate_review(self.con, 10052, source_id, "retain", "greek_manuscript",
                                "fixture classification", "search fixture", "tester")
        index_source = import_p52(self.con, FIXTURE)
        collect_stage(Client(self.con, "evidence", offline=True), 10052, "coverage")
        def review(mapped_ref, status="partial"):
            return record_coverage_review(
                self.con, "evidence-test", "John.18.31", mapped_ref, 10052, 10,
                index_source, status, "reviewed_transcription", "synthetic decision",
                "fixture citation", "tester")
        with self.assertRaises(ValueError):
            review("John.18.31")
        record_witness_assignment(self.con, 10052, source_id, "p52", "P52",
                                  "physical identity", "identity citation", "tester")
        with self.assertRaises(ValueError):
            review("John.18.34")
        review("John.18.31")
        self.assertEqual(main(["--db", str(self.path),
            "--coverage-review-inventory", "evidence-test",
            "--coverage-review-ref", "John.18.31",
            "--coverage-review-ntvmr-ref", "John.18.32",
            "--coverage-review-doc-id", "10052", "--coverage-review-page-id", "10",
            "--coverage-review-response-id", str(index_source),
            "--coverage-review-status", "partial",
            "--coverage-review-evidence-type", "reviewed_transcription",
            "--coverage-review-reason", "synthetic decision",
            "--coverage-review-citation", "fixture citation",
            "--coverage-review-reviewer", "tester"]), 0)
        report = coverage_review_report(self.con, "evidence-test")
        self.assertEqual(len(report["reviews"]), 2)
        self.assertEqual(report["verified_witnesses"], {"John.18.31": ["p52"]})
        self.assertFalse(report["whole_nt_complete"])
        self.assertEqual(main(["--db", str(self.path), "--coverage-report", "evidence-test",
                               "--coverage-report-ref", "John.18.31"]), 0)
        create_writing_unit(self.con, "p52-original", "p52", "Original hand",
                            "original", "hand review", "hand citation", "tester")
        create_writing_unit(self.con, "p52-correction", "p52", "Later correction",
                            "correction", "hand review", "hand citation", "tester")
        first_review_id = next(row["review_id"] for row in report["reviews"]
                               if row["ntvmr_ref"] == "John.18.31")
        self.con.execute("""INSERT INTO physical_witness(witness_id,label,created_at)
            VALUES('other','Other witness','2026-09-29T00:00:00+00:00')""")
        self.con.commit()
        create_writing_unit(self.con, "other-original", "other", "Other hand",
                            "original", "separate object", "identity source", "tester")
        with self.assertRaises(ValueError):
            assign_coverage_unit(self.con, first_review_id, "other-original",
                                 "wrong witness", "source", "tester")
        assign_coverage_unit(self.con, first_review_id, "p52-original",
                             "hand identified", "hand citation", "tester")
        self.assertEqual(writing_unit_report(self.con, "p52")["units"][1]
                         ["coverage_links"][0]["coverage_review_id"], first_review_id)
        self.assertTrue(writing_unit_report(self.con, "p52")["units"][1]
                        ["coverage_links"][0]["current_positive"])
        review("John.18.31", "rejected")
        self.assertFalse(writing_unit_report(self.con, "p52")["units"][1]
                         ["coverage_links"][0]["current_positive"])
        assign_coverage_unit(self.con, first_review_id, None,
                             "link corrected", "hand citation", "tester")
        self.assertFalse(writing_unit_report(self.con, "p52")["units"][1]
                         ["coverage_links"][0]["current_assignment"])
        self.assertEqual(coverage_review_report(self.con, "evidence-test")
                         ["verified_witnesses"], {"John.18.31": ["p52"]})
        changed = json.loads(json.dumps(P52))
        entries = changed["data"]["indexContents"]["indexContent"]
        changed["data"]["indexContents"]["indexContent"] = [
            row for row in entries if not isinstance(row, dict) or
            row["osisID"] != "John.18.32"]
        client, _, _ = self.client([(200, json.dumps(changed), {})], run_id="evidence")
        collect_stage(client, 10052, "coverage", refresh=True)
        stale = coverage_review_report(self.con, "evidence-test")
        self.assertTrue(all(row["review_needed"] for row in stale["reviews"]))
        self.assertEqual(stale["verified_witnesses"], {})
        review("John.18.32", "withdrawn")
        self.assertEqual(coverage_review_report(self.con, "evidence-test")
                         ["reviews"][1]["status"], "withdrawn")
        self.assertEqual(self.con.execute("SELECT count(*) FROM coverage_review").fetchone()[0], 4)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 1)

    def test_writing_unit_dates_keep_competing_intervals_and_explicit_selection(self):
        self.con.execute("""INSERT INTO physical_witness(witness_id,label,created_at)
            VALUES('object-1','Synthetic witness','2026-09-29T00:00:00+00:00')""")
        self.con.commit()
        create_writing_unit(self.con, "original", "object-1", "Original hand",
                            "original", "separate hand", "hand source", "tester")
        create_writing_unit(self.con, "addition", "object-1", "Later addition",
                            "supplement", "separate hand", "hand source", "tester")
        early = record_date_assessment(self.con, "original", "valid", 100, 300,
                                       "II-III CE", "scholar A", "2026-09-29", "tester")
        late = record_date_assessment(self.con, "original", "valid", 150, 200,
                                      "II CE", "scholar B", "2026-09-29", "tester")
        unknown = record_date_assessment(self.con, "addition", "unknown", None, None,
                                         "Undated addition", "scholar C", "2026-09-29", "tester")
        with self.assertRaises(ValueError):
            record_date_assessment(self.con, "addition", "valid", 300, 200,
                                   "bad interval", "source", "2026-09-29", "tester")
        with self.assertRaises(ValueError):
            record_date_assessment(self.con, "addition", "unknown", 100, 200,
                                   "unknown", "source", "2026-09-29", "tester")
        with self.assertRaises(ValueError):
            select_date_assessment(self.con, "addition", early, "policy-v1",
                                   "wrong unit", "tester")
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("""INSERT INTO date_selection(unit_id,policy_id,
                assessment_id,reason,reviewer,selected_at)
                VALUES(?,?,?,?,?,?)""",
                ("addition", "policy-v1", early, "wrong unit", "tester",
                 "2026-09-29T00:00:00+00:00"))
        with self.assertRaises(ValueError):
            apply_dating_action(self.con, {"action": "select_date", "unit_id": "original",
                                           "assessment_id": early, "reason": "incomplete"})
        first_selection = select_date_assessment(self.con, "original", early,
                                                 "policy-v1", "first choice", "tester")
        select_date_assessment(self.con, "original", late, "policy-v1",
                               "reassessment", "tester")
        select_date_assessment(self.con, "original", early, "policy-v2",
                               "alternate policy", "tester")
        select_date_assessment(self.con, "addition", unknown, "policy-v1",
                               "unknown retained", "tester")
        report = writing_unit_report(self.con, "object-1")
        original = next(unit for unit in report["units"] if unit["unit_id"] == "original")
        addition = next(unit for unit in report["units"] if unit["unit_id"] == "addition")
        self.assertEqual(original["selected_by_policy"]["policy-v1"]["assessment"]["date_min"], 150)
        self.assertEqual(original["selected_by_policy"]["policy-v1"]["assessment"]["date_max"], 200)
        self.assertTrue(original["selected_by_policy"]["policy-v1"]["rankable"])
        self.assertEqual(original["selected_by_policy"]["policy-v2"]["assessment"]["date_min"], 100)
        self.assertEqual(len(original["selection_history"]), 3)
        self.assertEqual(original["selection_history"][0]["selection_id"], first_selection)
        self.assertIsNone(addition["selected_by_policy"]["policy-v1"]["assessment"]["date_min"])
        self.assertFalse(addition["selected_by_policy"]["policy-v1"]["rankable"])
        self.assertFalse(report["rankings_computed"])
        action = {"action": "select_date", "unit_id": "original", "assessment_id": None,
                  "policy_id": "policy-v1",
                  "reason": "selection withdrawn", "reviewer": "tester"}
        action_path = Path(self.temp.name) / "date-action.json"
        action_path.write_text(json.dumps(action), encoding="utf-8")
        self.assertEqual(main(["--db", str(self.path), "--dating-action", str(action_path),
                               "--dry-run"]), 0)
        self.assertEqual(len(writing_unit_report(self.con, "object-1")["units"][1]
                             ["selection_history"]), 3)
        self.assertEqual(main(["--db", str(self.path), "--dating-action", str(action_path)]), 0)
        self.assertEqual(main(["--db", str(self.path), "--dating-report", "object-1"]), 0)
        self.assertIsNone(writing_unit_report(self.con, "object-1")["units"][1]
                          ["selected_by_policy"]["policy-v1"]["assessment"])
        self.assertEqual(writing_unit_report(self.con, "object-1")["units"][1]
                         ["selected_by_policy"]["policy-v2"]["assessment_id"], early)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)

    def test_ranking_snapshot_reverses_scenarios_and_tracks_changes(self):
        manifest = {"format_version": 1, "inventory_id": "ranking-test", "edition": "TEST",
                    "scope": "synthetic", "source_citation": "fixture", "reuse_terms": "test",
                    "mapping_citation": "fixture", "reviewer": "tester", "verses": [
                        {"osis_ref": ref, "editorial_status": "main", "ntvmr_refs": [ref]}
                        for ref in ("John.18.31", "John.18.32")]}
        import_edition_inventory(self.con, manifest)
        intervals = {"A": (100, 300), "B": (150, 200), "C": (180, 250),
                     "D": (190, 240), "E": (210, 260), "F": (220, 230),
                     "G": (None, None)}
        reviews = {}
        assessments = {}
        for number, (witness, (lower, upper)) in enumerate(intervals.items(), 1):
            doc_id = 20000 + number
            body = json.dumps({"docID": doc_id, "witness": witness})
            self.con.execute("""INSERT INTO source_response(endpoint,url,params_json,
                status_code,headers_json,body,body_sha256,retrieved_at,origin)
                VALUES(?,?,?,?,?,?,?,?,?)""", ("synthetic/index", f"fixture/{doc_id}",
                "{}", 200, "{}", body, hashlib.sha256(body.encode()).hexdigest(),
                "2026-09-29T00:00:00+00:00", "fixture"))
            response_id = self.con.execute("SELECT last_insert_rowid()").fetchone()[0]
            self.con.execute("""INSERT INTO document_metadata(doc_id,response_id,
                source_lang,date_status) VALUES(?,?,'g','unknown')""",
                (doc_id, response_id))
            for page_id in ((10, 20) if witness == "A" else (10,)):
                self.con.execute("""INSERT INTO coverage_index(doc_id,osis_ref,page_id,
                    response_id) VALUES(?,'John.18.31',?,?)""",
                    (doc_id, page_id, response_id))
            self.con.commit()
            record_candidate_review(self.con, doc_id, response_id, "retain",
                                    "greek_manuscript", "synthetic classification",
                                    "fixture", "tester")
            record_witness_assignment(self.con, doc_id, response_id, witness, witness,
                                      "synthetic identity", "fixture", "tester")
            create_writing_unit(self.con, f"{witness}-unit", witness, "Original",
                                "original", "synthetic hand", "fixture", "tester")
            assessments[witness] = record_date_assessment(
                self.con, f"{witness}-unit", "unknown" if lower is None else "valid",
                lower, upper, "synthetic CE",
                "fixture", "2026-09-29", "tester")
            select_date_assessment(self.con, f"{witness}-unit", assessments[witness],
                                   "policy-test", "synthetic choice", "tester")
            for page_id in ((10, 20) if witness == "A" else (10,)):
                review_id = record_coverage_review(
                    self.con, "ranking-test", "John.18.31", "John.18.31",
                    doc_id, page_id, response_id, "partial", "reviewed_transcription",
                    "synthetic surviving text", "fixture", "tester")
                assign_coverage_unit(self.con, review_id, f"{witness}-unit",
                                     "synthetic hand", "fixture", "tester")
                reviews.setdefault(witness, []).append(review_id)
        report = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(report["state"], "success")
        benchmark_path = Path(self.temp.name) / "benchmark.json"
        benchmark_path.write_text(json.dumps({
            "format_version": 1, "benchmark_id": "synthetic-ranking",
            "inventory_id": "ranking-test", "policy_id": "policy-test",
            "cases": [{"osis_ref": "John.18.31", "witness_id": "A",
                       "expected_coverage": "positive", "expected_date": [100, 300],
                       "coverage_citation": "fixture", "date_citation": "fixture",
                       "reviewed_on": "2026-09-29"}]}), encoding="utf-8")
        audited = audit_reviewed_database(self.path, benchmark_path)
        self.assertEqual(audited["findings"], [])
        self.assertEqual(audited["benchmark"]["passed"], 1)
        bad_benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
        bad_benchmark["cases"][0]["coverage_citation"] = "different source"
        benchmark_path.write_text(json.dumps(bad_benchmark), encoding="utf-8")
        self.assertIn("benchmark_coverage_mismatch", [finding["code"] for finding in
                      audit_reviewed_database(self.path, benchmark_path)["findings"]])
        bad_benchmark["cases"][0]["coverage_citation"] = "fixture"
        benchmark_path.write_text(json.dumps(bad_benchmark), encoding="utf-8")
        self.con.execute("""UPDATE ranking_entry SET event_year=999
            WHERE inventory_id='ranking-test' AND osis_ref='John.18.31'
            AND scenario='optimistic' AND rank=1""")
        self.con.commit()
        self.assertIn("ranking_entry_mismatch", [finding["code"] for finding in
                                      audit_reviewed_database(self.path)["findings"]])
        self.con.execute("""UPDATE ranking_entry SET event_year=100
            WHERE inventory_id='ranking-test' AND osis_ref='John.18.31'
            AND scenario='optimistic' AND rank=1""")
        self.con.commit()
        self.assertEqual(report["candidate_count"], 6)
        self.assertIn("invalid_or_unknown_date",
                      [row["reason"] for row in report["excluded_reviews"]])
        self.assertEqual([r["witness_id"] for r in report["scenarios"]["optimistic"]],
                         ["A", "B", "C", "D", "E"])
        self.assertEqual([r["witness_id"] for r in report["scenarios"]["pessimistic"]],
                         ["B", "F", "D", "C", "E"])
        self.assertEqual(report["scenarios"]["pessimistic"][0]["event_year"], 200)
        competing = record_date_assessment(
            self.con, "B-unit", "valid", 50, 400, "alternative synthetic CE",
            "second fixture citation", "2026-09-29", "tester")
        alternatives = dating_alternatives_report(
            self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(alternatives["state"], "complete")
        self.assertEqual(alternatives["combination_count"], 2)
        self.assertEqual(alternatives["eligible_witness_count"], 6)
        self.assertEqual([case["scenarios"]["optimistic"][0]["witness_id"]
                          for case in alternatives["combinations"]], ["A", "B"])
        self.assertEqual([case["scenarios"]["pessimistic"][0]["witness_id"]
                          for case in alternatives["combinations"]], ["B", "F"])
        self.assertEqual(alternatives["combinations"][1]["assessments"][1]["assessment_id"],
                         competing)
        self.assertEqual(alternatives["combinations"][1]["assessments"][1]["citation"],
                         "second fixture citation")
        self.assertEqual(dating_alternatives_report(
            self.con, "ranking-test", "John.18.31", "policy-test",
            max_combinations=1)["state"], "too_many_combinations")
        from export_attestation import build_exports
        dataset, graph = build_exports(self.con, "ranking-test", "policy-test")
        self.assertEqual(dataset["verses"][0]["dating_alternatives"]["combination_count"], 2)
        self.assertIsNone(graph["verses"][0]["scenarios"])
        self.assertEqual(len(graph["verses"][0]["dating_alternatives"]["combinations"]), 2)
        self.assertEqual(compute_ranking(self.con, "ranking-test", "John.18.32",
                                         "policy-test")["state"], "empty")
        later = record_date_assessment(self.con, "A-unit", "valid", 90, 190,
                                       "revised synthetic CE", "fixture", "2026-09-29", "tester")
        select_date_assessment(self.con, "A-unit", later, "policy-test",
                               "revised choice", "tester")
        self.assertEqual(ranking_report(self.con, "ranking-test", "John.18.31",
                                        "policy-test")["state"], "stale")
        self.assertIn("ranking_not_current", [finding["code"] for finding in
                                      audit_reviewed_database(self.path)["findings"]])
        self.assertIn("benchmark_date_mismatch", [finding["code"] for finding in
                                      audit_reviewed_database(self.path, benchmark_path)["findings"]])
        revised = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(revised["scenarios"]["pessimistic"][0]["witness_id"], "A")
        create_writing_unit(self.con, "A-later", "A", "Later hand", "supplement",
                            "synthetic hand", "fixture", "tester")
        alternate = record_date_assessment(self.con, "A-later", "valid", 80, 400,
                                           "synthetic interval", "fixture", "2026-09-29", "tester")
        select_date_assessment(self.con, "A-later", alternate, "policy-test",
                               "synthetic choice", "tester")
        assign_coverage_unit(self.con, reviews["A"][1], "A-later",
                             "later hand on second page", "fixture", "tester")
        revised = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(revised["scenarios"]["optimistic"][0]["unit_id"], "A-later")
        self.assertEqual(revised["scenarios"]["pessimistic"][0]["unit_id"], "A-unit")
        self.assertEqual(revised["scenarios"]["optimistic"][0]["date_citation"], "fixture")
        original_index = self.con.execute("""SELECT response_id FROM coverage_index
            WHERE doc_id=20001 LIMIT 1""").fetchone()[0]
        self.con.execute("""INSERT INTO source_response(endpoint,url,params_json,
            status_code,headers_json,body,body_sha256,retrieved_at,origin)
            SELECT endpoint,url || '/refresh',params_json,status_code,headers_json,'changed','changed',
            '2026-09-30T00:00:00+00:00',origin FROM source_response WHERE id=?""",
            (original_index,))
        changed_index = self.con.execute("SELECT last_insert_rowid()").fetchone()[0]
        self.con.execute("UPDATE coverage_index SET response_id=? WHERE doc_id=20001",
                         (changed_index,))
        self.con.commit()
        stale = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(stale["state"], "stale")
        self.assertEqual(stale["scenarios"], revised["scenarios"])
        self.con.execute("UPDATE coverage_index SET response_id=? WHERE doc_id=20001",
                         (original_index,))
        self.con.commit()
        self.con.execute("""INSERT INTO collection_job(run_id,doc_id,stage,state,
            error,updated_at) VALUES('failed-refresh',20001,'coverage','failed',
            'synthetic timeout','2026-09-30T00:00:00+00:00')""")
        self.con.commit()
        failed = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["scenarios"], revised["scenarios"])
        self.con.execute("""UPDATE collection_job SET state='success',error=NULL
            WHERE run_id='failed-refresh'""")
        self.con.commit()
        record_coverage_review(self.con, "ranking-test", "John.18.31", "John.18.31",
                               20002, 10, self.con.execute("""SELECT response_id FROM
                               coverage_index WHERE doc_id=20002""").fetchone()[0],
                               "withdrawn", "reviewed_transcription", "corrected",
                               "fixture", "tester")
        withdrawn = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(withdrawn["candidate_count"], 5)
        self.assertNotIn("B", [r["witness_id"] for r in
                              withdrawn["scenarios"]["optimistic"]])
        self.assertEqual(main(["--db", str(self.path), "--ranking-inventory", "ranking-test",
                               "--ranking-ref", "John.18.31", "--ranking-policy",
                               "policy-test"]), 0)
        for witness, review_ids in reviews.items():
            for review_id in review_ids:
                row = self.con.execute("""SELECT doc_id,page_id,index_response_id FROM
                    coverage_review WHERE id=?""", (review_id,)).fetchone()
                record_coverage_review(self.con, "ranking-test", "John.18.31",
                                       "John.18.31", *row, "withdrawn",
                                       "reviewed_transcription", "synthetic withdrawal",
                                       "fixture", "tester")
        empty = compute_ranking(self.con, "ranking-test", "John.18.31", "policy-test")
        self.assertEqual(empty["state"], "empty")
        self.assertEqual(empty["scenarios"], {"optimistic": [], "pessimistic": []})
        self.assertEqual(self.con.execute("SELECT count(*) FROM ranking_entry").fetchone()[0], 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        record_coverage_review(self.con, "ranking-test", "John.18.31", "John.18.31",
                               20001, 10, original_index, "rejected", "reviewed_transcription",
                               "synthetic negative review", "fixture", "tester")
        negative = json.loads(benchmark_path.read_text(encoding="utf-8"))
        negative["cases"][0]["expected_coverage"] = "rejected"
        negative["cases"][0]["expected_date"] = None
        negative["cases"][0]["date_citation"] = None
        benchmark_path.write_text(json.dumps(negative), encoding="utf-8")
        self.assertEqual(audit_reviewed_database(self.path, benchmark_path)["benchmark"]["passed"], 1)

    def test_reviewed_audit_is_read_only_and_requires_cited_cases(self):
        before = self.path.stat().st_size
        report = audit_reviewed_database(self.path)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["counts"]["ranking_snapshot"], 0)
        self.assertEqual(self.path.stat().st_size, before)
        absent = Path(self.temp.name) / "absent.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            audit_reviewed_database(absent)
        self.assertFalse(absent.exists())
        invalid = Path(self.temp.name) / "invalid.json"
        invalid.write_text(json.dumps({"format_version": 1, "benchmark_id": "x",
                                       "inventory_id": "x", "policy_id": "x",
                                       "cases": [{"osis_ref": "John.18.31"}]}), encoding="utf-8")
        with self.assertRaises(ValueError):
            load_benchmark(invalid)

    def test_cited_p52_source_controls_flag_missing_extra_and_failed_refresh(self):
        controls = load_source_controls(P52_CONTROLS)
        self.assertEqual(controls["doc_id"], 10052)
        import_p52(self.con, FIXTURE)
        self.assertEqual(collect_stage(Client(self.con, "source-control", offline=True),
                                       10052, "coverage"), "success")
        report = audit_reviewed_database(self.path, source_controls=P52_CONTROLS)
        self.assertEqual(report["source_controls"]["state"], "pass")
        self.assertEqual(report["findings"], [])
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        response_id = self.con.execute("""SELECT response_id FROM coverage_index
            WHERE doc_id=10052 LIMIT 1""").fetchone()[0]
        self.con.execute("UPDATE source_response SET body_sha256='changed' WHERE id=?",
                         (response_id,))
        self.con.commit()
        self.assertIn("source_control_source_changed", [row["code"] for row in
                      audit_reviewed_database(self.path, source_controls=P52_CONTROLS)["findings"]])
        self.con.execute("UPDATE source_response SET body_sha256=? WHERE id=?",
                         (controls["index_response_sha256"], response_id))
        self.con.commit()
        self.con.execute("""DELETE FROM coverage_index WHERE doc_id=10052
            AND osis_ref='John.18.33'""")
        self.con.execute("""INSERT INTO coverage_index(doc_id,osis_ref,page_id,response_id)
            VALUES(10052,'John.18.34',10,?)""", (response_id,))
        self.con.commit()
        codes = {row["code"] for row in audit_reviewed_database(
            self.path, source_controls=P52_CONTROLS)["findings"]}
        self.assertEqual(codes, {"source_control_index_mismatch",
                                 "source_control_neighbor_indexed"})
        self.con.execute("""INSERT INTO collection_job(run_id,doc_id,stage,state,
            error,updated_at) VALUES('later',10052,'coverage','failed','timeout',
            '2099-01-01T00:00:00+00:00')""")
        self.con.commit()
        codes = {row["code"] for row in audit_reviewed_database(
            self.path, source_controls=P52_CONTROLS)["findings"]}
        self.assertIn("source_control_collection_not_current", codes)

    def test_p52_catalogue_date_observation_keeps_selected_date_separate(self):
        control = load_date_source(P52_DATE_SOURCE)
        self.assertEqual(control["usage"], "catalogue_observation_only")
        self.assertEqual(audit_reviewed_database(
            self.path, date_source=P52_DATE_SOURCE)["date_source"]["state"], "finding")
        import_language_probe(self.con, LANGUAGE_FIXTURE)
        report = audit_reviewed_database(self.path, date_source=P52_DATE_SOURCE)
        self.assertEqual(report["date_source"]["state"], "pass")
        self.assertEqual(report["counts"]["date_assessment"], 0)
        self.assertEqual(report["counts"]["date_selection"], 0)
        self.assertEqual(self.con.execute("SELECT count(*) FROM request_attempt").fetchone()[0], 0)
        wrong = json.loads(P52_DATE_SOURCE.read_text(encoding="utf-8"))
        wrong["observed"]["date_min"] = 100
        wrong_path = Path(self.temp.name) / "wrong-date.json"
        wrong_path.write_text(json.dumps(wrong), encoding="utf-8")
        self.assertIn("date_source_observation_mismatch", [row["code"] for row in
                      audit_reviewed_database(self.path, date_source=wrong_path)["findings"]])
        self.con.execute("""UPDATE source_response SET body_sha256='changed'
            WHERE endpoint='metadata/liste/search' AND params_json=?""",
            (json.dumps(control["search_params"], sort_keys=True, separators=(",", ":")),))
        self.con.commit()
        self.assertIn("date_source_changed", [row["code"] for row in
                      audit_reviewed_database(self.path, date_source=P52_DATE_SOURCE)["findings"]])

    def test_ranking_ties_are_deterministic_and_events_are_simultaneous(self):
        rows = [{"witness_id": witness, "unit_id": witness,
                 "coverage_review_id": number, "date_min": 150, "date_max": 200}
                for number, witness in enumerate(("C", "A", "B"), 1)]
        for scenario, expected_year in (("optimistic", 150), ("pessimistic", 200)):
            ranked = rank_candidates(rows + [dict(rows[1], coverage_review_id=9)], scenario)
            self.assertEqual([row["witness_id"] for row in ranked], ["A", "B", "C"])
            self.assertEqual([row["event_year"] for row in ranked], [expected_year] * 3)
            self.assertEqual([row["rank"] for row in ranked], [1, 2, 3])

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
                         [{"doc_id": 10052, "page_ids": [10],
                           "review_decision": "unreviewed", "review_reason": None,
                           "review_source_changed": None}])
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
