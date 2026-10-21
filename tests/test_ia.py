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
        self.assertEqual(peticion["options"]["num_ctx"], 16384)
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


class TestNoSeQuedaEnAnuncios(CasoBrain):
    """El modelo debe responder o actuar, no decir "voy a revisar tu despensa" y parar."""

    def test_parece_anuncio(self):
        from brain.ai.brain_ai import parece_anuncio

        for texto_anuncio in (
            "Voy a revisar tu despensa para proponerte una receta.",
            "Déjame comprobar qué tienes en casa.",
            "Primero necesito revisar lo que hay en la nevera:",
            "Un momento, reviso el inventario.",
        ):
            self.assertTrue(parece_anuncio(texto_anuncio), texto_anuncio)

        for texto_respuesta in (
            "Tortilla de patatas: 4 huevos, 3 patatas y aceite. 1. Pela las patatas...",
            "Hecho, he encendido la luz del salón.",
            "",
        ):
            self.assertFalse(parece_anuncio(texto_respuesta), texto_respuesta)

        self.assertFalse(parece_anuncio("Receta: " + "paso largo " * 80))

    def test_receta_lleva_la_despensa_ya_consultada(self):
        self.brain.tools.ejecutar("anadir_inventario", {"nombre": "huevos", "cantidad": 6, "ubicacion": "nevera"})
        self.ollama.respuestas = [texto("Tortilla: 3 huevos y aceite. 1. Bate los huevos...")]

        respuesta = self.brain.ai.preguntar("dame una receta para cenar")

        sistema = self.ollama.peticiones[0]["messages"][0]["content"]
        self.assertIn("DESPENSA DEL USUARIO", sistema)
        self.assertIn("huevos", sistema)
        self.assertTrue(respuesta.startswith("Tortilla"))
        self.assertEqual(len(self.ollama.peticiones), 1)  # una sola llamada al modelo
        self.assertEqual(self.brain.ai.herramientas_usadas[0]["nombre"], "ingredientes_disponibles")

    def test_despensa_vacia_tambien_da_receta(self):
        self.ollama.respuestas = [texto("Arroz blanco: 1 taza de arroz, 2 de agua, sal. 1. Hierve el agua...")]

        respuesta = self.brain.ai.preguntar("¿qué puedo cocinar hoy?")

        self.assertIn("Arroz", respuesta)
        self.assertIn("DESPENSA DEL USUARIO", self.ollama.peticiones[0]["messages"][0]["content"])

    def test_si_solo_anuncia_se_le_exige_que_conteste(self):
        self.ollama.respuestas = [
            texto("Voy a revisar tu despensa para ver qué podemos preparar."),
            texto("Pasta con tomate: 200 g de pasta y salsa de tomate. 1. Cuece la pasta..."),
        ]

        respuesta = self.brain.ai.preguntar("hola, dime una receta de pasta")

        self.assertTrue(respuesta.startswith("Pasta con tomate"))
        exigencia = self.ollama.peticiones[1]["messages"][-1]
        self.assertEqual(exigencia["role"], "user")
        self.assertIn("hazlo ahora", exigencia["content"])

    def test_no_se_repite_sin_fin(self):
        self.ollama.respuestas = [texto("Voy a revisar tu despensa.")] * 3

        respuesta = self.brain.ai.preguntar("qué tiempo hace en mi casa")

        self.assertEqual(respuesta, "Voy a revisar tu despensa.")  # tras 2 avisos se acepta lo que diga
        self.assertEqual(len(self.ollama.peticiones), 3)

    def test_otras_peticiones_no_consultan_la_despensa(self):
        self.ollama.respuestas = [texto("Peso guardado.")]
        self.brain.ai.preguntar("hoy peso 80")

        self.assertNotIn("DESPENSA DEL USUARIO", self.ollama.peticiones[0]["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
