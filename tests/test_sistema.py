import http.client
import json
import sqlite3
import threading
import time
import unittest
import zipfile
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

from brain.core.config import Config
from brain.core.database import Database
from brain.core.scheduler import Planificador, SondeoHomeAssistant, registrar_tareas_por_defecto
from brain.integrations.home_assistant import guardar_configuracion
from brain.modules.sistema import CopiaError
from brain.web.servidor import crear_manejador
from tests.helpers import CasoBrain, HomeAssistantFalso, llamada, sensores_de_energia


class TestBaseDeDatos(CasoBrain):
    def test_indices_en_fechas(self):
        self.assertTrue({"idx_energia_fecha", "idx_sensores_fecha", "idx_sensores_tipo_fecha"} <= set(Database().indices()))

        with closing(sqlite3.connect(str(Database().ruta))) as con:
            plan = con.execute("EXPLAIN QUERY PLAN SELECT * FROM energia_registros WHERE fecha >= '2026-01-01'").fetchall()

        self.assertIn("idx_energia_fecha", str(plan))

    def test_herramientas_siguen_igual_pero_guardan_en_sqlite(self):
        e = self.brain.tools.ejecutar
        e("guardar_peso", {"peso": 88.4, "fecha": "2026-08-10"})
        e("guardar_peso", {"peso": 87.9, "fecha": "2026-08-10"})  # misma fecha: actualiza
        e("guardar_peso", {"peso": 90, "fecha": "2026-08-01"})
        e("guardar_sensor", {"tipo": "temp", "valor": 21.5, "ubicacion": "salón"})
        e("guardar_produccion_solar", {"kwh": 30, "fecha": "2026-08-10"})

        self.assertEqual(e("obtener_peso")["peso"], 87.9)
        self.assertEqual(e("peso_en_fecha", {"fecha": "2026-08-05"})["exacto"], False)
        self.assertEqual([r["fecha"] for r in e("historial_peso")["historial"]] if "historial" in e("historial_peso") else [], ["2026-08-01", "2026-08-10"] if "historial" in e("historial_peso") else [])
        self.assertEqual(e("ver_sensor", {"tipo": "temperatura"})["valor"], 21.5)
        self.assertEqual(e("ver_produccion_solar")["total_kwh"], 30)

        # Nada de esto está ya en los JSON
        self.assertFalse((Config.DATOS / "salud" / "salud.json").exists())
        self.assertTrue(Database().ruta.exists())

    def test_sensor_guarda_valores_no_numericos(self):
        self.brain.modules.obtener("sensores").registrar("presencia", "si")

        self.assertEqual(Database().lecturas_sensor("presencia")[0]["valor"], "si")

    def test_transaccion_se_deshace_si_falla(self):
        db = Database()

        with self.assertRaises(sqlite3.IntegrityError):
            with closing(db.conectar()) as con, con:
                con.execute("INSERT INTO peso (fecha, peso) VALUES ('2026-01-01', 80)")
                con.execute("INSERT INTO peso (fecha, peso) VALUES ('2026-01-01', NULL)")

        self.assertEqual(db.historial_peso(), [])


class TestMigracion(unittest.TestCase):
    def test_migra_los_json_antiguos(self):
        import tempfile

        antes = Config.DATOS
        carpeta = Path(tempfile.mkdtemp(prefix="brain_mig_"))
        Config.DATOS = carpeta

        try:
            (carpeta / "salud").mkdir()
            (carpeta / "salud" / "salud.json").write_text(
                json.dumps({"peso": [{"peso": 80, "fecha": "2026-01-02"}, {"peso": 81, "fecha": "2026-01-03"}], "otra": [1]}),
                encoding="utf-8",
            )
            (carpeta / "sensores").mkdir()
            (carpeta / "sensores" / "sensores.json").write_text(
                json.dumps({"temperatura": [{"valor": 20, "ubicacion": "x", "fecha": "2026-01-01T10:00:00"}]}), encoding="utf-8"
            )
            (carpeta / "energia").mkdir()
            (carpeta / "energia" / "energia.json").write_text(
                json.dumps({"placas_solares": [{"produccion": 12.5, "fecha": "2026-01-01"}]}), encoding="utf-8"
            )

            db = Database()

            self.assertEqual(len(db.historial_peso()), 2)
            self.assertEqual(db.lecturas_sensor("temperatura")[0]["valor"], 20)
            self.assertEqual(db.produccion(5)[0]["produccion"], 12.5)

            # Se conserva lo que no era una serie temporal y queda copia del original
            self.assertEqual(json.loads((carpeta / "salud" / "salud.json").read_text(encoding="utf-8")), {"otra": [1]})
            self.assertTrue((carpeta / "salud" / "salud.json.premigracion").exists())
            self.assertFalse((carpeta / "sensores" / "sensores.json").exists())

            # No se vuelve a migrar ni duplica
            Database()._migrar_json()
            self.assertEqual(len(db.historial_peso()), 2)
        finally:
            Config.DATOS = antes


class TestPlanificador(unittest.TestCase):
    def test_un_error_no_para_nada(self):
        plan = Planificador()
        cuenta = [0]

        def malo():
            raise RuntimeError("fallo")

        def bueno():
            cuenta[0] += 1

        plan.registrar("malo", malo, segundos=0.05)
        plan.registrar("bueno", bueno, segundos=0.05)
        plan.iniciar()
        time.sleep(0.5)

        try:
            self.assertTrue(plan.activo)
            self.assertGreaterEqual(cuenta[0], 3)

            estado = {t["nombre"]: t for t in plan.estado()}
            self.assertGreaterEqual(estado["malo"]["errores"], 3)
            self.assertIn("fallo", estado["malo"]["ultimo_error"])
            self.assertIsNone(estado["bueno"]["ultimo_error"])
        finally:
            plan.detener()

        self.assertFalse(plan.activo)

    def test_intervalo_en_horas_y_validacion(self):
        plan = Planificador()

        self.assertEqual(plan.registrar("a", lambda: None, horas=2).intervalo, 7200)

        with self.assertRaises(ValueError):
            plan.registrar("b", lambda: None)

    def test_tareas_por_defecto(self):
        plan = registrar_tareas_por_defecto(Planificador())

        self.assertEqual({t["nombre"] for t in plan.estado()}, {"copia_diaria", "sondeo_home_assistant", "recordatorios", "aviso_eventos", "automatizaciones", "resumen_diario", "mantenimiento"})


class TestSondeoHomeAssistant(CasoBrain):
    def test_guarda_energia_y_detecta_alertas(self):
        entidades = {
            **sensores_de_energia(),
            "binary_sensor.humo_cocina": {
                "estado": "on",
                "atributos": {"friendly_name": "Humo cocina", "device_class": "smoke"},
            },
        }
        ha = HomeAssistantFalso(entidades=entidades)
        ha.iniciar()
        self.addCleanup(ha.parar)
        guardar_configuracion(ha.url, HomeAssistantFalso.TOKEN)

        sondeo = SondeoHomeAssistant()
        resultado = sondeo()

        self.assertIn("1 alertas", resultado)
        self.assertEqual(sondeo.alertas[0]["entidad"], "binary_sensor.humo_cocina")
        self.assertEqual(len(Database().lecturas_energia()), 1)

    def test_sin_home_assistant_no_hace_nada(self):
        self.assertIn("no está configurado", SondeoHomeAssistant()())


class TestFaltantesReceta(CasoBrain):
    def test_compara_y_apunta_solo_lo_que_falta(self):
        e = self.brain.tools.ejecutar
        e("anadir_inventario", {"nombre": "Huevos", "cantidad": 6, "ubicacion": "frigorifico"})
        e("anadir_inventario", {"nombre": "Salmón", "cantidad": 1, "ubicacion": "congelador"})
        e("anadir_a_compra", {"producto": "cebollas", "cantidad": 2})
        self.brain.modules.obtener("inventario").guardar_seccion("despensa", [{"nombre": "Tomate frito", "cantidad": 0}])

        r = e(
            "anadir_faltantes_receta_a_compra",
            {"ingredientes": "2 huevos\n200 g de harina\nsal\nTomates fritos\n1 cebolla\nsalmon ahumado\naceite de girasol", "receta": "x"},
        )

        self.assertEqual([a["producto"] for a in r["añadidos_a_compra"]], ["Tomates fritos", "aceite de girasol"])
        self.assertEqual(r["ya_estaban_en_la_lista"], ["cebolla"])
        self.assertEqual([a["ingrediente"] for a in r["agotados"]], ["Tomates fritos"])
        self.assertEqual(
            {d["ingrediente"]: d["en"] for d in r["ya_disponibles"]},
            {"huevos": "frigorifico", "harina": "básicos de casa", "sal": "básicos de casa", "salmon ahumado": "congelador"},
        )

        compra = {i["producto"] for i in e("ver_lista_compra")["lista_compra"]}
        self.assertEqual(compra, {"cebollas", "Tomates fritos", "aceite de girasol"})

    def test_no_confunde_sal_con_salmon_y_acepta_comas(self):
        r = self.brain.tools.ejecutar("anadir_faltantes_receta_a_compra", {"ingredientes": "salmón, sal, limones"})

        self.assertEqual([a["producto"] for a in r["añadidos_a_compra"]], ["salmón", "limones"])

    def test_si_no_falta_nada(self):
        r = self.brain.tools.ejecutar("anadir_faltantes_receta_a_compra", {"ingredientes": "sal, aceite, agua"})

        self.assertEqual(r["añadidos_a_compra"], [])
        self.assertIn("No falta nada", r["resumen"])

    def test_texto_vacio(self):
        r = self.brain.tools.ejecutar("anadir_faltantes_receta_a_compra", {"ingredientes": "  "})

        self.assertIn("error", r)


class TestCopias(CasoBrain):
    def preparar(self):
        e = self.brain.tools.ejecutar
        e("guardar_peso", {"peso": 80, "fecha": "2026-01-01"})
        e("anadir_inventario", {"nombre": "Leche", "cantidad": 2})

    def test_crea_zip_con_formato_y_contenido(self):
        self.preparar()
        r = self.brain.tools.ejecutar("crear_copia_seguridad")["copia"]

        ruta = Config.DATOS / "backups" / r["archivo"]
        self.assertRegex(r["archivo"], r"^backup_\d{8}_\d{6}\.zip$")

        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()

        self.assertIn("brain.db", nombres)
        self.assertIn("inventario/inventario.json", nombres)
        self.assertIn("MANIFEST.json", nombres)
        self.assertFalse(any(n.startswith("backups/") for n in nombres))

    def test_rotacion_conserva_cinco(self):
        self.preparar()

        for _ in range(8):
            self.brain.tools.ejecutar("crear_copia_seguridad")

        copias = self.brain.tools.ejecutar("ver_copias_seguridad")["copias"]

        self.assertEqual(len(copias), 5)
        self.assertEqual(len(list((Config.DATOS / "backups").glob("backup_*.zip"))), 5)

    def test_restaurar_devuelve_el_estado_anterior(self):
        self.preparar()
        e = self.brain.tools.ejecutar
        nombre = e("crear_copia_seguridad")["copia"]["archivo"]

        e("guardar_peso", {"peso": 99, "fecha": "2026-02-02"})
        e("vaciar_inventario")

        r = e("restaurar_copia_seguridad", {"nombre": nombre})["restaurado"]

        self.assertEqual(r["restaurada"], nombre)
        self.assertEqual(e("obtener_peso")["peso"], 80)
        self.assertTrue(e("ver_inventario")["despensa"][0].startswith("Leche"))
        self.assertTrue((Config.DATOS / "backups" / r["copia_de_seguridad_previa"]).exists())

    def test_restaurar_la_ultima_sin_nombre(self):
        self.preparar()
        e = self.brain.tools.ejecutar
        e("crear_copia_seguridad")
        e("vaciar_inventario")

        self.assertIn("restaurado", e("restaurar_copia_seguridad"))
        self.assertIn("despensa", e("ver_inventario"))

    def test_rechaza_zip_danado_o_manipulado(self):
        self.preparar()
        e = self.brain.tools.ejecutar
        nombre = e("crear_copia_seguridad")["copia"]["archivo"]
        ruta = Config.DATOS / "backups" / nombre

        # Contenido alterado: no coincide con la suma del manifiesto
        manipulado = Config.DATOS / "backups" / "backup_20200101_000000.zip"

        with zipfile.ZipFile(ruta) as z, zipfile.ZipFile(manipulado, "w") as nuevo:
            for n in z.namelist():
                datos = z.read(n)
                nuevo.writestr(n, b"corrupto" if n == "inventario/inventario.json" else datos)

        r = e("restaurar_copia_seguridad", {"nombre": manipulado.name})
        self.assertIn("integridad", r["error"])

        # No es un ZIP
        basura = Config.DATOS / "backups" / "backup_20190101_000000.zip"
        basura.write_bytes(b"no soy un zip")
        self.assertIn("no es un ZIP", e("restaurar_copia_seguridad", {"nombre": basura.name})["error"])

        # Los datos actuales siguen intactos tras los rechazos
        self.assertEqual(e("obtener_peso")["peso"], 80)

    def test_nombre_inexistente_y_rutas_fuera_de_la_carpeta(self):
        self.preparar()
        e = self.brain.tools.ejecutar
        e("crear_copia_seguridad")

        self.assertIn("No existe", e("restaurar_copia_seguridad", {"nombre": "../../etc/passwd"})["error"])

    def test_sin_copias(self):
        self.assertIn("No hay copias", self.brain.tools.ejecutar("restaurar_copia_seguridad")["error"])

    def test_copia_si_toca_no_duplica(self):
        sistema = self.brain.modules.obtener("sistema")

        self.assertIsNotNone(sistema.copia_si_toca())
        self.assertIsNone(sistema.copia_si_toca())


class TestDocumentos(CasoBrain):
    def setUp(self):
        super().setUp()

        carpeta = Config.DATOS / "documentos"
        carpeta.mkdir(parents=True)
        (carpeta / "manual_lavadora.md").write_text(
            "# Lavadora\n\nPara el programa de lana pulsa el botón 3 dos segundos.\n\n## Filtro\n\nLimpia el filtro cada mes.\n",
            encoding="utf-8",
        )
        (carpeta / "caldera.txt").write_text("La caldera se purga abriendo la válvula roja. Presión ideal 1.5 bar.", encoding="cp1252")
        (carpeta / "wifi.json").write_text(json.dumps({"router": {"clave": "abc123", "sitio": "salón"}}), encoding="utf-8")
        (carpeta / "ignorado.pdf").write_bytes(b"%PDF")

    def test_busca_con_bm25(self):
        r = self.brain.tools.ejecutar("buscar_en_documentos", {"consulta": "¿cómo limpio el filtro de la lavadora?"})

        self.assertEqual(r["resultados"][0]["documento"], "manual_lavadora.md")
        self.assertIn("filtro", r["resultados"][0]["texto"].lower())

        r = self.brain.tools.ejecutar("buscar_en_documentos", {"consulta": "clave router"})
        self.assertEqual(r["resultados"][0]["documento"], "wifi.json")

        r = self.brain.tools.ejecutar("buscar_en_documentos", {"consulta": "purgar caldera presion"})
        self.assertEqual(r["resultados"][0]["documento"], "caldera.txt")

    def test_sin_resultados_y_consulta_vacia(self):
        e = self.brain.tools.ejecutar

        self.assertIn("No he encontrado", e("buscar_en_documentos", {"consulta": "submarino nuclear"})["mensaje"])
        self.assertIn("error", e("buscar_en_documentos", {"consulta": "de la el"}))

    def test_leer_lista_y_pagina(self):
        e = self.brain.tools.ejecutar

        nombres = [d["nombre"] for d in e("leer_documento")["documentos"]]
        self.assertEqual(nombres, ["caldera.txt", "manual_lavadora.md", "wifi.json"])  # sin el .pdf

        r = e("leer_documento", {"nombre": "caldera"})
        self.assertIn("válvula roja", r["texto"])  # cp1252 bien decodificado

        largo = Config.DATOS / "documentos" / "largo.txt"
        largo.write_text("palabra " * 2000, encoding="utf-8")
        pagina = e("leer_documento", {"nombre": "largo.txt"})
        self.assertIn("siguiente_desde", pagina)
        self.assertEqual(e("leer_documento", {"nombre": "largo", "desde": pagina["siguiente_desde"]})["desde"], pagina["siguiente_desde"])

    def test_no_sale_de_la_carpeta(self):
        self.assertIn("error", self.brain.tools.ejecutar("leer_documento", {"nombre": "../datos/salud"}))

    def test_el_indice_se_actualiza_solo(self):
        e = self.brain.tools.ejecutar
        self.assertIn("mensaje", e("buscar_en_documentos", {"consulta": "termostato"}))

        (Config.DATOS / "documentos" / "termostato.md").write_text("El termostato se programa con la rueda.", encoding="utf-8")

        self.assertEqual(e("buscar_en_documentos", {"consulta": "termostato"})["resultados"][0]["documento"], "termostato.md")

    def test_sin_carpeta_de_documentos(self):
        import shutil

        shutil.rmtree(Config.DATOS / "documentos")

        self.assertIn("No hay documentos", self.brain.tools.ejecutar("buscar_en_documentos", {"consulta": "algo"})["mensaje"])


class TestWebSistema(CasoBrain):
    def setUp(self):
        super().setUp()

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain))
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        super().tearDown()

    def pedir(self, metodo, ruta, cuerpo=None):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        cabeceras = {"Content-Type": "application/json", "Host": f"127.0.0.1:{self.puerto}"}
        con.request(metodo, ruta, json.dumps(cuerpo) if cuerpo is not None else None, cabeceras)
        r = con.getresponse()
        datos = json.loads(r.read().decode("utf-8"))
        con.close()
        return r.status, datos

    def test_crear_listar_y_restaurar(self):
        self.brain.tools.ejecutar("guardar_peso", {"peso": 70, "fecha": "2026-01-01"})

        codigo, r = self.pedir("POST", "/api/copia/crear", {})
        self.assertEqual(codigo, 200)

        codigo, estado = self.pedir("GET", "/api/sistema")
        self.assertEqual(len(estado["copias"]), 1)
        self.assertIn("tareas", estado)

        self.brain.tools.ejecutar("guardar_peso", {"peso": 95, "fecha": "2026-03-01"})
        codigo, r = self.pedir("POST", "/api/copia/restaurar", {"nombre": estado["copias"][0]["nombre"]})
        self.assertEqual(codigo, 200)
        self.assertEqual(self.brain.tools.ejecutar("obtener_peso")["peso"], 70)

        self.assertEqual(self.pedir("POST", "/api/copia/restaurar", {"nombre": "backup_19990101_000000.zip"})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/copia/restaurar", {})[0], 400)


if __name__ == "__main__":
    unittest.main()
