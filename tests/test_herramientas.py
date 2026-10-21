import unittest

from tests.helpers import CasoBrain


class TestHerramientas(CasoBrain):
    def test_estan_registradas_las_herramientas_esperadas(self):
        nombres = {h["nombre"] for h in self.brain.tools.listar()}

        esperadas = {
            "guardar_peso",
            "obtener_peso",
            "peso_en_fecha",
            "historial_peso",
            "anadir_inventario",
            "ver_inventario",
            "anadir_a_compra",
            "ver_lista_compra",
            "anadir_evento",
            "ver_agenda",
            "guardar_produccion_solar",
            "recordar",
            "consultar_memoria",
        }

        self.assertTrue(esperadas <= nombres, esperadas - nombres)

    def test_coma_decimal_y_numeros_como_texto(self):
        resultado = self.brain.tools.ejecutar("guardar_peso", {"peso": "88,4", "fecha": "2026-08-10"})

        self.assertEqual(resultado["guardado"]["peso"], 88.4)

    def test_fecha_opcional(self):
        resultado = self.brain.tools.ejecutar("guardar_peso", {"peso": 80, "fecha": ""})

        self.assertEqual(len(resultado["guardado"]["fecha"]), 10)

    def test_falta_argumento_obligatorio(self):
        with self.assertRaises(ValueError):
            self.brain.tools.ejecutar("guardar_peso", {})

    def test_argumento_inventado_se_ignora(self):
        # Los modelos pequeños inventan argumentos; lo importante es que la acción se haga.
        resultado = self.brain.tools.ejecutar("guardar_peso", {"peso": 80, "color": "rojo"})

        self.assertIn("guardado", resultado)

    def test_herramienta_inexistente(self):
        with self.assertRaises(ValueError):
            self.brain.tools.ejecutar("hackear_la_nasa")

    def test_tipo_incorrecto(self):
        with self.assertRaises(ValueError):
            self.brain.tools.ejecutar("guardar_peso", {"peso": "mucho"})

    def test_herramienta_sin_argumentos_ignora_los_que_envie_el_modelo(self):
        self.brain.tools.ejecutar("guardar_peso", {"peso": 80, "fecha": "2026-08-10"})

        self.assertEqual(self.brain.tools.ejecutar("obtener_peso", {"inventado": 1})["peso"], 80.0)

    def test_esquemas_para_ollama(self):
        esquemas = {e["function"]["name"]: e for e in self.brain.tools.esquemas()}

        parametros = esquemas["guardar_peso"]["function"]["parameters"]

        self.assertEqual(esquemas["guardar_peso"]["type"], "function")
        self.assertEqual(parametros["properties"]["peso"]["type"], "number")
        self.assertEqual(parametros["required"], ["peso"])
        self.assertEqual(esquemas["historial_peso"]["function"]["parameters"]["properties"]["cantidad"]["type"], "integer")


if __name__ == "__main__":
    unittest.main()
