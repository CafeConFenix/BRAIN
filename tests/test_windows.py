import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

from brain.ai import ollama as modulo_ollama
from brain.utils.consola import preparar_consola

PROYECTO = Path(__file__).resolve().parent.parent


class TestWindows(unittest.TestCase):
    def test_consola_cp1252_no_revienta_con_tildes_ni_emojis(self):
        crudo = io.BytesIO()
        falsa = io.TextIOWrapper(crudo, encoding="cp1252", errors="strict")

        with self.assertRaises(UnicodeEncodeError):
            falsa.write("ok ✓ 🧠")
            falsa.flush()

        crudo = io.BytesIO()
        falsa = io.TextIOWrapper(crudo, encoding="cp1252", errors="strict")

        with mock.patch.object(sys, "stdout", falsa), mock.patch.object(sys, "stderr", io.StringIO()):
            preparar_consola()

            print("Año 2026 — BRAIN ✓ 🧠 ¿qué tal?")
            sys.stdout.flush()

        self.assertIn("BRAIN".encode("utf-8"), crudo.getvalue())

    def test_busca_ollama_en_las_rutas_de_windows(self):
        import ntpath

        esperada = ntpath.join("C:\\Users\\Luis Gremón\\AppData\\Local", "Programs", "Ollama", "ollama.exe")

        falso_os = mock.MagicMock()
        falso_os.name = "nt"
        falso_os.environ = {
            "LOCALAPPDATA": "C:\\Users\\Luis Gremón\\AppData\\Local",
            "PROGRAMFILES": "C:\\Program Files",
        }
        falso_os.path = ntpath
        falso_os.path.isfile = lambda ruta: ruta == esperada

        with mock.patch.object(modulo_ollama, "os", falso_os), mock.patch.object(
            modulo_ollama.shutil, "which", return_value=None
        ):
            self.assertEqual(modulo_ollama.buscar_ejecutable(), esperada)

    def test_url_de_ollama_usa_ipv4(self):
        from brain.core.config import Config

        self.assertIn("127.0.0.1", Config.OLLAMA_URL)

    def test_scripts_de_windows_son_ascii(self):
        # Con ñ o tildes, el CMD y PowerShell 5 los leerían mal en algunos equipos.
        for patron in ("*.bat", "scripts/*.ps1"):
            for archivo in PROYECTO.glob(patron):
                contenido = archivo.read_bytes()

                try:
                    contenido.decode("ascii")
                except UnicodeDecodeError as error:
                    self.fail(f"{archivo.name} tiene caracteres no ASCII: {error}")

    def test_los_bat_llaman_solo_a_etiquetas_que_existen(self):
        for archivo in PROYECTO.glob("*.bat"):
            texto = archivo.read_text(encoding="ascii")

            etiquetas = set(re.findall(r"^:(\w+)", texto, re.MULTILINE))

            llamadas = set(re.findall(r"(?:call|goto)\s+:(\w+)", texto, re.IGNORECASE))

            self.assertTrue(llamadas <= etiquetas, f"{archivo.name}: {llamadas - etiquetas}")

    def test_los_bat_tienen_los_parentesis_equilibrados(self):
        for archivo in PROYECTO.glob("*.bat"):
            texto = re.sub(r'"[^"]*"', "", archivo.read_text(encoding="ascii"))

            self.assertEqual(texto.count("("), texto.count(")"), archivo.name)

    def test_los_echo_dentro_de_bloques_no_llevan_parentesis(self):
        # Un ")" dentro de un echo de un bloque if/for cierra el bloque antes de tiempo.
        for archivo in PROYECTO.glob("*.bat"):
            profundidad = 0

            for numero, linea in enumerate(archivo.read_text(encoding="ascii").splitlines(), 1):
                limpia = re.sub(r'"[^"]*"', "", linea)

                if profundidad > 0 and linea.strip().lower().startswith("echo"):
                    self.assertNotIn(")", linea, f"{archivo.name}:{numero}: {linea}")
                    self.assertNotIn("(", linea, f"{archivo.name}:{numero}: {linea}")

                profundidad += limpia.count("(") - limpia.count(")")

    def test_existen_los_lanzadores(self):
        for nombre in ("INSTALAR.bat", "INICIAR.bat", "INICIAR_CONSOLA.bat", "DIAGNOSTICO.bat"):
            self.assertTrue((PROYECTO / nombre).exists(), nombre)

        self.assertTrue((PROYECTO / "scripts" / "instalar.ps1").exists())


if __name__ == "__main__":
    unittest.main()
