import argparse
import os
import subprocess
import sys
import traceback
from pathlib import Path

from brain.utils.console import prepare_console


def read_arguments(arguments=None):
    parser = argparse.ArgumentParser(
        prog="BRAIN",
        description="BRAIN: your personal assistant with local artificial intelligence.",
    )

    mode = parser.add_mutually_exclusive_group()

    mode.add_argument(
        "--web",
        action="store_true",
        help="open the web interface in the browser (the default option)",
    )

    mode.add_argument(
        "--desktop",
        "--escritorio",
        action="store_true",
        help="open BRAIN as a program with its own window and a tray icon",
    )

    mode.add_argument(
        "--configure-access",
        "--configurar-acceso",
        action="store_true",
        help="turn on access from a phone or another PC (password and Tailscale)",
    )

    mode.add_argument(
        "--console",
        "--consola",
        action="store_true",
        help="chat with BRAIN in this window, with no browser",
    )

    mode.add_argument(
        "--close",
        "--cerrar",
        action="store_true",
        help="close BRAIN completely (window, tray icon and program) and exit",
    )

    mode.add_argument(
        "--diagnose",
        "--diagnostico",
        action="store_true",
        help="show the system's state and exit",
    )

    mode.add_argument(
        "--upgrade-model",
        "--mejorar-ia",
        action="store_true",
        help="measure your computer, pick the best AI model and download it",
    )

    mode.add_argument(
        "--configure-smart-home",
        "--configurar-domotica",
        action="store_true",
        help="connect BRAIN with Home Assistant to control lights and devices",
    )

    mode.add_argument(
        "--configure-energy",
        "--configurar-energia",
        action="store_true",
        help="choose the inverter's sensors to see energy in real time",
    )

    parser.add_argument(
        "--background",
        "--segundo-plano",
        action="store_true",
        help="with --desktop: start with only the tray icon, without opening the window",
    )

    parser.add_argument(
        "--no-relaunch",
        "--sin-relanzar",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="with --upgrade-model: ask no questions",
    )

    parser.add_argument(
        "--no-browser",
        "--no-navegador",
        action="store_true",
        help="with --web: do not open the browser automatically",
    )

    parser.add_argument(
        "--port",
        "--puerto",
        type=int,
        default=None,
        help="port of the web interface (default 8765)",
    )

    parser.add_argument(
        "--lang",
        "--idioma",
        choices=["en", "es"],
        default=None,
        help="interface language (en or es); remembered for next time",
    )

    return parser.parse_args(arguments)


def _ensure_streams():
    """
    pythonw.exe (no black window) has no text output: sys.stdout and
    sys.stderr are None. They are redirected so print() does not fail and
    errors are logged to data/logs/errors.log.
    """

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")

    if sys.stderr is None:
        try:
            from brain.core.config import Config

            Config.LOGS.mkdir(parents=True, exist_ok=True)
            sys.stderr = open(Config.LOGS / "errors.log", "a", encoding="utf-8", buffering=1)
        except OSError:
            sys.stderr = open(os.devnull, "w", encoding="utf-8")


def _relaunch_without_console(arguments):
    """
    On Windows, `python main.py --desktop` would leave a black console window
    open the whole time. It is relaunched with pythonw.exe (no console) and
    this copy ends.

    Returns the exit code if it relaunched, or None if that was not needed.
    """

    if os.name != "nt":
        return None

    executable = Path(sys.executable)
    pythonw = executable.with_name("pythonw.exe")

    if executable.name.lower() != "python.exe" or not pythonw.exists():
        return None

    root = Path(__file__).resolve().parent
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        child = subprocess.Popen(
            [str(pythonw), str(root / "main.py"), *arguments, "--no-relaunch"],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
    except OSError:
        return None  # if that fails, keep going with this copy (with a console)

    try:
        code = child.wait(timeout=1.5)
    except subprocess.TimeoutExpired:
        return 0  # still running: all good

    if code != 0:
        print("\nBRAIN could not start.")

        try:
            from brain.core.config import Config

            lines = (Config.LOGS / "errors.log").read_text(encoding="utf-8", errors="replace").strip().splitlines()
            print("\n".join(lines[-12:]))
        except OSError:
            pass

    return code


def main(arguments=None):
    prepare_console()

    from_command_line = arguments is None
    options = read_arguments(arguments)

    if options.lang:
        from brain import i18n

        i18n.set_language(options.lang)

    if options.close:
        from brain.desktop.shutdown import close_brain

        return close_brain()

    if options.desktop and from_command_line and not options.no_relaunch:
        code = _relaunch_without_console(sys.argv[1:])

        if code is not None:
            return code

    from brain.cli import console_chat, configure_smart_home, configure_energy, diagnose, upgrade_model, prepare_ai
    from brain.core import Brain
    from brain.core.config import Config

    quiet = (
        options.diagnose
        or options.upgrade_model
        or options.configure_smart_home
        or options.configure_energy
        or options.configure_access
    )

    brain = Brain(quiet=quiet)

    if options.upgrade_model:
        return upgrade_model(brain, auto=options.auto)

    if options.configure_smart_home:
        return configure_smart_home(brain)

    if options.configure_energy:
        return configure_energy(brain)

    if options.configure_access:
        from brain.desktop.remote_access import configure_access

        return configure_access(Config.WEB_PORT)

    if options.diagnose:
        diagnose(brain)
        return 0

    # Background tasks (backups, Home Assistant polling): they run in their
    # own thread and block neither the console nor the web.
    from brain.core.scheduler import start_scheduler

    start_scheduler()

    if options.desktop:
        from brain.desktop.app import execute

        return execute(brain, port=options.port or Config.WEB_PORT, background=options.background)

    if options.console:
        ready, message = prepare_ai(brain, interactive=True)

        if not ready:
            print(f"\n[BRAIN] {message}")
            print("You can carry on, but BRAIN won't be able to answer until this is fixed.\n")

        console_chat(brain)

        return 0

    from brain.web.server import serve

    ready, message = prepare_ai(brain, interactive=False)

    if not ready:
        print(f"\n[BRAIN] {message}")
        print("The web interface will open anyway and will remind you.\n")

    serve(
        brain,
        port=options.port or Config.WEB_PORT,
        open_browser=not options.no_browser,
    )

    return 0


def _warn_about_error(text):
    """With no black window there is nowhere to read the error: a Windows message box is shown instead."""

    if os.name != "nt" or sys.stdin is not None and sys.stdin.isatty():
        return

    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text[:900], "BRAIN could not start", 0x10)
    except Exception:
        pass


def _start():
    _ensure_streams()

    try:
        return main()
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        detail = traceback.format_exc()

        try:
            from brain.core import logger

            logger.error(detail)
        except Exception:
            pass

        print(detail, file=sys.stderr)
        _warn_about_error(f"{error}\n\nMore details in data\\logs\\errors.log")

        return 1


if __name__ == "__main__":
    sys.exit(_start())
