"""Pruebas en español del bloque de despensa: inventario, compra y menú."""

from brain import i18n
from tests.helpers import CaseBrain

PANTRY_LIST = """- Café latte macchiato 250 ml: 2 unidades
- Bebida energética candy zero 500 ml: 2 unidades
- Filetes de contramuslo de pollo 600 g aprox.: 2 unidades
- Cogollos 3 unidades: 3 unids
- Tomate triturado 400 g: 4 unidades
- Leche desnatada pack 6 x 1 L: 1 unidad"""


class TestEsPantry(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_add_many_message_in_spanish(self):
        r = self.brain.conversation.ask(PANTRY_LIST)

        self.assertIn("Hecho: he añadido", r)

    def test_inventory_error_in_spanish(self):
        with self.assertRaises(ValueError) as err:
            self.execute("remove_from_inventory", name="unicornio")

        self.assertIn("No encuentro", str(err.exception))

    def test_staple_messages_in_spanish(self):
        with self.assertRaises(ValueError) as err:
            self.execute("remove_staple", name="unicornio")

        self.assertIn("no está entre los básicos", str(err.exception))

    def test_search_too_short_in_spanish(self):
        with self.assertRaises(ValueError) as err:
            self.execute("search_everything", text="a")

        self.assertIn("Escribe al menos dos letras", str(err.exception))

    def test_expiries_label_in_spanish(self):
        self.execute("add_inventory", name="Leche", quantity=1, location="fridge")
        self.execute("set_expiry", product="Leche", date="today")

        notice = self.brain.modules.get("inventory").warn_expiries()

        self.assertIn("caduca hoy", notice["message"])
        self.assertIn("Cosas que caducan pronto", notice["title"])
