import unittest
from datetime import date

from brain.core.config import Config
from brain.modules.appliances import Appliances, add_months
from tests.helpers import CaseBrain


class TestAppliances(CaseBrain):
    def setUp(self):
        super().setUp()
        self.e = self.brain.tools.execute

    def test_save_complete_and_list(self):
        r = self.e("add_appliance", {"name": "Washer", "brand": "Bosch", "model": "WAN28258ES", "purchase_date": "2025-03-15", "warranty_months": 36})["saved"]
        self.assertEqual(r["warranty_until"], "2028-03-15")
        self.assertFalse(r["updated"])

        r = self.e("add_appliance", {"name": "washer", "location": "utility room"})["saved"]  # completes, does not overwrite
        self.assertTrue(r["updated"])
        self.assertEqual((r["brand"], r["location"]), ("Bosch", "utility room"))

        items = self.e("list_appliances")["appliances"]
        self.assertEqual(len(items), 1)
        self.assertIn("warranty", items[0]["warranty"])

    def test_errors_and_remove(self):
        self.assertIn("error", self.e("add_appliance", {"name": " "}))
        self.assertIn("error", self.e("add_appliance", {"name": "x", "warranty_months": 0}))
        self.assertIn("error", self.e("remove_appliance", {"name": "oven"}))

        self.e("add_appliance", {"name": "Oven"})
        self.assertEqual(self.e("remove_appliance", {"name": "oven"}), {"removed": "Oven"})
        self.assertIn("message", self.e("list_appliances"))

    def test_months_at_month_end(self):
        self.assertEqual(add_months(date(2025, 1, 31), 1), date(2025, 2, 28))
        self.assertEqual(add_months(date(2025, 11, 15), 3), date(2026, 2, 15))

    def test_warranties_by_expiry(self):
        self.e("add_appliance", {"name": "Fridge", "purchase_date": "2024-01-10", "warranty_months": 24})
        module = Appliances()

        self.assertEqual([a["name"] for a in module.expiring_warranties(30, today=date(2025, 12, 20))], ["Fridge"])
        self.assertEqual(module.expiring_warranties(30, today=date(2025, 6, 1)), [])
        self.assertIn("expired", module.warranty_state(module.devices()[0], today=date(2026, 6, 1)))

    def test_query_brings_the_record_and_the_manual(self):
        folder = Config.DATA / "documents"
        folder.mkdir(parents=True)
        (folder / "manual_bosch_washer.md").write_text(
            "# Bosch washer\n\n## Error E18\n\nError E18 means the drain is blocked. Clean the pump filter.\n",
            encoding="utf-8",
        )
        (folder / "boiler.txt").write_text("The boiler is bled by opening the red valve.", encoding="utf-8")
        self.e("add_appliance", {"name": "Washer", "brand": "Bosch", "model": "WAN28258ES"})

        r = self.e("query_appliance", {"name": "the washer", "problem": "shows error E18"})

        self.assertEqual(r["gadget"]["model"], "WAN28258ES")
        self.assertEqual(r["manual_fragments"][0]["document"], "manual_bosch_washer.md")

    def test_query_without_manuals_or_without_device(self):
        self.e("add_appliance", {"name": "Oven", "brand": "Teka"})

        self.assertEqual(self.e("query_appliance", {"name": "oven", "problem": "does not heat"})["manual_fragments"], [])
        self.assertIn("I have no appliance", self.e("query_appliance", {"name": "dryer"})["error"])


if __name__ == "__main__":
    unittest.main()
