import http.client
import json
import sqlite3
import threading
import time
import unittest
import zipfile
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from brain.core.config import Config
from brain.core.database import Database
from brain.core.scheduler import Scheduler, HomeAssistantPoller, register_default_tasks
from brain.integrations.home_assistant import save_config
from brain.modules.system import BackupError
from brain.web.server import create_handler
from tests.helpers import CaseBrain, FakeHomeAssistant, call, energy_sensors


class TestBaseDeDatos(CaseBrain):
    def test_indices_in_dates(self):
        self.assertTrue({"idx_energy_date", "idx_sensors_date", "idx_sensors_type_date"} <= set(Database().indices()))

        with closing(sqlite3.connect(str(Database().path))) as con:
            plan = con.execute("EXPLAIN QUERY PLAN SELECT * FROM energy_records WHERE date >= '2026-01-01'").fetchall()

        self.assertIn("idx_energy_date", str(plan))

    def test_tools_siguen_igual_pero_guardan_in_sqlite(self):
        e = self.brain.tools.execute
        e("save_weight", {"weight": 88.4, "date": "2026-08-10"})
        e("save_weight", {"weight": 87.9, "date": "2026-08-10"})  # misma fecha: actualiza
        e("save_weight", {"weight": 90, "date": "2026-08-01"})
        e("save_sensor", {"kind": "temp", "value": 21.5, "location": "salón"})
        e("save_solar_production", {"kwh": 30, "date": "2026-08-10"})

        self.assertEqual(e("get_weight")["weight"], 87.9)
        self.assertEqual(e("weight_on_date", {"date": "2026-08-05"})["exact"], False)
        self.assertEqual([r["date"] for r in e("weight_history")["history"]] if "history" in e("weight_history") else [], ["2026-08-01", "2026-08-10"] if "history" in e("weight_history") else [])
        self.assertEqual(e("show_sensor", {"kind": "temperature"})["value"], 21.5)
        self.assertEqual(e("show_solar_production")["total_kwh"], 30)

        # Nada de esto está ya en los JSON
        self.assertFalse((Config.DATA / "health" / "health.json").exists())
        self.assertTrue(Database().path.exists())

    def test_sensor_guarda_valores_no_numericos(self):
        self.brain.modules.get("sensors").record("presence", "yes")

        self.assertEqual(Database().sensor_readings("presence")[0]["value"], "yes")

    def test_transaccion_self_deshace_si_falla(self):
        db = Database()

        with self.assertRaises(sqlite3.IntegrityError):
            with closing(db.connect()) as con, con:
                con.execute("INSERT INTO weight (date, weight) VALUES ('2026-01-01', 80)")
                con.execute("INSERT INTO weight (date, weight) VALUES ('2026-01-01', NULL)")

        self.assertEqual(db.weight_history(), [])


class TestMigration(unittest.TestCase):
    def test_migrate_los_json_old(self):
        import tempfile

        before = Config.DATA
        folder = Path(tempfile.mkdtemp(prefix="brain_mig_"))
        Config.DATA = folder

        try:
            (folder / "health").mkdir()
            (folder / "health" / "health.json").write_text(
                json.dumps({"weight": [{"weight": 80, "date": "2026-01-02"}, {"weight": 81, "date": "2026-01-03"}], "other": [1]}),
                encoding="utf-8",
            )
            (folder / "sensors").mkdir()
            (folder / "sensors" / "sensors.json").write_text(
                json.dumps({"temperature": [{"value": 20, "location": "x", "date": "2026-01-01T10:00:00"}]}), encoding="utf-8"
            )
            (folder / "energy").mkdir()
            (folder / "energy" / "energy.json").write_text(
                json.dumps({"solar_panels": [{"production": 12.5, "date": "2026-01-01"}]}), encoding="utf-8"
            )

            db = Database()

            self.assertEqual(len(db.weight_history()), 2)
            self.assertEqual(db.sensor_readings("temperature")[0]["value"], 20)
            self.assertEqual(db.production(5)[0]["production"], 12.5)

            # Se conserva lo que no era una serie temporal y queda copia del original
            self.assertEqual(json.loads((folder / "health" / "health.json").read_text(encoding="utf-8")), {"other": [1]})
            self.assertTrue((folder / "health" / "health.json.premigration").exists())
            self.assertFalse((folder / "sensors" / "sensors.json").exists())

            # No se vuelve a migrar ni duplica
            Database()._migrate_json()
            self.assertEqual(len(db.weight_history()), 2)
        finally:
            Config.DATA = before


class TestScheduler(unittest.TestCase):
    def test_an_error_does_not_stop_anything(self):
        plan = Scheduler()
        count = [0]

        def bad():
            raise RuntimeError("failure")

        def good():
            count[0] += 1

        plan.register("bad", bad, seconds=0.05)
        plan.register("good", good, seconds=0.05)
        plan.start()
        time.sleep(0.5)

        try:
            self.assertTrue(plan.active)
            self.assertGreaterEqual(count[0], 3)

            state = {t["name"]: t for t in plan.state()}
            self.assertGreaterEqual(state["bad"]["errors"], 3)
            self.assertIn("failure", state["bad"]["last_error"])
            self.assertIsNone(state["good"]["last_error"])
        finally:
            plan.stop()

        self.assertFalse(plan.active)

    def test_interval_in_hours_and_validation(self):
        plan = Scheduler()

        self.assertEqual(plan.register("a", lambda: None, hours=2).interval, 7200)

        with self.assertRaises(ValueError):
            plan.register("b", lambda: None)

    def test_tasks_by_default(self):
        plan = register_default_tasks(Scheduler())

        self.assertEqual(
            {t["name"] for t in plan.state()},
            {
                "daily_backup", "home_assistant_poll", "reminders", "event_reminders", "automations",
                "daily_summary", "maintenance", "expiries", "habits", "household_chores",
            },
        )


class TestPollHomeAssistant(CaseBrain):
    def test_saves_energy_and_detects_alerts(self):
        entities = {
            **energy_sensors(),
            "binary_sensor.kitchen_smoke": {
                "state": "on",
                "attributes": {"friendly_name": "Kitchen smoke", "device_class": "smoke"},
            },
        }
        ha = FakeHomeAssistant(entities=entities)
        ha.start()
        self.addCleanup(ha.stop)
        save_config(ha.url, FakeHomeAssistant.TOKEN)

        poll = HomeAssistantPoller()
        result = poll()

        self.assertIn("1 alerts", result)
        self.assertEqual(poll.alerts[0]["entity"], "binary_sensor.kitchen_smoke")
        self.assertEqual(len(Database().energy_readings()), 1)

    def test_without_home_assistant_it_does_nothing(self):
        self.assertIn("is not configured", HomeAssistantPoller()())


class TestMissingRecipe(CaseBrain):
    def test_compara_y_apunta_only_lo_that_missing(self):
        e = self.brain.tools.execute
        e("add_inventory", {"name": "Huevos", "quantity": 6, "location": "fridge"})
        e("add_inventory", {"name": "Salmón", "quantity": 1, "location": "freezer"})
        e("add_to_shopping", {"product": "cebollas", "quantity": 2})
        self.brain.modules.get("inventory").save_section("pantry", [{"name": "Tomate frito", "quantity": 0}])

        r = e(
            "add_recipe_missing_to_shopping",
            {"ingredients": "2 huevos\n200 g de harina\nsal\nTomates fritos\n1 cebolla\nsalmon ahumado\naceite de girasol", "recipe": "x"},
        )

        self.assertEqual([a["product"] for a in r["added_to_shopping"]], ["Tomates fritos", "aceite de girasol"])
        self.assertEqual(r["were_already_in_list"], ["cebolla"])
        self.assertEqual([a["ingredient"] for a in r["depleted"]], ["Tomates fritos"])
        self.assertEqual(
            {d["ingredient"]: d["en"] for d in r["already_available"]},
            {"huevos": "fridge", "harina": "staples", "sal": "staples", "salmon ahumado": "freezer"},
        )

        shopping = {i["product"] for i in e("show_shopping_list")["shopping_list"]}
        self.assertEqual(shopping, {"cebollas", "Tomates fritos", "aceite de girasol"})

    def test_no_confunde_sal_with_salmon_y_acepta_comas(self):
        r = self.brain.tools.execute("add_recipe_missing_to_shopping", {"ingredients": "salmón, sal, limones"})

        self.assertEqual([a["product"] for a in r["added_to_shopping"]], ["salmón", "limones"])

    def test_si_no_missing_nothing(self):
        r = self.brain.tools.execute("add_recipe_missing_to_shopping", {"ingredients": "sal, aceite, agua"})

        self.assertEqual(r["added_to_shopping"], [])
        self.assertIn("Nothing is missing", r["summary"])

    def test_text_empty(self):
        r = self.brain.tools.execute("add_recipe_missing_to_shopping", {"ingredients": "  "})

        self.assertIn("error", r)


class TestBackups(CaseBrain):
    def prepare(self):
        e = self.brain.tools.execute
        e("save_weight", {"weight": 80, "date": "2026-01-01"})
        e("add_inventory", {"name": "Leche", "quantity": 2})

    def test_creates_a_zip_with_the_right_format_and_content(self):
        self.prepare()
        r = self.brain.tools.execute("create_backup")["backup"]

        path = Config.DATA / "backups" / r["file"]
        self.assertRegex(r["file"], r"^backup_\d{8}_\d{6}\.zip$")

        with zipfile.ZipFile(path) as z:
            names = z.namelist()

        self.assertIn("brain.db", names)
        self.assertIn("inventory/inventory.json", names)
        self.assertIn("MANIFEST.json", names)
        self.assertFalse(any(n.startswith("backups/") for n in names))

    def test_rotation_keeps_five(self):
        self.prepare()

        for _ in range(8):
            self.brain.tools.execute("create_backup")

        backups = self.brain.tools.execute("show_backups")["backups"]

        self.assertEqual(len(backups), 5)
        self.assertEqual(len(list((Config.DATA / "backups").glob("backup_*.zip"))), 5)

    def test_restore_returns_to_the_previous_state(self):
        self.prepare()
        e = self.brain.tools.execute
        name = e("create_backup")["backup"]["file"]

        e("save_weight", {"weight": 99, "date": "2026-02-02"})
        e("clear_inventory")

        r = e("restore_backup", {"name": name})["restored"]

        self.assertEqual(r["restored"], name)
        self.assertEqual(e("get_weight")["weight"], 80)
        self.assertTrue(e("show_inventory")["pantry"][0].startswith("Leche"))
        self.assertTrue((Config.DATA / "backups" / r["previous_backup"]).exists())

    def test_restores_the_latest_without_a_name(self):
        self.prepare()
        e = self.brain.tools.execute
        e("create_backup")
        e("clear_inventory")

        self.assertIn("restored", e("restore_backup"))
        self.assertIn("pantry", e("show_inventory"))

    def test_rejects_a_damaged_or_tampered_zip(self):
        self.prepare()
        e = self.brain.tools.execute
        name = e("create_backup")["backup"]["file"]
        path = Config.DATA / "backups" / name

        # Tampered content: does not match the manifest checksum
        tampered = Config.DATA / "backups" / "backup_20200101_000000.zip"

        with zipfile.ZipFile(path) as z, zipfile.ZipFile(tampered, "w") as new:
            for n in z.namelist():
                data = z.read(n)
                new.writestr(n, b"corrupted" if n == "inventory/inventory.json" else data)

        r = e("restore_backup", {"name": tampered.name})
        self.assertIn("Integrity", r["error"])

        # Not a ZIP
        trash = Config.DATA / "backups" / "backup_20190101_000000.zip"
        trash.write_bytes(b"not a zip")
        self.assertIn("not a valid ZIP", e("restore_backup", {"name": trash.name})["error"])

        # The current data is still intact after the rejections
        self.assertEqual(e("get_weight")["weight"], 80)

    def test_nonexistent_name_and_paths_outside_the_folder(self):
        self.prepare()
        e = self.brain.tools.execute
        e("create_backup")

        self.assertIn("does not exist", e("restore_backup", {"name": "../../etc/passwd"})["error"])

    def test_without_backups(self):
        self.assertIn("no backups", self.brain.tools.execute("restore_backup")["error"])

    def test_backs_up_if_due_and_does_not_duplicate(self):
        system = self.brain.modules.get("system")

        self.assertIsNotNone(system.backup_if_due())
        self.assertIsNone(system.backup_if_due())


class TestDocuments(CaseBrain):
    def setUp(self):
        super().setUp()

        folder = Config.DATA / "documents"
        folder.mkdir(parents=True)
        (folder / "washer_manual.md").write_text(
            "# Washer\n\nFor the wool program press button 3 for two seconds.\n\n## Filter\n\nClean the filter every month.\n",
            encoding="utf-8",
        )
        (folder / "boiler.txt").write_text("The boiler is purged by opening the red valve. Ideal pressure 1.5 bar.", encoding="cp1252")
        (folder / "wifi.json").write_text(json.dumps({"router": {"key": "abc123", "place": "living room"}}), encoding="utf-8")
        (folder / "ignored.pdf").write_bytes(b"%PDF")

    def test_searches_with_bm25(self):
        r = self.brain.tools.execute("search_documents", {"query": "how do I clean the washer filter?"})

        self.assertEqual(r["results"][0]["document"], "washer_manual.md")
        self.assertIn("filter", r["results"][0]["text"].lower())

        r = self.brain.tools.execute("search_documents", {"query": "router key"})
        self.assertEqual(r["results"][0]["document"], "wifi.json")

        r = self.brain.tools.execute("search_documents", {"query": "purge boiler pressure"})
        self.assertEqual(r["results"][0]["document"], "boiler.txt")

    def test_no_results_and_empty_query(self):
        e = self.brain.tools.execute

        self.assertIn("I found nothing", e("search_documents", {"query": "nuclear submarine"})["message"])
        self.assertIn("error", e("search_documents", {"query": "of the a"}))

    def test_reads_list_and_page(self):
        e = self.brain.tools.execute

        names = [d["name"] for d in e("read_document")["documents"]]
        self.assertEqual(names, ["boiler.txt", "washer_manual.md", "wifi.json"])  # no .pdf

        r = e("read_document", {"name": "boiler"})
        self.assertIn("red valve", r["text"])  # cp1252 decoded fine

        longer = Config.DATA / "documents" / "long.txt"
        longer.write_text("word " * 2000, encoding="utf-8")
        page = e("read_document", {"name": "long.txt"})
        self.assertIn("next_from", page)
        self.assertEqual(e("read_document", {"name": "long", "since": page["next_from"]})["since"], page["next_from"])

    def test_cannot_leave_the_folder(self):
        self.assertIn("error", self.brain.tools.execute("read_document", {"name": "../data/health"}))

    def test_the_index_updates_itself(self):
        e = self.brain.tools.execute
        self.assertIn("message", e("search_documents", {"query": "thermostat"}))

        (Config.DATA / "documents" / "thermostat.md").write_text("The thermostat is set with the dial.", encoding="utf-8")

        self.assertEqual(e("search_documents", {"query": "thermostat"})["results"][0]["document"], "thermostat.md")

    def test_without_a_documents_folder(self):
        import shutil

        shutil.rmtree(Config.DATA / "documents")

        self.assertIn("There are no documents", self.brain.tools.execute("search_documents", {"query": "something"})["message"])


class TestWebSystem(CaseBrain):
    def setUp(self):
        super().setUp()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain))
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def ask(self, method, path, body=None):
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json", "Host": f"127.0.0.1:{self.port}"}
        con.request(method, path, json.dumps(body) if body is not None else None, headers)
        r = con.getresponse()
        data = json.loads(r.read().decode("utf-8"))
        con.close()
        return r.status, data

    def test_create_list_y_restore(self):
        self.brain.tools.execute("save_weight", {"weight": 70, "date": "2026-01-01"})

        code, r = self.ask("POST", "/api/backup/create", {})
        self.assertEqual(code, 200)

        code, state = self.ask("GET", "/api/system")
        self.assertEqual(len(state["backups"]), 1)
        self.assertIn("tasks", state)

        self.brain.tools.execute("save_weight", {"weight": 95, "date": "2026-03-01"})
        code, r = self.ask("POST", "/api/backup/restore", {"name": state["backups"][0]["name"]})
        self.assertEqual(code, 200)
        self.assertEqual(self.brain.tools.execute("get_weight")["weight"], 70)

        self.assertEqual(self.ask("POST", "/api/backup/restore", {"name": "backup_19990101_000000.zip"})[0], 400)
        self.assertEqual(self.ask("POST", "/api/backup/restore", {})[0], 400)


if __name__ == "__main__":
    unittest.main()
