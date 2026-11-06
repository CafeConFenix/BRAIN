"""Pruebas en español del reconocimiento de temas para elegir herramientas."""

import unittest

from brain.ai.relevant_tools import relevant_categories as c


class TestEsRelevantTools(unittest.TestCase):
    def test_recognizes_spanish_topics(self):
        self.assertEqual(c("enciende la luz del salón"), {"smart_home", "memory"})
        self.assertEqual(c("¿Qué puedo cocinar hoy?"), {"recipes", "memory"})
        self.assertIn("notices", c("recuérdame en 20 minutos sacar el pollo"))
        self.assertIn("appliances", c("la lavadora no arranca"))
        self.assertIn("system", c("haz una copia de seguridad"))
        self.assertIn("energy", c("¿cuánto estoy consumiendo?"))
