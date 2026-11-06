"""Pruebas en español de la búsqueda y lectura de documentos."""

import json

from brain import i18n
from brain.core.config import Config
from tests.helpers import CaseBrain


class TestEsDocuments(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

        folder = Config.DATA / "documents"
        folder.mkdir(parents=True)
        (folder / "manual_lavadora.md").write_text(
            "# Lavadora\n\nPara el programa de lana pulsa el botón 3 dos segundos.\n\n## Filtro\n\nLimpia el filtro cada mes.\n",
            encoding="utf-8",
        )
        (folder / "caldera.txt").write_text("La caldera se purga abriendo la válvula roja. Presión ideal 1.5 bar.", encoding="cp1252")

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_searches_spanish_content(self):
        r = self.execute("search_documents", query="¿cómo limpio el filtro de la lavadora?")

        self.assertEqual(r["results"][0]["document"], "manual_lavadora.md")

    def test_reads_cp1252_accents(self):
        r = self.execute("read_document", name="caldera")

        self.assertIn("válvula roja", r["text"])

    def test_no_results_message_in_spanish(self):
        r = self.execute("search_documents", query="submarino nuclear")

        self.assertIn("No he encontrado nada", r["message"])

    def test_no_documents_message_in_spanish(self):
        import shutil

        shutil.rmtree(Config.DATA / "documents")

        r = self.execute("search_documents", query="algo")

        self.assertIn("No hay documentos", r["message"])
