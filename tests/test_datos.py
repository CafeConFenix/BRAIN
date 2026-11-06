import json
import tempfile
import unittest
from pathlib import Path

from brain.core.config import Config
from brain.core.data_manager import DataManager


class TestDataManager(unittest.TestCase):
    def setUp(self):
        self._before = Config.DATA
        self.folder = tempfile.TemporaryDirectory()
        Config.DATA = Path(self.folder.name)
        self.data = DataManager()

    def tearDown(self):
        Config.DATA = self._before
        self.folder.cleanup()

    def test_save_y_leer_with_accents(self):
        self.data.save_module("health", {"note": "Más café, ñandú"})

        self.assertEqual(self.data.read_module("health"), {"note": "Más café, ñandú"})

        text = (Path(self.folder.name) / "health" / "health.json").read_text(encoding="utf-8")

        self.assertIn("Más café", text)

    def test_add_record(self):
        self.data.add_record("health", "weight", {"weight": 80})
        self.data.add_record("health", "weight", {"weight": 81})

        self.assertEqual(len(self.data.read_module("health")["weight"]), 2)

    def test_no_deja_files_temporales(self):
        self.data.save_module("health", {"a": 1})

        surplus = list((Path(self.folder.name) / "health").glob("*.tmp"))

        self.assertEqual(surplus, [])

    def test_json_corrupto_no_rompe_y_self_aparta(self):
        path = Path(self.folder.name) / "health" / "health.json"
        path.parent.mkdir(parents=True)
        path.write_text("{esto no es json", encoding="utf-8")

        self.assertEqual(self.data.read_module("health"), {})
        self.assertTrue((path.parent / "health.json.corrupt").exists())

    def test_acepta_bom_of_windows(self):
        path = Path(self.folder.name) / "health" / "health.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"weight": [1]}).encode("utf-8"))

        self.assertEqual(self.data.read_module("health"), {"weight": [1]})

    def test_file_empty(self):
        path = Path(self.folder.name) / "health" / "health.json"
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")

        self.assertEqual(self.data.read_module("health"), {})

    def test_folder_with_espacios_y_eñes(self):
        root = Path(self.folder.name) / "Mis datos de Ñandú con espacios"

        Config.DATA = root

        DataManager().save_module("health", {"ok": True})

        self.assertTrue((root / "health" / "health.json").exists())


if __name__ == "__main__":
    unittest.main()
