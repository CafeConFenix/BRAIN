"""Automatic startup with Windows (the user's Run key; no administrator rights needed)."""

import os
import sys
from pathlib import Path

REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "BRAIN"


def _pythonw() -> str:
    """pythonw.exe starts with no black window; if it does not exist, the current interpreter is used."""

    current = Path(sys.executable)
    candidate = current.with_name("pythonw.exe")

    return str(candidate if candidate.exists() else current)


def command(root: Path) -> str:
    return f'"{_pythonw()}" "{Path(root) / "main.py"}" --desktop --background'


def available() -> bool:
    return os.name == "nt"


def enabled() -> bool:
    if not available():
        return False

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY) as key:
            winreg.QueryValueEx(key, NAME)
            return True
    except OSError:
        return False


def enable(root: Path) -> bool:
    if not available():
        return False

    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command(root))

    return True


def disable() -> bool:
    if not available():
        return False

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, NAME)
    except OSError:
        pass

    return True
