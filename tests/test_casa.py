import http.client
import json
import threading
import unittest
import zlib
from datetime import date, datetime, timedelta
from http.server import ThreadingHTTPServer

from brain.modules.documents import DocumentError
from brain.utils.search import search_all
from brain.utils.pdf import extract_text
from brain.web.server import create_handler
from tests.helpers import CaseBrain


def sample_pdf(phrase):
    content = f"BT /F1 12 Tf 72 700 Td ({phrase}) Tj ET".encode()
    stream = zlib.compress(content)

    return b"%PDF-1.4\n1 0 obj\n<< /Filter /FlateDecode >>\nstream\n" + stream + b"\nendstream\nendobj\ntrailer\n%%EOF"


def days(n):
    return (date.today() + timedelta(days=n)).isoformat()


class TestBudget(CaseBrain):
    def test_notifies_at_80_and_100_only_once(self):
        expenses = self.brain.modules.get("expenses")
        notices = self.brain.modules.get("notices")
        expenses.configure_budget(100)

        expenses.add(50, "supermarket")
        self.assertEqual(notices.items(), [])

        expenses.add(35, "supermarket")
        self.assertEqual([a["title"] for a in notices.items()], ["Budget at 80 %"])

        expenses.add(1, "supermarket")  # still at "notice": not repeated
        self.assertEqual(len(notices.items()), 1)

        expenses.add(20, "supermarket")
        self.assertIn("Budget exceeded", [a["title"] for a in notices.items()])

    def test_state_and_categories(self):
        expenses = self.brain.modules.get("expenses")
        expenses.configure_budget(200, "leisure", 30)
        expenses.add(40, "cinema")

        state = expenses.budget_state()

        self.assertEqual(state["percent"], 20)
        self.assertEqual(state["remaining"], 160)
        self.assertEqual(state["categories"][0]["level"], "exceeded")

    def test_without_budget_does_not_notify_or_fail(self):
        expenses = self.brain.modules.get("expenses")
        expenses.add(500, "car")

        self.assertFalse(expenses.budget_state()["configured"])
        self.assertEqual(self.brain.modules.get("notices").items(), [])

    def test_amount_invalid_da_message_claro(self):
        with self.assertRaises(ValueError) as c:
            self.brain.modules.get("expenses").configure_budget("mucho")

        self.assertIn("euros", str(c.exception))

    def test_tools(self):
        e = self.brain.tools.execute
        e("set_budget", {"total": "900"})
        e("add_expense", {"amount": "90", "description": "luz"})

        self.assertEqual(e("show_budget")["percent"], 10)


class TestExpiries(CaseBrain):
    def setUp(self):
        super().setUp()
        self.inv = self.brain.modules.get("inventory")

    def test_by_expire_ordena_y_clasifica(self):
        self.inv.add("yogur", 4, "fridge", days(-1))
        self.inv.add("leche", 1, "fridge", days(2))
        self.inv.add("arroz", 1, "pantry", days(300))
        self.inv.add("sal", 1, "pantry")

        items = self.inv.expiring(5)

        self.assertEqual([p["name"] for p in items], ["yogur", "leche"])
        self.assertEqual(items[0]["state"], "expired")
        self.assertEqual({p["name"]: p.get("expires") for p in self.inv.everything()}["leche"], days(2))

    def test_set_y_remove_expiry(self):
        self.inv.add("queso", 1, "fridge")
        self.inv.set_expiry("queso", days(1))
        self.assertEqual(self.inv.expiring(3)[0]["days"], 1)

        self.inv.set_expiry("queso", "")
        self.assertEqual(self.inv.expiring(3), [])

        with self.assertRaises(ValueError):
            self.inv.set_expiry("unicornio", days(1))

    def test_add_units_conserva_date(self):
        self.inv.add("leche", 1, "fridge", days(2))
        self.inv.add("leche", 2, "fridge")

        self.assertEqual(self.inv.expiring(3)[0]["name"], "leche")

    def test_notice_daily_a_sola_time(self):
        self.inv.add("leche", 1, "fridge", days(1))

        self.assertIsNotNone(self.inv.warn_expiries())
        self.assertIsNone(self.inv.warn_expiries())
        self.assertEqual(len(self.brain.modules.get("notices").items()), 1)

    def test_tools(self):
        e = self.brain.tools.execute
        e("add_inventory", {"name": "nata", "quantity": 1, "location": "fridge", "expires": days(1)})

        self.assertEqual(e("show_expiries")["products"][0]["name"], "nata")

    def test_date_invalid(self):
        with self.assertRaises(ValueError):
            self.inv.add("nata", 1, "fridge", "algun dia")


class TestHabitsNotice(CaseBrain):
    def test_recuerda_only_si_due_y_no_esta_done(self):
        h = self.brain.modules.get("habits")
        h.create("beber agua", 2, "vasos", "10:00")
        today = date.today()

        self.assertEqual(h.warn_pending(datetime(today.year, today.month, today.day, 9, 59)), 0)
        self.assertEqual(h.warn_pending(datetime(today.year, today.month, today.day, 10, 5)), 1)
        self.assertEqual(h.warn_pending(datetime(today.year, today.month, today.day, 11, 0)), 0)  # ya avisado

    def test_no_avisa_si_already_done(self):
        h = self.brain.modules.get("habits")
        h.create("pastilla", 1, hour="08:00")
        h.log("pastilla")

        self.assertEqual(h.warn_pending(datetime.now().replace(hour=23, minute=0)), 0)

    def test_hour_invalid(self):
        with self.assertRaises(ValueError):
            self.brain.modules.get("habits").create("x", 1, hour="25:99")

    def test_filtra_by_person(self):
        h = self.brain.modules.get("habits")
        h.create("correr", 1, person="Ana")
        h.create("agua", 1)

        self.assertEqual([x["habit"] for x in h.state(person="Luis")["habits"]], ["agua"])
        self.assertEqual(len(h.state(person="Ana")["habits"]), 2)


class TestChores(CaseBrain):
    def setUp(self):
        super().setUp()
        self.chores = self.brain.modules.get("chores")

    def test_the_turn_broken(self):
        self.chores.create("basura", "Ana, Luis, Marta", 2)

        self.assertEqual(self.chores.items()[0]["turn_of"], "Ana")
        self.chores.done("basura")
        self.assertEqual(self.chores.items()[0]["turn_of"], "Luis")
        self.chores.done("basura", "Marta")  # la hizo Marta: sigue Ana
        self.assertEqual(self.chores.items()[0]["turn_of"], "Ana")

    def test_program_the_next_time(self):
        self.chores.create("fregar", "Ana, Luis", 3)
        t = self.chores.done("fregar")

        self.assertEqual(t["next_due"], days(3))
        self.assertFalse(t["due_today"])

    def test_due_today_y_notice_a_time(self):
        self.chores.create("basura", "Ana, Luis", 1)

        self.assertEqual(len(self.chores.todays()), 1)
        self.assertEqual(len(self.chores.todays("Luis")), 0)
        self.assertEqual(self.chores.warn_today(), 1)
        self.assertEqual(self.chores.warn_today(), 0)

    def test_skip_turn_y_errors(self):
        self.chores.create("basura", "Ana, Luis", 1)
        self.assertEqual(self.chores.skip_turn("basura")["turn_of"], "Luis")

        self.chores.create("solo", "Ana", 1)

        with self.assertRaises(ValueError):
            self.chores.skip_turn("solo")

        with self.assertRaises(ValueError):
            self.chores.done("inexistente")

        with self.assertRaises(ValueError):
            self.chores.create("x", "", 0)

    def test_create_registra_a_las_people(self):
        self.chores.create("basura", "Ana, Luis", 1)

        self.assertEqual(self.brain.modules.get("profiles").names(), ["Ana", "Luis"])

    def test_tools(self):
        e = self.brain.tools.execute
        e("create_chore", {"name": "basura", "people": "Ana, Luis", "every_days": 2})
        e("chore_done", {"name": "basura"})

        self.assertEqual(e("list_chores")["tasks"][0]["turn_of"], "Luis")
        self.assertEqual(e("household_people")["people"], ["Ana", "Luis"])


class TestMenuYsearch(CaseBrain):
    def test_menu_apunta_only_lo_that_missing(self):
        self.brain.modules.get("inventory").add("lentejas", 1)
        menu = self.brain.modules.get("menu")
        menu.save("lunes comida: Lentejas | lentejas, chorizo\nmartes cena: Tortilla | huevos, patata")
        r = menu.add_missing_to_shopping()

        self.assertNotIn("lentejas", r["added"])
        self.assertIn("chorizo", r["added"])
        self.assertEqual(menu.add_missing_to_shopping()["added"], [])

    def test_search_junta_varias_fuentes(self):
        m = self.brain.modules
        m.get("inventory").add("leche de avena", 1, "fridge")
        m.get("expenses").add(3, "leche")
        m.get("shopping").add("leche")

        r = search_all(m, "leche")

        self.assertEqual({g["kind"] for g in r["groups"]}, {"pantry", "expenses", "shopping"})
        with self.assertRaises(ValueError):
            search_all(m, "a")

    def test_tool_find(self):
        self.brain.modules.get("inventory").add("cafe", 1)

        self.assertEqual(self.brain.tools.execute("search_everything", {"text": "cafe"})["total"], 1)


class TestManuales(CaseBrain):
    def test_pdf_self_lee_y_self_busca(self):
        self.assertIn("garantia de dos anos", extract_text(sample_pdf("La garantia de dos anos")))

        docs = self.brain.modules.get("documents")
        docs.save_file("Manual horno.pdf", sample_pdf("El horno se limpia con la funcion pirolitica."))

        self.assertEqual(docs.search("pirolitica")[0]["document"], "Manual horno.txt")

    def test_pdf_scanned_o_fake(self):
        docs = self.brain.modules.get("documents")

        with self.assertRaises(DocumentError):
            docs.save_file("foto.pdf", b"%PDF-1.4\n%%EOF")

        with self.assertRaises(DocumentError):
            docs.save_file("falso.pdf", b"no soy un pdf")

        with self.assertRaises(DocumentError):
            docs.save_file("virus.exe", b"MZ")

    def test_name_no_leaves_of_the_folder(self):
        docs = self.brain.modules.get("documents")
        docs.save_file("../../escape.txt", b"hola")

        self.assertTrue((docs.folder / "escape.txt").exists())

    def test_delete(self):
        docs = self.brain.modules.get("documents")
        docs.save_file("nota.txt", b"hola mundo")
        docs.delete("nota.txt")

        self.assertEqual(docs.items(), [])


class TestWebCasa(CaseBrain):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain))
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def ask(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
        h = dict(headers or {})

        if body is not None and not isinstance(body, bytes):
            h["Content-Type"] = "application/json"

        c.request(method, path, data, h)
        r = c.getresponse()
        result = json.loads(r.read() or b"{}")
        c.close()

        return r.status, result

    def test_budget_y_expenses(self):
        self.ask("POST", "/api/budget/save", {"total": 100})
        self.ask("POST", "/api/expenses/add", {"amount": 90, "description": "super"})
        code, r = self.ask("GET", "/api/budget")

        self.assertEqual((code, r["level"]), (200, "notice"))
        self.assertEqual(self.ask("POST", "/api/budget/save", {"total": "abc"})[0], 400)

    def test_habits_chores_y_menu(self):
        self.ask("POST", "/api/habits/create", {"name": "agua", "goal": 3, "hour": "10:00"})
        self.ask("POST", "/api/habits/log", {"name": "agua"})
        self.assertEqual(self.ask("GET", "/api/habits")[1]["habits"][0]["today"], 1)

        self.ask("POST", "/api/chores/create", {"name": "basura", "people": "Ana, Luis"})
        self.ask("POST", "/api/chores/done", {"name": "basura"})
        self.assertEqual(self.ask("GET", "/api/chores")[1]["tasks"][0]["turn_of"], "Luis")
        self.assertEqual(self.ask("POST", "/api/chores/done", {"name": "nada"})[0], 400)

        self.ask("POST", "/api/menu/save", {"text": "lunes comida: Lentejas | lentejas"})
        self.assertEqual(self.ask("GET", "/api/menu")[1]["missing"][0]["name"], "lentejas")
        self.assertEqual(self.ask("POST", "/api/menu/save", {"text": "nada"})[0], 400)

    def test_rutina_without_home_assistant(self):
        code, r = self.ask("GET", "/api/routine?kind=leaving")

        self.assertEqual((code, r["connected"]), (200, False))
        self.assertEqual(self.ask("GET", "/api/routine?kind=other")[0], 400)

    def test_upload_manual_y_find(self):
        code, r = self.ask("POST", "/api/documents/upload", b"La clave del wifi es patata123", {"X-Name": "wifi.txt", "Content-Type": "application/octet-stream"})

        self.assertEqual(code, 200)
        self.assertEqual(self.ask("GET", "/api/search?q=wifi")[1]["total"], 1)
        self.assertEqual(self.ask("POST", "/api/documents/upload", b"MZ", {"X-Name": "a.exe"})[0], 400)
        self.assertEqual(self.ask("POST", "/api/documents/delete", {"name": "wifi.txt"})[0], 200)

    def test_expiries_y_backup_a_other_place(self):
        self.brain.modules.get("inventory").add("leche", 1, "fridge", days(1))
        self.assertEqual(self.ask("GET", "/api/expiries")[1]["products"][0]["name"], "leche")

        destination = str(self.folder / "usb")
        self.assertEqual(self.ask("POST", "/api/backup/destination", {"path": destination})[1]["destination"], destination)
        self.ask("POST", "/api/backup/create", {})
        state = self.ask("GET", "/api/backup/state")[1]

        self.assertEqual(len(state["destination_backups"]), 1)

    def test_cost_light_without_tariff_y_with_ella(self):
        self.assertIn("error", self.ask("GET", "/api/energy/cost")[1]["month"])
        self.ask("POST", "/api/energy/tariff", {"buy": "0,15"})

        self.assertEqual(self.ask("GET", "/api/energy/cost")[1]["tariff"]["buy"], 0.15)


if __name__ == "__main__":
    unittest.main()
