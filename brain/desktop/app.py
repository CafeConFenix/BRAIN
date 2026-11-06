"""BRAIN as a program: server, its own window, a tray icon and background notices."""

import signal
import threading
import webbrowser
from pathlib import Path

from brain.core import logger
from brain.desktop import autostart, instance, preferences, window
from brain.desktop.tray import Tray

ROOT = Path(__file__).resolve().parents[2]
ICON = Path(__file__).with_name("brain.ico")


def _republish_access(port: int) -> None:
    from brain.core.config import Config
    from brain.desktop.remote_access import find_tailscale, publish
    from brain.web.access import Access

    try:
        if port != Config.WEB_PORT and Access().state().get("address"):
            executable = find_tailscale()

            if executable:
                publish(executable, port)
    except Exception as error:
        logger.error(f"Remote access: {error!r}")


def execute(brain, port: int, background: bool = False) -> int:
    from brain.cli import prepare_ai
    from brain.core.scheduler import start_scheduler
    from brain.web.server import create_server

    running = instance.port_running()

    if running:
        # A BRAIN is already open: just ask it to show its window.
        if not background:
            instance.ask_show(running)

        return 0

    state = {"window": None, "view": False}
    quit_app = threading.Event()
    lock = threading.Lock()

    def show() -> None:
        with lock:
            if window.bring_to_front():
                return  # already open: just bring it to the front

            process = state["window"]

            if process is not None and process.poll() is None:
                return  # it is opening

            state["view"] = False
            state["window"] = window.open_window(url)

            if state["window"] is None:
                webbrowser.open(url)

    def mute() -> None:
        notices = brain.modules.get("notices")

        if notices is not None:
            notices.configure(mute=not notices.config()["mute"])

    def toggle_autostart() -> None:
        if autostart.enabled():
            autostart.disable()
        else:
            autostart.enable(ROOT)

    def toggle_background() -> None:
        preferences.save(background=not preferences.read()["background"])

    def settings() -> dict:
        notices = brain.modules.get("notices")

        return {
            "mute": bool(notices.config()["mute"]) if notices is not None else False,
            "background": preferences.read()["background"],
            "autostart": autostart.enabled(),
            "autostart_available": autostart.available(),
        }

    server, port = create_server(
        brain,
        port,
        actions={
            "show": show,
            "mute": mute,
            "autostart": toggle_autostart,
            "background": toggle_background,
            "quit": quit_app.set,
        },
        settings=settings,
    )
    url = f"http://127.0.0.1:{port}"

    instance.register(port)
    start_scheduler()
    threading.Thread(target=server.serve_forever, name="brain-web", daemon=True).start()
    logger.system(f"Desktop BRAIN started at {url}")

    # If BRAIN could not use its usual port, access from a mobile (Tailscale)
    # would need to point at the new one: it republishes itself.
    threading.Thread(target=_republish_access, args=(port,), name="brain-access", daemon=True).start()

    # The AI gets ready separately so the window appears right away.
    threading.Thread(target=lambda: prepare_ai(brain, interactive=False), name="brain-ai", daemon=True).start()

    # Logging out of Windows, Ctrl+C or "terminate" should not leave the icon or window hanging.
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, name, None)

        if sig is not None:
            try:
                signal.signal(sig, lambda *_: quit_app.set())
            except (ValueError, OSError):
                pass  # only works from the main thread

    tray = Tray(ICON, port)
    with_tray = tray.start()

    if not background or not with_tray:
        show()

    try:
        while not quit_app.wait(1):
            process = state["window"]

            if process is None:
                continue

            opened = process.poll() is None or window.has_window()

            if opened:
                state["view"] = True
                continue

            if not state["view"]:
                # Edge handed the window to one of its other processes and ours ended
                # right away, or it has not shown signs of life yet: there is no way to
                # tell, so it is not closed.
                continue

            # The window has been closed.
            has_icon = with_tray and tray.active()

            if has_icon and preferences.read()["background"]:
                state["window"] = None  # BRAIN keeps running in the background; the icon reopens it
                logger.system("Window closed; BRAIN keeps running in the background")
                continue

            logger.system("Window closed; closing BRAIN")
            break
    except KeyboardInterrupt:
        pass
    finally:
        # First the icon (hidden gracefully), then the window, then the server.
        tray.stop()
        window.close(state["window"])
        server.shutdown()
        server.server_close()
        instance.forget()
        logger.system("Desktop BRAIN closed")

    return 0
