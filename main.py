import argparse
<<<<<<< HEAD
import os
import subprocess
import sys
import traceback
from pathlib import Path
=======
import sys
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

from brain.utils.consola import preparar_consola


def leer_argumentos(argumentos=None):
    parser = argparse.ArgumentParser(
        prog="BRAIN",
        description="BRAIN: tu asistente personal con inteligencia artificial local.",
    )

    modo = parser.add_mutually_exclusive_group()

    modo.add_argument(
        "--web",
        action="store_true",
        help="abre la interfaz web en el navegador (opción por defecto)",
    )

    modo.add_argument(
<<<<<<< HEAD
        "--escritorio",
        action="store_true",
        help="abre BRAIN como programa con ventana propia e icono junto al reloj",
    )

    modo.add_argument(
        "--configurar-acceso",
        action="store_true",
        help="activa el acceso desde el móvil u otro PC (contraseña y Tailscale)",
    )

    modo.add_argument(
=======
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
        "--consola",
        action="store_true",
        help="chatea con BRAIN en esta ventana, sin navegador",
    )

    modo.add_argument(
<<<<<<< HEAD
        "--cerrar",
        action="store_true",
        help="cierra BRAIN del todo (ventana, icono junto al reloj y programa) y sale",
    )

    modo.add_argument(
=======
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
        "--diagnostico",
        action="store_true",
        help="muestra el estado del sistema y sale",
    )

    modo.add_argument(
        "--mejorar-ia",
        action="store_true",
        help="mide tu ordenador, elige el mejor modelo de IA y lo descarga",
    )

    modo.add_argument(
        "--configurar-domotica",
        action="store_true",
        help="conecta BRAIN con Home Assistant para controlar luces y dispositivos",
    )

    modo.add_argument(
        "--configurar-energia",
        action="store_true",
        help="elige los sensores del inversor para ver la energía en tiempo real",
    )

    parser.add_argument(
<<<<<<< HEAD
        "--segundo-plano",
        action="store_true",
        help="con --escritorio: arrancar solo con el icono junto al reloj, sin abrir la ventana",
    )

    parser.add_argument(
        "--sin-relanzar",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
=======
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
        "--auto",
        action="store_true",
        help="con --mejorar-ia: no hacer preguntas",
    )

    parser.add_argument(
        "--no-navegador",
        action="store_true",
        help="con --web: no abrir el navegador automáticamente",
    )

    parser.add_argument(
        "--puerto",
        type=int,
        default=None,
        help="puerto de la interfaz web (por defecto 8765)",
    )

    return parser.parse_args(argumentos)


<<<<<<< HEAD
def _asegurar_flujos():
    """
    pythonw.exe (sin ventana negra) no tiene salida de texto: sys.stdout y
    sys.stderr valen None. Se redirigen para que print() no falle y los errores
    queden anotados en datos/logs/errores.log.
    """

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

    if sys.stderr is None:
        try:
            from brain.core.config import Config

            Config.LOGS.mkdir(parents=True, exist_ok=True)
            sys.stderr = open(Config.LOGS / "errores.log", "a", encoding="utf-8", buffering=1)
        except OSError:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _relanzar_sin_consola(argumentos):
    """
    En Windows, `python main.py --escritorio` dejaría una ventana negra abierta
    todo el rato. Se relanza con pythonw.exe (sin consola) y esta copia termina.

    Devuelve el código de salida si ha relanzado, o None si no hace falta.
    """

    if os.name != "nt":
        return None

    ejecutable = Path(sys.executable)
    pythonw = ejecutable.with_name("pythonw.exe")

    if ejecutable.name.lower() != "python.exe" or not pythonw.exists():
        return None

    raiz = Path(__file__).resolve().parent
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        hijo = subprocess.Popen(
            [str(pythonw), str(raiz / "main.py"), *argumentos, "--sin-relanzar"],
            cwd=str(raiz),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except OSError:
        return None  # si no se puede, se sigue con esta copia (con consola)

    try:
        codigo = hijo.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        return 0  # sigue en marcha: todo bien

    if codigo != 0:
        print("\nBRAIN no ha podido arrancar.")

        try:
            from brain.core.config import Config

            lineas = (Config.LOGS / "errores.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()
            print("\n".join(lineas[-12:]))
        except OSError:
            pass

    return codigo


def main(argumentos=None):
    preparar_consola()

    desde_linea_de_comandos = argumentos is None
    opciones = leer_argumentos(argumentos)

    if opciones.cerrar:
        from brain.escritorio.cierre import cerrar_brain

        return cerrar_brain()

    if opciones.escritorio and desde_linea_de_comandos and not opciones.sin_relanzar:
        codigo = _relanzar_sin_consola(sys.argv[1:])

        if codigo is not None:
            return codigo

=======
def main(argumentos=None):
    preparar_consola()

    opciones = leer_argumentos(argumentos)

>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    from brain.cli import chat_consola, configurar_domotica, configurar_energia, diagnostico, mejorar_ia, preparar_ia
    from brain.core import Brain
    from brain.core.config import Config

    silencioso = (
<<<<<<< HEAD
        opciones.diagnostico
        or opciones.mejorar_ia
        or opciones.configurar_domotica
        or opciones.configurar_energia
        or opciones.configurar_acceso
=======
        opciones.diagnostico or opciones.mejorar_ia or opciones.configurar_domotica or opciones.configurar_energia
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    )

    brain = Brain(silencioso=silencioso)

    if opciones.mejorar_ia:
        return mejorar_ia(brain, auto=opciones.auto)

    if opciones.configurar_domotica:
        return configurar_domotica(brain)

    if opciones.configurar_energia:
        return configurar_energia(brain)

<<<<<<< HEAD
    if opciones.configurar_acceso:
        from brain.escritorio.acceso_remoto import configurar_acceso

        return configurar_acceso(Config.PUERTO_WEB)

=======
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    if opciones.diagnostico:
        diagnostico(brain)
        return 0

<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    # Tareas en segundo plano (copias de seguridad, sondeo de Home Assistant):
    # corren en su propio hilo y no bloquean ni la consola ni la web.
    from brain.core.scheduler import iniciar_planificador

    iniciar_planificador()

<<<<<<< HEAD
    if opciones.escritorio:
        from brain.escritorio.aplicacion import ejecutar

        return ejecutar(brain, puerto=opciones.puerto or Config.PUERTO_WEB, segundo_plano=opciones.segundo_plano)

=======
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    if opciones.consola:
        listo, mensaje = preparar_ia(brain, interactivo=True)

        if not listo:
            print(f"\n[BRAIN] {mensaje}")
            print("Puedes seguir, pero BRAIN no podrá responder hasta que se arregle.\n")

        chat_consola(brain)

        return 0

    from brain.web.servidor import servir

    listo, mensaje = preparar_ia(brain, interactivo=False)

    if not listo:
        print(f"\n[BRAIN] {mensaje}")
        print("La interfaz web se abrirá igualmente y te lo recordará.\n")

    servir(
        brain,
        puerto=opciones.puerto or Config.PUERTO_WEB,
        abrir_navegador=not opciones.no_navegador,
    )

    return 0


<<<<<<< HEAD
def _avisar_del_error(texto):
    """Sin ventana negra no hay donde leer el error: se muestra un cuadro de Windows."""

    if os.name != "nt" or sys.stdin is not None and sys.stdin.isatty():
        return

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, texto[:900], "BRAIN no ha podido arrancar", 0x10)
    except Exception:
        pass


def _arrancar():
    _asegurar_flujos()

    try:
        return main()
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        detalle = traceback.format_exc()

        try:
            from brain.core import logger

            logger.error(detalle)
        except Exception:
            pass

        print(detalle, file=sys.stderr)
        _avisar_del_error(f"{error}\n\nMás detalles en datos\\logs\\errores.log")

        return 1


if __name__ == "__main__":
    sys.exit(_arrancar())
=======
if __name__ == "__main__":
    sys.exit(main())
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
