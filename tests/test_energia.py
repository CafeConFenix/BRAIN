import json

from brain.modules.energia import EnergiaTiempoReal, describir, detectar_sensores, guardar_sensores_energia
from brain.integrations.home_assistant import guardar_configuracion
from tests.helpers import CasoBrain, HomeAssistantFalso, llamada, sensores_de_energia, texto


class CasoEnergia(CasoBrain):
    def setUp(self):
        super().setUp()

        self.ha = HomeAssistantFalso(entidades=sensores_de_energia())
        self.ha.iniciar()

        guardar_configuracion(self.ha.url, HomeAssistantFalso.TOKEN)

    def tearDown(self):
        self.ha.parar()
        super().tearDown()


class TestDeteccion(CasoEnergia):
    def estados(self):
        return [{"entity_id": e, "state": d["estado"], "attributes": d["atributos"]} for e, d in self.ha.entidades.items()]

    def test_encuentra_el_inversor_y_descarta_strings_y_energia_diaria(self):
        c = detectar_sensores(self.estados())

        self.assertEqual(c["produccion"][0]["entidad"], "sensor.inversor_potencia_activa")
        self.assertEqual(c["produccion"][0]["valor_w"], 3200)
        entidades = {x["entidad"] for x in c["produccion"]}
        self.assertNotIn("sensor.inversor_pv1_power", entidades)
        self.assertNotIn("sensor.inversor_energia_hoy", entidades)

    def test_encuentra_el_contador_y_la_bateria_de_casa_no_la_del_movil(self):
        c = detectar_sensores(self.estados())

        self.assertEqual(c["red"][0]["entidad"], "sensor.contador_potencia")
        self.assertEqual([x["entidad"] for x in c["bateria_pct"]], ["sensor.bateria_nivel"])


class TestLecturaEnDirecto(CasoEnergia):
    def test_sin_configurar_avisa(self):
        guardar_configuracion("", "")

        r = EnergiaTiempoReal().leer()

        self.assertFalse(r["configurado"])
        self.assertIn("CONFIGURAR_DOMOTICA", r["mensaje"])

    def test_detecta_solo_y_calcula_el_consumo(self):
        r = EnergiaTiempoReal().leer()

        self.assertTrue(r["automatico"])
        self.assertEqual(r["produccion_w"], 3200)
        self.assertEqual(r["red_w"], -900)
        self.assertEqual(r["estado_red"], "vendiendo")
        # La casa gasta lo que producen las placas menos lo que se vende: 3200 - 900.
        self.assertEqual(r["consumo_w"], 2300)
        self.assertTrue(r["consumo_calculado"])
        self.assertEqual(r["bateria_pct"], 64)

    def test_usa_los_sensores_elegidos_y_el_signo_de_la_red(self):
        guardar_sensores_energia(
            {"produccion": "sensor.inversor_potencia_activa", "red": "sensor.contador_potencia", "red_invertida": True}
        )

        r = EnergiaTiempoReal().leer()

        self.assertEqual(r["red_w"], 900)
        self.assertEqual(r["estado_red"], "comprando")
        self.assertEqual(r["consumo_w"], 4100)

    def test_con_sensor_de_consumo_propio(self):
        self.ha.entidades["sensor.casa_consumo"] = {
            "estado": "1250",
            "atributos": {"friendly_name": "Consumo casa", "unit_of_measurement": "W"},
        }
        guardar_sensores_energia({"produccion": "sensor.inversor_potencia_activa", "consumo": "sensor.casa_consumo"})

        r = EnergiaTiempoReal().leer()

        self.assertEqual(r["consumo_w"], 1250)
        self.assertFalse(r["consumo_calculado"])
        self.assertEqual(r["cubierto_por_solar_pct"], 100)

    def test_el_resumen_habla_en_espanol(self):
        texto_ = describir(EnergiaTiempoReal().leer())

        self.assertIn("3.20 kW", texto_)
        self.assertIn("se vierten 900 W a la red", texto_)

    def test_un_sensor_caido_no_rompe(self):
        guardar_sensores_energia({"produccion": "sensor.no_existe"})

        r = EnergiaTiempoReal().leer()

        self.assertIn("error", r)

    def test_la_ia_responde_con_el_consumo_real(self):
        self.ollama.respuestas = [llamada("ver_energia_ahora"), texto("Ahora mismo la casa consume 2,3 kW.")]

        respuesta = self.brain.conversacion.preguntar("¿Cuánto estoy consumiendo?")

        self.assertIn("2,3 kW", respuesta)
        resultado = self.brain.ai.herramientas_usadas[0]["resultado"]
        self.assertEqual(resultado["consumo_w"], 2300)

    def test_endpoint_web(self):
        from brain.web.servidor import leer_energia

        self.assertEqual(leer_energia()["produccion_w"], 3200)
        json.dumps(leer_energia())
