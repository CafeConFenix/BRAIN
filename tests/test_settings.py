import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from brain.core.config import Config
from brain.integrations.home_assistant import save_config
from brain.modules.energy import read_energy_sensors
from brain.web.access import Access
from brain.web.server import create_handler
from tests.helpers import CaseBrain, FakeHomeAssistant, example_entities, energy_sensors, call, text

REMOTE_HOST = "casa.tail1234.ts.net"


class CaseWeb(CaseBrain):
    """Servidor web de BRAIN contra un Home Assistant falso."""

    entities = None
    connect = True

    def setUp(self):
        super().setUp()
        self.ha = FakeHomeAssistant(entities=self.entities if self.entities is not None else {**example_entities(), **energy_sensors()})
        self.ha.start()

        if self.connect:
            save_config(self.ha.url, FakeHomeAssistant.TOKEN)

        self.access = Access(Path(Config.DATA) / "access.json")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain, self.access))
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()
        self.dom = self.brain.modules.get("smart_home")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.ha.stop()
        super().tearDown()

    def ask(self, method, path, body=None, host=None, cookie=None):
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}

        if method == "POST":
            headers["Content-Type"] = "application/json"

        if cookie:
            headers["Cookie"] = cookie

        con.request(method, path, body=json.dumps(body or {}) if method == "POST" else None, headers=headers)
        r = con.getresponse()
        data = json.loads(r.read() or b"{}")
        con.close()

        return r.status, data

    def remote_session(self):
        self.access.set_password("una-clave-larga")
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        con.request("POST", "/api/access/login", body=json.dumps({"key": "una-clave-larga"}), headers={"Host": REMOTE_HOST, "Content-Type": "application/json"})
        r = con.getresponse()
        r.read()
        cookie = r.getheader("Set-Cookie").split(";")[0]
        con.close()

        return cookie


class TestDevicesHidden(CaseWeb):
    def test_ocultar_quita_of_panel_y_of_the_ia(self):
        self.assertIn("Kitchen light", [d["name"] for g in self.dom.panel()["groups"] for d in g["devices"]])
        self.dom.save_hidden(["light.kitchen"])
        names = [d["name"] for g in self.dom.panel()["groups"] for d in g["devices"]]
        self.assertNotIn("Kitchen light", names)
        self.assertIn("Living room light", names)
        # La IA tampoco lo encuentra ni lo puede turn_on.
        self.assertIn("error", self.brain.tools.execute("turn_on", {"device": "kitchen light"}))
        self.assertEqual(self.ha.calls, [])
        # Ni desde el panel, aunque se conozca su identificador.
        from brain.integrations.home_assistant import HomeAssistantError

        with self.assertRaises(HomeAssistantError):
            self.dom.toggle("light.kitchen", True)

    def test_selector_list_all_with_visibilidad(self):
        self.dom.save_hidden(["light.kitchen", "scene.night"])
        c = self.dom.configurable_devices()
        all_items = {d["entity"]: d["visible"] for g in c["groups"] for d in g["devices"]}
        self.assertFalse(all_items["light.kitchen"])
        self.assertFalse(all_items["scene.night"])
        self.assertTrue(all_items["light.living_room_ceiling"])
        self.assertNotIn("sensor.living_room_temp", all_items)  # los sensores no se eligen
        self.assertNotIn("cover.garage", all_items)  # los garajes nunca se controlan
        self.assertEqual(c["hidden"], 2)

    def test_show_of_new(self):
        self.dom.save_hidden(["light.kitchen"])
        self.dom.save_hidden([])
        self.assertIn("Kitchen light", [d["name"] for g in self.dom.panel()["groups"] for d in g["devices"]])

    def test_api_save_y_leer(self):
        code, data = self.ask("POST", "/api/config/devices/save", {"hidden": ["light.kitchen", "basura", ""]})
        self.assertEqual((code, data["hidden"]), (200, 1))  # "basura" no es un identificador
        code, data = self.ask("GET", "/api/config/devices")
        self.assertEqual(code, 200)
        self.assertTrue(data["connected"])
        self.assertEqual(data["hidden"], 1)
        self.assertEqual(self.ask("POST", "/api/config/devices/save", {})[0], 400)

    def test_self_conserva_between_arranques(self):
        self.dom.save_hidden(["light.kitchen"])
        from brain.core import Brain

        other = Brain(quiet=True).modules.get("smart_home")
        self.assertEqual(other.hidden(), {"light.kitchen"})

    def test_the_ia_sigue_encendiendo_lo_visible(self):
        self.dom.save_hidden(["light.kitchen"])
        r = self.brain.tools.execute("turn_on", {"device": "bedroom light"})
        self.assertEqual(r["done_at"], ["Bedroom light"])

    def test_the_device_oculto_sigue_in_the_list_of_elegir_from_remote(self):
        cookie = self.remote_session()
        self.assertEqual(self.ask("POST", "/api/config/devices/save", {"hidden": ["light.kitchen"]}, host=REMOTE_HOST, cookie=cookie)[0], 200)
        code, data = self.ask("GET", "/api/config/devices", host=REMOTE_HOST, cookie=cookie)
        self.assertEqual(code, 200)
        self.assertEqual(data["hidden"], 1)


class TestAssistant(CaseWeb):
    def test_state_y_first_time(self):
        code, e = self.ask("GET", "/api/config/state")
        self.assertEqual(code, 200)
        self.assertTrue(e["ha"]["configured"])
        self.assertNotIn("token", json.dumps(e).lower().replace("token_saved", ""))  # la llave nunca sale
        self.assertFalse(e["first_time"])

    def test_first_time_without_nothing_configured(self):
        import brain.web.config as c

        save_config("", "")
        self.assertTrue(c.config_state()["first_time"])
        self.ask("POST", "/api/config/skip")
        self.assertFalse(c.config_state()["first_time"])

    def test_only_from_the_computer_of_home(self):
        cookie = self.remote_session()

        for method, path in (("GET", "/api/config/state"), ("GET", "/api/config/energy"), ("POST", "/api/config/ha/save"), ("POST", "/api/config/energy/save"), ("POST", "/api/config/skip")):
            self.assertEqual(self.ask(method, path, {}, host=REMOTE_HOST, cookie=cookie)[0], 403, path)

    def test_save_home_assistant(self):
        save_config("", "")
        code, r = self.ask("POST", "/api/config/ha/save", {"url": self.ha.url, "token": FakeHomeAssistant.TOKEN})
        self.assertEqual(code, 200, r)
        self.assertTrue(r["ok"])
        self.assertIn({"kind": "lights", "total": 4}, r["summary"])
        self.assertTrue(r["energy_detected"])
        self.assertTrue(self.dom.connected())

    def test_token_incorrect_no_self_guarda(self):
        save_config("", "")
        code, r = self.ask("POST", "/api/config/ha/save", {"url": self.ha.url, "token": "mal"})
        self.assertEqual(code, 502)
        self.assertIn("token", r["error"])
        self.assertFalse(self.dom.connected())

    def test_missing_data(self):
        save_config("", "")
        self.assertEqual(self.ask("POST", "/api/config/ha/save", {"url": "", "token": "x"})[0], 400)
        self.assertEqual(self.ask("POST", "/api/config/ha/save", {"url": self.ha.url, "token": ""})[0], 400)

    def test_token_empty_reutiliza_the_saved(self):
        code, r = self.ask("POST", "/api/config/ha/save", {"url": self.ha.url, "token": ""})
        self.assertEqual(code, 200, r)

    def test_candidates_of_energy(self):
        code, r = self.ask("GET", "/api/config/energy")
        self.assertEqual(code, 200)
        roles = {x["role"]: x for x in r["roles"]}
        self.assertEqual(roles["production"]["candidates"][0]["entity"], "sensor.inversor_potencia_activa")
        self.assertEqual(roles["battery_pct"]["candidates"][0]["entity"], "sensor.bateria_nivel")
        self.assertTrue(any(p["entity"] == "sensor.inversor_pv1_power" for p in r["powers"]))
        self.assertEqual(roles["production"]["chosen"], "")

    def test_save_energy(self):
        code, r = self.ask(
            "POST",
            "/api/config/energy/save",
            {"production": "sensor.inversor_potencia_activa", "grid": "sensor.contador_potencia", "battery_pct": "sensor.bateria_nivel", "consumption": ""},
        )
        self.assertEqual(code, 200, r)
        saved = read_energy_sensors()
        self.assertEqual(saved["production"], "sensor.inversor_potencia_activa")
        self.assertNotIn("consumption", saved)
        self.assertIn("3", r["reading"])  # 3,2 kW
        self.assertEqual(self.ask("GET", "/api/config/energy")[1]["roles"][0]["chosen"], "sensor.inversor_potencia_activa")

    def test_energy_invertida_segun_lo_that_ve_the_user(self):
        # El contador marca -900 W. Si el usuario dice que ahora COMPRA, el signo está al revés.
        self.ask("POST", "/api/config/energy/save", {"production": "sensor.inversor_potencia_activa", "grid": "sensor.contador_potencia", "grid_now": "buying"})
        self.assertTrue(read_energy_sensors().get("grid_inverted"))
        self.ask("POST", "/api/config/energy/save", {"production": "sensor.inversor_potencia_activa", "grid": "sensor.contador_potencia", "grid_now": "selling"})
        self.assertFalse(read_energy_sensors().get("grid_inverted"))

    def test_energy_rechaza_sensors_malos(self):
        self.assertEqual(self.ask("POST", "/api/config/energy/save", {})[0], 400)
        self.assertEqual(self.ask("POST", "/api/config/energy/save", {"production": "sensor.no_existe"})[0], 400)
        self.assertEqual(self.ask("POST", "/api/config/energy/save", {"production": "sensor.living_room_temp"})[0], 400)  # no es potencia
        self.assertEqual(read_energy_sensors(), {})

    def test_without_home_assistant_connected(self):
        save_config("", "")
        self.assertEqual(self.ask("GET", "/api/config/energy")[0], 502)
        self.assertFalse(self.ask("GET", "/api/config/devices")[1]["connected"])


class TestNoticesSeen(CaseWeb):
    def test_mark_only_los_indicados(self):
        notices = self.brain.modules.get("notices")
        notices.notify("Uno", "x", quiet=True)
        notices.notify("Dos", "y", quiet=True)
        self.assertTrue(notices.items(unread_only=True))
        ids = [x["id"] for x in notices.items(unread_only=True)]
        code, r = self.ask("POST", "/api/notices/read", {"ids": ids[:1]})
        self.assertEqual(code, 200)
        self.assertEqual(r["marked"], 1)
        self.assertEqual(len(notices.items(unread_only=True)), len(ids) - 1)

    def test_the_page_brand_as_seen_a_los_2_seconds(self):
        html = (Path(__file__).resolve().parents[1] / "brain" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("function programarVisto", html)
        self.assertIn("}, 2000);", html)
        self.assertIn('enviarJSON("/api/notices/read", { ids })', html)


class TestFuncionesNew(CaseWeb):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    # ---- gastos ----

    def test_record_expenses_and_summary(self):
        g = self.execute("add_expense", amount="23,50", description="Walmart")["logged"]
        self.assertEqual((g["amount"], g["category"], g["id"]), (23.5, "groceries", 1))
        self.execute("add_expense", amount=60, description="electricity bill")
        self.execute("add_expense", amount="1.234,56", description="renovation", category="home")
        self.execute("add_expense", amount=10, description="odd thing")
        r = self.execute("show_expenses")
        self.assertEqual(r["total"], 1328.06)
        self.assertEqual(r["n"], 4)
        self.assertEqual(r["by_category"][0]["category"], "home")
        self.assertEqual({c["category"] for c in r["by_category"]}, {"home", "bills", "groceries", "other"})

    def test_expenses_by_month_and_delete(self):
        self.execute("add_expense", amount=5, description="cinema", date="2026-01-15")
        self.execute("add_expense", amount=7, description="coffee", date="2026-02-02")
        self.assertEqual(self.execute("show_expenses", month="2026-01")["total"], 5)
        self.assertIn("message", self.execute("show_expenses", month="2025-03"))
        self.assertEqual(self.execute("delete_expense")["deleted"]["amount"], 7)  # the latest
        self.assertEqual(self.execute("delete_expense", id="1")["deleted"]["description"], "cinema")
        with self.assertRaises(ValueError):
            self.execute("delete_expense", id="9")

    def test_invalid_expense_amounts(self):
        for bad in ("", "abc", 0, -5):
            with self.assertRaises(ValueError):
                self.execute("add_expense", amount=bad)

    # ---- hábitos ----

    def test_habits_progress_y_streak(self):
        from datetime import date as Date, timedelta

        today = Date.today()
        self.execute("create_habit", name="beber agua", goal=3, unit="vasos")

        for back in (2, 1):  # cumplido anteayer y ayer
            self.execute("log_habit", name="agua", quantity=3, date=(today - timedelta(days=back)).isoformat())

        r = self.execute("log_habit", name="agua")  # hoy 1 de 3: la racha de ayer sigue viva
        self.assertEqual((r["today"], r["met"], r["streak_days"]), (1, False, 2))
        r = self.execute("log_habit", name="beber agua", quantity=2)
        self.assertEqual((r["today"], r["met"], r["streak_days"]), (3, True, 3))
        v = self.execute("list_habits")
        self.assertEqual((v["met"], v["total"]), (1, 1))

    def test_habits_streak_self_rompe_y_correcciones(self):
        from datetime import date as Date, timedelta

        today = Date.today()
        self.execute("create_habit", name="pasear")
        self.execute("log_habit", name="pasear", date=(today - timedelta(days=3)).isoformat())
        r = self.execute("log_habit", name="pasear")
        self.assertEqual(r["streak_days"], 1)  # ayer y anteayer faltan: solo cuenta hoy
        r = self.execute("log_habit", name="pasear", quantity=-1)  # corregir
        self.assertEqual((r["today"], r["met"]), (0, False))

    def test_habits_errors(self):
        self.assertIn("message", self.execute("list_habits"))
        with self.assertRaises(ValueError):
            self.execute("log_habit", name="no existe")
        with self.assertRaises(ValueError):
            self.execute("create_habit", name="x", goal=0)
        self.execute("create_habit", name="leer")
        self.assertEqual(self.execute("delete_habit", name="leer")["deleted"]["name"], "leer")
        self.assertEqual(self.execute("list_habits")["total"] if "total" in self.execute("list_habits") else 0, 0)

    def test_parse_month(self):
        from datetime import date as Date
        from brain.modules.expenses import interpret_month

        today = Date.today()
        self.assertEqual(interpret_month(), f"{today.year:04d}-{today.month:02d}")
        self.assertEqual(interpret_month("2026-3"), "2026-03")
        self.assertEqual(interpret_month("octubre")[-2:], "10")
        self.assertRegex(interpret_month("mes pasado"), r"^\d{4}-\d{2}$")

    def test_the_ia_recibe_las_tools_of_expenses(self):
        from brain.ai.relevant_tools import relevant_categories

        self.assertIn("expenses", relevant_categories("cuánto he gastado este mes"))

    # ---- domótica ----

    def test_that_has_on(self):
        r = self.execute("whats_on")
        names = {d["name"] for d in r["on"]}
        self.assertEqual(names, {"Living room light", "Living room thermostat"})
        self.dom.save_hidden(["light.living_room_ceiling"])
        self.assertEqual({d["name"] for d in self.execute("whats_on")["on"]}, {"Living room thermostat"})

    def test_devices_with_problems(self):
        self.ha.entities["light.kitchen"]["state"] = "unavailable"
        self.ha.entities["sensor.pilas_puerta"] = {
            "state": "8",
            "attributes": {"friendly_name": "Pilas puerta", "device_class": "battery", "unit_of_measurement": "%"},
        }
        self.dom.forget_catalog()
        r = self.execute("devices_with_problems")
        self.assertEqual([d["name"] for d in r["offline"]], ["Kitchen light"])
        self.assertEqual(r["battery_low"][0]["battery_pct"], 8)
        self.assertFalse(r["all_good"])

    def test_all_well_without_problems(self):
        self.assertTrue(self.execute("devices_with_problems")["all_good"])

    # ---- ahorro solar ----

    def test_savings_solar(self):
        self.assertIn("error", self.execute("show_solar_savings"))
        self.assertEqual(self.execute("set_electricity_tariff", buy="0,15", sell=0.06)["tariff"], {"buy": 0.15, "sell": 0.06})
        self.assertIn("message", self.execute("show_solar_savings"))  # aún sin producción
        self.execute("save_solar_production", kwh=20, date="2026-10-01")
        self.execute("save_solar_production", kwh=30, date="2026-10-02")
        r = self.execute("show_solar_savings")
        self.assertEqual((r["kwh_produced"], r["max_value_eur"], r["min_value_eur"]), (50.0, 7.5, 3.0))

    def test_tariff_invalid(self):
        for bad in (0, -1, 50):
            with self.assertRaises(ValueError):
                self.execute("set_electricity_tariff", shopping=bad)

        with self.assertRaises(ValueError):
            self.execute("set_electricity_tariff")
