"""BRAIN como programa: servidor, ventana propia, icono junto al reloj y avisos en segundo plano."""

import signal
import threading
import webbrowser
from pathlib import Path

from brain.core import logger
from brain.escritorio import autoarranque, instancia, preferencias, ventana
from brain.escritorio.bandeja import Bandeja

RAIZ = Path(__file__).resolve().parents[2]
ICONO = Path(__file__).with_name("brain.ico")


def _republicar_acceso(puerto: int) -> None:
    from brain.core.config import Config
    from brain.escritorio.acceso_remoto import buscar_tailscale, publicar
    from brain.web.acceso import Acceso

    try:
        if puerto != Config.PUERTO_WEB and Acceso().estado().get("direccion"):
            ejecutable = buscar_tailscale()

            if ejecutable:
                publicar(ejecutable, puerto)
    except Exception as error:
        logger.error(f"Acceso remoto: {error!r}")


def ejecutar(brain, puerto: int, segundo_plano: bool = False) -> int:
    from brain.cli import preparar_ia
    from brain.core.scheduler import iniciar_planificador
    from brain.web.servidor import crear_servidor

    en_marcha = instancia.puerto_en_marcha()

    if en_marcha:
        # Ya hay un BRAIN abierto: solo se le pide que enseñe su ventana.
        if not segundo_plano:
            instancia.pedir_mostrar(en_marcha)

        return 0

    estado = {"ventana": None, "vista": False}
    salir = threading.Event()
    cerrojo = threading.Lock()

    def mostrar() -> None:
        with cerrojo:
            if ventana.traer_al_frente():
                return  # ya está abierta: solo se pone delante

            proceso = estado["ventana"]

            if proceso is not None and proceso.poll() is None:
                return  # se está abriendo

            estado["vista"] = False
            estado["ventana"] = ventana.abrir(url)

            if estado["ventana"] is None:
                webbrowser.open(url)

    def silenciar() -> None:
        avisos = brain.modules.obtener("avisos")

        if avisos is not None:
            avisos.configurar(silencio=not avisos.configuracion()["silencio"])

    def alternar_autoarranque() -> None:
        if autoarranque.activado():
            autoarranque.desactivar()
        else:
            autoarranque.activar(RAIZ)

    def alternar_segundo_plano() -> None:
        preferencias.guardar(segundo_plano=not preferencias.leer()["segundo_plano"])

    def ajustes() -> dict:
        avisos = brain.modules.obtener("avisos")

        return {
            "silencio": bool(avisos.configuracion()["silencio"]) if avisos is not None else False,
            "segundo_plano": preferencias.leer()["segundo_plano"],
            "autoarranque": autoarranque.activado(),
            "autoarranque_disponible": autoarranque.disponible(),
        }

    servidor, puerto = crear_servidor(
        brain,
        puerto,
        acciones={
            "mostrar": mostrar,
            "silencio": silenciar,
            "autoarranque": alternar_autoarranque,
            "segundo_plano": alternar_segundo_plano,
            "salir": salir.set,
        },
        ajustes=ajustes,
    )
    url = f"http://127.0.0.1:{puerto}"

    instancia.registrar(puerto)
    iniciar_planificador()
    threading.Thread(target=servidor.serve_forever, name="brain-web", daemon=True).start()
    logger.sistema(f"BRAIN de escritorio iniciado en {url}")

    # Si BRAIN no ha podido usar el puerto habitual, el acceso desde el movil
    # (Tailscale) tendria que apuntar al nuevo: se republica solo.
    threading.Thread(target=_republicar_acceso, args=(puerto,), name="brain-acceso", daemon=True).start()

    # La IA se prepara aparte para que la ventana aparezca enseguida.
    threading.Thread(target=lambda: preparar_ia(brain, interactivo=False), name="brain-ia", daemon=True).start()

    # Cerrar la sesión de Windows, Ctrl+C o "terminar" no deben dejar el icono ni la ventana colgados.
    for nombre in ("SIGINT", "SIGTERM", "SIGBREAK"):
        senal = getattr(signal, nombre, None)

        if senal is not None:
            try:
                signal.signal(senal, lambda *_: salir.set())
            except (ValueError, OSError):
                pass  # solo se puede desde el hilo principal

    bandeja = Bandeja(ICONO, puerto)
    con_bandeja = bandeja.iniciar()

    if not segundo_plano or not con_bandeja:
        mostrar()

    try:
        while not salir.wait(1):
            proceso = estado["ventana"]

            if proceso is None:
                continue

            abierta = proceso.poll() is None or ventana.hay_ventana()

            if abierta:
                estado["vista"] = True
                continue

            if not estado["vista"]:
                # Edge entregó la ventana a otro proceso suyo y el nuestro terminó al
                # instante, o aún no ha dado señales de vida: no se puede saber, no se cierra.
                continue

            # La ventana se ha cerrado.
            tiene_icono = con_bandeja and bandeja.activa()

            if tiene_icono and preferencias.leer()["segundo_plano"]:
                estado["ventana"] = None  # BRAIN sigue en segundo plano; el icono permite volver a abrirla
                logger.sistema("Ventana cerrada; BRAIN sigue en segundo plano")
                continue

            logger.sistema("Ventana cerrada; cerrando BRAIN")
            break
    except KeyboardInterrupt:
        pass
    finally:
        # Primero el icono (se oculta con elegancia), luego la ventana, luego el servidor.
        bandeja.detener()
        ventana.cerrar(estado["ventana"])
        servidor.shutdown()
        servidor.server_close()
        instancia.olvidar()
        logger.sistema("BRAIN de escritorio cerrado")

    return 0
