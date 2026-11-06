"""
Close BRAIN completely from the outside (CLOSE_BRAIN.bat / `main.py --close`).

It is first asked to quit by itself (that way it removes its tray icon and
closes its window properly). Only if it does not respond is it killed, and
then whatever may have been left behind is cleaned up: the tray icon and the
window.
"""

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Callable

from brain.core.config import Config
from brain.desktop import instance, window
from brain.utils.processes import execute


def _registered_pid() -> int:
    try:
        return int(json.loads((Path(Config.DATA) / "brain.instance").read_text(encoding="utf-8")).get("pid", 0))
    except (OSError, ValueError, TypeError):
        return 0


def _request_quit(port: int) -> bool:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/desktop/quit",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _kill(pid: int) -> None:
    if pid <= 0 or pid == os.getpid():
        return

    try:
        if os.name == "nt":
            execute(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.kill(pid, 9)
    except Exception:
        pass


def _old_copies() -> None:
    """Windows: closes copies of BRAIN that were not registered (browser mode, old versions)."""

    if os.name != "nt":
        return

    order = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe' OR Name = 'python.exe'\" | "
        "Where-Object { $_.ProcessId -ne " + str(os.getpid()) + " -and $_.CommandLine -like '*main.py*' -and "
        "$_.CommandLine -notlike '*--close*' -and $_.CommandLine -match '--desktop|--web|--console|BRAIN' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )

    try:
        execute(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", order], capture_output=True, timeout=20)
    except Exception:
        pass


def close_brain(say: Callable[[str], None] = print, wait: float = 12.0) -> int:
    port = instance.port_running()
    pid = _registered_pid()

    if port:
        say("Closing BRAIN...")
        _request_quit(port)
        limit = time.time() + wait

        while time.time() < limit and instance.port_running():
            time.sleep(0.3)

        if instance.port_running():
            say("BRAIN is not responding; closing it by force.")
            _kill(pid)
    elif pid:
        _kill(pid)

    _old_copies()

    # An orphaned icon removes itself as soon as it sees the stop signal.
    try:
        (Path(Config.DATA) / "tray.stop").write_text("stop", encoding="utf-8")
        time.sleep(1.5)
        (Path(Config.DATA) / "tray.stop").unlink()
    except OSError:
        pass

    window.close_leftovers()
    instance.forget()
    say("BRAIN is closed.")

    return 0
