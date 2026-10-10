"""Bounded build regression checks, independent of the production collection."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

from pipeline.browser_format import pack_browser_data
from build_collection import build_data, main, refresh
from pipeline.build_storage import record_store, records_digest
from pipeline.controlled_ntvmr import encoded
from pipeline.report_explorer import ExplorerPacker, expand_explorer_data, pack_explorer_data
from pipeline.source_reports import digest

ROOT = Path(__file__).resolve().parents[1]


class BoundedBuildTests(unittest.TestCase):
    def test_streaming_packer_matches_compatibility_formats_and_does_not_mutate_inputs(self):
        for name in ("explorer-normalized", "explorer-empty", "explorer-sparse"):
            source = json.loads((ROOT / "tests" / "fixtures" / f"{name}.v3.json").read_text(encoding="utf-8"))
            data = expand_explorer_data(source)
            before = deepcopy(data)
            packer = ExplorerPacker()
            # Claims may be reused by several observations. Intern in exactly
            # the fixture's encounter order, then consume its rows individually.
            packer.add({**data, "observations": {}})
            for ref, row in data["observations"].items():
                packer.add({**data, "observations": {ref: row}})
            packed = packer.finish({k: v for k, v in data.items() if k not in ("claims", "dates", "observations")})
            self.assertEqual(packed, pack_explorer_data(data), name)
            self.assertEqual(pack_browser_data(packed), pack_browser_data(data), name)
            self.assertEqual(pack_browser_data(deepcopy(packed), consume=True), pack_browser_data(data), name)
            self.assertEqual(data, before)

    def test_unknown_coverage_memory_does_not_retain_all_pair_objects(self):
        # 160,000 unknown pairs would retain tens of MB as dictionaries/lists.
        # The streaming packer retains shared records and integer vectors.
        tracemalloc.start()
        try:
            packer = ExplorerPacker()
            for verse in range(400):
                row = {"discovery": {"state": "not_searched"},
                       "dating_alternatives": {"combinations": []},
                       "reported_coverage": [{"witness_id": str(w), "state": "unknown", "claims": [],
                                              "date_assessments": [], "unknown_reason": "no_explicit_mapped_report"}
                                             for w in range(400)]}
                packer.add({"claims": {}, "dates": {}, "observations": {f"Gal.1.{verse}": row}})
            _, peak = tracemalloc.get_traced_memory()
            self.assertLess(peak, 12 * 1024 * 1024)
            self.assertEqual(len(packer.tables["coverage_records"]), 400)
        finally:
            tracemalloc.stop()

    def test_disk_records_replay_and_hash_exactly_and_clean_up_on_failure(self):
        records = [{"x": "é", "snapshot": 1}, {"x": [False, 1], "snapshot": 2}, {"x": None}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "interrupted"):
                with record_store(root) as factory:
                    spool = factory("fixture")
                    spool.extend(records)
                    self.assertEqual(list(spool), records)
                    self.assertEqual(list(spool), records)
                    self.assertEqual(spool[-2], records[-2])
                    self.assertEqual(records_digest(spool, omit=("snapshot",)),
                                     digest(encoded([{k: v for k, v in r.items() if k != "snapshot"} for r in records])))
                    raise ValueError("interrupted")
            self.assertEqual(list((root / ".cache").iterdir()), [])
        self.assertEqual(records_digest([]), digest("[]"))

    def test_expanded_production_work_is_rejected_before_reading_captures(self):
        config = {"coordinate_inventory": "coordinates.json", "documents": [{}] * 2000, "books": ["Gal"]}
        with patch("build_collection.read_json", return_value={"verses": [{"osis_ref": "Gal.1.1"}] * 1000}), \
                patch("build_collection.prepare_collection", side_effect=AssertionError("Must fail before extraction")):
            with self.assertRaisesRegex(ValueError, "Expanded coverage"):
                build_data(config)
        with self.assertRaisesRegex(ValueError, "Expanded coverage"):
            expand_explorer_data({"documents": [{}] * 2000, "observations": dict.fromkeys(range(1000))})

    def test_os_budget_rejects_one_large_allocation_in_a_child_process(self):
        script = """
from pipeline.build_memory import memory_budget
with memory_budget(256) as stats:
    try:
        value = bytearray(300 * 1024 * 1024)
    except MemoryError:
        pass
    else:
        raise AssertionError('OS did not enforce the build memory ceiling')
assert stats['peak_process_memory_bytes'] > 0
"""
        child = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_large_integer_encoding_fits_a_small_process_budget(self):
        # Nonrepeating values exercise all compression candidates. The former
        # list/JSON implementation exceeded this budget before choosing one.
        script = """
import random
from pipeline.build_memory import memory_budget
from pipeline.browser_format import pack_integers, unpack_integers
with memory_budget(160):
    rng = random.Random(826)
    packed = pack_integers(rng.randrange(2**31) for _ in range(1_000_000))
    rng = random.Random(826)
    restored = unpack_integers(packed)
    assert len(restored) == 1_000_000
    assert all(value == rng.randrange(2**31) for value in restored)
"""
        child = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(child.returncode, 0, child.stderr)

    def test_memory_failure_preserves_current_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "attestations.json"
            output.write_bytes(b"existing data\n")
            with patch("build_collection._build_browser_data", side_effect=MemoryError):
                with self.assertRaises(MemoryError):
                    refresh(Path(tmp))
                with patch("sys.stderr"):
                    self.assertEqual(main(["--data-dir", tmp]), 1)
            self.assertEqual(output.read_bytes(), b"existing data\n")
            (Path(tmp) / "collection.json").write_text("{}", encoding="utf-8")
            with patch("build_collection.prepare_collection", return_value=({}, {})), \
                    patch("build_collection.import_batch", side_effect=MemoryError):
                with self.assertRaises(MemoryError):
                    refresh(Path(tmp))
            self.assertEqual(output.read_bytes(), b"existing data\n")
            self.assertEqual(list((Path(tmp) / ".cache").iterdir()), [])
