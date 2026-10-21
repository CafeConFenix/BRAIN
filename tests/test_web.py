import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from tests.helpers import CasoBrain, llamada, texto
from brain.web.servidor import crear_manejador


class TestWeb(CasoBrain):
    def setUp(self):
        super().setUp()

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain))
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_address[1]

        threading.Thread(
            target=lambda: self.servidor.serve_forever(poll_interval=0.02),
            daemon=True,
        ).start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()

        super().tearDown()

    def peticion(self, metodo, ruta, cuerpo=None, cabeceras=None):
        conexion = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)

        encabezados = {"Content-Type": "application/json"} if metodo == "POST" else {}
        encabezados.update(cabeceras or {})

        conexion.request(
            metodo,
            ruta,
            body=json.dumps(cuerpo) if cuerpo is not None else None,
            headers=encabezados,
        )

        respuesta = conexion.getresponse()
        datos = respuesta.read()

        conexion.close()

        return respuesta.status, datos

    def test_pagina_principal(self):
        codigo, datos = self.peticion("GET", "/")

        self.assertEqual(codigo, 200)
        self.assertIn(b"BRAIN", datos)

    def test_estado(self):
        codigo, datos = self.peticion("GET", "/api/estado")

        estado = json.loads(datos)

        self.assertEqual(codigo, 200)
        self.assertTrue(estado["ia_lista"])
        self.assertEqual(estado["modelo"], "qwen3:4b")

    def test_estado_sin_modelos_explica_que_hacer(self):
        self.ollama.modelos.clear()

        estado = json.loads(self.peticion("GET", "/api/estado")[1])

        self.assertFalse(estado["ia_lista"])
        self.assertTrue(estado["sin_modelos"])
        self.assertIn("botón", estado["mensaje"])
        self.assertTrue(estado["recomendado"]["etiqueta"])

    def test_descarga_desde_la_web(self):
        import time

        self.ollama.modelos.clear()

        self.peticion("POST", "/api/descargar", {})

        for _ in range(50):
            estado = json.loads(self.peticion("GET", "/api/estado")[1])

            if estado["ia_lista"]:
                break

            time.sleep(0.1)

        self.assertTrue(estado["ia_lista"])
        self.assertEqual(len(self.ollama.descargados), 1)

    def test_chat_con_herramienta_y_panel(self):
        self.ollama.respuestas = [
            llamada("guardar_peso", peso=88.4, fecha="2026-08-10"),
            texto("Anotado."),
        ]

        codigo, datos = self.peticion("POST", "/api/chat", {"mensaje": "Hoy peso 88,4"})

        respuesta = json.loads(datos)

        self.assertEqual(codigo, 200)
        self.assertEqual(respuesta["respuesta"], "Anotado.")
        self.assertEqual(respuesta["herramientas"], ["guardar_peso"])

        resumen = json.loads(self.peticion("GET", "/api/resumen")[1])

        self.assertEqual(resumen["peso"][-1]["peso"], 88.4)

        historial = json.loads(self.peticion("GET", "/api/historial")[1])

        self.assertEqual(len(historial["mensajes"]), 2)

    def test_chat_mensaje_vacio(self):
        self.assertEqual(self.peticion("POST", "/api/chat", {"mensaje": "  "})[0], 400)

    def test_chat_sin_ia_devuelve_error_legible(self):
        self.ollama.modelos.clear()

        codigo, datos = self.peticion("POST", "/api/chat", {"mensaje": "hola"})

        self.assertEqual(codigo, 503)
        self.assertIn("error", json.loads(datos))

    def test_limpiar(self):
        self.ollama.respuestas = [texto("hola")]

        self.peticion("POST", "/api/chat", {"mensaje": "hola"})
        self.peticion("POST", "/api/limpiar", {})

        self.assertEqual(json.loads(self.peticion("GET", "/api/historial")[1])["mensajes"], [])

    def test_rechaza_otros_hosts_contra_dns_rebinding(self):
        codigo, _ = self.peticion("GET", "/api/resumen", cabeceras={"Host": "malvado.example.com"})

        self.assertEqual(codigo, 403)

    def test_rechaza_peticiones_de_otras_webs(self):
        codigo, _ = self.peticion(
            "POST",
            "/api/chat",
            {"mensaje": "hola"},
            cabeceras={"Origin": "http://malvado.example.com"},
        )

        self.assertEqual(codigo, 403)

    def test_post_exige_json(self):
        codigo, _ = self.peticion("POST", "/api/chat", None, cabeceras={"Content-Type": "text/plain"})

        self.assertEqual(codigo, 415)

    def test_ruta_inexistente(self):
        self.assertEqual(self.peticion("GET", "/nada")[0], 404)


if __name__ == "__main__":
    unittest.main()
