"""Checks for the full reference inventory and its recorded source exceptions."""

import json
from pathlib import Path
import tempfile
import unittest

from build_na28_inventory import OUTPUT, SOURCE, build, render
from controlled_ntvmr import connect, import_edition_inventory
from export_attestation import build_exports


class Na28InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))
        cls.manifest = build(cls.source)
        cls.rows = {row["osis_ref"]: row for row in cls.manifest["verses"]}

    def test_pinned_manifest_matches_publisher_coordinate_ledger(self):
        self.assertEqual(OUTPUT.read_text(encoding="utf-8"), render(self.manifest))
        self.assertEqual(len(self.source["chapters"]), 260)
        self.assertEqual(len(self.rows), 7957)
        self.assertEqual(self.manifest["verses"][0]["osis_ref"], "Matt.1.1")
        self.assertEqual(self.manifest["verses"][-1]["osis_ref"], "Rev.22.21")

    def test_editorial_exceptions_and_unresolved_mappings_stay_visible(self):
        self.assertEqual({ref for ref, row in self.rows.items()
                          if row["editorial_status"] == "omitted"},
                         set(self.source["skipped_coordinates"]))
        self.assertEqual(self.rows["Mark.16.9"]["editorial_status"], "bracketed")
        self.assertEqual(self.rows["Mark.16.20"]["editorial_status"], "bracketed")
        self.assertEqual(self.rows["Luke.22.43"]["editorial_status"], "bracketed")
        self.assertEqual(self.rows["John.7.53"]["editorial_status"], "bracketed")
        self.assertEqual(self.rows["John.8.11"]["editorial_status"], "bracketed")
        self.assertEqual(self.rows["John.8.12"]["editorial_status"], "main")
        self.assertIn("Only part", self.rows["Luke.23.34"]["editorial_note"])
        self.assertEqual(self.rows["1Cor.4.21"]["editorial_status"], "uncertain")
        self.assertEqual(self.rows["2Cor.13.13"]["editorial_status"], "main")
        self.assertNotIn("2Cor.13.14", self.rows)
        self.assertEqual(self.rows["3John.1.15"]["editorial_status"], "main")
        mapped = {ref for ref, row in self.rows.items() if row["ntvmr_refs"]}
        self.assertEqual(mapped, {"John.18.31", "John.18.32", "John.18.33",
                                  "John.18.37", "John.18.38"})
        self.assertTrue(self.rows["Matt.1.1"]["mapping_note"])

    def test_existing_importer_round_trips_every_coordinate(self):
        with tempfile.TemporaryDirectory() as directory:
            con = connect(Path(directory) / "inventory.sqlite")
            try:
                self.assertEqual(import_edition_inventory(con, self.manifest), 7957)
                self.assertEqual(con.execute("SELECT count(*) FROM edition_verse").fetchone()[0], 7957)
                self.assertEqual(con.execute("SELECT count(*) FROM edition_verse_map").fetchone()[0], 5)
                self.assertEqual(con.execute("SELECT count(DISTINCT book) FROM edition_verse").fetchone()[0], 27)
                self.assertEqual(con.execute("SELECT count(*) FROM (SELECT DISTINCT book,chapter FROM edition_verse)").fetchone()[0], 260)
                self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
                complete, default_graph = build_exports(
                    con, self.manifest["inventory_id"], "unselected")
                self.assertEqual(complete["counts"]["verse_count"], 7957)
                self.assertEqual(default_graph["counts"]["verse_count"], 7941)
                self.assertEqual(default_graph["counts"]["by_editorial_status"]["omitted"], 0)
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
