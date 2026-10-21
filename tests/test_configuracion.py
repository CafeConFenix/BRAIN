import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from brain.core.config import Config
from brain.integrations.home_assistant import guardar_configuracion
from brain.modules.energia import leer_sensores_energia
from brain.web.acceso import Acceso
from brain.web.servidor import crear_manejador
from tests.helpers import CasoBrain, HomeAssistantFalso, entidades_de_ejemplo, sensores_de_energia, llamada, texto

HOST_REMOTO = "casa.tail1234.ts.net"


class CasoWeb(CasoBrain):
    """Servidor web de BRAIN contra un Home Assistant falso."""

    entidades = None
    conectar = True

    def setUp(self):
        super().setUp()
        self.ha = HomeAssistantFalso(entidades=self.entidades if self.entidades is not None else {**entidades_de_ejemplo(), **sensores_de_energia()})
        self.ha.iniciar()

        if self.conectar:
            guardar_configuracion(self.ha.url, HomeAssistantFalso.TOKEN)

        self.acceso = Acceso(Path(Config.DATOS) / "acceso.json")
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain, self.acceso))
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True).start()
        self.dom = self.brain.modules.obtener("domotica")

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.ha.parar()
        super().tearDown()

    def pedir(self, metodo, ruta, cuerpo=None, host=None, cookie=None):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=15)
        cabeceras = {"Host": host or f"127.0.0.1:{self.puerto}"}

        if metodo == "POST":
            cabeceras["Content-Type"] = "application/json"

        if cookie:
            cabeceras["Cookie"] = cookie

        con.request(metodo, ruta, body=json.dumps(cuerpo or {}) if metodo == "POST" else None, headers=cabeceras)
        r = con.getresponse()
        datos = json.loads(r.read() or b"{}")
        con.close()

        return r.status, datos

    def sesion_remota(self):
        self.acceso.establecer_clave("una-clave-larga")
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        con.request("POST", "/api/acceso/entrar", body=json.dumps({"clave": "una-clave-larga"}), headers={"Host": HOST_REMOTO, "Content-Type": "application/json"})
        r = con.getresponse()
        r.read()
        cookie = r.getheader("Set-Cookie").split(";")[0]
        con.close()

        return cookie


class TestDispositivosOcultos(CasoWeb):
    def test_ocultar_quita_del_panel_y_de_la_ia(self):
        self.assertIn("Luz cocina", [d["nombre"] for g in self.dom.panel()["grupos"] for d in g["dispositivos"]])
        self.dom.guardar_ocultos(["light.cocina"])
        nombres = [d["nombre"] for g in self.dom.panel()["grupos"] for d in g["dispositivos"]]
        self.assertNotIn("Luz cocina", nombres)
        self.assertIn("Luz salón", nombres)
        # La IA tampoco lo encuentra ni lo puede encender.
        self.assertIn("error", self.brain.tools.ejecutar("encender", {"dispositivo": "luz de la cocina"}))
        self.assertEqual(self.ha.llamadas, [])
        # Ni desde el panel, aunque se conozca su identificador.
        from brain.integrations.home_assistant import HomeAssistantError

        with self.assertRaises(HomeAssistantError):
            self.dom.conmutar("light.cocina", True)

    def test_selector_lista_todo_con_visibilidad(self):
        self.dom.guardar_ocultos(["light.cocina", "scene.noche"])
        c = self.dom.dispositivos_configurables()
        todos = {d["entidad"]: d["visible"] for g in c["grupos"] for d in g["dispositivos"]}
        self.assertFalse(todos["light.cocina"])
        self.assertFalse(todos["scene.noche"])
        self.assertTrue(todos["light.salon_techo"])
        self.assertNotIn("sensor.temp_salon", todos)  # los sensores no se eligen
        self.assertNotIn("cover.garaje", todos)  # los garajes nunca se controlan
        self.assertEqual(c["ocultos"], 2)

    def test_mostrar_de_nuevo(self):
        self.dom.guardar_ocultos(["light.cocina"])
        self.dom.guardar_ocultos([])
        self.assertIn("Luz cocina", [d["nombre"] for g in self.dom.panel()["grupos"] for d in g["dispositivos"]])

    def test_api_guardar_y_leer(self):
        codigo, datos = self.pedir("POST", "/api/config/dispositivos/guardar", {"ocultos": ["light.cocina", "basura", ""]})
        self.assertEqual((codigo, datos["ocultos"]), (200, 1))  # "basura" no es un identificador
        codigo, datos = self.pedir("GET", "/api/config/dispositivos")
        self.assertEqual(codigo, 200)
        self.assertTrue(datos["conectado"])
        self.assertEqual(datos["ocultos"], 1)
        self.assertEqual(self.pedir("POST", "/api/config/dispositivos/guardar", {})[0], 400)

    def test_se_conserva_entre_arranques(self):
        self.dom.guardar_ocultos(["light.cocina"])
        from brain.core import Brain

        otro = Brain(silencioso=True).modules.obtener("domotica")
        self.assertEqual(otro.ocultos(), {"light.cocina"})

    def test_la_ia_sigue_encendiendo_lo_visible(self):
        self.dom.guardar_ocultos(["light.cocina"])
        r = self.brain.tools.ejecutar("encender", {"dispositivo": "luz del dormitorio"})
        self.assertEqual(r["hecho_en"], ["Luz dormitorio"])

    def test_el_dispositivo_oculto_sigue_en_la_lista_de_elegir_desde_remoto(self):
        cookie = self.sesion_remota()
        self.assertEqual(self.pedir("POST", "/api/config/dispositivos/guardar", {"ocultos": ["light.cocina"]}, host=HOST_REMOTO, cookie=cookie)[0], 200)
        codigo, datos = self.pedir("GET", "/api/config/dispositivos", host=HOST_REMOTO, cookie=cookie)
        self.assertEqual(codigo, 200)
        self.assertEqual(datos["ocultos"], 1)


class TestAsistente(CasoWeb):
    def test_estado_y_primera_vez(self):
        codigo, e = self.pedir("GET", "/api/config/estado")
        self.assertEqual(codigo, 200)
        self.assertTrue(e["ha"]["configurado"])
        self.assertNotIn("token", json.dumps(e).lower().replace("token_guardado", ""))  # la llave nunca sale
        self.assertFalse(e["primera_vez"])

    def test_primera_vez_sin_nada_configurado(self):
        import brain.web.configuracion as c

        guardar_configuracion("", "")
        self.assertTrue(c.estado_configuracion()["primera_vez"])
        self.pedir("POST", "/api/config/omitir")
        self.assertFalse(c.estado_configuracion()["primera_vez"])

    def test_solo_desde_el_ordenador_de_casa(self):
        cookie = self.sesion_remota()

        for metodo, ruta in (("GET", "/api/config/estado"), ("GET", "/api/config/energia"), ("POST", "/api/config/ha/guardar"), ("POST", "/api/config/energia/guardar"), ("POST", "/api/config/omitir")):
            self.assertEqual(self.pedir(metodo, ruta, {}, host=HOST_REMOTO, cookie=cookie)[0], 403, ruta)

    def test_guardar_home_assistant(self):
        guardar_configuracion("", "")
        codigo, r = self.pedir("POST", "/api/config/ha/guardar", {"url": self.ha.url, "token": HomeAssistantFalso.TOKEN})
        self.assertEqual(codigo, 200, r)
        self.assertTrue(r["ok"])
        self.assertIn({"tipo": "luces", "total": 4}, r["resumen"])
        self.assertTrue(r["energia_detectada"])
        self.assertTrue(self.dom.conectado())

    def test_token_incorrecto_no_se_guarda(self):
        guardar_configuracion("", "")
        codigo, r = self.pedir("POST", "/api/config/ha/guardar", {"url": self.ha.url, "token": "mal"})
        self.assertEqual(codigo, 502)
        self.assertIn("token", r["error"])
        self.assertFalse(self.dom.conectado())

    def test_faltan_datos(self):
        guardar_configuracion("", "")
        self.assertEqual(self.pedir("POST", "/api/config/ha/guardar", {"url": "", "token": "x"})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/config/ha/guardar", {"url": self.ha.url, "token": ""})[0], 400)

    def test_token_vacio_reutiliza_el_guardado(self):
        codigo, r = self.pedir("POST", "/api/config/ha/guardar", {"url": self.ha.url, "token": ""})
        self.assertEqual(codigo, 200, r)

    def test_candidatos_de_energia(self):
        codigo, r = self.pedir("GET", "/api/config/energia")
        self.assertEqual(codigo, 200)
        roles = {x["rol"]: x for x in r["roles"]}
        self.assertEqual(roles["produccion"]["candidatos"][0]["entidad"], "sensor.inversor_potencia_activa")
        self.assertEqual(roles["bateria_pct"]["candidatos"][0]["entidad"], "sensor.bateria_nivel")
        self.assertTrue(any(p["entidad"] == "sensor.inversor_pv1_power" for p in r["potencias"]))
        self.assertEqual(roles["produccion"]["elegido"], "")

    def test_guardar_energia(self):
        codigo, r = self.pedir(
            "POST",
            "/api/config/energia/guardar",
            {"produccion": "sensor.inversor_potencia_activa", "red": "sensor.contador_potencia", "bateria_pct": "sensor.bateria_nivel", "consumo": ""},
        )
        self.assertEqual(codigo, 200, r)
        guardado = leer_sensores_energia()
        self.assertEqual(guardado["produccion"], "sensor.inversor_potencia_activa")
        self.assertNotIn("consumo", guardado)
        self.assertIn("3", r["lectura"])  # 3,2 kW
        self.assertEqual(self.pedir("GET", "/api/config/energia")[1]["roles"][0]["elegido"], "sensor.inversor_potencia_activa")

    def test_energia_invertida_segun_lo_que_ve_el_usuario(self):
        # El contador marca -900 W. Si el usuario dice que ahora COMPRA, el signo está al revés.
        self.pedir("POST", "/api/config/energia/guardar", {"produccion": "sensor.inversor_potencia_activa", "red": "sensor.contador_potencia", "red_ahora": "comprando"})
        self.assertTrue(leer_sensores_energia().get("red_invertida"))
        self.pedir("POST", "/api/config/energia/guardar", {"produccion": "sensor.inversor_potencia_activa", "red": "sensor.contador_potencia", "red_ahora": "vendiendo"})
        self.assertFalse(leer_sensores_energia().get("red_invertida"))

    def test_energia_rechaza_sensores_malos(self):
        self.assertEqual(self.pedir("POST", "/api/config/energia/guardar", {})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/config/energia/guardar", {"produccion": "sensor.no_existe"})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/config/energia/guardar", {"produccion": "sensor.temp_salon"})[0], 400)  # no es potencia
        self.assertEqual(leer_sensores_energia(), {})

    def test_sin_home_assistant_conectado(self):
        guardar_configuracion("", "")
        self.assertEqual(self.pedir("GET", "/api/config/energia")[0], 502)
        self.assertFalse(self.pedir("GET", "/api/config/dispositivos")[1]["conectado"])


class TestAvisosVistos(CasoWeb):
    def test_marcar_solo_los_indicados(self):
        avisos = self.brain.modules.obtener("avisos")
        avisos.avisar("Uno", "x", silencioso=True)
        avisos.avisar("Dos", "y", silencioso=True)
        self.assertTrue(avisos.listar(solo_no_leidos=True))
        ids = [x["id"] for x in avisos.listar(solo_no_leidos=True)]
        codigo, r = self.pedir("POST", "/api/avisos/leer", {"ids": ids[:1]})
        self.assertEqual(codigo, 200)
        self.assertEqual(r["marcados"], 1)
        self.assertEqual(len(avisos.listar(solo_no_leidos=True)), len(ids) - 1)

    def test_la_pagina_marca_como_visto_a_los_2_segundos(self):
        html = (Path(__file__).resolve().parents[1] / "brain" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("function programarVisto", html)
        self.assertIn("}, 2000);", html)
        self.assertIn('enviarJSON("/api/avisos/leer", { ids })', html)


class TestFuncionesNuevas(CasoWeb):
    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)

    # ---- gastos ----

    def test_apuntar_gastos_y_resumen(self):
        g = self.ejecutar("anadir_gasto", importe="23,50", concepto="Mercadona")["apuntado"]
        self.assertEqual((g["importe"], g["categoria"], g["id"]), (23.5, "supermercado", 1))
        self.ejecutar("anadir_gasto", importe=60, concepto="factura de la luz")
        self.ejecutar("anadir_gasto", importe="1.234,56", concepto="reforma", categoria="hogar")
        self.ejecutar("anadir_gasto", importe=10, concepto="cosa rara")
        r = self.ejecutar("ver_gastos")
        self.assertEqual(r["total"], 1328.06)
        self.assertEqual(r["n"], 4)
        self.assertEqual(r["por_categoria"][0]["categoria"], "hogar")
        self.assertEqual({c["categoria"] for c in r["por_categoria"]}, {"hogar", "facturas", "supermercado", "otros"})

    def test_gastos_por_mes_y_borrar(self):
        self.ejecutar("anadir_gasto", importe=5, concepto="cine", fecha="2026-01-15")
        self.ejecutar("anadir_gasto", importe=7, concepto="cafe", fecha="2026-02-02")
        self.assertEqual(self.ejecutar("ver_gastos", mes="2026-01")["total"], 5)
        self.assertIn("mensaje", self.ejecutar("ver_gastos", mes="2025-03"))
        self.assertEqual(self.ejecutar("borrar_gasto")["borrado"]["importe"], 7)  # el último
        self.assertEqual(self.ejecutar("borrar_gasto", id="1")["borrado"]["concepto"], "cine")
        with self.assertRaises(ValueError):
            self.ejecutar("borrar_gasto", id="9")

    def test_gastos_importes_invalidos(self):
        for malo in ("", "abc", 0, -5):
            with self.assertRaises(ValueError):
                self.ejecutar("anadir_gasto", importe=malo)

    # ---- hábitos ----

    def test_habitos_progreso_y_racha(self):
        from datetime import date, timedelta

        hoy = date.today()
        self.ejecutar("crear_habito", nombre="beber agua", objetivo=3, unidad="vasos")

        for atras in (2, 1):  # cumplido anteayer y ayer
            self.ejecutar("anotar_habito", nombre="agua", cantidad=3, fecha=(hoy - timedelta(days=atras)).isoformat())

        r = self.ejecutar("anotar_habito", nombre="agua")  # hoy 1 de 3: la racha de ayer sigue viva
        self.assertEqual((r["hoy"], r["cumplido"], r["racha_dias"]), (1, False, 2))
        r = self.ejecutar("anotar_habito", nombre="beber agua", cantidad=2)
        self.assertEqual((r["hoy"], r["cumplido"], r["racha_dias"]), (3, True, 3))
        v = self.ejecutar("ver_habitos")
        self.assertEqual((v["cumplidos"], v["total"]), (1, 1))

    def test_habitos_racha_se_rompe_y_correcciones(self):
        from datetime import date, timedelta

        hoy = date.today()
        self.ejecutar("crear_habito", nombre="pasear")
        self.ejecutar("anotar_habito", nombre="pasear", fecha=(hoy - timedelta(days=3)).isoformat())
        r = self.ejecutar("anotar_habito", nombre="pasear")
        self.assertEqual(r["racha_dias"], 1)  # ayer y anteayer faltan: solo cuenta hoy
        r = self.ejecutar("anotar_habito", nombre="pasear", cantidad=-1)  # corregir
        self.assertEqual((r["hoy"], r["cumplido"]), (0, False))

    def test_habitos_errores(self):
        self.assertIn("mensaje", self.ejecutar("ver_habitos"))
        with self.assertRaises(ValueError):
            self.ejecutar("anotar_habito", nombre="no existe")
        with self.assertRaises(ValueError):
            self.ejecutar("crear_habito", nombre="x", objetivo=0)
        self.ejecutar("crear_habito", nombre="leer")
        self.assertEqual(self.ejecutar("borrar_habito", nombre="leer")["borrado"]["nombre"], "leer")
        self.assertEqual(self.ejecutar("ver_habitos")["total"] if "total" in self.ejecutar("ver_habitos") else 0, 0)

    def test_interpretar_mes(self):
        from datetime import date
        from brain.modules.gastos import interpretar_mes

        hoy = date.today()
        self.assertEqual(interpretar_mes(), f"{hoy.year:04d}-{hoy.month:02d}")
        self.assertEqual(interpretar_mes("2026-3"), "2026-03")
        self.assertEqual(interpretar_mes("octubre")[-2:], "10")
        self.assertRegex(interpretar_mes("mes pasado"), r"^\d{4}-\d{2}$")

    def test_la_ia_recibe_las_herramientas_de_gastos(self):
        from brain.ai.herramientas_relevantes import categorias_relevantes

        self.assertIn("gastos", categorias_relevantes("cuánto he gastado este mes"))

    # ---- domótica ----

    def test_que_hay_encendido(self):
        r = self.ejecutar("que_hay_encendido")
        nombres = {d["nombre"] for d in r["encendidos"]}
        self.assertEqual(nombres, {"Luz salón", "Termostato salón"})
        self.dom.guardar_ocultos(["light.salon_techo"])
        self.assertEqual({d["nombre"] for d in self.ejecutar("que_hay_encendido")["encendidos"]}, {"Termostato salón"})

    def test_dispositivos_con_problemas(self):
        self.ha.entidades["light.cocina"]["estado"] = "unavailable"
        self.ha.entidades["sensor.pilas_puerta"] = {
            "estado": "8",
            "atributos": {"friendly_name": "Pilas puerta", "device_class": "battery", "unit_of_measurement": "%"},
        }
        self.dom.olvidar_catalogo()
        r = self.ejecutar("dispositivos_con_problemas")
        self.assertEqual([d["nombre"] for d in r["sin_conexion"]], ["Luz cocina"])
        self.assertEqual(r["bateria_baja"][0]["bateria_pct"], 8)
        self.assertFalse(r["todo_bien"])

    def test_todo_bien_sin_problemas(self):
        self.assertTrue(self.ejecutar("dispositivos_con_problemas")["todo_bien"])

    # ---- ahorro solar ----

    def test_ahorro_solar(self):
        self.assertIn("error", self.ejecutar("ver_ahorro_solar"))
        self.assertEqual(self.ejecutar("configurar_tarifa_luz", compra="0,15", venta=0.06)["tarifa"], {"compra": 0.15, "venta": 0.06})
        self.assertIn("mensaje", self.ejecutar("ver_ahorro_solar"))  # aún sin producción
        self.ejecutar("guardar_produccion_solar", kwh=20, fecha="2026-10-01")
        self.ejecutar("guardar_produccion_solar", kwh=30, fecha="2026-10-02")
        r = self.ejecutar("ver_ahorro_solar")
        self.assertEqual((r["kwh_producidos"], r["valor_maximo_eur"], r["valor_minimo_eur"]), (50.0, 7.5, 3.0))

    def test_tarifa_invalida(self):
        for malo in (0, -1, 50):
            with self.assertRaises(ValueError):
                self.ejecutar("configurar_tarifa_luz", compra=malo)

        with self.assertRaises(ValueError):
            self.ejecutar("configurar_tarifa_luz")
