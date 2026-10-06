"""Verify current publisher coordinates, editorial statuses, and cited exceptions."""

from contextlib import closing
from pathlib import Path
import tempfile
import unittest

from build_collection import read_json
from build_na28_inventory import OUTPUT, PASSAGE_REVIEW, REVIEW, SOURCE, build
from controlled_ntvmr import connect, import_edition_inventory


class Na28InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = read_json(SOURCE)
        cls.manifest = build(cls.source, read_json(REVIEW), read_json(PASSAGE_REVIEW))
        cls.rows = {row["osis_ref"]: row for row in cls.manifest["verses"]}

    def test_current_inventory_matches_publisher_sources(self):
        self.assertEqual(read_json(OUTPUT), self.manifest)
        self.assertEqual(len(self.source["chapters"]), 260)
        self.assertEqual(len(self.rows), 7957)
        self.assertEqual(self.manifest["verses"][0]["osis_ref"], "Matt.1.1")
        self.assertEqual(self.manifest["verses"][-1]["osis_ref"], "Rev.22.21")

    def test_edition_status_is_separate_from_witness_mapping(self):
        self.assertEqual({ref for ref, row in self.rows.items() if row["editorial_status"] == "omitted"},
                         set(self.source["skipped_coordinates"]))
        for ref in ("Mark.16.9", "Mark.16.20", "Luke.22.43", "John.7.53", "John.8.11"):
            self.assertEqual(self.rows[ref]["editorial_status"], "bracketed")
        for ref in ("John.8.12", "1Cor.4.21", "2Cor.13.13", "3John.1.15"):
            self.assertEqual(self.rows[ref]["editorial_status"], "main")
        self.assertNotIn("2Cor.13.14", self.rows)
        self.assertTrue(all(not row["ntvmr_refs"] for row in self.rows.values()))
        self.assertIn("Only part", self.rows["Luke.23.34"]["editorial_note"])
        self.assertIn("LU12/JHN.5", self.rows["John.5.4"]["passage_citation"])

    def test_inventory_import_preserves_canonical_order_and_no_witness_claims(self):
        with tempfile.TemporaryDirectory() as tmp, closing(connect(Path(tmp) / "inventory.sqlite")) as con:
            self.assertEqual(import_edition_inventory(con, self.manifest), 7957)
            self.assertEqual(con.execute("SELECT count(DISTINCT book) FROM edition_verse").fetchone()[0], 27)
            self.assertEqual(con.execute("SELECT count(*) FROM edition_verse_map").fetchone()[0], 0)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
