from brain import i18n
from brain.integrations.home_assistant import save_config
from tests.helpers import CaseBrain, FakeHomeAssistant


def spanish_entities():
    return {
        "light.salon": {"state": "on", "area": "Salón", "attributes": {"friendly_name": "Luz salón", "brightness": 255}},
        "light.cocina": {"state": "off", "area": "Cocina", "attributes": {"friendly_name": "Luz cocina"}},
        "cover.persiana": {
            "state": "open",
            "area": "Dormitorio",
            "attributes": {"friendly_name": "Persiana dormitorio", "device_class": "shutter"},
        },
    }


class TestSpanishSmartHome(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)
        self.addCleanup(i18n.reset)

        self.ha = FakeHomeAssistant(entities=spanish_entities())
        self.ha.start()
        self.addCleanup(self.ha.stop)

        save_config(self.ha.url, FakeHomeAssistant.TOKEN)
        self.brain.modules.get("smart_home").forget_catalog()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_spanish_orders_find_devices(self):
        self.execute("turn_off", device="la luz de la cocina")
        self.assertEqual(self.ha.calls[-1][:2], ("light", "turn_off"))

        self.execute("move_blind", device="persiana del dormitorio", position=40)
        self.assertEqual(self.ha.calls[-1][1], "set_cover_position")

    def test_spanish_colors_and_safety_words(self):
        self.execute("adjust_light", device="luz del salón", color="rojo")
        self.assertEqual(self.ha.calls[-1][2]["rgb_color"], [255, 0, 0])

        self.assertIn("error", self.execute("turn_on", device="la cerradura de la puerta"))

    def test_messages_are_in_spanish(self):
        save_config("", "")
        self.brain.modules.get("smart_home").forget_catalog()

        self.assertIn("no está conectada", self.execute("turn_on", device="luz")["error"])
