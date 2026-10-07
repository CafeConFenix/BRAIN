import unittest

from tests.helpers import CasoBrain, llamada, texto


def mensajes_de_usuario(peticion):
    return [m["content"] for m in peticion["messages"] if m["role"] == "user"]


class TestIA(CasoBrain):
    def test_respuesta_simple(self):
        self.ollama.respuestas = [texto("Soy BRAIN.")]

        self.assertEqual(self.brain.ai.preguntar("¿Quién eres?"), "Soy BRAIN.")

    def test_elige_el_modelo_instalado(self):
        self.assertEqual(self.brain.ai.ollama.resolver_modelo(), "qwen3:4b")

    def test_se_envian_herramientas_y_contexto(self):
        self.ollama.respuestas = [texto("ok")]

        self.brain.ai.preguntar("hola")

        peticion = self.ollama.peticiones[0]

        self.assertGreater(len(peticion["tools"]), 5)
        self.assertEqual(peticion["options"]["num_ctx"], 8192)
        self.assertFalse(peticion["stream"])

    def test_el_prompt_incluye_fecha_personalidad_y_memoria(self):
        self.brain.modules.obtener("memoria").recordar("Me llamo Luis", "personas")

        self.ollama.respuestas = [texto("ok")]

        self.brain.ai.preguntar("hola")

        sistema = self.ollama.peticiones[0]["messages"][0]["content"]

        self.assertIn("FECHA Y HORA ACTUALES", sistema)
        self.assertIn("Me llamo Luis", sistema)
        self.assertIn("BRAIN", sistema)

    def test_usa_una_herramienta_y_responde_con_el_resultado(self):
        self.ollama.respuestas = [
            llamada("guardar_peso", peso="88,4", fecha="2026-08-10"),
            texto("Anotado: 88,4 kg."),
        ]

        respuesta = self.brain.ai.preguntar("Hoy peso 88,4")

        self.assertEqual(respuesta, "Anotado: 88,4 kg.")
        self.assertEqual(self.brain.modules.obtener("salud").peso_actual()["peso"], 88.4)
        self.assertEqual([h["nombre"] for h in self.brain.ai.herramientas_usadas], ["guardar_peso"])

        # La segunda petición lleva el resultado de la herramienta.
        roles = [m["role"] for m in self.ollama.peticiones[1]["messages"]]

        self.assertEqual(roles[-2:], ["assistant", "tool"])

    def test_encadena_varias_herramientas(self):
        self.ollama.respuestas = [
            llamada("anadir_a_compra", producto="leche", cantidad=2),
            llamada("anadir_a_compra", producto="pan"),
            llamada("ver_lista_compra"),
            texto("Tienes leche y pan en la lista."),
        ]

        respuesta = self.brain.ai.preguntar("Apunta leche y pan y dime qué hay")

        self.assertIn("leche", respuesta)
        self.assertEqual(len(self.brain.modules.obtener("compras").lista()), 2)
        self.assertEqual(len(self.brain.ai.herramientas_usadas), 3)

    def test_error_de_herramienta_se_devuelve_al_modelo(self):
        self.ollama.respuestas = [
            llamada("guardar_peso", peso="muchísimo"),
            texto("Ese peso no es válido, ¿cuánto pesas?"),
        ]

        respuesta = self.brain.ai.preguntar("Hoy peso muchísimo")

        self.assertIn("no es válido", respuesta)

        mensaje_tool = self.ollama.peticiones[1]["messages"][-1]

        self.assertEqual(mensaje_tool["role"], "tool")
        self.assertIn("error", mensaje_tool["content"])
        self.assertIsNone(self.brain.modules.obtener("salud").peso_actual())

    def test_herramienta_inventada(self):
        self.ollama.respuestas = [llamada("hackear_la_nasa"), texto("No puedo hacer eso.")]

        self.assertEqual(self.brain.ai.preguntar("hackea"), "No puedo hacer eso.")

    def test_el_modelo_responde_json_en_texto(self):
        self.ollama.respuestas = [
            texto('```json\n{"accion": "usar_herramienta", "nombre": "guardar_peso", '
                  '"argumentos": {"peso": 87, "fecha": "2026-08-11"}}\n```'),
            texto("Guardado: 87 kg."),
        ]

        respuesta = self.brain.ai.preguntar("Hoy peso 87")

        self.assertEqual(respuesta, "Guardado: 87 kg.")
        self.assertEqual(self.brain.modules.obtener("salud").peso_actual()["peso"], 87.0)

    def test_modelo_sin_herramientas_nativas_pasa_a_modo_texto(self):
        self.ollama.respuestas = [
            ("error", 400, "registry.ollama.ai/library/gemma:2b does not support tools"),
            texto('{"accion": "usar_herramienta", "nombre": "obtener_peso", "argumentos": {}}'),
            texto("Aún no tienes ningún peso."),
        ]

        respuesta = self.brain.ai.preguntar("¿Cuánto peso?")

        self.assertEqual(respuesta, "Aún no tienes ningún peso.")

        # La petición que se repite ya no lleva "tools" y la lista va en el prompt.
        repetida = self.ollama.peticiones[1]

        self.assertNotIn("tools", repetida)
        self.assertIn("HERRAMIENTAS DISPONIBLES", repetida["messages"][0]["content"])

        # La siguiente pregunta recuerda que ese modelo no admite herramientas.
        self.ollama.respuestas = [texto("ok")]

        self.brain.ai.preguntar("otra")

        self.assertNotIn("tools", self.ollama.peticiones[-1])

    def test_no_se_queda_en_bucle(self):
        self.ollama.respuestas = [llamada("obtener_peso")] * 20

        respuesta = self.brain.ai.preguntar("bucle")

        self.assertIn("a medias", respuesta)
        self.assertLessEqual(len(self.ollama.peticiones), self.brain.ai.MAX_PASOS)

    def test_quita_el_razonamiento_interno_de_qwen(self):
        self.ollama.respuestas = [texto("<think>pienso...</think>Hola Luis.")]

        self.assertEqual(self.brain.ai.preguntar("hola"), "Hola Luis.")

    def test_sin_modelos_instalados(self):
        from brain.ai.ollama import OllamaError

        self.ollama.modelos.clear()

        with self.assertRaises(OllamaError):
            self.brain.ai.preguntar("hola")

    def test_modelo_pedido_que_no_existe(self):
        from brain.ai.ollama import OllamaError

        with self.assertRaises(OllamaError) as contexto:
            self.brain.ai.preguntar("hola", modelo="inventado:1b")

        self.assertIn("ollama pull inventado:1b", str(contexto.exception))

    def test_ollama_apagado_da_un_error_claro(self):
        from brain.ai.ollama import Ollama, OllamaError

        cliente = Ollama(url="http://127.0.0.1:9")

        self.assertFalse(cliente.servidor_activo())

        with self.assertRaises(OllamaError) as contexto:
            cliente.modelos()

        self.assertIn("Ollama", str(contexto.exception))


if __name__ == "__main__":
    unittest.main()
