from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, guardar_configuracion, normalizar_url
from tests.helpers import CasoBrain, HomeAssistantFalso, llamada, texto


class CasoDomotica(CasoBrain):
    def setUp(self):
        super().setUp()

        self.ha = HomeAssistantFalso()
        self.ha.iniciar()

        guardar_configuracion(self.ha.url, HomeAssistantFalso.TOKEN)

        self.dom = self.brain.modules.obtener("domotica")
        self.dom.olvidar_catalogo()

    def tearDown(self):
        self.ha.parar()
        super().tearDown()

    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)


class TestCliente(CasoDomotica):
    def test_normaliza_direcciones(self):
        self.assertEqual(normalizar_url("192.168.1.5"), "http://192.168.1.5:8123")
        self.assertEqual(normalizar_url("homeassistant.local:8123/"), "http://homeassistant.local:8123")
        self.assertEqual(normalizar_url("https://casa.example.com/lovelace"), "https://casa.example.com:8123")

    def test_token_incorrecto(self):
        cliente = HomeAssistant(self.ha.url, "otro")

        with self.assertRaises(HomeAssistantError) as c:
            cliente.comprobar()

        self.assertIn("token", str(c.exception))

    def test_sin_conexion(self):
        cliente = HomeAssistant("http://127.0.0.1:1", "x", timeout=2)

        with self.assertRaises(HomeAssistantError):
            cliente.comprobar()

    def test_sin_configurar(self):
        resultado = HomeAssistant("", "")

        with self.assertRaises(HomeAssistantError) as c:
            resultado.estados()

        self.assertIn("CONFIGURAR_DOMOTICA", str(c.exception))


class TestControl(CasoDomotica):
    def test_enciende_una_luz_por_nombre(self):
        r = self.ejecutar("encender", dispositivo="luz de la cocina")

        self.assertEqual(r["hecho_en"], ["Luz cocina"])
        self.assertEqual(self.ha.llamadas, [("light", "turn_on", {"entity_id": "light.cocina"})])

    def test_apaga_con_acentos_y_mayusculas(self):
        self.ejecutar("apagar", dispositivo="LA LUZ DEL SALÓN")

        self.assertEqual(self.ha.llamadas[0][:2], ("light", "turn_off"))
        self.assertEqual(self.ha.llamadas[0][2]["entity_id"], "light.salon_techo")

    def test_ambiguo_pregunta_en_vez_de_adivinar(self):
        r = self.ejecutar("encender", dispositivo="luz")

        self.assertTrue(r["ambiguo"])
        self.assertEqual(self.ha.llamadas, [])

    def test_plural_o_todos_actua_sobre_todas(self):
        r = self.ejecutar("apagar", dispositivo="luces del salón")

        self.assertEqual(set(r["hecho_en"]), {"Lámpara salón", "Luz salón"})
        self.assertEqual(len(self.ha.llamadas), 2)

        self.ha.llamadas.clear()
        self.ejecutar("apagar", dispositivo="luz", todos=True)
        self.assertEqual(len(self.ha.llamadas), 4)

    def test_luz_por_habitacion(self):
        self.ejecutar("encender", dispositivo="luz del dormitorio")

        self.assertEqual(self.ha.llamadas[0][2]["entity_id"], "light.dormitorio")

    def test_regular_brillo_color_y_temperatura(self):
        self.ejecutar("regular_luz", dispositivo="luz de la cocina", brillo=30, color="azul")

        _, servicio, datos = self.ha.llamadas[-1]
        self.assertEqual(servicio, "turn_on")
        self.assertEqual(datos["brightness_pct"], 30)
        self.assertEqual(datos["rgb_color"], [0, 0, 255])

        self.ejecutar("regular_luz", dispositivo="luz de la cocina", temperatura="calida")
        self.assertEqual(self.ha.llamadas[-1][2]["color_temp_kelvin"], 2700)

    def test_brillo_se_limita_a_100(self):
        self.ejecutar("regular_luz", dispositivo="luz de la cocina", brillo=250)

        self.assertEqual(self.ha.llamadas[-1][2]["brightness_pct"], 100)

    def test_color_desconocido(self):
        r = self.ejecutar("regular_luz", dispositivo="luz de la cocina", color="infrarrojo")

        self.assertIn("error", r)
        self.assertEqual(self.ha.llamadas, [])

    def test_persiana(self):
        self.ejecutar("apagar", dispositivo="persiana del dormitorio")
        self.assertEqual(self.ha.llamadas[-1][:2], ("cover", "close_cover"))

        self.ejecutar("mover_persiana", dispositivo="persiana del dormitorio", posicion=40)
        self.assertEqual(self.ha.llamadas[-1][1:], ("set_cover_position", {"entity_id": "cover.persiana_dormitorio", "position": 40}))

    def test_termostato(self):
        self.ejecutar("poner_temperatura", dispositivo="termostato del salón", grados=22.5)
        self.assertEqual(self.ha.llamadas[-1][1:], ("set_temperature", {"entity_id": "climate.salon", "temperature": 22.5}))

        r = self.ejecutar("poner_temperatura", dispositivo="termostato del salón", grados=80)
        self.assertIn("error", r)

    def test_escena(self):
        self.ejecutar("activar_escena", escena="noche")

        self.assertEqual(self.ha.llamadas[-1][:2], ("scene", "turn_on"))

    def test_no_controla_garajes_ni_cerraduras(self):
        for orden in ("la puerta del garaje", "la cerradura de la entrada", "garaje"):
            r = self.ejecutar("encender", dispositivo=orden)

            self.assertIn("error", r, orden)

        self.assertEqual(self.ha.llamadas, [])

    def test_no_encontrado(self):
        r = self.ejecutar("encender", dispositivo="luz del sótano")

        self.assertIn("error", r)
        self.assertEqual(self.ha.llamadas, [])


class TestConsultas(CasoDomotica):
    def test_lista_luces_con_estado(self):
        r = self.ejecutar("ver_dispositivos", tipo="luces")

        self.assertEqual(r["total"], 4)
        salon = [a for a in r["aparatos"] if a["nombre"] == "Luz salón"][0]
        self.assertEqual(salon["estado"], "on")
        self.assertEqual(salon["brillo_pct"], 100)
        self.assertEqual(salon["habitacion"], "Salón")

    def test_lista_por_habitacion(self):
        r = self.ejecutar("ver_dispositivos", habitacion="dormitorio")

        nombres = {a["nombre"] for a in r["aparatos"]}
        self.assertEqual(nombres, {"Luz dormitorio", "Persiana dormitorio"})

    def test_sensor_y_cerradura_solo_lectura(self):
        r = self.ejecutar("estado_dispositivo", dispositivo="temperatura del salón")
        self.assertEqual(r["aparatos"][0]["estado"], "21.3")

        r = self.ejecutar("estado_dispositivo", dispositivo="cerradura entrada")
        self.assertEqual(r["aparatos"][0]["estado"], "locked")

    def test_sin_configurar_devuelve_error_claro(self):
        guardar_configuracion("", "")
        self.dom.olvidar_catalogo()

        r = self.ejecutar("encender", dispositivo="luz de la cocina")

        self.assertIn("CONFIGURAR_DOMOTICA", r["error"])


class TestConIA(CasoDomotica):
    def test_la_ia_enciende_una_luz(self):
        self.ollama.respuestas = [
            llamada("encender", dispositivo="luz de la cocina"),
            texto("Hecho, he encendido la luz de la cocina."),
        ]

        respuesta = self.brain.conversacion.preguntar("Enciende la luz de la cocina")

        self.assertIn("cocina", respuesta)
        self.assertEqual(self.ha.llamadas, [("light", "turn_on", {"entity_id": "light.cocina"})])
        self.assertIn("encender", [h["nombre"] for h in self.brain.ai.herramientas_usadas])
