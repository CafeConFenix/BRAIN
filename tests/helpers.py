import json
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brain.core.config import Config


class OllamaFalso:
    """
    Servidor que imita a Ollama (/api/tags y /api/chat) para poder probar
    BRAIN sin tener Ollama instalado ni gastar tiempo en la IA real.

    Las respuestas de /api/chat se programan en `respuestas`:
      - un diccionario  -> es el mensaje que devuelve el "modelo"
      - ("error", 400, "texto") -> responde con ese error HTTP
    """

    def __init__(self, modelos=("qwen3:4b",)):
        self.modelos = list(modelos)
        self.respuestas = []
        self.peticiones = []
        self.pull_ok = True
        self.descargados = []

        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _enviar(self, codigo, datos):
                cuerpo = json.dumps(datos).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def do_GET(self):
                if self.path == "/api/tags":
                    return self._enviar(200, {"models": [{"name": m} for m in falso.modelos]})

                self._enviar(404, {"error": "no existe"})

            def do_POST(self):
                longitud = int(self.headers.get("Content-Length", "0"))
                datos = json.loads(self.rfile.read(longitud).decode("utf-8"))

                if self.path == "/api/pull":
                    if falso.pull_ok:
                        falso.modelos.append(datos["model"])
                        lineas = [
                            {"status": "pulling", "completed": 50, "total": 100},
                            {"status": "success"},
                        ]
                    else:
                        lineas = [{"error": "model not found"}]

                    cuerpo = ("\n".join(json.dumps(x) for x in lineas) + "\n").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(cuerpo)))
                    self.end_headers()
                    self.wfile.write(cuerpo)
                    falso.descargados.append(datos["model"])
                    return

                falso.peticiones.append(datos)

                if falso.respuestas:
                    respuesta = falso.respuestas.pop(0)
                else:
                    respuesta = {"role": "assistant", "content": "(sin respuesta programada)"}

                if isinstance(respuesta, tuple):
                    _, codigo, texto = respuesta
                    return self._enviar(codigo, {"error": texto})

                self._enviar(200, {"message": respuesta})

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.hilo = threading.Thread(
            target=lambda: self.servidor.serve_forever(poll_interval=0.02),
            daemon=True,
        )

    @property
    def url(self):
        return f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def iniciar(self):
        self.hilo.start()

    def parar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


def llamada(herramienta, /, **argumentos):
    """Mensaje del modelo pidiendo usar una herramienta."""

    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": herramienta, "arguments": argumentos}}],
    }


def texto(contenido):
    """Mensaje normal del modelo."""

    return {"role": "assistant", "content": contenido}


class CasoBrain(unittest.TestCase):
    """
    Prepara cada test con una carpeta de datos temporal (no toca tus datos
    reales) y un Ollama falso.
    """

    modelos = ("qwen3:4b",)

    def setUp(self):
        self._antes = (Config.DATOS, Config.LOGS, Config.OLLAMA_URL, Config.MODELO)

        self.carpeta = Path(tempfile.mkdtemp(prefix="brain_test_"))

        Config.DATOS = self.carpeta / "datos"
        Config.LOGS = Config.DATOS / "logs"
        Config.MODELO = ""

        self.ollama = OllamaFalso(self.modelos)
        self.ollama.iniciar()

        Config.OLLAMA_URL = self.ollama.url

        from brain.core import Brain

        self.brain = Brain(silencioso=True)

    def tearDown(self):
        self.ollama.parar()

        Config.DATOS, Config.LOGS, Config.OLLAMA_URL, Config.MODELO = self._antes

        shutil.rmtree(self.carpeta, ignore_errors=True)


class HomeAssistantFalso:
    """
    Servidor que imita a Home Assistant (/api/states, /api/template y
    /api/services) para probar la domótica sin tener una casa real.
    """

    TOKEN = "token-de-prueba"

    def __init__(self, entidades=None):
        self.entidades = entidades if entidades is not None else entidades_de_ejemplo()
        self.llamadas = []

        falso = self

        class Manejador(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _enviar(self, codigo, datos, texto=False):
                cuerpo = (datos if texto else json.dumps(datos)).encode("utf-8")
                self.send_response(codigo)
                self.send_header("Content-Type", "text/plain" if texto else "application/json")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)

            def _autorizado(self):
                return self.headers.get("Authorization") == f"Bearer {falso.TOKEN}"

            def do_GET(self):
                if not self._autorizado():
                    return self._enviar(401, {"message": "401: Unauthorized"})

                if self.path == "/api/":
                    return self._enviar(200, {"message": "API running."})

                if self.path == "/api/states":
                    return self._enviar(
                        200,
                        [
                            {"entity_id": e, "state": d["estado"], "attributes": d.get("atributos", {})}
                            for e, d in falso.entidades.items()
                        ],
                    )

                if self.path.startswith("/api/states/"):
                    entidad = self.path[len("/api/states/") :]
                    d = falso.entidades.get(entidad)

                    if d is None:
                        return self._enviar(404, {})

                    return self._enviar(200, {"entity_id": entidad, "state": d["estado"], "attributes": d.get("atributos", {})})

                self._enviar(404, {})

            def do_POST(self):
                if not self._autorizado():
                    return self._enviar(401, {"message": "401: Unauthorized"})

                longitud = int(self.headers.get("Content-Length", "0"))
                datos = json.loads(self.rfile.read(longitud).decode("utf-8") or "{}")

                if self.path == "/api/template":
                    lineas = "".join(f"{e}|{d.get('area', '')}\n" for e, d in falso.entidades.items())
                    return self._enviar(200, lineas, texto=True)

                if self.path.startswith("/api/services/"):
                    _, _, _, dominio, servicio = self.path.split("/")
                    falso.llamadas.append((dominio, servicio, datos))
                    return self._enviar(200, [])

                self._enviar(404, {})

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
        self.hilo = threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.servidor.server_address[1]}"

    def iniciar(self):
        self.hilo.start()

    def parar(self):
        self.servidor.shutdown()
        self.servidor.server_close()


def entidades_de_ejemplo():
    return {
        "light.salon_techo": {
            "estado": "on",
            "area": "Salón",
            "atributos": {"friendly_name": "Luz salón", "brightness": 255},
        },
        "light.salon_lampara": {
            "estado": "off",
            "area": "Salón",
            "atributos": {"friendly_name": "Lámpara salón"},
        },
        "light.cocina": {"estado": "off", "area": "Cocina", "atributos": {"friendly_name": "Luz cocina"}},
        "light.dormitorio": {"estado": "off", "area": "Dormitorio", "atributos": {"friendly_name": "Luz dormitorio"}},
        "cover.persiana_dormitorio": {
            "estado": "open",
            "area": "Dormitorio",
            "atributos": {"friendly_name": "Persiana dormitorio", "device_class": "shutter", "current_position": 100},
        },
        "cover.garaje": {
            "estado": "closed",
            "area": "Garaje",
            "atributos": {"friendly_name": "Puerta del garaje", "device_class": "garage"},
        },
        "lock.entrada": {"estado": "locked", "area": "Entrada", "atributos": {"friendly_name": "Cerradura entrada"}},
        "climate.salon": {
            "estado": "heat",
            "area": "Salón",
            "atributos": {"friendly_name": "Termostato salón", "current_temperature": 20.5, "temperature": 21},
        },
        "scene.noche": {"estado": "scening", "atributos": {"friendly_name": "Noche"}},
        "sensor.temp_salon": {
            "estado": "21.3",
            "area": "Salón",
            "atributos": {"friendly_name": "Temperatura salón", "unit_of_measurement": "°C"},
        },
    }


def sensores_de_energia():
    """Sensores típicos de un inversor solar y un contador, para las pruebas."""

    def potencia(nombre, valor, unidad="W"):
        return {"estado": str(valor), "atributos": {"friendly_name": nombre, "unit_of_measurement": unidad, "device_class": "power"}}

    return {
        "sensor.inversor_potencia_activa": potencia("Inversor Huawei Potencia activa", 3.2, "kW"),
        "sensor.inversor_pv1_power": potencia("Inversor PV1 power", 1600),
        "sensor.inversor_energia_hoy": {"estado": "12", "atributos": {"friendly_name": "Inversor energía hoy", "unit_of_measurement": "kWh"}},
        "sensor.contador_potencia": potencia("Contador potencia red", -900),
        "sensor.bateria_nivel": {"estado": "64", "atributos": {"friendly_name": "Batería nivel", "unit_of_measurement": "%", "device_class": "battery"}},
        "sensor.movil_bateria": {"estado": "40", "atributos": {"friendly_name": "Móvil batería", "unit_of_measurement": "%", "device_class": "battery"}},
    }
