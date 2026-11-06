"""Pruebas en español del módulo de salud."""

from brain import i18n
from tests.helpers import CaseBrain


class TestEsHealth(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_invalid_weight_error_in_spanish(self):
        with self.assertRaises(ValueError) as err:
            self.execute("save_weight", weight=900)

        self.assertIn("no parece correcto", str(err.exception))

    def test_no_weight_message_in_spanish(self):
        r = self.execute("weight_on_date", date="2026-01-01")

        self.assertIn("No hay ningún peso", r["message"])

    def test_no_measurements_message_in_spanish(self):
        r = self.execute("show_body_measurements")

        self.assertIn("No hay medidas corporales", r["message"])
