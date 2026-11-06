import http.client
import io
import json
import threading
import unittest
import wave
from http.server import ThreadingHTTPServer

from brain.integrations.home_assistant import save_config
from brain.utils.lists import interpret_list, looks_like_pasted_list
from brain.web import server
from brain.web.server import create_handler
from brain.voice.recognition import VoiceError, wav_to_audio
from tests.helpers import CaseBrain, FakeHomeAssistant, call, text

PANTRY_LIST = """- Café latte macchiato 250 ml: 2 unidades
- Bebida energética candy zero 500 ml: 2 unidades
- Filetes de contramuslo de pollo 600 g aprox.: 2 unidades
- Cogollos 3 unidades: 3 unids
- Tomate triturado 400 g: 4 unidades
- Leche desnatada pack 6 x 1 L: 1 unidad"""


class CaseWeb(CaseBrain):
    """Servidor web de BRAIN con Ollama falso y Home Assistant falso."""

    def setUp(self):
        super().setUp()

        self.ha = FakeHomeAssistant()
        self.ha.start()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain))
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]

        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()

        self.inventory = self.brain.modules.get("inventory")
        self.shopping = self.brain.modules.get("shopping")

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.ha.stop()

        super().tearDown()

    def connect_home(self):
        save_config(self.ha.url, FakeHomeAssistant.TOKEN)
        self.brain.modules.get("smart_home").forget_catalog()

    def api(self, method, path, body=None, kind="application/json", raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

        data = raw if raw is not None else (json.dumps(body) if body is not None else None)

        connection.request(method, path, body=data, headers={"Content-Type": kind} if method == "POST" else {})

        response = connection.getresponse()
        content = response.read()
        connection.close()

        return response.status, json.loads(content.decode("utf-8")) if content else {}


class TestListsPegadas(CaseBrain):
    def test_recognizes_the_pantry_format(self):
        self.assertTrue(looks_like_pasted_list(PANTRY_LIST))

        r = interpret_list(PANTRY_LIST)
        names = dict(r["products"])

        self.assertEqual(r["destination"], "pantry")
        self.assertEqual(names["Café latte macchiato 250 ml"], 2)
        self.assertEqual(names["Filetes de contramuslo de pollo 600 g"], 2)
        self.assertEqual(names["Cogollos 3 unidades"], 3)
        self.assertEqual(names["Leche desnatada pack 6 x 1 L"], 1)

    def test_does_not_confuse_normal_orders_with_lists(self):
        for phrase in ("apunta leche, pan y huevos", "¿qué tengo en la despensa?", "elimina toda la lista de la compra"):
            self.assertFalse(looks_like_pasted_list(phrase), phrase)

    def test_the_title_is_not_a_product(self):
        r = interpret_list("Añade esto a mi despensa\n" + PANTRY_LIST)

        self.assertEqual(r["title"], "Añade esto a mi despensa")
        self.assertEqual(len(r["products"]), 6)

    def test_goes_to_the_shopping_list_only_if_stated(self):
        self.assertEqual(interpret_list("Lista de la compra:\n" + PANTRY_LIST)["destination"], "shopping")
        self.assertEqual(interpret_list("Para la nevera\n" + PANTRY_LIST)["destination"], "fridge")

    def test_the_chat_saves_the_list_in_the_pantry_without_the_ai(self):
        response = self.brain.conversation.ask(PANTRY_LIST)

        self.assertIn("6 products", response)
        self.assertEqual(self.ollama.requests, [])  # no se llamó al modelo
        self.assertEqual(len(self.brain.modules.get("inventory").items("pantry")["pantry"]), 6)
        self.assertEqual(self.brain.modules.get("shopping").items(), [])

    def test_the_chat_sends_it_to_the_shopping_list_if_the_user_asks(self):
        self.brain.conversation.ask("Añade esto a la lista de la compra\n" + PANTRY_LIST)

        self.assertEqual(len(self.brain.modules.get("shopping").items()), 6)
        self.assertEqual(self.brain.modules.get("inventory").items("pantry")["pantry"], [])

    def test_the_history_trims_long_messages(self):
        longer = "\n".join(f"- Producto {i} 500 g: 1 unidad" for i in range(200))

        self.brain.conversation.ask(longer)

        saved = self.brain.conversation.messages()[0]["content"]
        self.assertLess(len(saved), 1300)
        self.assertIn("trimmed", saved)


class TestDeleted(CaseBrain):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_empty_the_shopping_list(self):
        self.execute("add_many_to_shopping", products="leche\npan\nhuevos")

        self.assertEqual(self.execute("clear_shopping_list")["deleted"], 3)
        self.assertEqual(self.brain.modules.get("shopping").items(), [])

    def test_remove_a_product_from_the_shopping_list(self):
        self.execute("add_many_to_shopping", products="leche\npan")

        self.execute("remove_from_shopping", product="leche")

        self.assertEqual([i["product"] for i in self.brain.modules.get("shopping").items()], ["pan"])

    def test_delete_y_empty_inventory(self):
        self.execute("add_many_to_inventory", products="Leche entera, 6\nPan, 2\nSal")

        self.assertEqual(len(self.execute("delete_from_inventory", name="leche")["deleted"]), 1)
        self.assertEqual(self.execute("clear_inventory")["deleted"], 2)

    def test_the_ai_empties_the_shopping_list_when_asked(self):
        self.execute("add_many_to_shopping", products="leche\npan")
        self.ollama.responses = [call("clear_shopping_list"), text("Listo, la lista de la compra está vacía.")]

        response = self.brain.conversation.ask("elimina toda la lista de la compra")

        self.assertIn("vacía", response)
        self.assertEqual(self.brain.modules.get("shopping").items(), [])

    def test_empty_response_is_retried(self):
        self.ollama.responses = [text(""), text("Aquí estoy.")]

        self.assertEqual(self.brain.conversation.ask("hola"), "Aquí estoy.")
        self.assertEqual(len(self.ollama.requests), 2)

    def test_two_empty_responses_give_a_useful_message(self):
        self.ollama.responses = [text(""), text("")]

        response = self.brain.conversation.ask("hola")

        self.assertIn("I did not know what to do with that", response)


class TestRecipes(CaseBrain):
    def execute(self, tool, **arguments):
        return self.brain.tools.execute(tool, arguments)

    def test_ingredients_incluyen_pantry_y_staples(self):
        self.execute("add_inventory", name="Huevos", quantity=6, location="fridge")
        self.execute("add_inventory", name="Arroz", quantity=2)

        r = self.execute("available_ingredients")

        self.assertTrue(any("Huevos" in i for i in r["inventory"]))
        self.assertTrue(any("Arroz" in i for i in r["inventory"]))
        for staple in ("olive oil", "salt", "sugar", "flour", "water", "pepper"):
            self.assertIn(staple, r["staples"])

    def test_staples_can_be_edited(self):
        self.execute("add_staple", name="white wine")
        self.execute("remove_staple", name="cinnamon")

        staples = self.execute("list_staples")["staples"]

        self.assertIn("white wine", staples)
        self.assertNotIn("cinnamon", staples)

    def test_the_normal_inventory_is_not_affected_by_staples(self):
        self.execute("add_staple", name="white wine")
        self.execute("add_inventory", name="Leche", quantity=2)

        self.assertEqual(self.execute("show_inventory")["pantry"], ["Leche (x2)"])

    def test_the_ai_queries_the_ingredients_before_suggesting(self):
        self.execute("add_inventory", name="Arroz", quantity=2)
        self.ollama.responses = [call("available_ingredients"), text("Puedes hacer arroz blanco con aceite y sal.")]

        response = self.brain.conversation.ask("dame una receta")

        self.assertIn("arroz", response.lower())
        self.assertEqual(self.brain.ai.tools_used[0]["name"], "available_ingredients")
        # La IA recibió el resultado real, con los básicos incluidos.
        final_request = json.dumps(self.ollama.requests[-1]["messages"], ensure_ascii=False)
        self.assertIn("olive oil", final_request)


class TestWebLanguage(CaseWeb):
    def tearDown(self):
        from brain import i18n

        i18n.reset()
        super().tearDown()

    def test_switches_language(self):
        from brain import i18n

        code, r = self.api("POST", "/api/language", {"code": "es"})

        self.assertEqual((code, r["language"]), (200, "es"))
        self.assertEqual(i18n.language(), "es")

        code, r = self.api("GET", "/api/state")
        self.assertEqual(r["language"], "es")

    def test_rejects_unknown_language(self):
        self.assertEqual(self.api("POST", "/api/language", {"code": "fr"})[0], 400)


class TestWebDatos(CaseWeb):
    def test_import_with_vista_previa_y_confirmacion(self):
        code, r = self.api("POST", "/api/import", {"text": PANTRY_LIST, "destination": "pantry", "preview_only": True})

        self.assertEqual((code, r["total"]), (200, 6))
        self.assertEqual(self.inventory.items("pantry")["pantry"], [])  # solo era una vista previa

        code, r = self.api("POST", "/api/import", {"text": PANTRY_LIST, "destination": "pantry"})

        self.assertEqual(code, 200)
        self.assertEqual(len(self.inventory.items("pantry")["pantry"]), 6)

    def test_import_to_the_shopping_list_and_empty_text(self):
        self.api("POST", "/api/import", {"text": PANTRY_LIST, "destination": "shopping"})

        self.assertEqual(len(self.shopping.items()), 6)
        self.assertEqual(self.api("POST", "/api/import", {"text": "   \n  "})[0], 400)

    def test_delete_from_the_web(self):
        self.api("POST", "/api/import", {"text": PANTRY_LIST, "destination": "shopping"})

        self.api("POST", "/api/shopping/remove", {"product": "Tomate triturado 400 g"})
        self.assertEqual(len(self.shopping.items()), 5)

        self.assertEqual(self.api("POST", "/api/shopping/clear", {})[1]["deleted"], 5)
        self.assertEqual(self.shopping.items(), [])

        self.api("POST", "/api/import", {"text": PANTRY_LIST, "destination": "pantry"})
        self.api("POST", "/api/inventory/delete", {"name": "cogollos"})
        self.assertEqual(len(self.inventory.items("pantry")["pantry"]), 5)

        self.api("POST", "/api/inventory/clear", {})
        self.assertEqual(self.inventory.items("pantry")["pantry"], [])

    def test_deleting_something_that_does_not_exist_gives_404(self):
        self.assertEqual(self.api("POST", "/api/shopping/remove", {"product": "unicornio"})[0], 404)

    def test_the_summary_brings_the_staples(self):
        code, r = self.api("GET", "/api/summary")

        self.assertIn("olive oil", r["staples"])


class TestWebSmartHome(CaseWeb):
    def test_without_connect_lo_dice(self):
        code, r = self.api("GET", "/api/devices")

        self.assertEqual(code, 200)
        self.assertFalse(r["connected"])

    def test_list_devices_by_room_with_state(self):
        self.connect_home()

        code, r = self.api("GET", "/api/devices")

        rooms = {g["room"]: g["devices"] for g in r["groups"]}

        self.assertTrue(r["connected"])
        self.assertIn("Living room", rooms)
        luz = [d for d in rooms["Living room"] if d["name"] == "Living room light"][0]
        self.assertTrue(luz["on"])
        self.assertEqual(luz["kind"], "light")
        self.assertEqual([e["name"] for e in r["scenes"]], ["Night"])

    def test_does_not_show_locks_or_garages(self):
        self.connect_home()

        entities = {d["entity"] for g in self.api("GET", "/api/devices")[1]["groups"] for d in g["devices"]}

        self.assertNotIn("lock.hallway", entities)
        self.assertNotIn("cover.garage", entities)

    def test_switch_turn_on_y_turn_off(self):
        self.connect_home()

        code, r = self.api("POST", "/api/device", {"entity": "light.kitchen", "on": True})

        self.assertEqual((code, r["on"]), (200, True))
        self.assertEqual(self.ha.calls[-1], ("light", "turn_on", {"entity_id": "light.kitchen"}))

        self.api("POST", "/api/device", {"entity": "light.living_room_ceiling", "on": False})
        self.assertEqual(self.ha.calls[-1][:2], ("light", "turn_off"))

    def test_blind_opens_and_closes(self):
        self.connect_home()

        self.api("POST", "/api/device", {"entity": "cover.bedroom_blind", "on": False})

        self.assertEqual(self.ha.calls[-1][:2], ("cover", "close_cover"))

    def test_cannot_control_dangerous_or_made_up_devices(self):
        self.connect_home()

        for entity in ("lock.hallway", "cover.garage", "alarm_control_panel.casa", "light.no_existe"):
            code, r = self.api("POST", "/api/device", {"entity": entity, "on": True})

            self.assertEqual(code, 502, entity)

        self.assertEqual(self.ha.calls, [])

    def test_scene(self):
        self.connect_home()

        self.api("POST", "/api/scene", {"entity": "scene.night"})

        self.assertEqual(self.ha.calls[-1][:2], ("scene", "turn_on"))
        self.assertEqual(self.api("POST", "/api/scene", {"entity": "light.kitchen"})[0], 502)

    def test_home_assistant_off_does_not_break_the_web(self):
        self.connect_home()
        self.ha.stop()

        code, r = self.api("GET", "/api/devices")

        self.assertEqual(code, 200)
        self.assertIn("error", r)

        self.ha = FakeHomeAssistant()  # para que tearDown pueda parar algo
        self.ha.start()


def create_wav(seconds=1.0, frequency=16000, channels=1, amplitud=8000):
    import math
    import struct

    frames = int(seconds * frequency)
    data = b"".join(
        struct.pack("<h", int(amplitud * math.sin(2 * math.pi * 440 * i / frequency))) * channels for i in range(frames)
    )

    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(frequency)
        w.writeframes(data)

    return buffer.getvalue()


class FakeRecognizer:
    def __init__(self, available=True):
        self._available = available
        self.installations = 0
        self.audios = []

    def available(self):
        return self._available

    def state(self):
        return {"available": self._available, "installing": False, "step": "", "error": "", "model": "small"}

    def install(self):
        self.installations += 1

        return True

    def transcribe(self, content):
        if not self._available:
            raise VoiceError("El reconocimiento de voz no está instalado. Pulsa «Instalar voz».")

        self.audios.append(content)

        return "enciende la living room light"


class TestVoice(CaseWeb):
    def setUp(self):
        super().setUp()

        self.original = server.recognizer
        server.recognizer = FakeRecognizer()

    def tearDown(self):
        server.recognizer = self.original

        super().tearDown()

    def test_state_of_the_voice(self):
        code, r = self.api("GET", "/api/voice")

        self.assertTrue(r["available"])

    def test_transcribe_the_audio_received(self):
        wav = create_wav()

        code, r = self.api("POST", "/api/voice", kind="audio/wav", raw=wav)

        self.assertEqual((code, r["text"]), (200, "enciende la living room light"))
        self.assertEqual(server.recognizer.audios, [wav])

    def test_without_install_asks_install(self):
        server.recognizer = FakeRecognizer(available=False)

        code, r = self.api("POST", "/api/voice", kind="audio/wav", raw=create_wav())

        self.assertEqual(code, 503)
        self.assertIn("Instalar voz", r["error"])

        self.api("POST", "/api/voice/install", {})
        self.assertEqual(server.recognizer.installations, 1)

    def test_rejects_what_is_not_audio(self):
        self.assertEqual(self.api("POST", "/api/voice", {"a": 1})[0], 400)
        self.assertEqual(self.api("POST", "/api/voice", kind="audio/wav", raw=b"")[0], 400)

    def test_other_webpage_cannot_use_the_microphone(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        connection.request("POST", "/api/voice", body=create_wav(), headers={"Content-Type": "audio/wav", "Origin": "http://malo.example"})

        self.assertEqual(connection.getresponse().status, 403)


@unittest.skipUnless(__import__("importlib").util.find_spec("numpy"), "necesita numpy")
class TestAudio(unittest.TestCase):
    def test_wav_to_audio(self):
        audio = wav_to_audio(create_wav(1.0))

        self.assertEqual(len(audio), 16000)
        self.assertEqual(str(audio.dtype), "float32")
        self.assertLessEqual(float(abs(audio).max()), 1.0)

    def test_resamples_and_mixes_to_mono(self):
        audio = wav_to_audio(create_wav(1.0, frequency=48000, channels=2))

        self.assertEqual(len(audio), 16000)

    def test_rechaza_audio_broken_o_demasiado_long(self):
        with self.assertRaises(VoiceError):
            wav_to_audio(b"esto no es un wav")

        with self.assertRaises(VoiceError):
            wav_to_audio(create_wav(61.0, frequency=8000))
