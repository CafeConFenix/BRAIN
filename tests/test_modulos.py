import unittest

from tests.helpers import CasoBrain


class TestModulos(CasoBrain):
    def modulo(self, nombre):
        return self.brain.modules.obtener(nombre)

    def test_se_cargan_todos_los_modulos(self):
        self.assertEqual(
            self.brain.modules.listar(),
            ["calendario", "compras", "domotica", "energia", "inventario", "memoria", "salud", "sensores"],
        )

    # -- salud ---------------------------------------------------------

    def test_peso_actualiza_el_mismo_dia(self):
        salud = self.modulo("salud")

        salud.guardar_peso(90, "2026-08-01")
        salud.guardar_peso(89, "2026-08-01")

        self.assertEqual(salud.historial_peso(), [{"peso": 89.0, "fecha": "2026-08-01"}])

    def test_peso_actual_es_el_de_la_fecha_mas_reciente(self):
        salud = self.modulo("salud")

        salud.guardar_peso(88, "2026-08-10")
        salud.guardar_peso(90, "2026-08-01")

        self.assertEqual(salud.peso_actual()["fecha"], "2026-08-10")

    def test_peso_en_fecha_exacta_y_aproximada(self):
        salud = self.modulo("salud")

        salud.guardar_peso(90, "2026-08-01")
        salud.guardar_peso(88, "2026-08-10")

        self.assertTrue(salud.peso_en("2026-08-01")["exacto"])

        aproximado = salud.peso_en("2026-08-05")

        self.assertFalse(aproximado["exacto"])
        self.assertEqual(aproximado["peso"], 90.0)
        self.assertIsNone(salud.peso_en("2026-07-01"))

    def test_peso_invalido(self):
        with self.assertRaises(ValueError):
            self.modulo("salud").guardar_peso(5, "2026-08-01")

        with self.assertRaises(ValueError):
            self.modulo("salud").guardar_peso(80, "no es una fecha")

    def test_fechas_en_formato_español(self):
        salud = self.modulo("salud")

        salud.guardar_peso(80, "05/08/2026")

        self.assertEqual(salud.peso_actual()["fecha"], "2026-08-05")

    # -- inventario ----------------------------------------------------

    def test_inventario_suma_y_resta(self):
        inv = self.modulo("inventario")

        inv.añadir("Leche", 2, "nevera")
        inv.añadir("leche", 1, "frigorífico")

        self.assertEqual(inv.listar("frigorifico")["frigorifico"][0]["cantidad"], 3)

        inv.quitar("LECHE", 1)

        self.assertEqual(inv.buscar("lec")[0]["cantidad"], 2)

        inv.quitar("leche", 5)

        self.assertEqual(inv.buscar("leche"), [])

    def test_inventario_ubicacion_desconocida_va_a_la_despensa(self):
        inv = self.modulo("inventario")

        self.assertEqual(inv.añadir("pan", 1, "sitio raro")["ubicacion"], "despensa")
        self.assertEqual(inv.añadir("llave", 1, "garaje")["ubicacion"], "herramientas")

        with self.assertRaises(ValueError):
            inv.normalizar_ubicacion("sitio raro", estricta=True)

    def test_inventario_quitar_inexistente(self):
        with self.assertRaises(ValueError):
            self.modulo("inventario").quitar("unicornio")

    # -- compras -------------------------------------------------------

    def test_lista_de_la_compra(self):
        compras = self.modulo("compras")

        compras.añadir("pan", 1)
        compras.añadir("Pan", 2)

        self.assertEqual(compras.lista(), [{"producto": "pan", "cantidad": 3}])

        compras.comprado("pan")

        self.assertEqual(compras.lista(), [])
        self.assertEqual(len(compras.historial()), 1)

        with self.assertRaises(ValueError):
            compras.comprado("pan")

    # -- calendario ----------------------------------------------------

    def test_agenda(self):
        cal = self.modulo("calendario")

        cal.añadir_evento("Dentista", "hoy", "9.30")
        cal.añadir_evento("Evento lejano", "2999-01-01")
        cal.añadir_tarea("Pagar la luz")

        agenda = cal.agenda(7)

        self.assertEqual([e["titulo"] for e in agenda["eventos"]], ["Dentista"])
        self.assertEqual(agenda["eventos"][0]["hora"], "09:30")
        self.assertEqual(len(agenda["tareas_pendientes"]), 1)

        cal.completar_tarea("luz")

        self.assertEqual(cal.agenda(7)["tareas_pendientes"], [])

    def test_hora_invalida(self):
        with self.assertRaises(ValueError):
            self.modulo("calendario").añadir_evento("X", "hoy", "25:99")

    # -- energía -------------------------------------------------------

    def test_produccion_solar(self):
        energia = self.modulo("energia")

        energia.registrar_produccion(30, "2026-08-01")
        energia.registrar_produccion(40, "2026-08-02")
        energia.registrar_produccion(50, "2026-08-02")

        resultado = energia.produccion(7)

        self.assertEqual(resultado["total_kwh"], 80.0)
        self.assertEqual(resultado["media_kwh"], 40.0)

    # -- memoria -------------------------------------------------------

    def test_memoria(self):
        memoria = self.modulo("memoria")

        memoria.recordar("Mi hermana se llama Ana", "persona")

        repetido = memoria.recordar("mi hermana se llama ana", "personas")

        self.assertTrue(repetido["ya_existia"])
        self.assertIn("Ana", memoria.resumen_para_ia())

        memoria.olvidar("hermana")

        self.assertEqual(memoria.resumen_para_ia(), "")

        with self.assertRaises(ValueError):
            memoria.olvidar("nada")

    # -- sensores ------------------------------------------------------

    def test_sensores(self):
        sensores = self.modulo("sensores")

        self.assertIsNone(sensores.ultima("temperatura"))

        sensores.registrar("temp", 21.5, "salón")

        self.assertEqual(sensores.ultima("temperatura")["valor"], 21.5)

        with self.assertRaises(ValueError):
            sensores.registrar("radiacion", 1)


if __name__ == "__main__":
    unittest.main()
