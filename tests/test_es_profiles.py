"""Pruebas en español de las personas de la casa."""

from brain import i18n
from tests.helpers import CaseBrain


class TestEsProfiles(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_no_people_message_in_spanish(self):
        r = self.execute("list_people")

        self.assertIn("Todavía no hay personas", r["message"])

    def test_unknown_person_error_in_spanish(self):
        with self.assertRaises(ValueError) as err:
            self.execute("remove_person", name="Nadie")

        self.assertIn("No conozco a", str(err.exception))
