import unittest
from datetime import datetime, timedelta

from brain.core.scheduler import AutomationEngine
from brain.integrations.home_assistant import save_config
from brain.modules.automations import Automations, interpret_days
from tests.helpers import CaseBrain, FakeHomeAssistant, example_entities, energy_sensors


class CaseAuto(CaseBrain):
    def setUp(self):
        super().setUp()
        entities = {**example_entities(), **energy_sensors()}
        self.ha = FakeHomeAssistant(entities=entities)
        self.ha.start()
        save_config(self.ha.url, FakeHomeAssistant.TOKEN)
        self.e = self.brain.tools.execute
        self.auto = Automations()

    def tearDown(self):
        self.ha.stop()
        super().tearDown()

    def notice_titles(self):
        return [a["title"] for a in self.e("list_notices", {"all_items": True}).get("notices", [])]


class TestCreate(CaseAuto):
    def test_create_list_pausar_delete(self):
        r = self.e("create_automation", {"name": "Aviso sol", "trigger": "energy", "magnitude": "sobrante",
                                            "condition": "mayor", "value": "1500", "action": "notice", "message": "Pon la lavadora"})
        self.assertIn("1500", r["created"]["rule"])

        self.assertEqual(self.e("list_automations")["automations"][0]["name"], "Aviso sol")
        self.assertFalse(self.e("enable_automation", {"name": "sol", "active": False})["active"])
        self.assertEqual(self.e("delete_automation", {"name": "Aviso sol"})["deleted"]["name"], "Aviso sol")
        self.assertIn("message", self.e("list_automations"))

    def test_validations(self):
        e = self.e
        base = {"name": "x", "action": "notice"}

        self.assertIn("error", e("create_automation", {**base, "trigger": "luna"}))
        self.assertIn("HH:MM", e("create_automation", {**base, "trigger": "hour", "hour": "tarde"})["error"])
        self.assertIn("days", e("create_automation", {**base, "trigger": "hour", "hour": "8:00", "days": "quincenas"})["error"])
        self.assertIn("error", e("create_automation", {**base, "trigger": "energy", "magnitude": "viento", "condition": "mayor", "value": 1}))
        self.assertIn("error", e("create_automation", {**base, "trigger": "energy", "magnitude": "consumption", "condition": "mayor", "value": "mucho"}))
        self.assertIn("error", e("create_automation", {"name": "y", "trigger": "hour", "hour": "8:00", "action": "turn_on"}))  # sin objetivo
        self.assertIn("cannot find", e("create_automation", {"name": "z", "trigger": "hour", "hour": "8:00", "action": "turn_on", "goal": "nave espacial"})["error"])

        e("create_automation", {**base, "trigger": "hour", "hour": "8:00"})
        self.assertIn("already an automation", e("create_automation", {**base, "trigger": "hour", "hour": "9:00"})["error"])

    def test_no_acepta_cerraduras(self):
        r = self.e("create_automation", {"name": "puerta", "trigger": "hour", "hour": "8:00", "action": "turn_on", "goal": "cerradura de la puerta"})

        self.assertIn("error", r)

    def test_dias(self):
        self.assertEqual(interpret_days("laborables"), [0, 1, 2, 3, 4])
        self.assertEqual(interpret_days("lunes, jueves"), [0, 3])
        self.assertEqual(interpret_days("fin de semana"), [5, 6])


class TestRun(CaseAuto):
    def test_hour_self_ejecuta_a_time_to_day_dentro_of_the_window(self):
        self.e("create_automation", {"name": "Buenos días", "trigger": "hour", "hour": "07:30", "action": "notice", "message": "Arriba"})

        day = datetime(2026, 10, 12, 7, 30)  # lunes

        self.assertEqual(self.auto.evaluate(day - timedelta(minutes=1)), [])
        self.assertEqual(len(self.auto.evaluate(day + timedelta(minutes=1))), 1)
        self.assertEqual(self.auto.evaluate(day + timedelta(minutes=2)), [])  # ya hecha hoy
        self.assertEqual(len(self.auto.evaluate(day + timedelta(days=1, minutes=1))), 1)  # al día siguiente, otra vez
        self.assertEqual(self.auto.evaluate(day + timedelta(days=2, minutes=30)), [])  # fuera de ventana
        self.assertIn("Buenos días", self.notice_titles())

    def test_hour_respects_los_days(self):
        self.e("create_automation", {"name": "Lunes", "trigger": "hour", "hour": "09:00", "days": "lunes", "action": "notice"})

        self.assertEqual(self.auto.evaluate(datetime(2026, 10, 13, 9, 1)), [])  # martes
        self.assertEqual(len(self.auto.evaluate(datetime(2026, 10, 12, 9, 1))), 1)

    def test_hour_turn_on_a_device_real(self):
        self.e("create_automation", {"name": "Luz noche", "trigger": "hour", "hour": "20:00", "action": "turn_on", "goal": "kitchen light"})

        r = self.auto.evaluate(datetime(2026, 10, 12, 20, 2))

        self.assertIn("turn_on kitchen light", r[0])
        self.assertTrue(self.ha.calls)

    def test_energy_dispara_to_cruzar_the_umbral_y_no_repite(self):
        self.e("create_automation", {"name": "Sol", "trigger": "energy", "magnitude": "production", "condition": "mayor", "value": "3000",
                                        "action": "notice", "message": "Mucho sol", "wait_minutes": 0})
        now = datetime(2026, 10, 12, 12, 0)

        valores = iter([2000, 3200, 3500, 2500, 3300])
        self.auto._energy = lambda: {"configured": True, "production_w": next(valores), "consumption_w": 500}

        results = [len(self.auto.evaluate(now + timedelta(minutes=i))) for i in range(5)]

        # 1ª lectura (2000) no cumple; 2ª cruza -> dispara; 3ª sigue cumpliendo -> no; 4ª baja; 5ª vuelve a cruzar -> dispara
        self.assertEqual(results, [0, 1, 0, 0, 1])

    def test_the_first_reading_already_cumplida_no_dispara(self):
        self.e("create_automation", {"name": "Sol", "trigger": "energy", "magnitude": "production", "condition": "mayor", "value": "100", "action": "notice"})
        self.auto._energy = lambda: {"configured": True, "production_w": 5000}

        self.assertEqual(self.auto.evaluate(datetime.now()), [])

    def test_wait_between_runs(self):
        self.e("create_automation", {"name": "Sol", "trigger": "energy", "magnitude": "sobrante", "condition": "mayor", "value": "1000",
                                        "action": "notice", "wait_minutes": 30})
        base = datetime(2026, 10, 12, 12, 0)
        valores = iter([0, 2000, 0, 2000, 0, 2000])
        self.auto._energy = lambda: {"configured": True, "production_w": next(valores), "consumption_w": 0}

        results = [len(self.auto.evaluate(base + timedelta(minutes=10 * i))) for i in range(6)]

        self.assertEqual(results, [0, 1, 0, 0, 0, 1])  # el 2º cruce (min 30) cae dentro de la espera... el 3º ya no

    def test_sensor_de_home_assistant(self):
        r = self.e("create_automation", {"name": "Frío", "trigger": "sensor", "sensor": "living room temperature", "condition": "menor",
                                            "value": "18", "action": "notice", "message": "Hace frío"})
        self.assertNotIn("error", r)

        self.assertEqual(self.auto.evaluate(datetime.now()), [])  # 21.3 ºC: no se cumple

        self.ha.entities["sensor.living_room_temp"]["state"] = "16.5"
        self.assertEqual(len(self.auto.evaluate(datetime.now())), 1)

    def test_sensor_ambiguous_o_nonexistent(self):
        self.assertIn("error", self.e("create_automation", {"name": "a", "trigger": "sensor", "sensor": "submarino", "condition": "mayor", "value": "1", "action": "notice"}))

    def test_a_rule_broken_no_for_las_demas_y_the_motor_no_falla(self):
        self.e("create_automation", {"name": "Rota", "trigger": "energy", "magnitude": "production", "condition": "mayor", "value": "1", "action": "notice"})
        self.e("create_automation", {"name": "Buena", "trigger": "hour", "hour": "10:00", "action": "notice"})

        def mal():
            raise RuntimeError("inversor roto")

        self.auto._energy = mal

        done = self.auto.evaluate(datetime(2026, 10, 12, 10, 1))  # el fallo del inversor no impide la regla de hora

        self.assertEqual(len(done), 1)
        self.assertIn("Buena", done[0])

    def test_run_now_y_motor_of_scheduler(self):
        self.e("create_automation", {"name": "Prueba", "trigger": "hour", "hour": "03:00", "action": "notice", "message": "ding"})

        self.assertIn("notice sent", self.e("run_automation", {"name": "prueba"})["result"])
        self.assertEqual(self.e("list_automations")["automations"][0]["runs"], 1)
        self.assertIn("run", AutomationEngine()())


if __name__ == "__main__":
    unittest.main()
