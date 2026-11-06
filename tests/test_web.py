import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from tests.helpers import CaseBrain, call, text
from brain.web.server import create_handler


class TestWeb(CaseBrain):
    def setUp(self):
        super().setUp()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain))
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]

        threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.02),
            daemon=True,
        ).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

        super().tearDown()

    def req(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

        extra_headers = {"Content-Type": "application/json"} if method == "POST" else {}
        extra_headers.update(headers or {})

        connection.request(
            method,
            path,
            body=json.dumps(body) if body is not None else None,
            headers=extra_headers,
        )

        response = connection.getresponse()
        data = response.read()

        connection.close()

        return response.status, data

    def test_page_principal(self):
        code, data = self.req("GET", "/")

        self.assertEqual(code, 200)
        self.assertIn(b"BRAIN", data)

    def test_state(self):
        code, data = self.req("GET", "/api/state")

        state = json.loads(data)

        self.assertEqual(code, 200)
        self.assertTrue(state["ai_ready"])
        self.assertEqual(state["model"], "qwen3:4b")

    def test_state_without_models_explica_that_hacer(self):
        self.ollama.models.clear()

        state = json.loads(self.req("GET", "/api/state")[1])

        self.assertFalse(state["ai_ready"])
        self.assertTrue(state["without_models"])
        self.assertIn("button", state["message"])
        self.assertTrue(state["recommended"]["label"])

    def test_download_from_the_web(self):
        import time

        self.ollama.models.clear()

        self.req("POST", "/api/download", {})

        for _ in range(50):
            state = json.loads(self.req("GET", "/api/state")[1])

            if state["ai_ready"]:
                break

            time.sleep(0.1)

        self.assertTrue(state["ai_ready"])
        self.assertEqual(len(self.ollama.downloaded), 1)

    def test_chat_with_tool_y_panel(self):
        self.ollama.responses = [
            call("save_weight", weight=88.4, date="2026-08-10"),
            text("Anotado."),
        ]

        code, data = self.req("POST", "/api/chat", {"message": "Hoy peso 88,4"})

        response = json.loads(data)

        self.assertEqual(code, 200)
        self.assertEqual(response["response"], "Anotado.")
        self.assertEqual(response["tools"], ["save_weight"])

        summary = json.loads(self.req("GET", "/api/summary")[1])

        self.assertEqual(summary["weight"][-1]["weight"], 88.4)

        history = json.loads(self.req("GET", "/api/history")[1])

        self.assertEqual(len(history["messages"]), 2)

    def test_chat_message_empty(self):
        self.assertEqual(self.req("POST", "/api/chat", {"message": "  "})[0], 400)

    def test_chat_without_ia_devuelve_error_legible(self):
        self.ollama.models.clear()

        code, data = self.req("POST", "/api/chat", {"message": "hola"})

        self.assertEqual(code, 503)
        self.assertIn("error", json.loads(data))

    def test_clear(self):
        self.ollama.responses = [text("hola")]

        self.req("POST", "/api/chat", {"message": "hola"})
        self.req("POST", "/api/clear", {})

        self.assertEqual(json.loads(self.req("GET", "/api/history")[1])["messages"], [])

    def test_rechaza_other_hosts_contra_dns_rebinding(self):
        code, _ = self.req("GET", "/api/summary", headers={"Host": "malvado.example.com"})

        self.assertEqual(code, 403)

    def test_rechaza_requests_of_other_webs(self):
        code, _ = self.req(
            "POST",
            "/api/chat",
            {"message": "hola"},
            headers={"Origin": "http://malvado.example.com"},
        )

        self.assertEqual(code, 403)

    def test_post_requires_json(self):
        code, _ = self.req("POST", "/api/chat", None, headers={"Content-Type": "text/plain"})

        self.assertEqual(code, 415)

    def test_route_nonexistent(self):
        self.assertEqual(self.req("GET", "/nada")[0], 404)


if __name__ == "__main__":
    unittest.main()
