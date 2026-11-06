"""Pruebas en español del planificador y las tareas periódicas del sistema."""

from brain import i18n
from brain.core.scheduler import Scheduler, HomeAssistantPoller, check_reminders
from tests.helpers import CaseBrain


class TestEsScheduler(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def test_interval_error_in_spanish(self):
        plan = Scheduler()

        with self.assertRaises(ValueError) as err:
            plan.register("a", lambda: None)

        self.assertIn("mayor que cero", str(err.exception))

    def test_without_home_assistant_message_in_spanish(self):
        self.assertIn("no está configurado", HomeAssistantPoller()())

    def test_reminders_message_in_spanish(self):
        self.assertEqual(check_reminders(), "0 recordatorios")


if __name__ == "__main__":
    import unittest

    unittest.main()
