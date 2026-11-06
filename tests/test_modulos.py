import unittest

from tests.helpers import CaseBrain


class TestModulos(CaseBrain):
    def module(self, name):
        return self.brain.modules.get(name)

    def test_self_cargan_all_los_modules(self):
        self.assertEqual(
            sorted(self.brain.modules.items()),
            ["appliances", "automations", "calendar", "chores", "documents", "energy", "expenses", "habits", "health", "inventory", "memory", "menu", "notices", "profiles", "routines", "sensors", "shopping", "smart_home", "summary", "system"],
        )

    # -- health ---------------------------------------------------------

    def test_weight_updates_on_the_same_day(self):
        health = self.module("health")

        health.save_weight(90, "2026-08-01")
        health.save_weight(89, "2026-08-01")

        self.assertEqual(health.weight_history(), [{"weight": 89.0, "date": "2026-08-01"}])

    def test_current_weight_is_the_most_recent_date(self):
        health = self.module("health")

        health.save_weight(88, "2026-08-10")
        health.save_weight(90, "2026-08-01")

        self.assertEqual(health.current_weight()["date"], "2026-08-10")

    def test_weight_on_date_exact_and_approximate(self):
        health = self.module("health")

        health.save_weight(90, "2026-08-01")
        health.save_weight(88, "2026-08-10")

        self.assertTrue(health.weight_at("2026-08-01")["exact"])

        approximate = health.weight_at("2026-08-05")

        self.assertFalse(approximate["exact"])
        self.assertEqual(approximate["weight"], 90.0)
        self.assertIsNone(health.weight_at("2026-07-01"))

    def test_invalid_weight(self):
        with self.assertRaises(ValueError):
            self.module("health").save_weight(5, "2026-08-01")

        with self.assertRaises(ValueError):
            self.module("health").save_weight(80, "not a date")

    def test_dates_in_day_month_year_format(self):
        health = self.module("health")

        health.save_weight(80, "05/08/2026")

        self.assertEqual(health.current_weight()["date"], "2026-08-05")

    # -- inventario ----------------------------------------------------

    def test_inventory_sum_y_resta(self):
        inv = self.module("inventory")

        inv.add("Leche", 2, "nevera")
        inv.add("leche", 1, "frigorífico")

        self.assertEqual(inv.items("fridge")["fridge"][0]["quantity"], 3)

        inv.remove("LECHE", 1)

        self.assertEqual(inv.search("lec")[0]["quantity"], 2)

        inv.remove("leche", 5)

        self.assertEqual(inv.search("leche"), [])

    def test_inventory_location_unknown_va_a_the_pantry(self):
        inv = self.module("inventory")

        self.assertEqual(inv.add("pan", 1, "sitio raro")["location"], "pantry")
        self.assertEqual(inv.add("llave", 1, "garaje")["location"], "tools")

        with self.assertRaises(ValueError):
            inv.normalize_location("sitio raro", strict=True)

    def test_inventory_remove_nonexistent(self):
        with self.assertRaises(ValueError):
            self.module("inventory").remove("unicornio")

    # -- compras -------------------------------------------------------

    def test_list_of_the_shopping(self):
        shopping = self.module("shopping")

        shopping.add("pan", 1)
        shopping.add("Pan", 2)

        self.assertEqual(shopping.items(), [{"product": "pan", "quantity": 3}])

        shopping.bought("pan")

        self.assertEqual(shopping.items(), [])
        self.assertEqual(len(shopping.history()), 1)

        with self.assertRaises(ValueError):
            shopping.bought("pan")

    # -- calendario ----------------------------------------------------

    def test_agenda(self):
        cal = self.module("calendar")

        cal.add_event("Dentista", "hoy", "9.30")
        cal.add_event("Evento lejano", "2999-01-01")
        cal.add_task("Pagar la luz")

        agenda = cal.agenda(7)

        self.assertEqual([e["title"] for e in agenda["events"]], ["Dentista"])
        self.assertEqual(agenda["events"][0]["hour"], "09:30")
        self.assertEqual(len(agenda["pending_tasks"]), 1)

        cal.complete_task("luz")

        self.assertEqual(cal.agenda(7)["pending_tasks"], [])

    def test_hour_invalid(self):
        with self.assertRaises(ValueError):
            self.module("calendar").add_event("X", "hoy", "25:99")

    # -- energía -------------------------------------------------------

    def test_production_solar(self):
        energy = self.module("energy")

        energy.record_production(30, "2026-08-01")
        energy.record_production(40, "2026-08-02")
        energy.record_production(50, "2026-08-02")

        result = energy.production(7)

        self.assertEqual(result["total_kwh"], 80.0)
        self.assertEqual(result["average_kwh"], 40.0)

    # -- memoria -------------------------------------------------------

    def test_memory(self):
        memory = self.module("memory")

        memory.remember("Mi hermana se llama Ana", "person")

        repeated = memory.remember("mi hermana se llama ana", "people")

        self.assertTrue(repeated["already_existed"])
        self.assertIn("Ana", memory.summary_for_ai())

        memory.forget("hermana")

        self.assertEqual(memory.summary_for_ai(), "")

        with self.assertRaises(ValueError):
            memory.forget("nada")

    # -- sensores ------------------------------------------------------

    def test_sensores(self):
        sensors = self.module("sensors")

        self.assertIsNone(sensors.last("temperature"))

        sensors.record("temp", 21.5, "living room")

        self.assertEqual(sensors.last("temperature")["value"], 21.5)

        with self.assertRaises(ValueError):
            sensors.record("radiation", 1)


if __name__ == "__main__":
    unittest.main()
