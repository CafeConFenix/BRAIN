"""Pruebas en español del bloque de IA: detección de anuncios/recetas y prompt del sistema."""

from brain import i18n
from tests.helpers import CaseBrain, call, text


class TestEsIA(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def test_looks_like_announcement_in_spanish(self):
        from brain.ai.brain_ai import looks_like_announcement

        for announcement_text in (
            "Voy a revisar tu despensa para sugerirte una receta.",
            "Dejame comprobar que tienes en casa.",
            "Primero necesito revisar la nevera:",
            "Un momento, reviso el inventario.",
        ):
            self.assertTrue(looks_like_announcement(announcement_text), announcement_text)

        for response_text in (
            "Tortilla de patatas: 4 huevos, 3 patatas y aceite. 1. Pela las patatas...",
            "Hecho, he encendido la luz del salón.",
            "",
        ):
            self.assertFalse(looks_like_announcement(response_text), response_text)

    def test_asks_recipe_in_spanish(self):
        from brain.ai.brain_ai import asks_recipe

        for message in ("dame una receta para cenar", "¿qué puedo cocinar hoy?", "que hago de comer"):
            self.assertTrue(asks_recipe(message), message)

        self.assertFalse(asks_recipe("¿cuánto peso?"))

    def test_system_prompt_in_spanish(self):
        self.ollama.responses = [text("ok")]

        self.brain.ai.ask("hola")

        system = self.ollama.requests[0]["messages"][0]["content"]

        self.assertIn("Personalidad de BRAIN", system)
        self.assertIn("REGLAS", system)
        self.assertIn("FECHA Y HORA ACTUALES", system)

    def test_pantry_section_translated_in_spanish(self):
        self.brain.tools.execute("add_inventory", {"name": "huevos", "quantity": 6, "location": "nevera"})
        self.ollama.responses = [text("Tortilla: 3 huevos y aceite. 1. Bate los huevos...")]

        self.brain.ai.ask("dame una receta para cenar")

        system = self.ollama.requests[0]["messages"][0]["content"]

        self.assertIn("DESPENSA DEL USUARIO", system)
        self.assertIn("huevos", system)

    def test_only_announcing_is_told_to_do_it_now_in_spanish(self):
        self.ollama.responses = [
            text("Voy a revisar tu despensa para ver qué podemos hacer."),
            text("Pasta con tomate: 200 g de pasta y salsa de tomate. 1. Cuece la pasta..."),
        ]

        response = self.brain.ai.ask("hola, dame una receta de pasta")

        self.assertTrue(response.startswith("Pasta con tomate"))
        requirement = self.ollama.requests[1]["messages"][-1]
        self.assertEqual(requirement["role"], "user")
        self.assertIn("hazlo ahora", requirement["content"])

    def test_ollama_error_in_spanish(self):
        from brain.ai.ollama import Ollama, OllamaError

        client = Ollama(url="http://127.0.0.1:9")

        with self.assertRaises(OllamaError) as context:
            client.models()

        self.assertIn("No se puede conectar con Ollama", str(context.exception))

    def test_personality_base_is_loaded_in_spanish(self):
        from brain.core.knowledge_manager import KnowledgeManager

        personality = KnowledgeManager().personality()

        self.assertIn("Personalidad de BRAIN", personality)
        self.assertIn("No es un chatbot", personality)


if __name__ == "__main__":
    import unittest

    unittest.main()
