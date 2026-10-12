import json

from brain.modules.inventario import parsear_lista
from tests.helpers import CasoBrain, llamada, texto

LISTA_REAL = """Aceite de oliva intenso Dia La Almazara del Olivar 5 L, 1 unidad
Arroz con leche Dia Caprichoso 4 x 125 g, 1 unidad
Leche entera Dia 1 L, 6 unidades
Garbanzos cocidos Dia 400 g, 2 unidades"""


class TestAnalizador(CasoBrain):
    def test_entiende_los_formatos_habituales(self):
        pares = dict(
            parsear_lista(
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

    def test_la_cantidad_no_se_confunde_con_el_tamano(self):
        pares = dict(parsear_lista(LISTA_REAL))

        self.assertEqual(pares["Aceite de oliva intenso Dia La Almazara del Olivar 5 L"], 1)
        self.assertEqual(pares["Arroz con leche Dia Caprichoso 4 x 125 g"], 1)
        self.assertEqual(pares["Leche entera Dia 1 L"], 6)

    def test_suma_repetidos(self):
        self.assertEqual(parsear_lista("leche\nLeche\n2 x leche"), [("leche", 4)])


class TestCargaMasiva(CasoBrain):
    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)

    def test_carga_una_lista_larga_de_una_vez(self):
        lista = "\n".join(f"Producto {i} Dia 500 g, {i % 3 + 1} unidades" for i in range(36))

        r = self.ejecutar("anadir_varios_inventario", productos=lista)

        self.assertEqual(r["total_productos"], 36)
        self.assertEqual(len(self.brain.modules.obtener("inventario").listar("despensa")["despensa"]), 36)

    def test_cantidad_con_texto_ya_no_falla(self):
        r = self.ejecutar("anadir_inventario", nombre="Leche", cantidad="1 unidad")

        self.assertEqual(r["guardado"]["cantidad"], 1)

        r = self.ejecutar("anadir_inventario", nombre="Arroz", cantidad="dos")
        self.assertEqual(r["guardado"]["cantidad"], 2)

        r = self.ejecutar("anadir_inventario", nombre="Harina", cantidad="1,5 kg")
        self.assertEqual(r["guardado"]["cantidad"], 1.5)

    def test_ubicacion_inventada_va_a_la_despensa(self):
        r = self.ejecutar("anadir_inventario", nombre="Sal", ubicacion="armario de la cocina")

        self.assertEqual(r["guardado"]["ubicacion"], "despensa")

    def test_ver_inventario_pidiendo_otro_sitio_no_dice_vacio(self):
        self.ejecutar("anadir_inventario", nombre="Sal", ubicacion="frigorifico")

        r = self.ejecutar("ver_inventario", ubicacion="despensa")

        self.assertIn("inventario", r)

    def test_la_ia_carga_una_lista_con_una_sola_llamada(self):
        self.ollama.respuestas = [
            llamada("anadir_varios_inventario", productos=LISTA_REAL, ubicacion="despensa"),
            texto("Hecho: he añadido 4 productos a la despensa."),
        ]

        respuesta = self.brain.conversacion.preguntar(LISTA_REAL)

        self.assertIn("4 productos", respuesta)
        self.assertEqual(len(self.brain.modules.obtener("inventario").listar("despensa")["despensa"]), 4)

    def test_aguanta_muchas_llamadas_seguidas(self):
        self.ollama.respuestas = [llamada("anadir_inventario", nombre=f"p{i}", cantidad="1 unidad") for i in range(10)] + [
            texto("Listo.")
        ]

        self.assertEqual(self.brain.conversacion.preguntar("añade 10 cosas"), "Listo.")
        self.assertEqual(len(self.brain.modules.obtener("inventario").listar("despensa")["despensa"]), 10)


class TestSeHaAcabado(CasoBrain):
    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)

    def test_pasa_de_la_despensa_a_la_compra(self):
        self.ejecutar("anadir_inventario", nombre="Leche entera", cantidad=2)

        r = self.ejecutar("se_ha_acabado", producto="leche")

        self.assertTrue(r["quitado_del_inventario"])
        self.assertEqual(self.brain.modules.obtener("inventario").buscar("leche"), [])

        compra = self.brain.modules.obtener("compras").lista()
        self.assertEqual([c["producto"] for c in compra], ["Leche entera"])

    def test_aunque_no_estuviera_en_el_inventario_se_apunta(self):
        r = self.ejecutar("se_ha_acabado", producto="Aceite")

        self.assertFalse(r["quitado_del_inventario"])
        self.assertEqual(self.brain.modules.obtener("compras").lista()[0]["producto"], "Aceite")

    def test_no_duplica_si_ya_estaba_en_la_compra(self):
        self.ejecutar("anadir_a_compra", producto="pan")
        self.ejecutar("se_ha_acabado", producto="pan")

        self.assertEqual(len(self.brain.modules.obtener("compras").lista()), 1)

    def test_gastar_lo_ultimo_lo_apunta_en_la_compra(self):
        self.ejecutar("anadir_inventario", nombre="Huevos", cantidad=2)

        r = self.ejecutar("quitar_inventario", nombre="huevos", cantidad=2)

        self.assertTrue(r["añadido_a_la_compra"])
        self.assertEqual(self.brain.modules.obtener("compras").lista()[0]["producto"], "Huevos")

    def test_gastar_algo_pero_que_queda_no_lo_apunta(self):
        self.ejecutar("anadir_inventario", nombre="Huevos", cantidad=6)
        self.ejecutar("quitar_inventario", nombre="huevos", cantidad=2)

        self.assertEqual(self.brain.modules.obtener("compras").lista(), [])

    def test_varias_a_la_compra(self):
        r = self.ejecutar("anadir_varias_a_compra", productos="leche, pan, 2 x huevos")

        self.assertEqual(r["total_productos"], 3)
        self.assertEqual(len(self.brain.modules.obtener("compras").lista()), 3)


class TestMemoria(CasoBrain):
    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)

    def test_tipo_desconocido_no_da_error(self):
        r = self.ejecutar("recordar", texto="Mi hermana se llama Ana", tipo="familia")

        self.assertEqual(r["guardado"]["tipo"], "contexto")

    def test_consultar_con_cualquier_palabra_muestra_todo(self):
        self.ejecutar("recordar", texto="Mi hermana se llama Ana", tipo="personas")

        for tipo in ("todo", "todos", "recuerdos", "lo que sabes"):
            self.assertIn("personas", self.ejecutar("consultar_memoria", tipo=tipo), tipo)

        self.assertIn("personas", self.ejecutar("consultar_memoria", tipo="persona"))


class TestPanelWeb(CasoBrain):
    def test_el_resumen_trae_la_despensa(self):
        from brain.web.servidor import construir_resumen

        self.brain.tools.ejecutar("anadir_varios_inventario", {"productos": "Leche, 2 unidades\nPan"})

        despensa = construir_resumen(self.brain)["despensa"]

        self.assertEqual({a["nombre"] for a in despensa}, {"Leche", "Pan"})
        self.assertEqual({a["ubicacion"] for a in despensa}, {"despensa"})
        json.dumps(despensa)
