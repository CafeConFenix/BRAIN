import json

from brain.modules.energy import RealtimeEnergy, describe, detect_sensors, save_energy_sensors
from brain.integrations.home_assistant import save_config
from tests.helpers import CaseBrain, FakeHomeAssistant, call, energy_sensors, text


class CaseEnergy(CaseBrain):
    def setUp(self):
        super().setUp()

        self.ha = FakeHomeAssistant(entities=energy_sensors())
        self.ha.start()

        save_config(self.ha.url, FakeHomeAssistant.TOKEN)

    def tearDown(self):
        self.ha.stop()
        super().tearDown()


class TestDetection(CaseEnergy):
    def states(self):
        return [{"entity_id": e, "state": d["state"], "attributes": d["attributes"]} for e, d in self.ha.entities.items()]

    def test_finds_the_inverter_and_discards_strings_and_daily_energy(self):
        c = detect_sensors(self.states())

        self.assertEqual(c["production"][0]["entity"], "sensor.inversor_potencia_activa")
        self.assertEqual(c["production"][0]["value_w"], 3200)
        entities = {x["entity"] for x in c["production"]}
        self.assertNotIn("sensor.inversor_pv1_power", entities)
        self.assertNotIn("sensor.inversor_energia_hoy", entities)

    def test_finds_the_meter_and_the_home_battery_not_the_phone_one(self):
        c = detect_sensors(self.states())

        self.assertEqual(c["grid"][0]["entity"], "sensor.contador_potencia")
        self.assertEqual([x["entity"] for x in c["battery_pct"]], ["sensor.bateria_nivel"])


class TestLiveReading(CaseEnergy):
    def test_warns_when_not_configured(self):
        save_config("", "")

        r = RealtimeEnergy().read()

        self.assertFalse(r["configured"])
        self.assertIn("CONFIGURE_SMART_HOME", r["message"])

    def test_detects_sensors_by_itself_and_computes_consumption(self):
        r = RealtimeEnergy().read()

        self.assertTrue(r["automatic"])
        self.assertEqual(r["production_w"], 3200)
        self.assertEqual(r["grid_w"], -900)
        self.assertEqual(r["grid_state"], "selling")
        # La casa gasta lo que producen las placas menos lo que se vende: 3200 - 900.
        self.assertEqual(r["consumption_w"], 2300)
        self.assertTrue(r["computed_consumption"])
        self.assertEqual(r["battery_pct"], 64)

    def test_uses_the_chosen_sensors_and_the_grid_sign(self):
        save_energy_sensors(
            {"production": "sensor.inversor_potencia_activa", "grid": "sensor.contador_potencia", "grid_inverted": True}
        )

        r = RealtimeEnergy().read()

        self.assertEqual(r["grid_w"], 900)
        self.assertEqual(r["grid_state"], "buying")
        self.assertEqual(r["consumption_w"], 4100)

    def test_with_its_own_consumption_sensor(self):
        self.ha.entities["sensor.casa_consumo"] = {
            "state": "1250",
            "attributes": {"friendly_name": "Consumo casa", "unit_of_measurement": "W"},
        }
        save_energy_sensors({"production": "sensor.inversor_potencia_activa", "consumption": "sensor.casa_consumo"})

        r = RealtimeEnergy().read()

        self.assertEqual(r["consumption_w"], 1250)
        self.assertFalse(r["computed_consumption"])
        self.assertEqual(r["solar_covered_pct"], 100)

    def test_the_summary_is_plain_language(self):
        text_ = describe(RealtimeEnergy().read())

        self.assertIn("3.20 kW", text_)
        self.assertIn("900 W is fed into the grid", text_)

    def test_a_failed_sensor_does_not_break_it(self):
        save_energy_sensors({"production": "sensor.no_existe"})

        r = RealtimeEnergy().read()

        self.assertIn("error", r)

    def test_the_ai_answers_with_the_real_consumption(self):
        self.ollama.responses = [call("show_energy_now"), text("Ahora mismo la casa consume 2,3 kW.")]

        response = self.brain.conversation.ask("¿Cuánto estoy consumiendo?")

        self.assertIn("2,3 kW", response)
        result = self.brain.ai.tools_used[0]["result"]
        self.assertEqual(result["consumption_w"], 2300)

    def test_web_endpoint(self):
        from brain.web.server import read_energy

        self.assertEqual(read_energy()["production_w"], 3200)
        json.dumps(read_energy())
