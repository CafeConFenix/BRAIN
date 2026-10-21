import http.client
import json
import threading
import unittest
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from unittest import mock

from brain.core.config import Config
from brain.core.scheduler import AvisoEventos, SondeoHomeAssistant, revisar_recordatorios
from brain.integrations.home_assistant import guardar_configuracion
from brain.web.servidor import crear_manejador
from tests.helpers import CasoBrain, HomeAssistantFalso, sensores_de_energia


class CasoAvisos(CasoBrain):
    def setUp(self):
        super().setUp()
        parche = mock.patch("brain.modules.avisos.notificador.notificar")
        self.notificar = parche.start()
        self.addCleanup(parche.stop)
        self.avisos = self.brain.modules.obtener("avisos")
        self.e = self.brain.tools.ejecutar

    def sonido(self, nombre="campana.wav"):
        carpeta = Config.DATOS / "sonidos"
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre).write_bytes(b"RIFF....WAVE")


class TestAvisos(CasoAvisos):
    def test_aviso_se_guarda_y_notifica_con_su_sonido(self):
        self.sonido()
        self.e("asignar_sonido", {"tipo": "recordatorio", "archivo": "campana"})

        self.avisos.configurar(no_molestar_desde="ninguno")
        self.avisos.avisar("Hola", "mundo", tipo="recordatorio")

        self.assertEqual(self.notificar.call_count, 1)
        titulo, mensaje, ruta = self.notificar.call_args[0]
        self.assertEqual((titulo, mensaje, ruta.name), ("Hola", "mundo", "campana.wav"))
        self.assertEqual(self.e("ver_avisos")["avisos"][0]["titulo"], "Hola")

        self.e("marcar_avisos_leidos")
        self.assertIn("mensaje", self.e("ver_avisos"))

    def test_silencio_y_no_molestar(self):
        self.avisos.configurar(silencio=True)
        self.avisos.avisar("a", tipo="info")
        self.avisos.avisar("b", tipo="alerta")
        self.assertEqual(self.notificar.call_count, 0)  # se guardan pero no suenan
        self.assertEqual(len(self.avisos.listar()), 2)

        self.avisos.configurar(silencio=False)
        ahora = datetime.now()
        desde = (ahora - timedelta(minutes=5)).strftime("%H:%M")
        hasta = (ahora + timedelta(minutes=5)).strftime("%H:%M")
        self.avisos.configurar(no_molestar_desde=desde, no_molestar_hasta=hasta)

        self.avisos.avisar("normal", tipo="info")
        self.assertEqual(self.notificar.call_count, 0)

        self.avisos.avisar("fuego", tipo="alerta")  # las críticas atraviesan "no molestar"
        self.assertEqual(self.notificar.call_count, 1)

    def test_franja_que_cruza_la_medianoche(self):
        self.avisos.configurar(no_molestar_desde="23:00", no_molestar_hasta="07:00")
        dia = datetime(2026, 1, 1)

        self.assertTrue(self.avisos.en_no_molestar(dia.replace(hour=23, minute=30)))
        self.assertTrue(self.avisos.en_no_molestar(dia.replace(hour=3)))
        self.assertFalse(self.avisos.en_no_molestar(dia.replace(hour=12)))

    def test_validaciones(self):
        self.assertIn("error", self.e("asignar_sonido", {"tipo": "volcan", "archivo": "x"}))
        self.assertIn("No hay sonidos", self.e("asignar_sonido", {"tipo": "info", "archivo": "x"})["error"])
        self.assertIn("error", self.e("configurar_avisos", {"no_molestar_desde": "las diez"}))

        self.sonido()
        self.assertIn("No encuentro", self.e("asignar_sonido", {"tipo": "info", "archivo": "otro"})["error"])
        self.assertEqual(self.e("asignar_sonido", {"tipo": "info", "archivo": "ninguno"})["asignado"]["sonido"], None)

    def test_ruta_de_sonido_no_sale_de_la_carpeta(self):
        self.sonido()

        self.assertIsNone(self.avisos.ruta_sonido("../brain.db"))
        self.assertIsNotNone(self.avisos.ruta_sonido("campana.wav"))


class TestRecordatorios(CasoAvisos):
    def test_crear_listar_cancelar(self):
        r = self.e("crear_recordatorio", {"mensaje": "sacar el pollo", "en_minutos": 20})["programado"]

        self.assertEqual(self.e("ver_recordatorios")["recordatorios"][0]["mensaje"], "sacar el pollo")
        self.assertEqual(self.e("cancelar_recordatorio", {"id": r["id"]}), {"cancelado": r["id"]})
        self.assertIn("error", self.e("cancelar_recordatorio", {"id": r["id"]}))

    def test_errores(self):
        self.assertIn("error", self.e("crear_recordatorio", {"mensaje": "x"}))
        self.assertIn("error", self.e("crear_recordatorio", {"mensaje": "x", "fecha_hora": "2020-01-01 10:00"}))
        self.assertIn("error", self.e("crear_recordatorio", {"mensaje": "x", "fecha_hora": "pronto"}))

    def test_solo_hora_pasa_a_manana_si_ya_paso(self):
        ahora = datetime.now()
        hace_poco = (ahora - timedelta(minutes=2)).strftime("%H:%M")

        cuando = self.e("crear_recordatorio", {"mensaje": "x", "fecha_hora": hace_poco})["programado"]["cuando"]

        self.assertGreater(datetime.strptime(cuando, "%Y-%m-%d %H:%M"), ahora)

    def test_el_planificador_lo_dispara_una_sola_vez(self):
        self.avisos.crear_recordatorio("llamar", en_minutos=1)
        self.avisos.db.tomar_recordatorios_vencidos("2000-01-01T00:00:00")  # nada vencido aún

        self.assertEqual(revisar_recordatorios(), "0 recordatorios")

        with mock.patch("brain.modules.avisos.datetime") as reloj:
            reloj.now.return_value = datetime.now() + timedelta(minutes=5)
            reloj.side_effect = datetime
            self.assertEqual(revisar_recordatorios(), "1 recordatorios")
            self.assertEqual(revisar_recordatorios(), "0 recordatorios")

        self.assertEqual(self.e("ver_avisos")["avisos"][0]["titulo"], "Recordatorio")


class TestAvisosDelPlanificador(CasoAvisos):
    def test_evento_con_hora_avisa_30_minutos_antes(self):
        ahora = datetime.now()
        self.e("anadir_evento", {"titulo": "Dentista", "fecha": ahora.strftime("%Y-%m-%d"), "hora": (ahora + timedelta(minutes=20)).strftime("%H:%M")})
        self.e("anadir_evento", {"titulo": "Lejano", "fecha": ahora.strftime("%Y-%m-%d"), "hora": "23:59"})

        aviso = AvisoEventos()

        if ahora.hour * 60 + ahora.minute < 23 * 60 + 29:  # evita falsos fallos justo antes de medianoche
            self.assertEqual(aviso(), "1 avisos de agenda")
            self.assertEqual(aviso(), "0 avisos de agenda")  # no repite

    def test_alerta_de_home_assistant_avisa_una_vez(self):
        entidades = {
            **sensores_de_energia(),
            "binary_sensor.agua_bano": {"estado": "on", "atributos": {"friendly_name": "Fuga baño", "device_class": "moisture"}},
        }
        ha = HomeAssistantFalso(entidades=entidades)
        ha.iniciar()
        self.addCleanup(ha.parar)
        guardar_configuracion(ha.url, HomeAssistantFalso.TOKEN)

        sondeo = SondeoHomeAssistant()
        sondeo()
        sondeo()

        avisos = self.e("ver_avisos", {"todos": True})["avisos"]
        self.assertEqual(len(avisos), 1)
        self.assertIn("Fuga de agua", avisos[0]["titulo"])
        self.assertEqual(avisos[0]["nivel"], "critico")


class TestWebAvisos(CasoAvisos):
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

    def pedir(self, metodo, ruta, cuerpo=None, crudo=False):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        cabeceras = {"Content-Type": "application/json", "Host": f"127.0.0.1:{self.puerto}"}
        con.request(metodo, ruta, json.dumps(cuerpo) if cuerpo is not None else None, cabeceras)
        r = con.getresponse()
        datos = r.read()
        con.close()
        return r.status, (datos if crudo else json.loads(datos.decode("utf-8")))

    def test_lista_marca_leidos_y_sirve_el_sonido(self):
        self.sonido()
        self.avisos.asignar_sonido("info", "campana.wav")
        self.avisos.configurar(no_molestar_desde="ninguno")
        self.avisos.avisar("Hola", "web")

        codigo, r = self.pedir("GET", "/api/avisos")
        self.assertEqual((codigo, r["no_leidos"], r["avisos"][0]["sonido"]), (200, 1, "campana.wav"))
        self.assertIn("sonar_web", r["avisos"][0])

        self.assertEqual(self.pedir("GET", "/api/sonido/campana.wav", crudo=True)[1][:4], b"RIFF")
        self.assertEqual(self.pedir("GET", "/api/sonido/..%2Fbrain.db")[0], 404)

        self.pedir("POST", "/api/avisos/leer", {})
        self.assertEqual(self.pedir("GET", "/api/avisos")[1]["no_leidos"], 0)


if __name__ == "__main__":
    unittest.main()
