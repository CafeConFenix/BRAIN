import http.client
import json
import threading
import unittest
from datetime import date, datetime
from http.server import ThreadingHTTPServer

from brain.ai.vision import VisionError, interpret_response
from brain.core.config import Config
from brain.web.server import create_handler
from tests.helpers import CaseBrain

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class TestSummaryDaily(CaseBrain):
    def test_gathers_agenda_shopping_and_weight(self):
        e = self.brain.tools.execute
        e("add_event", {"title": "Doctor", "hour": "10:00"})
        e("add_to_shopping", {"product": "milk", "quantity": 2})
        e("save_weight", {"weight": 80, "date": date.today().isoformat()})

        r = e("show_daily_summary")["summary"]

        self.assertIn("10:00 Doctor", r)
        self.assertIn("milk", r)
        self.assertIn("Last weight: 80 kg", r)

    def test_self_envia_a_time_to_day_y_a_su_hour(self):
        summary = self.brain.modules.get("summary")
        today = date.today()

        self.assertIsNone(summary.send_if_due(datetime(today.year, today.month, today.day, 7, 0)))  # antes de la hora
        self.assertIsNotNone(summary.send_if_due(datetime(today.year, today.month, today.day, 8, 45)))
        self.assertIsNone(summary.send_if_due(datetime(today.year, today.month, today.day, 9, 0)))  # ya enviado

        notices = self.brain.modules.get("notices").items()
        self.assertEqual([a["kind"] for a in notices], ["summary"])

    def test_configure_hour_y_disable(self):
        e = self.brain.tools.execute

        self.assertEqual(e("set_daily_summary", {"hour": "7.45"})["config"]["hour"], "07:45")
        self.assertIn("error", e("set_daily_summary", {"hour": "25:00"}))

        e("set_daily_summary", {"active": False})
        today = date.today()
        self.assertIsNone(self.brain.modules.get("summary").send_if_due(datetime(today.year, today.month, today.day, 12, 0)))


class TestConversations(CaseBrain):
    def test_histories_independent_y_persistentes(self):
        g = self.brain.conversations
        recipes = g.create("Recetas", "Esta conversación es solo de cocina.")["id"]

        self.ollama.responses += [{"role": "assistant", "content": "Una tortilla."}, {"role": "assistant", "content": "Tienes cita."}]

        self.assertEqual(g.ask(recipes, "¿Qué ceno?"), "Una tortilla.")
        self.assertEqual(g.ask("general", "¿Qué tengo hoy?"), "Tienes cita.")

        self.assertEqual([m["content"] for m in g.get(recipes).messages()], ["¿Qué ceno?", "Una tortilla."])
        self.assertEqual([m["content"] for m in g.get("general").messages()], ["¿Qué tengo hoy?", "Tienes cita."])

        # El tema solo llega a la IA en su conversación
        system = [p["messages"][0]["content"] for p in self.ollama.requests]
        self.assertIn("solo de cocina", system[0])
        self.assertNotIn("solo de cocina", system[1])

        # Tras reabrir BRAIN siguen ahí
        from brain.core import Brain

        other = Brain(quiet=True)
        self.assertEqual(len(other.conversations.get(recipes).messages()), 2)
        self.assertEqual(other.conversations.get(recipes).instructions, "Esta conversación es solo de cocina.")

    def test_title_automatic_list_rename_delete(self):
        g = self.brain.conversations
        id_ = g.create()["id"]
        self.ollama.responses.append({"role": "assistant", "content": "ok"})
        g.ask(id_, "Dame ideas para una cena con amigos")

        items = g.items()
        self.assertEqual(items[0]["id"], "general")
        self.assertEqual(items[1]["title"], "Dame ideas para una cena con amigos")

        g.rename(id_, "Cenas")
        self.assertEqual(g.items()[1]["title"], "Cenas")

        g.delete(id_)
        self.assertEqual([c["id"] for c in g.items()], ["general"])

        with self.assertRaises(KeyError):
            g.get(id_)

        with self.assertRaises(ValueError):
            g.delete("general")

    def test_the_conversation_principal_sigue_siendo_brain_conversation(self):
        self.assertIs(self.brain.conversation, self.brain.conversations.get("general"))


class TestVision(CaseBrain):
    RESPONSE = '{"weight_kg": 87.4, "date": null, "measurements": {"bmi": 27.3, "body_fat_pct": 24.1}}'

    def test_interpreta_y_valid(self):
        r = interpret_response("Aquí: " + self.RESPONSE, date(2026, 10, 11))

        self.assertEqual(r, {"weight": 87.4, "date": "2026-10-11", "measurements": {"bmi": 27.3, "body_fat_pct": 24.1}})

        for bad in ("sin json", '{"weight_kg": null}', '{"weight_kg": 5}'):
            with self.assertRaises(VisionError):
                interpret_response(bad)

        # Una medida absurda se descarta pero el peso se conserva
        self.assertEqual(interpret_response('{"weight_kg": 80, "measurements": {"bmi": 900}}')["measurements"], {})

    def test_tool_without_measurements(self):
        self.assertIn("message", self.brain.tools.execute("show_body_measurements"))


class TestWebNews(CaseBrain):
    def setUp(self):
        super().setUp()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain))
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def ask(self, method, path, body=None, kind="application/json"):
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        con.request(method, path, body, {"Content-Type": kind, "Host": f"127.0.0.1:{self.port}"})
        r = con.getresponse()
        data = json.loads(r.read().decode("utf-8"))
        con.close()
        return r.status, data

    def test_conversations_by_the_web(self):
        code, r = self.ask("POST", "/api/conversations/create", {"title": "Recetas", "instructions": "Solo cocina"})
        self.assertEqual(code, 200)
        id_ = r["conversation"]["id"]

        self.ollama.responses.append({"role": "assistant", "content": "Pasta."})
        code, r = self.ask("POST", "/api/chat", {"message": "¿Qué como?", "conversation": id_})
        self.assertEqual((code, r["response"]), (200, "Pasta."))

        self.assertEqual(len(self.ask("GET", f"/api/history?conversation={id_}")[1]["messages"]), 2)
        self.assertEqual(self.ask("GET", "/api/history")[1]["messages"], [])  # la principal sigue vacía

        self.assertEqual([c["id"] for c in self.ask("GET", "/api/conversations")[1]["conversations"]][0], "general")

        self.assertEqual(self.ask("POST", "/api/chat", {"message": "hola", "conversation": "nope"})[0], 404)
        self.assertEqual(self.ask("POST", "/api/conversations/delete", {"id": "general"})[0], 400)
        self.assertEqual(self.ask("POST", "/api/clear", {"conversation": id_})[0], 200)
        self.assertEqual(self.ask("POST", "/api/conversations/delete", {"id": id_})[0], 200)

    def test_captura_of_scale(self):
        name = self.ollama.models[0]
        self.ollama.with_vision.add(name)
        self.ollama.responses.append({"role": "assistant", "content": TestVision.RESPONSE})

        code, r = self.ask("POST", "/api/image", PNG, "image/png")

        self.assertEqual(code, 200, r)
        self.assertEqual(r["weight"], 87.4)
        self.assertIn("87.4 kg", r["response"])

        # La IA recibió la imagen
        self.assertIn("images", self.ollama.requests[-1]["messages"][0])

        self.assertEqual(self.brain.tools.execute("get_weight")["weight"], 87.4)
        self.assertEqual({m["name"] for m in self.brain.tools.execute("show_body_measurements")["measurements"]}, {"bmi", "body_fat_pct"})
        self.assertEqual(len(self.brain.conversation.messages()), 2)

    def test_captura_without_model_with_vision_o_invalid(self):
        code, r = self.ask("POST", "/api/image", PNG, "image/png")
        self.assertEqual(code, 422)
        self.assertIn("vision", r["error"])

        self.assertEqual(self.ask("POST", "/api/image", b"not an image", "image/png")[0], 422)
        self.assertEqual(self.ask("POST", "/api/image", b"x", "text/plain")[0], 400)

        self.assertEqual(self.ask("POST", "/api/image?conversation=nope", PNG, "image/png")[0], 404)
        self.assertIsNone(self.brain.tools.execute("get_weight"))


if __name__ == "__main__":
    unittest.main()


class TestRelevantTools(unittest.TestCase):
    def test_only_the_tools_of_each_topic_are_sent(self):
        from brain.ai.relevant_tools import relevant_categories as c

        self.assertEqual(c("turn on the living room light"), {"smart_home", "memory"})
        self.assertEqual(c("what can I cook today?"), {"recipes", "memory"})
        self.assertIn("notices", c("remind me in 20 minutes to take out the chicken"))
        self.assertIn("appliances", c("the washer won't start"))
        self.assertIn("system", c("make a backup"))
        self.assertIn("energy", c("how much am I consuming?"))

    def test_without_a_clear_topic_the_usual_set_is_sent_and_context_counts(self):
        from brain.ai.relevant_tools import BASIC, relevant_categories as c

        self.assertEqual(c("hi, how's it going?"), set(BASIC) | {"memory"})

        # "yes, add it" says nothing on its own, but the conversation was about shopping
        previous = [{"role": "assistant", "content": "You're out of milk. Shall I add it to the shopping list?"}]
        self.assertIn("shopping", c("yes, do it", previous))

    def test_the_ai_receives_fewer_tools_than_the_total(self):
        from brain.tools.registry import ToolRegistry

        record = ToolRegistry()

        self.assertLess(len(record.schemas({"smart_home", "memory"})), len(record.schemas()) // 3)

    def test_the_request_to_ollama_only_carries_the_tools_of_the_topic(self):
        case = CaseBrain("setUp")  # reuses the test environment
        case.setUp()

        try:
            case.ollama.responses.append({"role": "assistant", "content": "Hecho."})
            case.brain.conversation.ask("Apunta leche en la lista de la compra")

            sent = {t["function"]["name"] for t in case.ollama.requests[-1]["tools"]}

            self.assertIn("add_to_shopping", sent)
            self.assertNotIn("turn_on", sent)
            self.assertLess(len(sent), 15)
        finally:
            case.tearDown()
