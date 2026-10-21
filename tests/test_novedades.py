import http.client
import json
import threading
import unittest
from datetime import date, datetime
from http.server import ThreadingHTTPServer

from brain.ai.vision import VisionError, interpretar_respuesta
from brain.core.config import Config
from brain.web.servidor import crear_manejador
from tests.helpers import CasoBrain

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class TestResumenDiario(CasoBrain):
    def test_junta_agenda_compra_y_peso(self):
        e = self.brain.tools.ejecutar
        e("anadir_evento", {"titulo": "Médico", "hora": "10:00"})
        e("anadir_a_compra", {"producto": "leche", "cantidad": 2})
        e("guardar_peso", {"peso": 80, "fecha": date.today().isoformat()})

        r = e("ver_resumen_diario")["resumen"]

        self.assertIn("10:00 Médico", r)
        self.assertIn("leche", r)
        self.assertIn("Último peso: 80 kg", r)

    def test_se_envia_una_vez_al_dia_y_a_su_hora(self):
        resumen = self.brain.modules.obtener("resumen")
        hoy = date.today()

        self.assertIsNone(resumen.enviar_si_toca(datetime(hoy.year, hoy.month, hoy.day, 7, 0)))  # antes de la hora
        self.assertIsNotNone(resumen.enviar_si_toca(datetime(hoy.year, hoy.month, hoy.day, 8, 45)))
        self.assertIsNone(resumen.enviar_si_toca(datetime(hoy.year, hoy.month, hoy.day, 9, 0)))  # ya enviado

        avisos = self.brain.modules.obtener("avisos").listar()
        self.assertEqual([a["tipo"] for a in avisos], ["resumen"])

    def test_configurar_hora_y_desactivar(self):
        e = self.brain.tools.ejecutar

        self.assertEqual(e("configurar_resumen_diario", {"hora": "7.45"})["configuracion"]["hora"], "07:45")
        self.assertIn("error", e("configurar_resumen_diario", {"hora": "25:00"}))

        e("configurar_resumen_diario", {"activo": False})
        hoy = date.today()
        self.assertIsNone(self.brain.modules.obtener("resumen").enviar_si_toca(datetime(hoy.year, hoy.month, hoy.day, 12, 0)))


class TestConversaciones(CasoBrain):
    def test_historiales_independientes_y_persistentes(self):
        g = self.brain.conversaciones
        recetas = g.crear("Recetas", "Esta conversación es solo de cocina.")["id"]

        self.ollama.respuestas += [{"role": "assistant", "content": "Una tortilla."}, {"role": "assistant", "content": "Tienes cita."}]

        self.assertEqual(g.preguntar(recetas, "¿Qué ceno?"), "Una tortilla.")
        self.assertEqual(g.preguntar("general", "¿Qué tengo hoy?"), "Tienes cita.")

        self.assertEqual([m["content"] for m in g.obtener(recetas).mensajes()], ["¿Qué ceno?", "Una tortilla."])
        self.assertEqual([m["content"] for m in g.obtener("general").mensajes()], ["¿Qué tengo hoy?", "Tienes cita."])

        # El tema solo llega a la IA en su conversación
        sistema = [p["messages"][0]["content"] for p in self.ollama.peticiones]
        self.assertIn("solo de cocina", sistema[0])
        self.assertNotIn("solo de cocina", sistema[1])

        # Tras reabrir BRAIN siguen ahí
        from brain.core import Brain

        otro = Brain(silencioso=True)
        self.assertEqual(len(otro.conversaciones.obtener(recetas).mensajes()), 2)
        self.assertEqual(otro.conversaciones.obtener(recetas).instrucciones, "Esta conversación es solo de cocina.")

    def test_titulo_automatico_listar_renombrar_borrar(self):
        g = self.brain.conversaciones
        id_ = g.crear()["id"]
        self.ollama.respuestas.append({"role": "assistant", "content": "ok"})
        g.preguntar(id_, "Dame ideas para una cena con amigos")

        lista = g.listar()
        self.assertEqual(lista[0]["id"], "general")
        self.assertEqual(lista[1]["titulo"], "Dame ideas para una cena con amigos")

        g.renombrar(id_, "Cenas")
        self.assertEqual(g.listar()[1]["titulo"], "Cenas")

        g.borrar(id_)
        self.assertEqual([c["id"] for c in g.listar()], ["general"])

        with self.assertRaises(KeyError):
            g.obtener(id_)

        with self.assertRaises(ValueError):
            g.borrar("general")

    def test_la_conversacion_principal_sigue_siendo_brain_conversacion(self):
        self.assertIs(self.brain.conversacion, self.brain.conversaciones.obtener("general"))


class TestVision(CasoBrain):
    RESPUESTA = '{"peso_kg": 87.4, "fecha": null, "medidas": {"imc": 27.3, "grasa_corporal_pct": 24.1}}'

    def test_interpreta_y_valida(self):
        r = interpretar_respuesta("Aquí: " + self.RESPUESTA, date(2026, 10, 11))

        self.assertEqual(r, {"peso": 87.4, "fecha": "2026-10-11", "medidas": {"imc": 27.3, "grasa_corporal_pct": 24.1}})

        for malo in ("sin json", '{"peso_kg": null}', '{"peso_kg": 5}'):
            with self.assertRaises(VisionError):
                interpretar_respuesta(malo)

        # Una medida absurda se descarta pero el peso se conserva
        self.assertEqual(interpretar_respuesta('{"peso_kg": 80, "medidas": {"imc": 900}}')["medidas"], {})

    def test_herramienta_sin_medidas(self):
        self.assertIn("mensaje", self.brain.tools.ejecutar("ver_medidas_corporales"))


class TestWebNovedades(CasoBrain):
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

    def pedir(self, metodo, ruta, cuerpo=None, tipo="application/json"):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        if isinstance(cuerpo, (dict, list)):
            cuerpo = json.dumps(cuerpo)
        con.request(metodo, ruta, cuerpo, {"Content-Type": tipo, "Host": f"127.0.0.1:{self.puerto}"})
        r = con.getresponse()
        datos = json.loads(r.read().decode("utf-8"))
        con.close()
        return r.status, datos

    def test_conversaciones_por_la_web(self):
        codigo, r = self.pedir("POST", "/api/conversaciones/crear", {"titulo": "Recetas", "instrucciones": "Solo cocina"})
        self.assertEqual(codigo, 200)
        id_ = r["conversacion"]["id"]

        self.ollama.respuestas.append({"role": "assistant", "content": "Pasta."})
        codigo, r = self.pedir("POST", "/api/chat", {"mensaje": "¿Qué como?", "conversacion": id_})
        self.assertEqual((codigo, r["respuesta"]), (200, "Pasta."))

        self.assertEqual(len(self.pedir("GET", f"/api/historial?conversacion={id_}")[1]["mensajes"]), 2)
        self.assertEqual(self.pedir("GET", "/api/historial")[1]["mensajes"], [])  # la principal sigue vacía

        self.assertEqual([c["id"] for c in self.pedir("GET", "/api/conversaciones")[1]["conversaciones"]][0], "general")

        self.assertEqual(self.pedir("POST", "/api/chat", {"mensaje": "hola", "conversacion": "nope"})[0], 404)
        self.assertEqual(self.pedir("POST", "/api/conversaciones/borrar", {"id": "general"})[0], 400)
        self.assertEqual(self.pedir("POST", "/api/limpiar", {"conversacion": id_})[0], 200)
        self.assertEqual(self.pedir("POST", "/api/conversaciones/borrar", {"id": id_})[0], 200)

    def test_captura_de_bascula(self):
        nombre = self.ollama.modelos[0]
        self.ollama.con_vision.add(nombre)
        self.ollama.respuestas.append({"role": "assistant", "content": TestVision.RESPUESTA})

        codigo, r = self.pedir("POST", "/api/imagen", PNG, "image/png")

        self.assertEqual(codigo, 200, r)
        self.assertEqual(r["peso"], 87.4)
        self.assertIn("87,4 kg", r["respuesta"])

        # La IA recibió la imagen
        self.assertIn("images", self.ollama.peticiones[-1]["messages"][0])

        self.assertEqual(self.brain.tools.ejecutar("obtener_peso")["peso"], 87.4)
        self.assertEqual({m["nombre"] for m in self.brain.tools.ejecutar("ver_medidas_corporales")["medidas"]}, {"imc", "grasa_corporal_pct"})
        self.assertEqual(len(self.brain.conversacion.mensajes()), 2)

    def test_captura_sin_modelo_con_vision_o_invalida(self):
        codigo, r = self.pedir("POST", "/api/imagen", PNG, "image/png")
        self.assertEqual(codigo, 422)
        self.assertIn("visión", r["error"])

        self.assertEqual(self.pedir("POST", "/api/imagen", b"no soy imagen", "image/png")[0], 422)
        self.assertEqual(self.pedir("POST", "/api/imagen", b"x", "text/plain")[0], 400)

        self.assertEqual(self.pedir("POST", "/api/imagen?conversacion=nope", PNG, "image/png")[0], 404)
        self.assertIsNone(self.brain.tools.ejecutar("obtener_peso"))


if __name__ == "__main__":
    unittest.main()


class TestHerramientasRelevantes(unittest.TestCase):
    def test_solo_se_envian_las_de_cada_tema(self):
        from brain.ai.herramientas_relevantes import categorias_relevantes as c

        self.assertEqual(c("enciende la luz del salón"), {"domotica", "memoria"})
        self.assertEqual(c("¿Qué puedo cocinar hoy?"), {"recetas", "memoria"})
        self.assertIn("avisos", c("recuérdame en 20 minutos sacar el pollo"))
        self.assertIn("electrodomesticos", c("la lavadora no arranca"))
        self.assertIn("sistema", c("haz una copia de seguridad"))
        self.assertIn("energia", c("¿cuánto estoy consumiendo?"))

    def test_sin_tema_claro_se_envia_lo_habitual_y_el_contexto_cuenta(self):
        from brain.ai.herramientas_relevantes import BASICAS, categorias_relevantes as c

        self.assertEqual(c("hola, ¿qué tal?"), set(BASICAS) | {"memoria"})

        # "sí, apúntalo" no dice nada, pero la conversación hablaba de la compra
        previo = [{"role": "assistant", "content": "Te falta leche. ¿La añado a la lista de la compra?"}]
        self.assertIn("compras", c("sí, hazlo", previo))

    def test_la_ia_recibe_menos_herramientas_que_el_total(self):
        from brain.tools.registry import ToolRegistry

        registro = ToolRegistry()

        self.assertLess(len(registro.esquemas({"domotica", "memoria"})), len(registro.esquemas()) // 3)

    def test_la_peticion_a_ollama_lleva_solo_las_herramientas_del_tema(self):
        caso = CasoBrain("setUp")  # reutiliza el entorno de pruebas
        caso.setUp()

        try:
            caso.ollama.respuestas.append({"role": "assistant", "content": "Hecho."})
            caso.brain.conversacion.preguntar("Apunta leche en la lista de la compra")

            enviadas = {t["function"]["name"] for t in caso.ollama.peticiones[-1]["tools"]}

            self.assertIn("anadir_a_compra", enviadas)
            self.assertNotIn("encender", enviadas)
            self.assertLess(len(enviadas), 15)
        finally:
            caso.tearDown()
