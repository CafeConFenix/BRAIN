import json
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from brain.core.config import Config


class FakeOllama:
    """
    Servidor que imita a Ollama (/api/tags y /api/chat) para poder probar
    BRAIN sin tener Ollama instalado ni gastar tiempo en la IA real.

    Las respuestas de /api/chat se programan en `respuestas`:
      - un diccionario  -> es el mensaje que devuelve el "model"
      - ("error", 400, "text") -> responde con ese error HTTP
    """

    def __init__(self, models=("qwen3:4b",)):
        self.models = list(models)
        self.responses = []
        self.requests = []
        self.pull_ok = True
        self.downloaded = []
        self.with_vision = set()  # modelos que declaran la capacidad "vision"

        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, data):
                body = json.dumps(data).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    return self._send(200, {"models": [{"name": m} for m in fake.models]})

                self._send(404, {"error": "no existe"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8"))

                if self.path == "/api/show":
                    capabilities = ["completion", "tools"] + (["vision"] if data.get("model") in fake.with_vision else [])
                    return self._send(200, {"capabilities": capabilities})

                if self.path == "/api/pull":
                    if fake.pull_ok:
                        fake.models.append(data["model"])
                        lines = [
                            {"status": "pulling", "completed": 50, "total": 100},
                            {"status": "success"},
                        ]
                    else:
                        lines = [{"error": "model not found"}]

                    body = ("\n".join(json.dumps(x) for x in lines) + "\n").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    fake.downloaded.append(data["model"])
                    return

                fake.requests.append(data)

                if fake.responses:
                    response = fake.responses.pop(0)
                else:
                    response = {"role": "assistant", "content": "(sin respuesta programada)"}

                if isinstance(response, tuple):
                    _, code, text = response
                    return self._send(code, {"error": text})

                self._send(200, {"message": response})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.02),
            daemon=True,
        )

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def call(tool, /, **arguments):
    """Mensaje del modelo pidiendo usar una herramienta."""

    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": tool, "arguments": arguments}}],
    }


def text(content):
    """Mensaje normal del modelo."""

    return {"role": "assistant", "content": content}


class CaseBrain(unittest.TestCase):
    """
    Prepara cada test con una carpeta de datos temporal (no toca tus datos
    reales) y un Ollama falso.
    """

    models = ("qwen3:4b",)

    def setUp(self):
        self._before = (Config.DATA, Config.LOGS, Config.OLLAMA_URL, Config.MODEL)

        self.folder = Path(tempfile.mkdtemp(prefix="brain_test_"))

        Config.DATA = self.folder / "data"
        Config.LOGS = Config.DATA / "logs"
        Config.MODEL = ""

        self.ollama = FakeOllama(self.models)
        self.ollama.start()

        Config.OLLAMA_URL = self.ollama.url

        from brain.core import Brain

        self.brain = Brain(quiet=True)

    def tearDown(self):
        self.ollama.stop()

        Config.DATA, Config.LOGS, Config.OLLAMA_URL, Config.MODEL = self._before

        shutil.rmtree(self.folder, ignore_errors=True)


class FakeHomeAssistant:
    """
    Servidor que imita a Home Assistant (/api/states, /api/template y
    /api/services) para probar la domótica sin tener una casa real.
    """

    TOKEN = "token-de-prueba"

    def __init__(self, entities=None):
        self.entities = entities if entities is not None else example_entities()
        self.calls = []

        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code, data, text=False):
                body = (data if text else json.dumps(data)).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/plain" if text else "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self):
                return self.headers.get("Authorization") == f"Bearer {fake.TOKEN}"

            def do_GET(self):
                if not self._authorized():
                    return self._send(401, {"message": "401: Unauthorized"})

                if self.path == "/api/":
                    return self._send(200, {"message": "API running."})

                if self.path == "/api/states":
                    return self._send(
                        200,
                        [
                            {"entity_id": e, "state": d["state"], "attributes": d.get("attributes", {})}
                            for e, d in fake.entities.items()
                        ],
                    )

                if self.path.startswith("/api/states/"):
                    entity = self.path[len("/api/states/") :]
                    d = fake.entities.get(entity)

                    if d is None:
                        return self._send(404, {})

                    return self._send(200, {"entity_id": entity, "state": d["state"], "attributes": d.get("attributes", {})})

                self._send(404, {})

            def do_POST(self):
                if not self._authorized():
                    return self._send(401, {"message": "401: Unauthorized"})

                length = int(self.headers.get("Content-Length", "0"))
                data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")

                if self.path == "/api/template":
                    lines = "".join(f"{e}|{d.get('area', '')}\n" for e, d in fake.entities.items())
                    return self._send(200, lines, text=True)

                if self.path.startswith("/api/services/"):
                    _, _, _, domain, service = self.path.split("/")
                    fake.calls.append((domain, service, data))
                    return self._send(200, [])

                self._send(404, {})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def example_entities():
    return {
        "light.living_room_ceiling": {
            "state": "on",
            "area": "Living room",
            "attributes": {"friendly_name": "Living room light", "brightness": 255},
        },
        "light.living_room_lamp": {
            "state": "off",
            "area": "Living room",
            "attributes": {"friendly_name": "Living room lamp"},
        },
        "light.kitchen": {"state": "off", "area": "Kitchen", "attributes": {"friendly_name": "Kitchen light"}},
        "light.bedroom": {"state": "off", "area": "Bedroom", "attributes": {"friendly_name": "Bedroom light"}},
        "cover.bedroom_blind": {
            "state": "open",
            "area": "Bedroom",
            "attributes": {"friendly_name": "Bedroom blind", "device_class": "shutter", "current_position": 100},
        },
        "cover.garage": {
            "state": "closed",
            "area": "Garage",
            "attributes": {"friendly_name": "Garage door", "device_class": "garage"},
        },
        "lock.hallway": {"state": "locked", "area": "Hallway", "attributes": {"friendly_name": "Hallway lock"}},
        "climate.living_room": {
            "state": "heat",
            "area": "Living room",
            "attributes": {"friendly_name": "Living room thermostat", "current_temperature": 20.5, "temperature": 21},
        },
        "scene.night": {"state": "scening", "attributes": {"friendly_name": "Night"}},
        "sensor.living_room_temp": {
            "state": "21.3",
            "area": "Living room",
            "attributes": {"friendly_name": "Living room temperature", "unit_of_measurement": "°C"},
        },
    }


def energy_sensors():
    """Sensores típicos de un inversor solar y un contador, para las pruebas."""

    def power(name, value, unit="W"):
        return {"state": str(value), "attributes": {"friendly_name": name, "unit_of_measurement": unit, "device_class": "power"}}

    return {
        "sensor.inversor_potencia_activa": power("Inversor Huawei Potencia activa", 3.2, "kW"),
        "sensor.inversor_pv1_power": power("Inversor PV1 power", 1600),
        "sensor.inversor_energia_hoy": {"state": "12", "attributes": {"friendly_name": "Inversor energía hoy", "unit_of_measurement": "kWh"}},
        "sensor.contador_potencia": power("Contador potencia red", -900),
        "sensor.bateria_nivel": {"state": "64", "attributes": {"friendly_name": "Batería nivel", "unit_of_measurement": "%", "device_class": "battery"}},
        "sensor.movil_bateria": {"state": "40", "attributes": {"friendly_name": "Móvil batería", "unit_of_measurement": "%", "device_class": "battery"}},
    }
