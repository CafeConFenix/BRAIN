import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from tests.helpers import CasoBrain
from brain.core.config import Config
from brain.escritorio import autoarranque, instancia, ventana
from brain.escritorio.bandeja import Bandeja
from brain.web import acceso as modulo_acceso
from brain.web.acceso import Acceso
from brain.web.servidor import crear_manejador

RAIZ = Path(__file__).resolve().parents[1]
HOST_REMOTO = "casa.tail1234.ts.net"


class TestAcceso(CasoBrain):
    def setUp(self):
        super().setUp()
        self.acceso = Acceso(Path(Config.DATOS) / "acceso.json")

    def test_sin_contrasena(self):
        self.assertFalse(self.acceso.configurada())
        self.assertFalse(self.acceso.verificar_clave("lo que sea"))

    def test_clave_corta_rechazada(self):
        with self.assertRaises(ValueError):
            self.acceso.establecer_clave("corta")

    def test_clave_correcta_e_incorrecta(self):
        self.acceso.establecer_clave("una-clave-larga")
        self.assertTrue(self.acceso.verificar_clave("una-clave-larga"))
        self.assertFalse(self.acceso.verificar_clave("otra-clave-larga"))

    def test_la_clave_no_se_guarda_en_claro(self):
        self.acceso.establecer_clave("una-clave-larga")
        self.assertNotIn("una-clave-larga", (Path(Config.DATOS) / "acceso.json").read_text())

    def test_sesion_valida_y_manipulada(self):
        self.acceso.establecer_clave("una-clave-larga")
        cookie = self.acceso.crear_sesion()
        self.assertTrue(self.acceso.sesion_valida(cookie))
        self.assertFalse(self.acceso.sesion_valida(cookie[:-2] + "00"))
        self.assertFalse(self.acceso.sesion_valida("basura"))
        self.assertFalse(self.acceso.sesion_valida(None))

    def test_cambiar_clave_cierra_sesiones(self):
        self.acceso.establecer_clave("una-clave-larga")
        cookie = self.acceso.crear_sesion()
        self.acceso.establecer_clave("clave-nueva-larga")
        self.assertFalse(self.acceso.sesion_valida(cookie))

    def test_sesion_caducada(self):
        self.acceso.establecer_clave("una-clave-larga")
        cookie = self.acceso.crear_sesion()

        with mock.patch.object(modulo_acceso.time, "time", return_value=time.time() + modulo_acceso.DURACION_SESION + 10):
            self.assertFalse(self.acceso.sesion_valida(cookie))

    def test_bloqueo_tras_fallos(self):
        self.acceso.establecer_clave("una-clave-larga")

        for _ in range(modulo_acceso.MAX_FALLOS):
            self.acceso.verificar_clave("mal")

        self.assertGreater(self.acceso.segundos_de_bloqueo(), 0)
        self.assertFalse(self.acceso.verificar_clave("una-clave-larga"))

    def test_hosts(self):
        self.assertTrue(self.acceso.es_local("127.0.0.1:8765", 8765))
        self.assertFalse(self.acceso.es_local("127.0.0.1:9999", 8765))
        self.assertTrue(self.acceso.es_remoto_permitido("casa.tail1234.ts.net"))
        self.assertTrue(self.acceso.es_remoto_permitido("casa.tail1234.ts.net:443"))
        self.assertFalse(self.acceso.es_remoto_permitido("malvado.example.com"))
        self.assertFalse(self.acceso.es_remoto_permitido("ts.net.malvado.com"))
        self.acceso.anadir_host("mi-pc.lan")
        self.assertTrue(self.acceso.es_remoto_permitido("mi-pc.lan"))


class TestServidorRemoto(CasoBrain):
    def setUp(self):
        super().setUp()
        self.acceso = Acceso(Path(Config.DATOS) / "acceso.json")
        self.mostrado = threading.Event()
        self.salido = threading.Event()
        self.servidor = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            crear_manejador(self.brain, self.acceso, self.mostrado.set, acciones={"salir": self.salido.set}, ajustes=lambda: {"segundo_plano": True, "autoarranque": False}),
        )
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        super().tearDown()

    def pedir(self, metodo, ruta, cuerpo=None, host=None, cabeceras=None, bruto=None):
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        h = {"Host": host or f"127.0.0.1:{self.puerto}"}

        if metodo == "POST" and bruto is None:
            h["Content-Type"] = "application/json"

        h.update(cabeceras or {})
        datos = bruto if bruto is not None else (json.dumps(cuerpo) if cuerpo is not None else None)
        con.request(metodo, ruta, body=datos, headers=h)
        r = con.getresponse()
        texto = r.read()
        cabs = dict(r.getheaders())
        con.close()

        return r.status, texto, cabs

    def iniciar_sesion_remota(self):
        self.acceso.establecer_clave("una-clave-larga")
        codigo, _, cabs = self.pedir("POST", "/api/acceso/entrar", {"clave": "una-clave-larga"}, host=HOST_REMOTO)
        self.assertEqual(codigo, 200)

        return cabs["Set-Cookie"].split(";")[0]

    def test_remoto_sin_contrasena_configurada(self):
        codigo, _, _ = self.pedir("GET", "/api/estado", host=HOST_REMOTO)
        self.assertEqual(codigo, 403)

    def test_remoto_sin_sesion_pide_login(self):
        self.acceso.establecer_clave("una-clave-larga")
        codigo, cuerpo, _ = self.pedir("GET", "/", host=HOST_REMOTO)
        self.assertEqual(codigo, 200)
        self.assertIn(b"Contrase", cuerpo)
        codigo, _, _ = self.pedir("GET", "/api/estado", host=HOST_REMOTO)
        self.assertEqual(codigo, 401)
        codigo, _, _ = self.pedir("POST", "/api/chat", {"mensaje": "hola"}, host=HOST_REMOTO)
        self.assertEqual(codigo, 401)

    def test_cabeceras_de_tailscale_serve(self):
        """Lo que llega a través de `tailscale serve`: Host privado y cabeceras de proxy."""

        self.acceso.establecer_clave("una-clave-larga")
        proxy = {"X-Forwarded-For": "100.64.0.9", "X-Forwarded-Proto": "https", "Tailscale-User-Login": "yo@example.com"}
        codigo, cuerpo, _ = self.pedir("GET", "/", host=HOST_REMOTO, cabeceras=proxy)
        self.assertEqual((codigo, b"Contrase" in cuerpo), (200, True))
        codigo, _, cabs = self.pedir("POST", "/api/acceso/entrar", {"clave": "una-clave-larga"}, host=HOST_REMOTO,
                                     cabeceras={**proxy, "Origin": f"https://{HOST_REMOTO}"})
        self.assertEqual(codigo, 200)
        codigo, _, _ = self.pedir("GET", "/", host=HOST_REMOTO, cabeceras={**proxy, "Cookie": cabs["Set-Cookie"].split(";")[0]})
        self.assertEqual(codigo, 200)

    def test_un_fallo_interno_responde_500(self):
        with mock.patch("brain.web.servidor.construir_estado", side_effect=RuntimeError("boom")):
            codigo, cuerpo, _ = self.pedir("GET", "/api/estado")

        self.assertEqual(codigo, 500)
        self.assertIn(b"boom", cuerpo)

    def test_login_incorrecto(self):
        self.acceso.establecer_clave("una-clave-larga")
        codigo, _, _ = self.pedir("POST", "/api/acceso/entrar", {"clave": "mal"}, host=HOST_REMOTO)
        self.assertEqual(codigo, 401)

    def test_login_y_acceso(self):
        cookie = self.iniciar_sesion_remota()
        codigo, _, _ = self.pedir("GET", "/api/estado", host=HOST_REMOTO, cabeceras={"Cookie": cookie})
        self.assertEqual(codigo, 200)

    def test_cookie_segura_con_https(self):
        self.acceso.establecer_clave("una-clave-larga")
        _, _, cabs = self.pedir("POST", "/api/acceso/entrar", {"clave": "una-clave-larga"}, host=HOST_REMOTO, cabeceras={"X-Forwarded-Proto": "https"})
        self.assertIn("Secure", cabs["Set-Cookie"])
        self.assertIn("HttpOnly", cabs["Set-Cookie"])
        self.assertIn("SameSite=Strict", cabs["Set-Cookie"])

    def test_host_desconocido_rechazado(self):
        codigo, _, _ = self.pedir("GET", "/api/estado", host="malvado.example.com")
        self.assertEqual(codigo, 403)

    def test_origen_distinto_rechazado(self):
        cookie = self.iniciar_sesion_remota()
        codigo, _, _ = self.pedir("POST", "/api/limpiar", {}, host=HOST_REMOTO, cabeceras={"Cookie": cookie, "Origin": "https://malvado.example.com"})
        self.assertEqual(codigo, 403)

    def test_local_no_pide_contrasena(self):
        codigo, _, _ = self.pedir("GET", "/api/estado")
        self.assertEqual(codigo, 200)

    def test_cambiar_clave_solo_en_local(self):
        cookie = self.iniciar_sesion_remota()
        codigo, _, _ = self.pedir("POST", "/api/acceso/clave", {"clave": "otra-clave-larga"}, host=HOST_REMOTO, cabeceras={"Cookie": cookie})
        self.assertEqual(codigo, 403)
        codigo, _, _ = self.pedir("POST", "/api/acceso/clave", {"clave": "otra-clave-larga"})
        self.assertEqual(codigo, 200)
        self.assertTrue(self.acceso.verificar_clave("otra-clave-larga"))

    def test_estado_acceso_solo_local(self):
        cookie = self.iniciar_sesion_remota()
        self.assertEqual(self.pedir("GET", "/api/acceso", host=HOST_REMOTO, cabeceras={"Cookie": cookie})[0], 403)
        self.assertEqual(self.pedir("GET", "/api/acceso")[0], 200)

    def test_salir_borra_cookie(self):
        cookie = self.iniciar_sesion_remota()
        codigo, _, cabs = self.pedir("POST", "/api/acceso/salir", {}, host=HOST_REMOTO, cabeceras={"Cookie": cookie})
        self.assertEqual(codigo, 200)
        self.assertIn("Max-Age=0", cabs["Set-Cookie"])

    def test_pwa_publica_tras_login(self):
        cookie = self.iniciar_sesion_remota()

        for ruta in ("/manifest.webmanifest", "/sw.js", "/iconos/icono-192.png", "/iconos/icono-512.png", "/favicon.ico"):
            codigo, cuerpo, _ = self.pedir("GET", ruta, host=HOST_REMOTO, cabeceras={"Cookie": cookie})
            self.assertEqual(codigo, 200, ruta)
            self.assertTrue(cuerpo)

    def test_manifest_valido(self):
        _, cuerpo, _ = self.pedir("GET", "/manifest.webmanifest")
        datos = json.loads(cuerpo)
        self.assertEqual(datos["display"], "standalone")
        self.assertEqual({i["sizes"] for i in datos["icons"]}, {"192x192", "512x512"})

    def test_mostrar_ventana_solo_en_local(self):
        cookie = self.iniciar_sesion_remota()
        self.assertEqual(self.pedir("POST", "/api/escritorio/mostrar", {}, host=HOST_REMOTO, cabeceras={"Cookie": cookie})[0], 404)
        self.assertFalse(self.mostrado.is_set())
        self.assertEqual(self.pedir("POST", "/api/escritorio/mostrar", {})[0], 200)
        self.assertTrue(self.mostrado.wait(2))

    def test_salir_solo_en_local_y_responde_antes(self):
        cookie = self.iniciar_sesion_remota()
        self.assertEqual(self.pedir("POST", "/api/escritorio/salir", {}, host=HOST_REMOTO, cabeceras={"Cookie": cookie})[0], 404)
        self.assertFalse(self.salido.is_set())
        self.assertEqual(self.pedir("POST", "/api/escritorio/salir", {})[0], 200)
        self.assertTrue(self.salido.wait(2))
        self.assertEqual(self.pedir("POST", "/api/escritorio/inexistente", {})[0], 404)

    def test_salir_rechaza_otros_origenes(self):
        codigo, _, _ = self.pedir("POST", "/api/escritorio/salir", {}, cabeceras={"Origin": "https://malvado.example.com"})
        self.assertEqual(codigo, 403)
        self.assertFalse(self.salido.is_set())

    def test_boton_de_cerrar_solo_en_local(self):
        self.assertTrue(json.loads(self.pedir("GET", "/api/escritorio")[1])["disponible"])
        cookie = self.iniciar_sesion_remota()
        self.assertFalse(json.loads(self.pedir("GET", "/api/escritorio", host=HOST_REMOTO, cabeceras={"Cookie": cookie})[1])["disponible"])

    def test_ajustes_del_escritorio_solo_en_local(self):
        local = json.loads(self.pedir("GET", "/api/escritorio/estado")[1])
        self.assertTrue(local["disponible"])
        self.assertTrue(local["segundo_plano"])
        self.assertFalse(local["autoarranque"])
        cookie = self.iniciar_sesion_remota()
        remoto = json.loads(self.pedir("GET", "/api/escritorio/estado", host=HOST_REMOTO, cabeceras={"Cookie": cookie})[1])
        self.assertEqual(remoto, {"disponible": False})

    # ---- sonidos propios ----

    def test_subir_asignar_y_borrar_sonido(self):
        codigo, cuerpo, _ = self.pedir("POST", "/api/sonido/subir", bruto=b"RIFFxxxxWAVE", cabeceras={"Content-Type": "audio/wav", "X-Nombre": "Mi%20timbre.wav"})
        self.assertEqual(codigo, 200, cuerpo)
        datos = json.loads(cuerpo)
        self.assertEqual(datos["archivo"], "Mi timbre.wav")
        self.assertIn("Mi timbre.wav", datos["archivos"])

        codigo, cuerpo, _ = self.pedir("POST", "/api/sonidos/asignar", {"tipo": "alerta", "archivo": "Mi timbre.wav"})
        self.assertEqual(codigo, 200)
        self.assertEqual(json.loads(cuerpo)["asignados"]["alerta"], "Mi timbre.wav")
        self.assertEqual(self.pedir("GET", "/api/sonido/Mi%20timbre.wav")[0], 200)

        codigo, cuerpo, _ = self.pedir("POST", "/api/sonidos/borrar", {"archivo": "Mi timbre.wav"})
        self.assertEqual(codigo, 200)
        datos = json.loads(cuerpo)
        self.assertEqual(datos["archivos"], [])
        self.assertEqual(datos["asignados"], {})

    def test_sonido_con_extension_peligrosa_o_ruta(self):
        for nombre in ("virus.exe", "script.ps1", "sin_extension"):
            codigo, _, _ = self.pedir("POST", "/api/sonido/subir", bruto=b"abc", cabeceras={"Content-Type": "audio/wav", "X-Nombre": nombre})
            self.assertEqual(codigo, 400, nombre)

        codigo, cuerpo, _ = self.pedir("POST", "/api/sonido/subir", bruto=b"abc", cabeceras={"Content-Type": "audio/wav", "X-Nombre": "..%2F..%2Fsalida.wav"})
        self.assertEqual(codigo, 200)
        self.assertEqual(json.loads(cuerpo)["archivo"], "salida.wav")
        self.assertTrue((Path(Config.DATOS) / "sonidos" / "salida.wav").exists())
        self.assertFalse((Path(Config.DATOS).parent / "salida.wav").exists())

    def test_sonido_demasiado_grande(self):
        avisos = self.brain.modules.obtener("avisos")

        with self.assertRaises(ValueError):
            avisos.guardar_sonido("a.wav", b"x" * (3 * 1024 * 1024 + 1))

        with self.assertRaises(ValueError):
            avisos.guardar_sonido("a.wav", b"")

    def test_subir_sonido_remoto_requiere_sesion(self):
        self.acceso.establecer_clave("una-clave-larga")
        codigo, _, _ = self.pedir("POST", "/api/sonido/subir", bruto=b"abc", host=HOST_REMOTO, cabeceras={"Content-Type": "audio/wav", "X-Nombre": "a.wav"})
        self.assertEqual(codigo, 401)


class TestEscritorio(CasoBrain):
    def test_instancia_unica(self):
        self.assertIsNone(instancia.puerto_en_marcha())
        instancia.registrar(1)  # nadie escucha en el puerto 1
        self.assertIsNone(instancia.puerto_en_marcha())
        instancia.olvidar()
        self.assertFalse((Path(Config.DATOS) / "brain.instancia").exists())

    def test_ventana_modo_aplicacion(self):
        args = ventana.argumentos(Path("msedge.exe"), "http://127.0.0.1:8765", Path("perfil"))
        self.assertIn("--app=http://127.0.0.1:8765", args)
        self.assertTrue(any(a.startswith("--user-data-dir=") for a in args))

    def test_sin_navegador_no_abre(self):
        with mock.patch.object(ventana, "buscar_navegador", return_value=None):
            self.assertIsNone(ventana.abrir("http://127.0.0.1:8765"))

    def test_comando_autoarranque(self):
        orden = autoarranque.comando(Path("C:/BRAIN"))
        self.assertIn("main.py", orden)
        self.assertIn("--escritorio --segundo-plano", orden)

    def test_bandeja_no_windows(self):
        with mock.patch("brain.escritorio.bandeja.os.name", "posix"):
            self.assertFalse(Bandeja(RAIZ / "brain" / "escritorio" / "brain.ico", 8765).iniciar())

    def test_script_de_la_bandeja(self):
        from brain.escritorio.bandeja import SCRIPT

        for opcion in ("mostrar", "silencio", "autoarranque", "salir"):
            self.assertIn(f'Enviar "{opcion}"', SCRIPT)

        self.assertIn("BRAIN_PID", SCRIPT)  # el icono desaparece si BRAIN se cierra
        SCRIPT.encode("ascii")

    def test_argumentos_main(self):
        from main import leer_argumentos

        a = leer_argumentos(["--escritorio", "--segundo-plano"])
        self.assertTrue(a.escritorio and a.segundo_plano)
        self.assertTrue(leer_argumentos(["--configurar-acceso"]).configurar_acceso)

    def test_version(self):
        self.assertEqual(Config.VERSION, "1.0.6")


class TestPaquete(unittest.TestCase):
    def test_iconos(self):
        for nombre in ("icono-192.png", "icono-512.png", "apple-touch-icon.png", "brain.ico"):
            self.assertGreater((RAIZ / "brain" / "web" / "static" / "iconos" / nombre).stat().st_size, 1000)

        self.assertTrue((RAIZ / "brain" / "escritorio" / "brain.ico").exists())

    def test_scripts_de_windows(self):
        for ruta in ("instalador/crear_setup.ps1", "instalador/preparar_ollama.ps1", "scripts/instalar.ps1", "CREAR_SETUP.bat", "CONFIGURAR_ACCESO.bat", "INICIAR.bat", "INICIAR_NAVEGADOR.bat", "CERRAR_BRAIN.bat"):
            datos = (RAIZ / ruta).read_bytes()
            self.assertIn(b"\r\n", datos, ruta)
            self.assertNotIn(b"\n", datos.replace(b"\r\n", b""), f"{ruta}: hay saltos de línea sin CRLF")

            if ruta.endswith(".ps1"):
                datos.decode("ascii")  # PowerShell 5 lee mal los acentos sin BOM

    def test_todos_los_bat_encuentran_el_python_portable(self):
        for bat in RAIZ.glob("*.bat"):
            texto = bat.read_text()

            if ":buscar_python" in texto:
                self.assertIn('call :probar_ruta "%~dp0python\\python.exe"', texto, bat.name)

    def test_instalador_grafico_con_inno_setup(self):
        crear = (RAIZ / "instalador" / "crear_setup.ps1").read_text()
        self.assertIn("ISCC.exe", crear)
        self.assertIn("python-3.12.8-embed", crear)
        self.assertIn("instalbrain", crear)

        iss = (RAIZ / "instalador" / "brain.iss").read_text(encoding="utf-8-sig")
        self.assertIn("OutputBaseFilename=instalbrain ({#Version})", iss)
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("Spanish.isl", iss)
        self.assertIn("datos\\*", iss)  # los datos del usuario nunca se empaquetan ni se pisan
        self.assertIn("--cerrar", iss)  # cierra BRAIN antes de actualizar o desinstalar
        self.assertIn("runhidden", iss)  # ninguna ventana negra
        self.assertIn("{app}\\python\\pythonw.exe", iss)

        for imagen in ("lateral.bmp", "pequena.bmp"):
            self.assertTrue((RAIZ / "instalador" / "imagenes" / imagen).exists(), imagen)

    def test_el_instalador_no_necesita_internet_para_python(self):
        iss = (RAIZ / "instalador" / "brain.iss").read_text(encoding="utf-8-sig")
        self.assertIn("{#PythonDir}", iss)
        self.assertNotIn("Invoke-WebRequest", iss)


if __name__ == "__main__":
    unittest.main()


class TestAutoprueba(CasoBrain):
    def setUp(self):
        super().setUp()
        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain, Acceso(Path(Config.DATOS) / "acceso.json")))
        self.puerto = self.servidor.server_address[1]
        threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True).start()

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        super().tearDown()

    def test_probar_local_correcto_y_motivo_si_falla(self):
        from brain.escritorio.acceso_remoto import probar_local

        Acceso(Path(Config.DATOS) / "acceso.json").establecer_clave("una-clave-larga")
        self.assertEqual(probar_local(self.puerto, HOST_REMOTO), "")
        self.assertIn("codigo 403", probar_local(self.puerto, "no-es-tailscale.example.com"))
        self.assertIn("no responde", probar_local(1, HOST_REMOTO))


class TestCierreLimpio(CasoBrain):
    """Cerrar la ventana o salir debe cerrar BRAIN y quitar el icono (sin icono fantasma)."""

    def test_el_script_oculta_y_libera_el_icono(self):
        from brain.escritorio.bandeja import SCRIPT

        self.assertIn("$icono.Visible = $false", SCRIPT)
        self.assertIn("$icono.Dispose()", SCRIPT)
        self.assertIn("BRAIN_PARAR", SCRIPT)  # BRAIN pide el cierre con un archivo
        self.assertIn('Enviar "segundo_plano"', SCRIPT)
        self.assertIn('"estado"', SCRIPT)

    def test_el_script_va_codificado(self):
        import base64

        from brain.escritorio.bandeja import SCRIPT, Bandeja

        comando = Bandeja._comando()
        self.assertEqual(comando[-2], "-EncodedCommand")
        self.assertEqual(base64.b64decode(comando[-1]).decode("utf-16-le"), SCRIPT)

    def test_detener_pide_cerrar_y_espera(self):
        bandeja = Bandeja(RAIZ / "brain" / "escritorio" / "brain.ico", 8765)
        falso = mock.Mock()
        falso.wait.side_effect = lambda timeout=None: self.assertTrue(bandeja.archivo_parar.exists())
        bandeja.proceso = falso
        bandeja.detener()
        falso.wait.assert_called_once()
        falso.kill.assert_not_called()  # terminó solo: nada de matarlo a la fuerza
        self.assertFalse(bandeja.archivo_parar.exists())

    def test_detener_mata_si_no_responde(self):
        import subprocess

        bandeja = Bandeja(RAIZ / "brain" / "escritorio" / "brain.ico", 8765)
        falso = mock.Mock()
        falso.wait.side_effect = subprocess.TimeoutExpired("powershell", 5)
        bandeja.proceso = falso
        bandeja.detener()
        falso.kill.assert_called_once()

    def test_ventana_no_deja_restos(self):
        args = ventana.argumentos(Path("msedge.exe"), "http://127.0.0.1:8765", Path("perfil"))
        self.assertIn("--disable-background-mode", args)
        ventana.cerrar(None)  # no falla sin ventana ni en Linux
        self.assertFalse(ventana.hay_ventana())
        self.assertFalse(ventana.traer_al_frente())

    def test_procesos_sin_ventana(self):
        from brain.utils import procesos

        with mock.patch.object(procesos.os, "name", "posix"):
            self.assertEqual(procesos.sin_ventana(), {})

        with mock.patch.object(procesos.os, "name", "nt"):
            self.assertTrue(procesos.sin_ventana()["creationflags"] & 0x08000000)

    def test_preferencias(self):
        from brain.escritorio import preferencias

        self.assertFalse(preferencias.leer()["segundo_plano"])  # por defecto, cerrar la ventana cierra BRAIN
        preferencias.guardar(segundo_plano=True)
        self.assertTrue(preferencias.leer()["segundo_plano"])
        (Path(Config.DATOS) / "escritorio.json").write_text("{roto", encoding="utf-8")
        self.assertFalse(preferencias.leer()["segundo_plano"])

    def test_main_flujos_sin_consola(self):
        import io
        import main

        with mock.patch.object(main.sys, "stdout", None), mock.patch.object(main.sys, "stderr", None):
            main._asegurar_flujos()
            self.assertIsNotNone(main.sys.stdout)
            self.assertIsNotNone(main.sys.stderr)
            print("esto no debe fallar con pythonw")
            main.sys.stdout.close()
            main.sys.stderr.close()

    def test_main_no_relanza_fuera_de_windows(self):
        import main

        self.assertIsNone(main._relanzar_sin_consola(["--escritorio"]))
        self.assertTrue(main.leer_argumentos(["--cerrar"]).cerrar)

    def test_cerrar_sin_brain_abierto(self):
        from brain.escritorio.cierre import cerrar_brain

        mensajes = []
        self.assertEqual(cerrar_brain(mensajes.append), 0)
        self.assertEqual(mensajes[-1], "BRAIN está cerrado.")

    def test_cerrar_pide_salir_a_la_copia_en_marcha(self):
        from brain.escritorio.cierre import cerrar_brain

        salido = threading.Event()
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain, Acceso(Path(Config.DATOS) / "acceso.json"), acciones={"salir": lambda: None}))
        servidor.daemon_threads = True
        puerto = servidor.server_address[1]

        def al_salir():
            salido.set()
            servidor.shutdown()
            servidor.server_close()
            instancia.olvidar()

        servidor.RequestHandlerClass = crear_manejador(self.brain, Acceso(Path(Config.DATOS) / "acceso.json"), acciones={"salir": al_salir})
        threading.Thread(target=lambda: servidor.serve_forever(poll_interval=0.02), daemon=True).start()
        instancia.registrar(puerto)
        self.assertEqual(cerrar_brain(lambda _: None, espera=8), 0)
        self.assertTrue(salido.is_set())
        self.assertFalse((Path(Config.DATOS) / "brain.instancia").exists())

    # ---- el bucle principal del programa de escritorio ----

    def ejecutar_aplicacion(self, segundo_plano_guardado, ventana_cierra):
        from brain.escritorio import aplicacion, preferencias

        preferencias.guardar(segundo_plano=segundo_plano_guardado)
        acciones = {}
        servidor = mock.Mock()
        servidor.serve_forever.side_effect = lambda: time.sleep(30)
        proceso = mock.Mock()
        proceso.poll.side_effect = lambda: 0 if ventana_cierra.is_set() else None
        bandeja = mock.Mock()
        bandeja.iniciar.return_value = True
        bandeja.activa.return_value = True
        resultado = {}

        def crear(brain, puerto, acciones=None, ajustes=None):
            self.assertIn("segundo_plano", acciones)
            self.assertIn("segundo_plano", ajustes())
            resultado["acciones"] = acciones

            return servidor, 8765

        with mock.patch("brain.web.servidor.crear_servidor", crear), \
                mock.patch("brain.cli.preparar_ia"), \
                mock.patch("brain.core.scheduler.iniciar_planificador"), \
                mock.patch.object(aplicacion, "Bandeja", return_value=bandeja), \
                mock.patch.object(aplicacion.ventana, "abrir", return_value=proceso), \
                mock.patch.object(aplicacion.ventana, "hay_ventana", return_value=False), \
                mock.patch.object(aplicacion.ventana, "traer_al_frente", return_value=False), \
                mock.patch.object(aplicacion.ventana, "cerrar") as cerrar, \
                mock.patch.object(aplicacion, "_republicar_acceso"):
            hilo = threading.Thread(target=lambda: resultado.setdefault("codigo", aplicacion.ejecutar(self.brain, 8765)), daemon=True)
            hilo.start()
            time.sleep(1.5)
            ventana_cierra.set()  # el usuario cierra la ventana
            hilo.join(timeout=4)

            if hilo.is_alive():
                resultado["acciones"]["salir"]()
                hilo.join(timeout=4)

            return resultado, hilo, bandeja, cerrar

    def test_cerrar_la_ventana_cierra_brain_y_el_icono(self):
        resultado, hilo, bandeja, cerrar = self.ejecutar_aplicacion(False, threading.Event())
        self.assertEqual(resultado.get("codigo"), 0)
        bandeja.detener.assert_called_once()  # el icono se quita
        cerrar.assert_called_once()  # y la ventana se cierra del todo

    def test_con_segundo_plano_cerrar_la_ventana_no_cierra_brain(self):
        cierra = threading.Event()
        resultado, hilo, bandeja, cerrar = self.ejecutar_aplicacion(True, cierra)
        # No terminó por cerrar la ventana: solo lo hizo al pedir "Salir" desde el icono.
        self.assertEqual(resultado.get("codigo"), 0)
        self.assertTrue(cierra.is_set())
        bandeja.detener.assert_called_once()
        cerrar.assert_called_once()
