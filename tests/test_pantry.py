import json

from brain.modules.inventory import parse_list
from tests.helpers import CaseBrain, call, text

REAL_LIST = """Aceite de oliva intenso Dia La Almazara del Olivar 5 L, 1 unidad
Arroz con leche Dia Caprichoso 4 x 125 g, 1 unidad
Leche entera Dia 1 L, 6 unidades
Garbanzos cocidos Dia 400 g, 2 unidades"""


class TestAnalyzer(CaseBrain):
    def test_understands_the_usual_formats(self):
        pares = dict(
            parse_list(
                "- Leche entera, 2 unidades\n2 x huevos\nPan x3\nSal\n1. Yogur natural 4 uds\nAtún, 6 latas; Arroz, 3".replace(
                    "\\\n", "\n"
                )
            )
        )

        self.assertEqual(pares["Leche entera"], 2)
        self.assertEqual(pares["huevos"], 2)
        self.assertEqual(pares["Pan"], 3)
        self.assertEqual(pares["Sal"], 1)
        self.assertEqual(pares["Yogur natural"], 4)
        self.assertEqual(pares["Atún"], 6)
        self.assertEqual(pares["Arroz"], 3)

    def test_the_quantity_is_not_confused_with_the_size(self):
        pares = dict(parse_list(REAL_LIST))

        self.assertEqual(pares["Aceite de oliva intenso Dia La Almazara del Olivar 5 L"], 1)
        self.assertEqual(pares["Arroz con leche Dia Caprichoso 4 x 125 g"], 1)
        self.assertEqual(pares["Leche entera Dia 1 L"], 6)

    def test_sum_repetidos(self):
        self.assertEqual(parse_list("leche\nLeche\n2 x leche"), [("leche", 4)])


class TestLoadBulk(CaseBrain):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_load_a_long_list_at_once(self):
        items = "\n".join(f"Producto {i} Dia 500 g, {i % 3 + 1} unidades" for i in range(36))

        r = self.execute("add_many_to_inventory", products=items)

        self.assertEqual(r["total_products"], 36)
        self.assertEqual(len(self.brain.modules.get("inventory").items("pantry")["pantry"]), 36)

    def test_quantity_with_existing_text_does_not_fail(self):
        r = self.execute("add_inventory", name="Leche", quantity="1 unidad")

        self.assertEqual(r["saved"]["quantity"], 1)

        r = self.execute("add_inventory", name="Arroz", quantity="dos")
        self.assertEqual(r["saved"]["quantity"], 2)

        r = self.execute("add_inventory", name="Harina", quantity="1,5 kg")
        self.assertEqual(r["saved"]["quantity"], 1.5)

    def test_made_up_location_goes_to_the_pantry(self):
        r = self.execute("add_inventory", name="Sal", location="armario de la cocina")

        self.assertEqual(r["saved"]["location"], "pantry")

    def test_viewing_inventory_for_another_place_does_not_say_empty(self):
        self.execute("add_inventory", name="Sal", location="fridge")

        r = self.execute("show_inventory", location="pantry")

        self.assertIn("inventory", r)

    def test_the_ai_loads_a_list_with_a_single_call(self):
        self.ollama.responses = [
            call("add_many_to_inventory", products=REAL_LIST, location="pantry"),
            text("Hecho: he añadido 4 productos a la despensa."),
        ]

        response = self.brain.conversation.ask(REAL_LIST)

        self.assertIn("4 products", response)
        self.assertEqual(len(self.brain.modules.get("inventory").items("pantry")["pantry"]), 4)

    def test_aguanta_muchas_calls_seguidas(self):
        self.ollama.responses = [call("add_inventory", name=f"p{i}", quantity="1 unidad") for i in range(10)] + [
            text("Listo.")
        ]

        self.assertEqual(self.brain.conversation.ask("añade 10 cosas"), "Listo.")
        self.assertEqual(len(self.brain.modules.get("inventory").items("pantry")["pantry"]), 10)


class TestSelfHaFinished(CaseBrain):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_moves_from_the_pantry_to_the_shopping_list(self):
        self.execute("add_inventory", name="Leche entera", quantity=2)

        r = self.execute("ran_out", product="leche")

        self.assertTrue(r["removed_from_inventory"])
        self.assertEqual(self.brain.modules.get("inventory").search("leche"), [])

        shopping = self.brain.modules.get("shopping").items()
        self.assertEqual([c["product"] for c in shopping], ["Leche entera"])

    def test_even_if_not_in_the_inventory_it_is_logged(self):
        r = self.execute("ran_out", product="Aceite")

        self.assertFalse(r["removed_from_inventory"])
        self.assertEqual(self.brain.modules.get("shopping").items()[0]["product"], "Aceite")

    def test_does_not_duplicate_if_already_on_the_shopping_list(self):
        self.execute("add_to_shopping", product="pan")
        self.execute("ran_out", product="pan")

        self.assertEqual(len(self.brain.modules.get("shopping").items()), 1)

    def test_using_the_last_one_logs_it_on_the_shopping_list(self):
        self.execute("add_inventory", name="Huevos", quantity=2)

        r = self.execute("remove_from_inventory", name="huevos", quantity=2)

        self.assertTrue(r["added_to_shopping"])
        self.assertEqual(self.brain.modules.get("shopping").items()[0]["product"], "Huevos")

    def test_using_some_but_some_remaining_does_not_log_it(self):
        self.execute("add_inventory", name="Huevos", quantity=6)
        self.execute("remove_from_inventory", name="huevos", quantity=2)

        self.assertEqual(self.brain.modules.get("shopping").items(), [])

    def test_several_to_the_shopping_list(self):
        r = self.execute("add_many_to_shopping", products="leche, pan, 2 x huevos")

        self.assertEqual(r["total_products"], 3)
        self.assertEqual(len(self.brain.modules.get("shopping").items()), 3)


class TestMemory(CaseBrain):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_unknown_kind_does_not_raise_an_error(self):
        r = self.execute("remember", text="My sister is called Ana", kind="whatever")

        self.assertEqual(r["saved"]["kind"], "context")

    def test_query_with_any_word_shows_everything(self):
        self.execute("remember", text="My sister is called Ana", kind="people")

        for kind in ("all", "everything", "memories", "what you know"):
            self.assertIn("people", self.execute("query_memory", kind=kind), kind)

        self.assertIn("people", self.execute("query_memory", kind="person"))


class TestPanelWeb(CaseBrain):
    def test_the_summary_brings_the_pantry(self):
        from brain.web.server import build_summary

        self.brain.tools.execute("add_many_to_inventory", {"products": "Leche, 2 unidades\nPan"})

        pantry = build_summary(self.brain)["pantry"]

        self.assertEqual({a["name"] for a in pantry}, {"Leche", "Pan"})
        self.assertEqual({a["location"] for a in pantry}, {"pantry"})
        json.dumps(pantry)
