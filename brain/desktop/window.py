"""
BRAIN's own window.

It uses Microsoft Edge (it ships with Windows) or Chrome in "app mode": a
window with no tabs or address bar, with its own profile, separate from your
usual browser and from Brave. There is nothing to install.

This also has everything needed for the window to behave well: detecting
whether it is still open, bringing it to the front and closing it completely
(Edge launches several processes and, if only the first one is killed, the
window can stay alive).
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from brain.core.config import Config
from brain.utils.processes import execute, no_window

# Window title: it is the page's <title>.
TITLE = "BRAIN"


def _candidates() -> List[Path]:
    routes: List[Path] = []

    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(variable)

        if base:
            routes.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)

        if base:
            routes.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")

    for name in ("msedge", "chrome", "google-chrome", "chromium"):
        found = shutil.which(name)

        if found:
            routes.append(Path(found))

    return routes


def find_browser() -> Optional[Path]:
    for path in _candidates():
        if path.exists():
            return path

    return None


def profile_folder() -> Path:
    return Path(Config.DATA) / "window"


def arguments(browser: Path, url: str, profile: Path) -> List[str]:
    return [
        str(browser),
        f"--app={url}",
        f"--user-data-dir={profile}",
        "--window-size=1320,860",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
        # Without this, Edge/Chrome can stay alive in the background after the window closes.
        "--disable-background-mode",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
    ]


def open_window(url: str) -> Optional[subprocess.Popen]:
    """Opens BRAIN's window. Returns the process, or None if there is no Edge or Chrome."""

    browser = find_browser()

    if browser is None:
        return None

    profile = profile_folder()
    profile.mkdir(parents=True, exist_ok=True)

    return subprocess.Popen(
        arguments(browser, url, profile),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        **no_window(),
    )


# ---------------------------------------------------------------- Windows


def _find_hwnd() -> int:
    """Handle of BRAIN's window (0 if it does not exist or this is not Windows)."""

    if os.name != "nt":
        return 0

    try:
        import ctypes

        user = ctypes.windll.user32
        user.FindWindowW.restype = ctypes.c_void_p

        return int(user.FindWindowW("Chrome_WidgetWin_1", TITLE) or 0)
    except Exception:
        return 0


def has_window() -> bool:
    """True if BRAIN's window is open (even if minimized)."""

    return _find_hwnd() != 0


def bring_to_front() -> bool:
    """Restores the window if minimized and brings it to the front. False if it could not."""

    hwnd = _find_hwnd()

    if not hwnd:
        return False

    try:
        import ctypes

        user = ctypes.windll.user32
        user.IsIconic.argtypes = [ctypes.c_void_p]
        user.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user.SetForegroundWindow.argtypes = [ctypes.c_void_p]

        if user.IsIconic(hwnd):
            user.ShowWindow(hwnd, 9)  # SW_RESTORE

        return bool(user.SetForegroundWindow(hwnd))
    except Exception:
        return False


def close(process: Optional[subprocess.Popen]) -> None:
    """Closes the window and every process the browser launched."""

    if process is not None:
        try:
            if os.name == "nt":
                execute(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
            else:
                process.terminate()
        except Exception:
            pass

    close_leftovers()


def close_leftovers() -> None:
    """
    Kills any Edge/Chrome using BRAIN's own profile.

    Covers the case of a window left alive from a previous run: Edge reuses
    the process of the same profile and the one we launch ends instantly, so
    there is no PID to close.
    """

    if os.name != "nt":
        return

    profile = str(profile_folder()).replace("'", "''")
    order = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
        f"$_.CommandLine.Contains('{profile}') }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )

    try:
        execute(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", order], capture_output=True, timeout=15)
    except Exception:
        pass
