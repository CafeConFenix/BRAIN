import io
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

from brain.ai import ollama as ollama_module
from brain.utils.console import prepare_console

PROJECT = Path(__file__).resolve().parent.parent


class TestWindows(unittest.TestCase):
    def test_console_cp1252_no_revienta_with_tildes_ni_emojis(self):
        raw = io.BytesIO()
        fake = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")

        with self.assertRaises(UnicodeEncodeError):
            fake.write("ok ✓ 🧠")
            fake.flush()

        raw = io.BytesIO()
        fake = io.TextIOWrapper(raw, encoding="cp1252", errors="strict")

        with mock.patch.object(sys, "stdout", fake), mock.patch.object(sys, "stderr", io.StringIO()):
            prepare_console()

            print("Año 2026 — BRAIN ✓ 🧠 ¿qué tal?")
            sys.stdout.flush()

        self.assertIn("BRAIN".encode("utf-8"), raw.getvalue())

    def test_busca_ollama_in_las_routes_of_windows(self):
        import ntpath

        expected = ntpath.join("C:\\Users\\Luis Gremón\\AppData\\Local", "Programs", "Ollama", "ollama.exe")

        fake_os = mock.MagicMock()
        fake_os.name = "nt"
        fake_os.environ = {
            "LOCALAPPDATA": "C:\\Users\\Luis Gremón\\AppData\\Local",
            "PROGRAMFILES": "C:\\Program Files",
        }
        fake_os.path = ntpath
        fake_os.path.isfile = lambda path: path == expected

        with mock.patch.object(ollama_module, "os", fake_os), mock.patch.object(
            ollama_module.shutil, "which", return_value=None
        ):
            self.assertEqual(ollama_module.find_executable(), expected)

    def test_url_of_ollama_uses_ipv4(self):
        from brain.core.config import Config

        self.assertIn("127.0.0.1", Config.OLLAMA_URL)

    def test_scripts_de_windows_son_ascii(self):
        # Con ñ o tildes, el CMD y PowerShell 5 los leerían mal en algunos equipos.
        for patron in ("*.bat", "scripts/*.ps1"):
            for file in PROJECT.glob(patron):
                content = file.read_bytes()

                try:
                    content.decode("ascii")
                except UnicodeDecodeError as error:
                    self.fail(f"{file.name} tiene caracteres no ASCII: {error}")

    def test_los_bat_llaman_only_a_labels_that_exist(self):
        for file in PROJECT.glob("*.bat"):
            text = file.read_text(encoding="ascii")

            labels = set(re.findall(r"^:(\w+)", text, re.MULTILINE))

            calls = set(re.findall(r"(?:call|goto)\s+:(\w+)", text, re.IGNORECASE))

            self.assertTrue(calls <= labels, f"{file.name}: {calls - labels}")

    def test_los_bat_tienen_los_parentheses_equilibrados(self):
        for file in PROJECT.glob("*.bat"):
            text = re.sub(r'"[^"]*"', "", file.read_text(encoding="ascii"))

            self.assertEqual(text.count("("), text.count(")"), file.name)

    def test_los_echo_dentro_of_bloques_no_llevan_parentheses(self):
        # Un ")" dentro de un echo de un bloque if/for cierra el bloque antes de tiempo.
        for file in PROJECT.glob("*.bat"):
            depth = 0

            for number, line in enumerate(file.read_text(encoding="ascii").splitlines(), 1):
                clean = re.sub(r'"[^"]*"', "", line)

                if depth > 0 and line.strip().lower().startswith("echo"):
                    self.assertNotIn(")", line, f"{file.name}:{number}: {line}")
                    self.assertNotIn("(", line, f"{file.name}:{number}: {line}")

                depth += clean.count("(") - clean.count(")")

    def test_exist_los_launchers(self):
        for name in ("INSTALAR.bat", "INICIAR.bat", "INICIAR_CONSOLA.bat", "DIAGNOSTICO.bat"):
            self.assertTrue((PROJECT / name).exists(), name)

        self.assertTrue((PROJECT / "scripts" / "instalar.ps1").exists())


if __name__ == "__main__":
    unittest.main()
