import unittest

from tests.helpers import CasoBrain, llamada, texto


class TestConversacion(CasoBrain):
    def test_el_historial_viaja_a_la_ia(self):
        self.ollama.respuestas = [texto("Pesas 88 kg."), texto("El 5 de agosto pesabas 90.")]

        self.brain.conversacion.preguntar("¿Cuánto peso?")
        self.brain.conversacion.preguntar("¿Y el 5 de agosto?")

        mensajes = self.ollama.peticiones[1]["messages"]

        roles = [m["role"] for m in mensajes]

        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertEqual(mensajes[1]["content"], "¿Cuánto peso?")
        self.assertEqual(mensajes[2]["content"], "Pesas 88 kg.")

    def test_el_historial_se_recuerda_al_reabrir(self):
        self.ollama.respuestas = [texto("Hola Luis.")]

        self.brain.conversacion.preguntar("Hola")

        from brain.core import Brain

        otro = Brain(silencioso=True)

        self.assertEqual(
            otro.conversacion.mensajes(),
            [
                {"role": "user", "content": "Hola"},
                {"role": "assistant", "content": "Hola Luis."},
            ],
        )

    def test_limpiar_borra_tambien_del_disco(self):
        self.ollama.respuestas = [texto("Hola.")]

        self.brain.conversacion.preguntar("Hola")
        self.brain.conversacion.limpiar()

        from brain.core import Brain

        self.assertEqual(Brain(silencioso=True).conversacion.mensajes(), [])

    def test_limite_del_historial(self):
        self.ollama.respuestas = [texto(f"r{i}") for i in range(30)]

        for i in range(30):
            self.brain.conversacion.preguntar(f"p{i}")

        mensajes = self.brain.conversacion.mensajes()

        self.assertLessEqual(len(mensajes), 20)
        self.assertEqual(mensajes[0]["role"], "user")
        self.assertEqual(mensajes[-1]["content"], "r29")

    def test_si_falla_la_ia_no_se_guarda_el_mensaje(self):
        from brain.ai.ollama import OllamaError

        self.ollama.modelos.clear()

        with self.assertRaises(OllamaError):
            self.brain.conversacion.preguntar("Hola")

        self.assertEqual(self.brain.conversacion.mensajes(), [])

    def test_historial_dañado_no_rompe_el_arranque(self):
        self.brain.data.guardar("conversaciones", "historial", {"mensajes": [{"role": "raro"}, 5, None]})

        from brain.core import Brain

        self.assertEqual(Brain(silencioso=True).conversacion.mensajes(), [])

    def test_flujo_completo_peso_y_consulta_historica(self):
        salud = self.brain.modules.obtener("salud")

        salud.guardar_peso(189.2, "2026-08-05")
        salud.guardar_peso(188.5, "2026-08-10")

        self.ollama.respuestas = [
            llamada("peso_en_fecha", fecha="2026-08-05"),
            texto("El 5 de agosto pesabas 189,2 kg."),
        ]

        respuesta = self.brain.conversacion.preguntar("¿Cuánto pesaba el 5 de agosto?")

        self.assertIn("189,2", respuesta)

        resultado_herramienta = self.ollama.peticiones[1]["messages"][-1]["content"]

        self.assertIn("189.2", resultado_herramienta)


if __name__ == "__main__":
    unittest.main()
