from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, save_config, normalize_url
from tests.helpers import CaseBrain, FakeHomeAssistant, call, text


class CaseSmartHome(CaseBrain):
    def setUp(self):
        super().setUp()

        self.ha = FakeHomeAssistant()
        self.ha.start()

        save_config(self.ha.url, FakeHomeAssistant.TOKEN)

        self.dom = self.brain.modules.get("smart_home")
        self.dom.forget_catalog()

    def tearDown(self):
        self.ha.stop()
        super().tearDown()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)


class TestClient(CaseSmartHome):
    def test_normalizes_addresses(self):
        self.assertEqual(normalize_url("192.168.1.5"), "http://192.168.1.5:8123")
        self.assertEqual(normalize_url("homeassistant.local:8123/"), "http://homeassistant.local:8123")
        self.assertEqual(normalize_url("https://casa.example.com/lovelace"), "https://casa.example.com:8123")

    def test_wrong_token(self):
        client = HomeAssistant(self.ha.url, "otro")

        with self.assertRaises(HomeAssistantError) as c:
            client.check()

        self.assertIn("token", str(c.exception))

    def test_without_connection(self):
        client = HomeAssistant("http://127.0.0.1:1", "x", timeout=2)

        with self.assertRaises(HomeAssistantError):
            client.check()

    def test_without_configuration(self):
        result = HomeAssistant("", "")

        with self.assertRaises(HomeAssistantError) as c:
            result.states()

        self.assertIn("CONFIGURE_SMART_HOME", str(c.exception))


class TestControl(CaseSmartHome):
    def test_turn_on_a_light_by_name(self):
        r = self.execute("turn_on", device="kitchen light")

        self.assertEqual(r["done_at"], ["Kitchen light"])
        self.assertEqual(self.ha.calls, [("light", "turn_on", {"entity_id": "light.kitchen"})])

    def test_turn_off_ignoring_case(self):
        self.execute("turn_off", device="THE LIVING ROOM LIGHT")

        self.assertEqual(self.ha.calls[0][:2], ("light", "turn_off"))
        self.assertEqual(self.ha.calls[0][2]["entity_id"], "light.living_room_ceiling")

    def test_ambiguous_asks_instead_of_guessing(self):
        r = self.execute("turn_on", device="light")

        self.assertTrue(r["ambiguous"])
        self.assertEqual(self.ha.calls, [])

    def test_plural_or_all_acts_on_every_match(self):
        r = self.execute("turn_off", device="living room lights")

        self.assertEqual(set(r["done_at"]), {"Living room lamp", "Living room light"})
        self.assertEqual(len(self.ha.calls), 2)

        self.ha.calls.clear()
        self.execute("turn_off", device="light", all_items=True)
        self.assertEqual(len(self.ha.calls), 4)

    def test_light_by_room(self):
        self.execute("turn_on", device="bedroom light")

        self.assertEqual(self.ha.calls[0][2]["entity_id"], "light.bedroom")

    def test_adjust_brightness_color_and_temperature(self):
        self.execute("adjust_light", device="kitchen light", brightness=30, color="azul")

        _, service, data = self.ha.calls[-1]
        self.assertEqual(service, "turn_on")
        self.assertEqual(data["brightness_pct"], 30)
        self.assertEqual(data["rgb_color"], [0, 0, 255])

        self.execute("adjust_light", device="kitchen light", temperature="calida")
        self.assertEqual(self.ha.calls[-1][2]["color_temp_kelvin"], 2700)

    def test_brightness_is_capped_at_100(self):
        self.execute("adjust_light", device="kitchen light", brightness=250)

        self.assertEqual(self.ha.calls[-1][2]["brightness_pct"], 100)

    def test_color_unknown(self):
        r = self.execute("adjust_light", device="kitchen light", color="infrared")

        self.assertIn("error", r)
        self.assertEqual(self.ha.calls, [])

    def test_blind(self):
        self.execute("turn_off", device="bedroom blind")
        self.assertEqual(self.ha.calls[-1][:2], ("cover", "close_cover"))

        self.execute("move_blind", device="bedroom blind", position=40)
        self.assertEqual(self.ha.calls[-1][1:], ("set_cover_position", {"entity_id": "cover.bedroom_blind", "position": 40}))

    def test_thermostat(self):
        self.execute("set_temperature", device="living room thermostat", degrees=22.5)
        self.assertEqual(self.ha.calls[-1][1:], ("set_temperature", {"entity_id": "climate.living_room", "temperature": 22.5}))

        r = self.execute("set_temperature", device="living room thermostat", degrees=80)
        self.assertIn("error", r)

    def test_scene(self):
        self.execute("activate_scene", scene="night")

        self.assertEqual(self.ha.calls[-1][:2], ("scene", "turn_on"))

    def test_does_not_control_garages_or_locks(self):
        for order in ("the garage door", "the hallway lock", "garage"):
            r = self.execute("turn_on", device=order)

            self.assertIn("error", r, order)

        self.assertEqual(self.ha.calls, [])

    def test_no_found(self):
        r = self.execute("turn_on", device="basement light")

        self.assertIn("error", r)
        self.assertEqual(self.ha.calls, [])


class TestQueries(CaseSmartHome):
    def test_list_lights_with_state(self):
        r = self.execute("list_devices", kind="lights")

        self.assertEqual(r["total"], 4)
        living_room = [a for a in r["devices"] if a["name"] == "Living room light"][0]
        self.assertEqual(living_room["state"], "on")
        self.assertEqual(living_room["brightness_pct"], 100)
        self.assertEqual(living_room["room"], "Living room")

    def test_list_by_room(self):
        r = self.execute("list_devices", room="bedroom")

        names = {a["name"] for a in r["devices"]}
        self.assertEqual(names, {"Bedroom light", "Bedroom blind"})

    def test_sensor_and_lock_are_read_only(self):
        r = self.execute("device_state", device="living room temperature")
        self.assertEqual(r["devices"][0]["state"], "21.3")

        r = self.execute("device_state", device="hallway lock")
        self.assertEqual(r["devices"][0]["state"], "locked")

    def test_without_configuration_returns_a_clear_error(self):
        save_config("", "")
        self.dom.forget_catalog()

        r = self.execute("turn_on", device="kitchen light")

        self.assertIn("CONFIGURE_SMART_HOME", r["error"])


class TestWithAI(CaseSmartHome):
    def test_the_ai_turns_on_a_light(self):
        self.ollama.responses = [
            call("turn_on", device="kitchen light"),
            text("Done, I turned on the kitchen light."),
        ]

        response = self.brain.conversation.ask("Turn on the kitchen light")

        self.assertIn("kitchen", response)
        self.assertEqual(self.ha.calls, [("light", "turn_on", {"entity_id": "light.kitchen"})])
        self.assertIn("turn_on", [h["name"] for h in self.brain.ai.tools_used])
