import unittest

from tests.helpers import CaseBrain


class TestTools(CaseBrain):
    def test_are_registered_las_tools_expected(self):
        names = {h["name"] for h in self.brain.tools.items()}

        expected = {
            "save_weight",
            "get_weight",
            "weight_on_date",
            "weight_history",
            "add_inventory",
            "show_inventory",
            "add_to_shopping",
            "show_shopping_list",
            "add_event",
            "show_agenda",
            "save_solar_production",
            "remember",
            "query_memory",
        }

        self.assertTrue(expected <= names, expected - names)

    def test_coma_decimal_y_numbers_as_text(self):
        result = self.brain.tools.execute("save_weight", {"weight": "88,4", "date": "2026-08-10"})

        self.assertEqual(result["saved"]["weight"], 88.4)

    def test_date_opcional(self):
        result = self.brain.tools.execute("save_weight", {"weight": 80, "date": ""})

        self.assertEqual(len(result["saved"]["date"]), 10)

    def test_missing_argument_required(self):
        with self.assertRaises(ValueError):
            self.brain.tools.execute("save_weight", {})

    def test_argument_inventado_self_ignora(self):
        # Los modelos pequeños inventan argumentos; lo importante es que la acción se haga.
        result = self.brain.tools.execute("save_weight", {"weight": 80, "color": "rojo"})

        self.assertIn("saved", result)

    def test_tool_nonexistent(self):
        with self.assertRaises(ValueError):
            self.brain.tools.execute("hackear_the_nasa")

    def test_type_incorrect(self):
        with self.assertRaises(ValueError):
            self.brain.tools.execute("save_weight", {"weight": "mucho"})

    def test_tool_without_arguments_ignora_los_that_envie_the_model(self):
        self.brain.tools.execute("save_weight", {"weight": 80, "date": "2026-08-10"})

        self.assertEqual(self.brain.tools.execute("get_weight", {"inventado": 1})["weight"], 80.0)

    def test_schemas_for_ollama(self):
        schemas = {e["function"]["name"]: e for e in self.brain.tools.schemas()}

        parameters = schemas["save_weight"]["function"]["parameters"]

        self.assertEqual(schemas["save_weight"]["type"], "function")
        self.assertEqual(parameters["properties"]["weight"]["type"], "number")
        self.assertEqual(parameters["required"], ["weight"])
        self.assertEqual(schemas["weight_history"]["function"]["parameters"]["properties"]["quantity"]["type"], "integer")


if __name__ == "__main__":
    unittest.main()
