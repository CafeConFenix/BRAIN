import http.client
import json
import threading
import unittest
import zlib
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer

from brain.modules.documentos import DocumentoError
from brain.utils.buscador import buscar_todo
from brain.utils.pdf import extraer_texto
from brain.web.servidor import crear_manejador
from tests.helpers import CasoBrain


def pdf_de_prueba(frase):
    contenido = f"BT /F1 12 Tf 72 700 Td ({frase}) Tj ET".encode()
    flujo = zlib.compress(contenido)

    return b"%PDF-1.4\n1 0 obj\n<< /Filter /FlateDecode >>\nstream\n" + flujo + b"\nendstream\nendobj\ntrailer\n%%EOF"


def dias(n):
    return (date.today() + timedelta(days=n)).isoformat()


class TestPresupuesto(CasoBrain):
    def test_avisa_al_80_y_al_100_una_sola_vez(self):
        gastos = self.brain.modules.obtener("gastos")
        avisos = self.brain.modules.obtener("avisos")
        gastos.configurar_presupuesto(100)

        gastos.anadir(50, "super")
        self.assertEqual(avisos.listar(), [])

        gastos.anadir(35, "super")
        self.assertEqual([a["titulo"] for a in avisos.listar()], ["Presupuesto al 80 %"])

        gastos.anadir(1, "super")  # sigue en "aviso": no se repite
        self.assertEqual(len(avisos.listar()), 1)

        gastos.anadir(20, "super")
        self.assertIn("Presupuesto superado", [a["titulo"] for a in avisos.listar()])

    def test_estado_y_categorias(self):
        gastos = self.brain.modules.obtener("gastos")
        gastos.configurar_presupuesto(200, "ocio", 30)
        gastos.anadir(40, "cine")

        estado = gastos.estado_presupuesto()

        self.assertEqual(estado["porcentaje"], 20)
        self.assertEqual(estado["queda"], 160)
        self.assertEqual(estado["categorias"][0]["nivel"], "superado")

    def test_sin_presupuesto_no_avisa_ni_falla(self):
        gastos = self.brain.modules.obtener("gastos")
        gastos.anadir(500, "coche")

        self.assertFalse(gastos.estado_presupuesto()["configurado"])
        self.assertEqual(self.brain.modules.obtener("avisos").listar(), [])

    def test_importe_invalido_da_mensaje_claro(self):
        with self.assertRaises(ValueError) as c:
            self.brain.modules.obtener("gastos").configurar_presupuesto("mucho")

        self.assertIn("euros", str(c.exception))

    def test_herramientas(self):
        e = self.brain.tools.ejecutar
        e("fijar_presupuesto", {"total": "900"})
        e("anadir_gasto", {"importe": "90", "concepto": "luz"})

        self.assertEqual(e("ver_presupuesto")["porcentaje"], 10)


class TestCaducidades(CasoBrain):
    def setUp(self):
        super().setUp()
        self.inv = self.brain.modules.obtener("inventario")

    def test_por_caducar_ordena_y_clasifica(self):
        self.inv.añadir("yogur", 4, "frigorifico", dias(-1))
        self.inv.añadir("leche", 1, "frigorifico", dias(2))
        self.inv.añadir("arroz", 1, "despensa", dias(300))
        self.inv.añadir("sal", 1, "despensa")

        lista = self.inv.por_caducar(5)

        self.assertEqual([p["nombre"] for p in lista], ["yogur", "leche"])
        self.assertEqual(lista[0]["estado"], "caducado")
        self.assertEqual({p["nombre"]: p.get("caduca") for p in self.inv.todo()}["leche"], dias(2))

    def test_poner_y_quitar_caducidad(self):
        self.inv.añadir("queso", 1, "frigorifico")
        self.inv.poner_caducidad("queso", dias(1))
        self.assertEqual(self.inv.por_caducar(3)[0]["dias"], 1)

        self.inv.poner_caducidad("queso", "")
        self.assertEqual(self.inv.por_caducar(3), [])

        with self.assertRaises(ValueError):
            self.inv.poner_caducidad("unicornio", dias(1))

    def test_sumar_unidades_conserva_fecha(self):
        self.inv.añadir("leche", 1, "frigorifico", dias(2))
        self.inv.añadir("leche", 2, "frigorifico")

        self.assertEqual(self.inv.por_caducar(3)[0]["nombre"], "leche")

    def test_aviso_diario_una_sola_vez(self):
        self.inv.añadir("leche", 1, "frigorifico", dias(1))

        self.assertIsNotNone(self.inv.avisar_caducidades())
        self.assertIsNone(self.inv.avisar_caducidades())
        self.assertEqual(len(self.brain.modules.obtener("avisos").listar()), 1)

    def test_herramientas(self):
        e = self.brain.tools.ejecutar
        e("anadir_inventario", {"nombre": "nata", "cantidad": 1, "ubicacion": "frigorifico", "caduca": dias(1)})

        self.assertEqual(e("ver_caducidades")["productos"][0]["nombre"], "nata")

    def test_fecha_invalida(self):
        with self.assertRaises(ValueError):
            self.inv.añadir("nata", 1, "frigorifico", "algun dia")


class TestHabitosAviso(CasoBrain):
    def test_recuerda_solo_si_toca_y_no_esta_cumplido(self):
        h = self.brain.modules.obtener("habitos")
        h.crear("beber agua", 2, "vasos", "10:00")
        hoy = date.today()

        self.assertEqual(h.avisar_pendientes(datetime(hoy.year, hoy.month, hoy.day, 9, 59)), 0)
        self.assertEqual(h.avisar_pendientes(datetime(hoy.year, hoy.month, hoy.day, 10, 5)), 1)
        self.assertEqual(h.avisar_pendientes(datetime(hoy.year, hoy.month, hoy.day, 11, 0)), 0)  # ya avisado

    def test_no_avisa_si_ya_cumplido(self):
        h = self.brain.modules.obtener("habitos")
        h.crear("pastilla", 1, hora="08:00")
        h.anotar("pastilla")

        self.assertEqual(h.avisar_pendientes(datetime.now().replace(hour=23, minute=0)), 0)

    def test_hora_invalida(self):
        with self.assertRaises(ValueError):
            self.brain.modules.obtener("habitos").crear("x", 1, hora="25:99")

    def test_filtra_por_persona(self):
        h = self.brain.modules.obtener("habitos")
        h.crear("correr", 1, persona="Ana")
        h.crear("agua", 1)

        self.assertEqual([x["habito"] for x in h.estado(persona="Luis")["habitos"]], ["agua"])
        self.assertEqual(len(h.estado(persona="Ana")["habitos"]), 2)


class TestHogar(CasoBrain):
    def setUp(self):
        super().setUp()
        self.hogar = self.brain.modules.obtener("hogar")

    def test_el_turno_rota(self):
        self.hogar.crear("basura", "Ana, Luis, Marta", 2)

        self.assertEqual(self.hogar.listar()[0]["le_toca_a"], "Ana")
        self.hogar.hecha("basura")
        self.assertEqual(self.hogar.listar()[0]["le_toca_a"], "Luis")
        self.hogar.hecha("basura", "Marta")  # la hizo Marta: sigue Ana
        self.assertEqual(self.hogar.listar()[0]["le_toca_a"], "Ana")

    def test_programa_la_siguiente_vez(self):
        self.hogar.crear("fregar", "Ana, Luis", 3)
        t = self.hogar.hecha("fregar")

        self.assertEqual(t["proxima"], dias(3))
        self.assertFalse(t["toca_hoy"])

    def test_toca_hoy_y_aviso_una_vez(self):
        self.hogar.crear("basura", "Ana, Luis", 1)

        self.assertEqual(len(self.hogar.de_hoy()), 1)
        self.assertEqual(len(self.hogar.de_hoy("Luis")), 0)
        self.assertEqual(self.hogar.avisar_de_hoy(), 1)
        self.assertEqual(self.hogar.avisar_de_hoy(), 0)

    def test_saltar_turno_y_errores(self):
        self.hogar.crear("basura", "Ana, Luis", 1)
        self.assertEqual(self.hogar.saltar_turno("basura")["le_toca_a"], "Luis")

        self.hogar.crear("solo", "Ana", 1)

        with self.assertRaises(ValueError):
            self.hogar.saltar_turno("solo")

        with self.assertRaises(ValueError):
            self.hogar.hecha("inexistente")

        with self.assertRaises(ValueError):
            self.hogar.crear("x", "", 0)

    def test_crear_registra_a_las_personas(self):
        self.hogar.crear("basura", "Ana, Luis", 1)

        self.assertEqual(self.brain.modules.obtener("perfiles").nombres(), ["Ana", "Luis"])

    def test_herramientas(self):
        e = self.brain.tools.ejecutar
        e("crear_tarea_hogar", {"nombre": "basura", "personas": "Ana, Luis", "cada_dias": 2})
        e("tarea_hogar_hecha", {"nombre": "basura"})

        self.assertEqual(e("ver_tareas_hogar")["tareas"][0]["le_toca_a"], "Luis")
        self.assertEqual(e("personas_casa")["personas"], ["Ana", "Luis"])


class TestMenuYBuscador(CasoBrain):
    def test_menu_apunta_solo_lo_que_falta(self):
        self.brain.modules.obtener("inventario").añadir("lentejas", 1)
        menu = self.brain.modules.obtener("menu")
        menu.guardar("lunes comida: Lentejas | lentejas, chorizo\nmartes cena: Tortilla | huevos, patata")
        r = menu.añadir_faltantes_a_compra()

        self.assertNotIn("lentejas", r["añadidos"])
        self.assertIn("chorizo", r["añadidos"])
        self.assertEqual(menu.añadir_faltantes_a_compra()["añadidos"], [])

    def test_buscador_junta_varias_fuentes(self):
        m = self.brain.modules
        m.obtener("inventario").añadir("leche de avena", 1, "frigorifico")
        m.obtener("gastos").anadir(3, "leche")
        m.obtener("compras").añadir("leche")

        r = buscar_todo(m, "leche")

        self.assertEqual({g["tipo"] for g in r["grupos"]}, {"despensa", "gastos", "compra"})
        with self.assertRaises(ValueError):
            buscar_todo(m, "a")

    def test_herramienta_buscar(self):
        self.brain.modules.obtener("inventario").añadir("cafe", 1)

        self.assertEqual(self.brain.tools.ejecutar("buscar_en_todo", {"texto": "cafe"})["total"], 1)


class TestManuales(CasoBrain):
    def test_pdf_se_lee_y_se_busca(self):
        self.assertIn("garantia de dos anos", extraer_texto(pdf_de_prueba("La garantia de dos anos")))

        docs = self.brain.modules.obtener("documentos")
        docs.guardar_archivo("Manual horno.pdf", pdf_de_prueba("El horno se limpia con la funcion pirolitica."))

        self.assertEqual(docs.buscar("pirolitica")[0]["documento"], "Manual horno.txt")

    def test_pdf_escaneado_o_falso(self):
        docs = self.brain.modules.obtener("documentos")

        with self.assertRaises(DocumentoError):
            docs.guardar_archivo("foto.pdf", b"%PDF-1.4\n%%EOF")

        with self.assertRaises(DocumentoError):
            docs.guardar_archivo("falso.pdf", b"no soy un pdf")

        with self.assertRaises(DocumentoError):
            docs.guardar_archivo("virus.exe", b"MZ")

    def test_nombre_no_sale_de_la_carpeta(self):
        docs = self.brain.modules.obtener("documentos")
        docs.guardar_archivo("../../escape.txt", b"hola")

        self.assertTrue((docs.carpeta / "escape.txt").exists())

    def test_borrar(self):
        docs = self.brain.modules.obtener("documentos")
        docs.guardar_archivo("nota.txt", b"hola mundo")
        docs.borrar("nota.txt")

        self.assertEqual(docs.listar(), [])


class TestWebCasa(CasoBrain):
    def setUp(self):
        super().setUp()
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain))
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True).start()
        self.addCleanup(self.servidor.server_close)
        self.addCleanup(self.servidor.shutdown)

    def pedir(self, metodo, ruta, cuerpo=None, cabeceras=None):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        datos = cuerpo if isinstance(cuerpo, bytes) else (json.dumps(cuerpo).encode() if cuerpo is not None else None)
        h = dict(cabeceras or {})

        if cuerpo is not None and not isinstance(cuerpo, bytes):
            h["Content-Type"] = "application/json"

        c.request(metodo, ruta, datos, h)
        r = c.getresponse()
        resultado = json.loads(r.read() or b"{}")
        c.close()

        return r.status, resultado

    def test_presupuesto_y_gastos(self):
        self.pedir("POST", "/api/presupuesto/guardar", {"total": 100})
        self.pedir("POST", "/api/gastos/anadir", {"importe": 90, "concepto": "super"})
        codigo, r = self.pedir("GET", "/api/presupuesto")

        self.assertEqual((codigo, r["nivel"]), (200, "aviso"))
        self.assertEqual(self.pedir("POST", "/api/presupuesto/guardar", {"total": "abc"})[0], 400)

    def test_habitos_hogar_y_menu(self):
        self.pedir("POST", "/api/habitos/crear", {"nombre": "agua", "objetivo": 3, "hora": "10:00"})
        self.pedir("POST", "/api/habitos/anotar", {"nombre": "agua"})
        self.assertEqual(self.pedir("GET", "/api/habitos")[1]["habitos"][0]["hoy"], 1)

        self.pedir("POST", "/api/hogar/crear", {"nombre": "basura", "personas": "Ana, Luis"})
        self.pedir("POST", "/api/hogar/hecha", {"nombre": "basura"})
        self.assertEqual(self.pedir("GET", "/api/hogar")[1]["tareas"][0]["le_toca_a"], "Luis")
        self.assertEqual(self.pedir("POST", "/api/hogar/hecha", {"nombre": "nada"})[0], 400)

        self.pedir("POST", "/api/menu/guardar", {"texto": "lunes comida: Lentejas | lentejas"})
        self.assertEqual(self.pedir("GET", "/api/menu")[1]["faltan"][0]["nombre"], "lentejas")
        self.assertEqual(self.pedir("POST", "/api/menu/guardar", {"texto": "nada"})[0], 400)

    def test_rutina_sin_home_assistant(self):
        codigo, r = self.pedir("GET", "/api/rutina?tipo=salgo")

        self.assertEqual((codigo, r["conectado"]), (200, False))
        self.assertEqual(self.pedir("GET", "/api/rutina?tipo=otra")[0], 400)

    def test_subir_manual_y_buscar(self):
        codigo, r = self.pedir("POST", "/api/documentos/subir", b"La clave del wifi es patata123", {"X-Nombre": "wifi.txt", "Content-Type": "application/octet-stream"})

        self.assertEqual(codigo, 200)
        self.assertEqual(self.pedir("GET", "/api/buscar?q=wifi")[1]["total"], 1)
        self.assertEqual(self.pedir("POST", "/api/documentos/subir", b"MZ", {"X-Nombre": "a.exe"})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/documentos/borrar", {"nombre": "wifi.txt"})[0], 200)

    def test_caducidades_y_copia_a_otro_sitio(self):
        self.brain.modules.obtener("inventario").añadir("leche", 1, "frigorifico", dias(1))
        self.assertEqual(self.pedir("GET", "/api/caducidades")[1]["productos"][0]["nombre"], "leche")

        destino = str(self.carpeta / "usb")
        self.assertEqual(self.pedir("POST", "/api/copia/destino", {"ruta": destino})[1]["destino"], destino)
        self.pedir("POST", "/api/copia/crear", {})
        estado = self.pedir("GET", "/api/copia/estado")[1]

        self.assertEqual(len(estado["copias_destino"]), 1)

    def test_coste_luz_sin_tarifa_y_con_ella(self):
        self.assertIn("error", self.pedir("GET", "/api/energia/coste")[1]["mes"])
        self.pedir("POST", "/api/energia/tarifa", {"compra": "0,15"})

        self.assertEqual(self.pedir("GET", "/api/energia/coste")[1]["tarifa"]["compra"], 0.15)


if __name__ == "__main__":
    unittest.main()
