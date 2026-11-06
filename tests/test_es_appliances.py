from datetime import date

from brain import i18n
from brain.modules.appliances import Appliances
from tests.helpers import CaseBrain


class TestSpanishAppliances(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)
        self.addCleanup(i18n.reset)

    def test_messages_and_warranty_are_in_spanish(self):
        e = self.brain.tools.execute
        e("add_appliance", {"name": "Lavadora", "purchase_date": "2024-01-10", "warranty_months": 24})

        module = Appliances()

        self.assertIn("caducó", module.warranty_state(module.devices()[0], today=date(2026, 6, 1)))
        self.assertIn("No tengo registrado", e("query_appliance", {"name": "secadora"})["error"])

    def test_memory_understands_spanish_kinds(self):
        memory = self.brain.modules.get("memory")

        self.assertEqual(memory.remember("mi hermana se llama Ana", "personas")["kind"], "people")
        self.assertEqual(memory.normalize_type("preferencias"), "preferences")
