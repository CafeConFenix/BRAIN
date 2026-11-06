import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests.helpers import CaseBrain
from brain.core.config import Config
from brain.desktop import autostart, instance, window
from brain.desktop.tray import Tray
from brain.web import access as access_module
from brain.web.access import Access
from brain.web.server import create_handler

ROOT = Path(__file__).resolve().parents[1]
REMOTE_HOST = "casa.tail1234.ts.net"


class TestAccess(CaseBrain):
    def setUp(self):
        super().setUp()
        self.access = Access(Path(Config.DATA) / "access.json")

    def test_without_contrasena(self):
        self.assertFalse(self.access.configured())
        self.assertFalse(self.access.verify_password("lo que sea"))

    def test_key_short_rechazada(self):
        with self.assertRaises(ValueError):
            self.access.set_password("corta")

    def test_key_correct_e_incorrecta(self):
        self.access.set_password("una-clave-larga")
        self.assertTrue(self.access.verify_password("una-clave-larga"))
        self.assertFalse(self.access.verify_password("otra-clave-larga"))

    def test_the_key_no_self_guarda_in_claro(self):
        self.access.set_password("una-clave-larga")
        self.assertNotIn("una-clave-larga", (Path(Config.DATA) / "access.json").read_text())

    def test_session_valid_y_manipulada(self):
        self.access.set_password("una-clave-larga")
        cookie = self.access.create_session()
        self.assertTrue(self.access.valid_session(cookie))
        self.assertFalse(self.access.valid_session(cookie[:-2] + "00"))
        self.assertFalse(self.access.valid_session("basura"))
        self.assertFalse(self.access.valid_session(None))

    def test_change_key_close_sessions(self):
        self.access.set_password("una-clave-larga")
        cookie = self.access.create_session()
        self.access.set_password("clave-nueva-larga")
        self.assertFalse(self.access.valid_session(cookie))

    def test_session_caducada(self):
        self.access.set_password("una-clave-larga")
        cookie = self.access.create_session()

        with mock.patch.object(access_module.time, "time", return_value=time.time() + access_module.SESSION_DURATION + 10):
            self.assertFalse(self.access.valid_session(cookie))

    def test_lock_after_failures(self):
        self.access.set_password("una-clave-larga")

        for _ in range(access_module.MAX_FAILURES):
            self.access.verify_password("mal")

        self.assertGreater(self.access.lock_seconds(), 0)
        self.assertFalse(self.access.verify_password("una-clave-larga"))

    def test_hosts(self):
        self.assertTrue(self.access.is_local("127.0.0.1:8765", 8765))
        self.assertFalse(self.access.is_local("127.0.0.1:9999", 8765))
        self.assertTrue(self.access.is_remote_allowed("casa.tail1234.ts.net"))
        self.assertTrue(self.access.is_remote_allowed("casa.tail1234.ts.net:443"))
        self.assertFalse(self.access.is_remote_allowed("malvado.example.com"))
        self.assertFalse(self.access.is_remote_allowed("ts.net.malvado.com"))
        self.access.add_host("mi-pc.lan")
        self.assertTrue(self.access.is_remote_allowed("mi-pc.lan"))


class TestServerRemote(CaseBrain):
    def setUp(self):
        super().setUp()
        self.access = Access(Path(Config.DATA) / "access.json")
        self.shown = threading.Event()
        self.exited = threading.Event()
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            create_handler(self.brain, self.access, self.shown.set, actions={"quit": self.exited.set}, settings=lambda: {"background": True, "autostart": False}),
        )
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def ask(self, method, path, body=None, host=None, headers=None, raw=None):
        con = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.port}"}

        if method == "POST" and raw is None:
            h["Content-Type"] = "application/json"

        h.update(headers or {})
        data = raw if raw is not None else (json.dumps(body) if body is not None else None)
        con.request(method, path, body=data, headers=h)
        r = con.getresponse()
        text = r.read()
        cabs = dict(r.getheaders())
        con.close()

        return r.status, text, cabs

    def start_remote_session(self):
        self.access.set_password("una-clave-larga")
        code, _, cabs = self.ask("POST", "/api/access/login", {"key": "una-clave-larga"}, host=REMOTE_HOST)
        self.assertEqual(code, 200)

        return cabs["Set-Cookie"].split(";")[0]

    def test_remote_without_contrasena_configured(self):
        code, _, _ = self.ask("GET", "/api/state", host=REMOTE_HOST)
        self.assertEqual(code, 403)

    def test_remote_without_session_asks_login(self):
        self.access.set_password("una-clave-larga")
        code, body, _ = self.ask("GET", "/", host=REMOTE_HOST)
        self.assertEqual(code, 200)
        self.assertIn(b"Password", body)
        code, _, _ = self.ask("GET", "/api/state", host=REMOTE_HOST)
        self.assertEqual(code, 401)
        code, _, _ = self.ask("POST", "/api/chat", {"message": "hola"}, host=REMOTE_HOST)
        self.assertEqual(code, 401)

    def test_headers_of_tailscale_serve(self):
        """Lo que llega a través de `tailscale serve`: Host privado y cabeceras de proxy."""

        self.access.set_password("una-clave-larga")
        proxy = {"X-Forwarded-For": "100.64.0.9", "X-Forwarded-Proto": "https", "Tailscale-User-Login": "yo@example.com"}
        code, body, _ = self.ask("GET", "/", host=REMOTE_HOST, headers=proxy)
        self.assertEqual((code, b"Password" in body), (200, True))
        code, _, cabs = self.ask("POST", "/api/access/login", {"key": "una-clave-larga"}, host=REMOTE_HOST,
                                     headers={**proxy, "Origin": f"https://{REMOTE_HOST}"})
        self.assertEqual(code, 200)
        code, _, _ = self.ask("GET", "/", host=REMOTE_HOST, headers={**proxy, "Cookie": cabs["Set-Cookie"].split(";")[0]})
        self.assertEqual(code, 200)

    def test_a_failure_interno_responde_500(self):
        with mock.patch("brain.web.server.build_state", side_effect=RuntimeError("boom")):
            code, body, _ = self.ask("GET", "/api/state")

        self.assertEqual(code, 500)
        self.assertIn(b"boom", body)

    def test_login_incorrect(self):
        self.access.set_password("una-clave-larga")
        code, _, _ = self.ask("POST", "/api/access/login", {"key": "mal"}, host=REMOTE_HOST)
        self.assertEqual(code, 401)

    def test_login_y_access(self):
        cookie = self.start_remote_session()
        code, _, _ = self.ask("GET", "/api/state", host=REMOTE_HOST, headers={"Cookie": cookie})
        self.assertEqual(code, 200)

    def test_cookie_segura_with_https(self):
        self.access.set_password("una-clave-larga")
        _, _, cabs = self.ask("POST", "/api/access/login", {"key": "una-clave-larga"}, host=REMOTE_HOST, headers={"X-Forwarded-Proto": "https"})
        self.assertIn("Secure", cabs["Set-Cookie"])
        self.assertIn("HttpOnly", cabs["Set-Cookie"])
        self.assertIn("SameSite=Strict", cabs["Set-Cookie"])

    def test_host_unknown_rejected(self):
        code, _, _ = self.ask("GET", "/api/state", host="malvado.example.com")
        self.assertEqual(code, 403)

    def test_origen_different_rejected(self):
        cookie = self.start_remote_session()
        code, _, _ = self.ask("POST", "/api/clear", {}, host=REMOTE_HOST, headers={"Cookie": cookie, "Origin": "https://malvado.example.com"})
        self.assertEqual(code, 403)

    def test_local_no_asks_contrasena(self):
        code, _, _ = self.ask("GET", "/api/state")
        self.assertEqual(code, 200)

    def test_change_key_only_in_local(self):
        cookie = self.start_remote_session()
        code, _, _ = self.ask("POST", "/api/access/password", {"key": "otra-clave-larga"}, host=REMOTE_HOST, headers={"Cookie": cookie})
        self.assertEqual(code, 403)
        code, _, _ = self.ask("POST", "/api/access/password", {"key": "otra-clave-larga"})
        self.assertEqual(code, 200)
        self.assertTrue(self.access.verify_password("otra-clave-larga"))

    def test_state_access_only_local(self):
        cookie = self.start_remote_session()
        self.assertEqual(self.ask("GET", "/api/access", host=REMOTE_HOST, headers={"Cookie": cookie})[0], 403)
        self.assertEqual(self.ask("GET", "/api/access")[0], 200)

    def test_exit_borra_cookie(self):
        cookie = self.start_remote_session()
        code, _, cabs = self.ask("POST", "/api/access/logout", {}, host=REMOTE_HOST, headers={"Cookie": cookie})
        self.assertEqual(code, 200)
        self.assertIn("Max-Age=0", cabs["Set-Cookie"])

    def test_pwa_publica_after_login(self):
        cookie = self.start_remote_session()

        for path in ("/manifest.webmanifest", "/sw.js", "/iconos/icono-192.png", "/iconos/icono-512.png", "/favicon.ico"):
            code, body, _ = self.ask("GET", path, host=REMOTE_HOST, headers={"Cookie": cookie})
            self.assertEqual(code, 200, path)
            self.assertTrue(body)

    def test_manifest_valid(self):
        _, body, _ = self.ask("GET", "/manifest.webmanifest")
        data = json.loads(body)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual({i["sizes"] for i in data["icons"]}, {"192x192", "512x512"})

    def test_show_window_only_in_local(self):
        cookie = self.start_remote_session()
        self.assertEqual(self.ask("POST", "/api/desktop/show", {}, host=REMOTE_HOST, headers={"Cookie": cookie})[0], 404)
        self.assertFalse(self.shown.is_set())
        self.assertEqual(self.ask("POST", "/api/desktop/show", {})[0], 200)
        self.assertTrue(self.shown.wait(2))

    def test_exit_only_in_local_y_responde_antes(self):
        cookie = self.start_remote_session()
        self.assertEqual(self.ask("POST", "/api/desktop/quit", {}, host=REMOTE_HOST, headers={"Cookie": cookie})[0], 404)
        self.assertFalse(self.exited.is_set())
        self.assertEqual(self.ask("POST", "/api/desktop/quit", {})[0], 200)
        self.assertTrue(self.exited.wait(2))
        self.assertEqual(self.ask("POST", "/api/desktop/inexistente", {})[0], 404)

    def test_exit_rechaza_other_origenes(self):
        code, _, _ = self.ask("POST", "/api/desktop/quit", {}, headers={"Origin": "https://malvado.example.com"})
        self.assertEqual(code, 403)
        self.assertFalse(self.exited.is_set())

    def test_boton_of_close_only_in_local(self):
        self.assertTrue(json.loads(self.ask("GET", "/api/desktop")[1])["available"])
        cookie = self.start_remote_session()
        self.assertFalse(json.loads(self.ask("GET", "/api/desktop", host=REMOTE_HOST, headers={"Cookie": cookie})[1])["available"])

    def test_settings_of_desktop_only_in_local(self):
        local = json.loads(self.ask("GET", "/api/desktop/state")[1])
        self.assertTrue(local["available"])
        self.assertTrue(local["background"])
        self.assertFalse(local["autostart"])
        cookie = self.start_remote_session()
        remote = json.loads(self.ask("GET", "/api/desktop/state", host=REMOTE_HOST, headers={"Cookie": cookie})[1])
        self.assertEqual(remote, {"available": False})

    # ---- sonidos propios ----

    def test_upload_assign_y_delete_sound(self):
        code, body, _ = self.ask("POST", "/api/sound/upload", raw=b"RIFFxxxxWAVE", headers={"Content-Type": "audio/wav", "X-Name": "Mi%20timbre.wav"})
        self.assertEqual(code, 200, body)
        data = json.loads(body)
        self.assertEqual(data["file"], "Mi timbre.wav")
        self.assertIn("Mi timbre.wav", data["files"])

        code, body, _ = self.ask("POST", "/api/sounds/assign", {"kind": "alert", "file": "Mi timbre.wav"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["assigned"]["alert"], "Mi timbre.wav")
        self.assertEqual(self.ask("GET", "/api/sound/Mi%20timbre.wav")[0], 200)

        code, body, _ = self.ask("POST", "/api/sounds/delete", {"file": "Mi timbre.wav"})
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["files"], [])
        self.assertEqual(data["assigned"], {})

    def test_sound_with_extension_peligrosa_o_route(self):
        for name in ("virus.exe", "script.ps1", "sin_extension"):
            code, _, _ = self.ask("POST", "/api/sound/upload", raw=b"abc", headers={"Content-Type": "audio/wav", "X-Name": name})
            self.assertEqual(code, 400, name)

        code, body, _ = self.ask("POST", "/api/sound/upload", raw=b"abc", headers={"Content-Type": "audio/wav", "X-Name": "..%2F..%2Fsalida.wav"})
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)["file"], "salida.wav")
        self.assertTrue((Path(Config.DATA) / "sounds" / "salida.wav").exists())
        self.assertFalse((Path(Config.DATA).parent / "salida.wav").exists())

    def test_sound_demasiado_large(self):
        notices = self.brain.modules.get("notices")

        with self.assertRaises(ValueError):
            notices.save_sound("a.wav", b"x" * (3 * 1024 * 1024 + 1))

        with self.assertRaises(ValueError):
            notices.save_sound("a.wav", b"")

    def test_upload_sound_remote_requiere_session(self):
        self.access.set_password("una-clave-larga")
        code, _, _ = self.ask("POST", "/api/sound/upload", raw=b"abc", host=REMOTE_HOST, headers={"Content-Type": "audio/wav", "X-Name": "a.wav"})
        self.assertEqual(code, 401)


class TestDesktop(CaseBrain):
    def test_instance_unica(self):
        self.assertIsNone(instance.port_running())
        instance.register(1)  # nobody is listening on port 1
        self.assertIsNone(instance.port_running())
        instance.forget()
        self.assertFalse((Path(Config.DATA) / "brain.instance").exists())

    def test_window_mode_app(self):
        args = window.arguments(Path("msedge.exe"), "http://127.0.0.1:8765", Path("perfil"))
        self.assertIn("--app=http://127.0.0.1:8765", args)
        self.assertTrue(any(a.startswith("--user-data-dir=") for a in args))

    def test_without_browser_no_abre(self):
        with mock.patch.object(window, "find_browser", return_value=None):
            self.assertIsNone(window.open_window("http://127.0.0.1:8765"))

    def test_command_autostart(self):
        order = autostart.command(Path("C:/BRAIN"))
        self.assertIn("main.py", order)
        self.assertIn("--desktop --background", order)

    def test_tray_no_windows(self):
        with mock.patch("brain.desktop.tray.os.name", "posix"):
            self.assertFalse(Tray(ROOT / "brain" / "desktop" / "brain.ico", 8765).start())

    def test_script_of_the_tray(self):
        from brain.desktop.tray import SCRIPT

        for option in ("show", "mute", "autostart", "quit"):
            self.assertIn(f'Send "{option}"', SCRIPT)

        self.assertIn("BRAIN_PID", SCRIPT)  # el icono desaparece si BRAIN se cierra
        SCRIPT.encode("ascii")

    def test_arguments_main(self):
        from main import read_arguments

        a = read_arguments(["--desktop", "--background"])
        self.assertTrue(a.desktop and a.background)
        self.assertTrue(read_arguments(["--configure-access"]).configure_access)
        self.assertEqual(read_arguments(["--lang", "es"]).lang, "es")
        self.assertIsNone(read_arguments([]).lang)

    def test_lang_flag_switches_language(self):
        import main
        from brain import i18n

        try:
            main.main(["--diagnose", "--lang", "es"])
            self.assertEqual(i18n.language(), "es")
        finally:
            i18n.reset()

    def test_version(self):
        self.assertEqual(Config.VERSION, "2.0.0")


class TestPackage(unittest.TestCase):
    def test_icons(self):
        for name in ("icono-192.png", "icono-512.png", "apple-touch-icon.png", "brain.ico"):
            self.assertGreater((ROOT / "brain" / "web" / "static" / "iconos" / name).stat().st_size, 1000)

        self.assertTrue((ROOT / "brain" / "desktop" / "brain.ico").exists())

    def test_scripts_de_windows(self):
        for path in ("instalador/crear_setup.ps1", "instalador/preparar_ollama.ps1", "scripts/instalar.ps1", "CREAR_SETUP.bat", "CONFIGURAR_ACCESO.bat", "INICIAR.bat", "INICIAR_NAVEGADOR.bat", "CERRAR_BRAIN.bat"):
            data = (ROOT / path).read_bytes()
            self.assertIn(b"\r\n", data, path)
            self.assertNotIn(b"\n", data.replace(b"\r\n", b""), f"{path}: hay saltos de línea sin CRLF")

            if path.endswith(".ps1"):
                data.decode("ascii")  # PowerShell 5 lee mal los acentos sin BOM

    def test_all_los_bat_encuentran_the_python_portable(self):
        for bat in ROOT.glob("*.bat"):
            text = bat.read_text()

            if ":find_python" in text:
                self.assertIn('call :try_path "%~dp0python\\python.exe"', text, bat.name)

    def test_instalador_grafico_with_inno_setup(self):
        create = (ROOT / "instalador" / "crear_setup.ps1").read_text()
        self.assertIn("ISCC.exe", create)
        self.assertIn("python-3.12.8-embed", create)
        self.assertIn("instalbrain", create)

        iss = (ROOT / "instalador" / "brain.iss").read_text(encoding="utf-8-sig")
        self.assertIn("OutputBaseFilename=instalbrain ({#Version})", iss)
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("Spanish.isl", iss)
        self.assertIn("data\\*", iss)  # the user's data is never packaged or overwritten
        self.assertIn("--close", iss)  # cierra BRAIN antes de actualizar o desinstalar
        self.assertIn("runhidden", iss)  # ninguna ventana negra
        self.assertIn("{app}\\python\\pythonw.exe", iss)

        for image in ("lateral.bmp", "pequena.bmp"):
            self.assertTrue((ROOT / "instalador" / "imagenes" / image).exists(), image)

    def test_the_instalador_no_necesita_internet_for_python(self):
        iss = (ROOT / "instalador" / "brain.iss").read_text(encoding="utf-8-sig")
        self.assertIn("{#PythonDir}", iss)
        self.assertNotIn("Invoke-WebRequest", iss)


if __name__ == "__main__":
    unittest.main()


class TestSelfTest(CaseBrain):
    def setUp(self):
        super().setUp()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain, Access(Path(Config.DATA) / "access.json")))
        self.port = self.server.server_address[1]
        threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def test_test_local_correct_y_reason_si_falla(self):
        from brain.desktop.remote_access import try_local

        Access(Path(Config.DATA) / "access.json").set_password("una-clave-larga")
        self.assertEqual(try_local(self.port, REMOTE_HOST), "")
        self.assertIn("code 403", try_local(self.port, "not-tailscale.example.com"))
        self.assertIn("is not responding", try_local(1, REMOTE_HOST))


class TestShutdownClean(CaseBrain):
    """Cerrar la ventana o salir debe cerrar BRAIN y quitar el icono (sin icono fantasma)."""

    def test_the_script_oculta_y_libera_the_icon(self):
        from brain.desktop.tray import SCRIPT

        self.assertIn("$icon.Visible = $false", SCRIPT)
        self.assertIn("$icon.Dispose()", SCRIPT)
        self.assertIn("BRAIN_STOP", SCRIPT)  # BRAIN pide el cierre con un archivo
        self.assertIn('Send "background"', SCRIPT)
        self.assertIn('"state"', SCRIPT)

    def test_the_script_va_encoded(self):
        import base64

        from brain.desktop.tray import SCRIPT, Tray

        command = Tray._command()
        self.assertEqual(command[-2], "-EncodedCommand")
        self.assertEqual(base64.b64decode(command[-1]).decode("utf-16-le"), SCRIPT)

    def test_stop_asks_close_y_wait(self):
        tray = Tray(ROOT / "brain" / "desktop" / "brain.ico", 8765)
        fake = mock.Mock()
        fake.wait.side_effect = lambda timeout=None: self.assertTrue(tray.stop_file.exists())
        tray.process = fake
        tray.stop()
        fake.wait.assert_called_once()
        fake.kill.assert_not_called()  # terminó solo: nada de matarlo a la fuerza
        self.assertFalse(tray.stop_file.exists())

    def test_stop_mata_si_no_responde(self):
        import subprocess

        tray = Tray(ROOT / "brain" / "desktop" / "brain.ico", 8765)
        fake = mock.Mock()
        fake.wait.side_effect = subprocess.TimeoutExpired("powershell", 5)
        tray.process = fake
        tray.stop()
        fake.kill.assert_called_once()

    def test_window_no_deja_leftovers(self):
        args = window.arguments(Path("msedge.exe"), "http://127.0.0.1:8765", Path("perfil"))
        self.assertIn("--disable-background-mode", args)
        window.close(None)  # no falla sin ventana ni en Linux
        self.assertFalse(window.has_window())
        self.assertFalse(window.bring_to_front())

    def test_processes_without_window(self):
        from brain.utils import processes

        with mock.patch.object(processes.os, "name", "posix"):
            self.assertEqual(processes.no_window(), {})

        with mock.patch.object(processes.os, "name", "nt"):
            self.assertTrue(processes.no_window()["creationflags"] & 0x08000000)

    def test_preferences(self):
        from brain.desktop import preferences

        self.assertFalse(preferences.read()["background"])  # por defecto, cerrar la ventana cierra BRAIN
        preferences.save(background=True)
        self.assertTrue(preferences.read()["background"])
        (Path(Config.DATA) / "desktop.json").write_text("{roto", encoding="utf-8")
        self.assertFalse(preferences.read()["background"])

    def test_main_streams_without_console(self):
        import io
        import main

        with mock.patch.object(main.sys, "stdout", None), mock.patch.object(main.sys, "stderr", None):
            main._ensure_streams()
            self.assertIsNotNone(main.sys.stdout)
            self.assertIsNotNone(main.sys.stderr)
            print("esto no debe fallar con pythonw")
            main.sys.stdout.close()
            main.sys.stderr.close()

    def test_main_no_relanza_outside_of_windows(self):
        import main

        self.assertIsNone(main._relaunch_without_console(["--desktop"]))
        self.assertTrue(main.read_arguments(["--close"]).close)

    def test_close_without_brain_open(self):
        from brain.desktop.shutdown import close_brain

        messages = []
        self.assertEqual(close_brain(messages.append), 0)
        self.assertEqual(messages[-1], "BRAIN is closed.")

    def test_close_asks_exit_a_the_backup_in_running(self):
        from brain.desktop.shutdown import close_brain

        exited = threading.Event()
        server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.brain, Access(Path(Config.DATA) / "access.json"), actions={"quit": lambda: None}))
        server.daemon_threads = True
        port = server.server_address[1]

        def on_quit():
            exited.set()
            server.shutdown()
            server.server_close()
            instance.forget()

        server.RequestHandlerClass = create_handler(self.brain, Access(Path(Config.DATA) / "access.json"), actions={"quit": on_quit})
        threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True).start()
        instance.register(port)
        self.assertEqual(close_brain(lambda _: None, wait=8), 0)
        self.assertTrue(exited.is_set())
        self.assertFalse((Path(Config.DATA) / "brain.instance").exists())

    # ---- el bucle principal del programa de escritorio ----

    def run_app(self, saved_background, window_closes):
        from brain.desktop import app, preferences

        preferences.save(background=saved_background)
        actions = {}
        server = mock.Mock()
        server.serve_forever.side_effect = lambda: time.sleep(30)
        process = mock.Mock()
        process.poll.side_effect = lambda: 0 if window_closes.is_set() else None
        tray = mock.Mock()
        tray.start.return_value = True
        tray.active.return_value = True
        result = {}

        def create(brain, port, actions=None, settings=None):
            self.assertIn("background", actions)
            self.assertIn("background", settings())
            result["actions"] = actions

            return server, 8765

        with mock.patch("brain.web.server.create_server", create), \
                mock.patch("brain.cli.prepare_ai"), \
                mock.patch("brain.core.scheduler.start_scheduler"), \
                mock.patch.object(app, "Tray", return_value=tray), \
                mock.patch.object(app.window, "open_window", return_value=process), \
                mock.patch.object(app.window, "has_window", return_value=False), \
                mock.patch.object(app.window, "bring_to_front", return_value=False), \
                mock.patch.object(app.window, "close") as close, \
                mock.patch.object(app, "_republish_access"):
            thread = threading.Thread(target=lambda: result.setdefault("code", app.execute(self.brain, 8765)), daemon=True)
            thread.start()
            time.sleep(1.5)
            window_closes.set()  # el usuario cierra la ventana
            thread.join(timeout=4)

            if thread.is_alive():
                result["actions"]["quit"]()
                thread.join(timeout=4)

            return result, thread, tray, close

    def test_close_the_window_close_brain_y_the_icon(self):
        result, thread, tray, close = self.run_app(False, threading.Event())
        self.assertEqual(result.get("code"), 0)
        tray.stop.assert_called_once()  # el icono se quita
        close.assert_called_once()  # y la ventana se cierra del todo

    def test_with_second_plano_close_the_window_no_close_brain(self):
        closes = threading.Event()
        result, thread, tray, close = self.run_app(True, closes)
        # No terminó por cerrar la ventana: solo lo hizo al pedir "Salir" desde el icono.
        self.assertEqual(result.get("code"), 0)
        self.assertTrue(closes.is_set())
        tray.stop.assert_called_once()
        close.assert_called_once()
