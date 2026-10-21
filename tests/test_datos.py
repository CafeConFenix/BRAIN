import json
import tempfile
import unittest
from pathlib import Path

from brain.core.config import Config
from brain.core.data_manager import DataManager


class TestDataManager(unittest.TestCase):
    def setUp(self):
        self._antes = Config.DATOS
        self.carpeta = tempfile.TemporaryDirectory()
        Config.DATOS = Path(self.carpeta.name)
        self.data = DataManager()

    def tearDown(self):
        Config.DATOS = self._antes
        self.carpeta.cleanup()

    def test_guardar_y_leer_con_acentos(self):
        self.data.guardar_modulo("salud", {"nota": "Más café, ñandú"})

        self.assertEqual(self.data.leer_modulo("salud"), {"nota": "Más café, ñandú"})

        texto = (Path(self.carpeta.name) / "salud" / "salud.json").read_text(encoding="utf-8")

        self.assertIn("Más café", texto)

    def test_añadir_registro(self):
        self.data.añadir_registro("salud", "peso", {"peso": 80})
        self.data.añadir_registro("salud", "peso", {"peso": 81})

        self.assertEqual(len(self.data.leer_modulo("salud")["peso"]), 2)

    def test_no_deja_archivos_temporales(self):
        self.data.guardar_modulo("salud", {"a": 1})

        sobrantes = list((Path(self.carpeta.name) / "salud").glob("*.tmp"))

        self.assertEqual(sobrantes, [])

    def test_json_corrupto_no_rompe_y_se_aparta(self):
        ruta = Path(self.carpeta.name) / "salud" / "salud.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("{esto no es json", encoding="utf-8")

        self.assertEqual(self.data.leer_modulo("salud"), {})
        self.assertTrue((ruta.parent / "salud.json.corrupto").exists())

    def test_acepta_bom_de_windows(self):
        ruta = Path(self.carpeta.name) / "salud" / "salud.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_bytes(b"\xef\xbb\xbf" + json.dumps({"peso": [1]}).encode("utf-8"))

        self.assertEqual(self.data.leer_modulo("salud"), {"peso": [1]})

    def test_archivo_vacio(self):
        ruta = Path(self.carpeta.name) / "salud" / "salud.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("", encoding="utf-8")

        self.assertEqual(self.data.leer_modulo("salud"), {})

    def test_carpeta_con_espacios_y_eñes(self):
        raiz = Path(self.carpeta.name) / "Mis datos de Ñandú con espacios"

        Config.DATOS = raiz

        DataManager().guardar_modulo("salud", {"ok": True})

        self.assertTrue((raiz / "salud" / "salud.json").exists())


if __name__ == "__main__":
    unittest.main()
