import unittest
from datetime import datetime, timedelta

from brain.core.scheduler import MotorAutomatizaciones
from brain.integrations.home_assistant import guardar_configuracion
from brain.modules.automatizaciones import Automatizaciones, interpretar_dias
from tests.helpers import CasoBrain, HomeAssistantFalso, entidades_de_ejemplo, sensores_de_energia


class CasoAuto(CasoBrain):
    def setUp(self):
        super().setUp()
        entidades = {**entidades_de_ejemplo(), **sensores_de_energia()}
        self.ha = HomeAssistantFalso(entidades=entidades)
        self.ha.iniciar()
        guardar_configuracion(self.ha.url, HomeAssistantFalso.TOKEN)
        self.e = self.brain.tools.ejecutar
        self.auto = Automatizaciones()

    def tearDown(self):
        self.ha.parar()
        super().tearDown()

    def aviso_titulos(self):
        return [a["titulo"] for a in self.e("ver_avisos", {"todos": True}).get("avisos", [])]


class TestCrear(CasoAuto):
    def test_crear_listar_pausar_borrar(self):
        r = self.e("crear_automatizacion", {"nombre": "Aviso sol", "disparador": "energia", "magnitud": "sobrante",
                                            "condicion": "mayor", "valor": "1500", "accion": "aviso", "mensaje": "Pon la lavadora"})
        self.assertIn("1500", r["creada"]["regla"])

        self.assertEqual(self.e("ver_automatizaciones")["automatizaciones"][0]["nombre"], "Aviso sol")
        self.assertFalse(self.e("activar_automatizacion", {"nombre": "sol", "activa": False})["activa"])
        self.assertEqual(self.e("borrar_automatizacion", {"nombre": "Aviso sol"})["borrada"]["nombre"], "Aviso sol")
        self.assertIn("mensaje", self.e("ver_automatizaciones"))

    def test_validaciones(self):
        e = self.e
        base = {"nombre": "x", "accion": "aviso"}

        self.assertIn("error", e("crear_automatizacion", {**base, "disparador": "luna"}))
        self.assertIn("HH:MM", e("crear_automatizacion", {**base, "disparador": "hora", "hora": "tarde"})["error"])
        self.assertIn("días", e("crear_automatizacion", {**base, "disparador": "hora", "hora": "8:00", "dias": "quincenas"})["error"])
        self.assertIn("error", e("crear_automatizacion", {**base, "disparador": "energia", "magnitud": "viento", "condicion": "mayor", "valor": 1}))
        self.assertIn("error", e("crear_automatizacion", {**base, "disparador": "energia", "magnitud": "consumo", "condicion": "mayor", "valor": "mucho"}))
        self.assertIn("error", e("crear_automatizacion", {"nombre": "y", "disparador": "hora", "hora": "8:00", "accion": "encender"}))  # sin objetivo
        self.assertIn("No encuentro", e("crear_automatizacion", {"nombre": "z", "disparador": "hora", "hora": "8:00", "accion": "encender", "objetivo": "nave espacial"})["error"])

        e("crear_automatizacion", {**base, "disparador": "hora", "hora": "8:00"})
        self.assertIn("Ya existe", e("crear_automatizacion", {**base, "disparador": "hora", "hora": "9:00"})["error"])

    def test_no_acepta_cerraduras(self):
        r = self.e("crear_automatizacion", {"nombre": "puerta", "disparador": "hora", "hora": "8:00", "accion": "encender", "objetivo": "cerradura de la puerta"})

        self.assertIn("error", r)

    def test_dias(self):
        self.assertEqual(interpretar_dias("laborables"), [0, 1, 2, 3, 4])
        self.assertEqual(interpretar_dias("lunes, jueves"), [0, 3])
        self.assertEqual(interpretar_dias("fin de semana"), [5, 6])


class TestEjecucion(CasoAuto):
    def test_hora_se_ejecuta_una_vez_al_dia_dentro_de_la_ventana(self):
        self.e("crear_automatizacion", {"nombre": "Buenos días", "disparador": "hora", "hora": "07:30", "accion": "aviso", "mensaje": "Arriba"})

        dia = datetime(2026, 10, 12, 7, 30)  # lunes

        self.assertEqual(self.auto.evaluar(dia - timedelta(minutes=1)), [])
        self.assertEqual(len(self.auto.evaluar(dia + timedelta(minutes=1))), 1)
        self.assertEqual(self.auto.evaluar(dia + timedelta(minutes=2)), [])  # ya hecha hoy
        self.assertEqual(len(self.auto.evaluar(dia + timedelta(days=1, minutes=1))), 1)  # al día siguiente, otra vez
        self.assertEqual(self.auto.evaluar(dia + timedelta(days=2, minutes=30)), [])  # fuera de ventana
        self.assertIn("Buenos días", self.aviso_titulos())

    def test_hora_respeta_los_dias(self):
        self.e("crear_automatizacion", {"nombre": "Lunes", "disparador": "hora", "hora": "09:00", "dias": "lunes", "accion": "aviso"})

        self.assertEqual(self.auto.evaluar(datetime(2026, 10, 13, 9, 1)), [])  # martes
        self.assertEqual(len(self.auto.evaluar(datetime(2026, 10, 12, 9, 1))), 1)

    def test_hora_enciende_un_aparato_real(self):
        self.e("crear_automatizacion", {"nombre": "Luz noche", "disparador": "hora", "hora": "20:00", "accion": "encender", "objetivo": "luz de la cocina"})

        r = self.auto.evaluar(datetime(2026, 10, 12, 20, 2))

        self.assertIn("encender luz de la cocina", r[0])
        self.assertTrue(self.ha.llamadas)

    def test_energia_dispara_al_cruzar_el_umbral_y_no_repite(self):
        self.e("crear_automatizacion", {"nombre": "Sol", "disparador": "energia", "magnitud": "produccion", "condicion": "mayor", "valor": "3000",
                                        "accion": "aviso", "mensaje": "Mucho sol", "espera_minutos": 0})
        ahora = datetime(2026, 10, 12, 12, 0)

        valores = iter([2000, 3200, 3500, 2500, 3300])
        self.auto._energia = lambda: {"configurado": True, "produccion_w": next(valores), "consumo_w": 500}

        resultados = [len(self.auto.evaluar(ahora + timedelta(minutes=i))) for i in range(5)]

        # 1ª lectura (2000) no cumple; 2ª cruza -> dispara; 3ª sigue cumpliendo -> no; 4ª baja; 5ª vuelve a cruzar -> dispara
        self.assertEqual(resultados, [0, 1, 0, 0, 1])

    def test_la_primera_lectura_ya_cumplida_no_dispara(self):
        self.e("crear_automatizacion", {"nombre": "Sol", "disparador": "energia", "magnitud": "produccion", "condicion": "mayor", "valor": "100", "accion": "aviso"})
        self.auto._energia = lambda: {"configurado": True, "produccion_w": 5000}

        self.assertEqual(self.auto.evaluar(datetime.now()), [])

    def test_espera_entre_ejecuciones(self):
        self.e("crear_automatizacion", {"nombre": "Sol", "disparador": "energia", "magnitud": "sobrante", "condicion": "mayor", "valor": "1000",
                                        "accion": "aviso", "espera_minutos": 30})
        base = datetime(2026, 10, 12, 12, 0)
        valores = iter([0, 2000, 0, 2000, 0, 2000])
        self.auto._energia = lambda: {"configurado": True, "produccion_w": next(valores), "consumo_w": 0}

        resultados = [len(self.auto.evaluar(base + timedelta(minutes=10 * i))) for i in range(6)]

        self.assertEqual(resultados, [0, 1, 0, 0, 0, 1])  # el 2º cruce (min 30) cae dentro de la espera... el 3º ya no

    def test_sensor_de_home_assistant(self):
        r = self.e("crear_automatizacion", {"nombre": "Frío", "disparador": "sensor", "sensor": "temperatura salón", "condicion": "menor",
                                            "valor": "18", "accion": "aviso", "mensaje": "Hace frío"})
        self.assertNotIn("error", r)

        self.assertEqual(self.auto.evaluar(datetime.now()), [])  # 21.3 ºC: no se cumple

        self.ha.entidades["sensor.temp_salon"]["estado"] = "16.5"
        self.assertEqual(len(self.auto.evaluar(datetime.now())), 1)

    def test_sensor_ambiguo_o_inexistente(self):
        self.assertIn("error", self.e("crear_automatizacion", {"nombre": "a", "disparador": "sensor", "sensor": "submarino", "condicion": "mayor", "valor": "1", "accion": "aviso"}))

    def test_una_regla_rota_no_para_las_demas_y_el_motor_no_falla(self):
        self.e("crear_automatizacion", {"nombre": "Rota", "disparador": "energia", "magnitud": "produccion", "condicion": "mayor", "valor": "1", "accion": "aviso"})
        self.e("crear_automatizacion", {"nombre": "Buena", "disparador": "hora", "hora": "10:00", "accion": "aviso"})

        def mal():
            raise RuntimeError("inversor roto")

        self.auto._energia = mal

        hechas = self.auto.evaluar(datetime(2026, 10, 12, 10, 1))  # el fallo del inversor no impide la regla de hora

        self.assertEqual(len(hechas), 1)
        self.assertIn("Buena", hechas[0])

    def test_ejecutar_ahora_y_motor_del_planificador(self):
        self.e("crear_automatizacion", {"nombre": "Prueba", "disparador": "hora", "hora": "03:00", "accion": "aviso", "mensaje": "ding"})

        self.assertIn("aviso enviado", self.e("ejecutar_automatizacion", {"nombre": "prueba"})["resultado"])
        self.assertEqual(self.e("ver_automatizaciones")["automatizaciones"][0]["ejecuciones"], 1)
        self.assertIn("ejecutadas", MotorAutomatizaciones()())


if __name__ == "__main__":
    unittest.main()
