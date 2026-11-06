"""Pruebas en español de los avisos y recordatorios."""

from brain import i18n
from tests.helpers import CaseBrain


class TestEsNotices(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_missing_message_error_in_spanish(self):
        r = self.execute("create_reminder", message="   ")

        self.assertIn("Falta el texto", r["error"])

    def test_no_reminders_message_in_spanish(self):
        r = self.execute("list_reminders")

        self.assertIn("No hay recordatorios pendientes", r["message"])

    def test_cancel_unknown_reminder_in_spanish(self):
        r = self.execute("cancel_reminder", id=999)

        self.assertIn("No hay ningún recordatorio pendiente", r["error"])

    def test_no_sounds_message_in_spanish(self):
        r = self.execute("assign_sound", kind="info", file="x")

        self.assertIn("No hay sonidos", r["error"])

    def test_test_notice_in_spanish(self):
        r = self.execute("send_test_notice")

        self.assertEqual(r["sent"]["title"], "Aviso de prueba")
