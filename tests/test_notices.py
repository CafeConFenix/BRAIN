import http.client
import json
import threading
import unittest
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from unittest import mock

from brain.core.config import Config
from brain.core.scheduler import NoticeEvents, HomeAssistantPoller, check_reminders
from brain.integrations.home_assistant import save_config
from brain.web.server import create_handler
from tests.helpers import CaseBrain, FakeHomeAssistant, energy_sensors


class CaseNotices(CaseBrain):
    def setUp(self):
        super().setUp()
        patch = mock.patch("brain.modules.notices.notifier.notify")
        self.notify = patch.start()
        self.addCleanup(patch.stop)
        self.notices = self.brain.modules.get("notices")
        self.e = self.brain.tools.execute

    def sound(self, name="bell.wav"):
        folder = Config.DATA / "sounds"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(b"RIFF....WAVE")


class TestNotices(CaseNotices):
    def test_notice_is_saved_and_notified_with_its_sound(self):
        self.sound()
        self.e("assign_sound", {"kind": "reminder", "file": "bell"})

        self.notices.configure(dnd_from="ninguno")
        self.notices.notify("Hola", "mundo", kind="reminder")

        self.assertEqual(self.notify.call_count, 1)
        title, message, path = self.notify.call_args[0]
        self.assertEqual((title, message, path.name), ("Hola", "mundo", "bell.wav"))
        self.assertEqual(self.e("list_notices")["notices"][0]["title"], "Hola")

        self.e("mark_notices_read")
        self.assertIn("message", self.e("list_notices"))

    def test_mute_and_do_not_disturb(self):
        self.notices.configure(mute=True)
        self.notices.notify("a", kind="info")
        self.notices.notify("b", kind="alert")
        self.assertEqual(self.notify.call_count, 0)  # se guardan pero no suenan
        self.assertEqual(len(self.notices.items()), 2)

        self.notices.configure(mute=False)
        now = datetime.now()
        since = (now - timedelta(minutes=5)).strftime("%H:%M")
        until = (now + timedelta(minutes=5)).strftime("%H:%M")
        self.notices.configure(dnd_from=since, dnd_until=until)

        self.notices.notify("normal", kind="info")
        self.assertEqual(self.notify.call_count, 0)

        self.notices.notify("fuego", kind="alert")  # las críticas atraviesan "no molestar"
        self.assertEqual(self.notify.call_count, 1)

    def test_window_that_crosses_midnight(self):
        self.notices.configure(dnd_from="23:00", dnd_until="07:00")
        day = datetime(2026, 1, 1)

        self.assertTrue(self.notices.in_do_not_disturb(day.replace(hour=23, minute=30)))
        self.assertTrue(self.notices.in_do_not_disturb(day.replace(hour=3)))
        self.assertFalse(self.notices.in_do_not_disturb(day.replace(hour=12)))

    def test_validations(self):
        self.assertIn("error", self.e("assign_sound", {"kind": "volcan", "file": "x"}))
        self.assertIn("There are no sounds", self.e("assign_sound", {"kind": "info", "file": "x"})["error"])
        self.assertIn("error", self.e("configure_notices", {"dnd_from": "las diez"}))

        self.sound()
        self.assertIn("can't find", self.e("assign_sound", {"kind": "info", "file": "other"})["error"])
        self.assertEqual(self.e("assign_sound", {"kind": "info", "file": "ninguno"})["assigned"]["sound"], None)

    def test_sound_path_cannot_leave_the_folder(self):
        self.sound()

        self.assertIsNone(self.notices.sound_path("../brain.db"))
        self.assertIsNotNone(self.notices.sound_path("bell.wav"))


class TestReminders(CaseNotices):
    def test_create_list_cancel(self):
        r = self.e("create_reminder", {"message": "sacar el pollo", "in_minutes": 20})["scheduled"]

        self.assertEqual(self.e("list_reminders")["reminders"][0]["message"], "sacar el pollo")
        self.assertEqual(self.e("cancel_reminder", {"id": r["id"]}), {"canceled": r["id"]})
        self.assertIn("error", self.e("cancel_reminder", {"id": r["id"]}))

    def test_errors(self):
        self.assertIn("error", self.e("create_reminder", {"message": "x"}))
        self.assertIn("error", self.e("create_reminder", {"message": "x", "date_time": "2020-01-01 10:00"}))
        self.assertIn("error", self.e("create_reminder", {"message": "x", "date_time": "pronto"}))

    def test_time_only_moves_to_tomorrow_if_already_past(self):
        now = datetime.now()
        recently = (now - timedelta(minutes=2)).strftime("%H:%M")

        due = self.e("create_reminder", {"message": "x", "date_time": recently})["scheduled"]["due"]

        self.assertGreater(datetime.strptime(due, "%Y-%m-%d %H:%M"), now)

    def test_the_scheduler_fires_it_only_once(self):
        self.notices.create_reminder("llamar", in_minutes=1)
        self.notices.db.take_due_reminders("2000-01-01T00:00:00")  # nada vencido aún

        self.assertEqual(check_reminders(), "0 reminders")

        with mock.patch("brain.modules.notices.datetime") as clock:
            clock.now.return_value = datetime.now() + timedelta(minutes=5)
            clock.side_effect = datetime
            self.assertEqual(check_reminders(), "1 reminders")
            self.assertEqual(check_reminders(), "0 reminders")

        self.assertEqual(self.e("list_notices")["notices"][0]["title"], "Reminder")


class TestNoticesOfScheduler(CaseNotices):
    def test_event_with_a_time_warns_30_minutes_before(self):
        now = datetime.now()
        self.e("add_event", {"title": "Dentista", "date": now.strftime("%Y-%m-%d"), "hour": (now + timedelta(minutes=20)).strftime("%H:%M")})
        self.e("add_event", {"title": "Lejano", "date": now.strftime("%Y-%m-%d"), "hour": "23:59"})

        notice = NoticeEvents()

        if now.hour * 60 + now.minute < 23 * 60 + 29:  # evita falsos fallos justo antes de medianoche
            self.assertEqual(notice(), "1 calendar reminders")
            self.assertEqual(notice(), "0 calendar reminders")  # no repite

    def test_home_assistant_alert_warns_in_time(self):
        entities = {
            **energy_sensors(),
            "binary_sensor.agua_bano": {"state": "on", "attributes": {"friendly_name": "Fuga baño", "device_class": "moisture"}},
        }
        ha = FakeHomeAssistant(entities=entities)
        ha.start()
        self.addCleanup(ha.stop)
        save_config(ha.url, FakeHomeAssistant.TOKEN)

        poll = HomeAssistantPoller()
        poll()
        poll()

        notices = self.e("list_notices", {"all_items": True})["notices"]
        self.assertEqual(len(notices), 1)
        self.assertIn("Water leak", notices[0]["title"])
        self.assertEqual(notices[0]["level"], "critical")


class TestWebNotices(CaseNotices):
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

    def ask(self, method, path, body=None, raw=False):
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json", "Host": f"127.0.0.1:{self.port}"}
        con.request(method, path, json.dumps(body) if body is not None else None, headers)
        r = con.getresponse()
        data = r.read()
        con.close()
        return r.status, (data if raw else json.loads(data.decode("utf-8")))

    def test_list_marks_read_and_serves_the_sound(self):
        self.sound()
        self.notices.assign_sound("info", "bell.wav")
        self.notices.configure(dnd_from="ninguno")
        self.notices.notify("Hola", "web")

        code, r = self.ask("GET", "/api/notices")
        self.assertEqual((code, r["unread"], r["notices"][0]["sound"]), (200, 1, "bell.wav"))
        self.assertIn("play_in_web", r["notices"][0])

        self.assertEqual(self.ask("GET", "/api/sound/bell.wav", raw=True)[1][:4], b"RIFF")
        self.assertEqual(self.ask("GET", "/api/sound/..%2Fbrain.db")[0], 404)

        self.ask("POST", "/api/notices/read", {})
        self.assertEqual(self.ask("GET", "/api/notices")[1]["unread"], 0)


if __name__ == "__main__":
    unittest.main()
