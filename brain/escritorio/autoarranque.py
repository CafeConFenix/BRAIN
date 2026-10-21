"""Arranque automático con Windows (clave Run del usuario; no necesita permisos de administrador)."""

import os
import sys
from pathlib import Path

CLAVE = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE = "BRAIN"


def _pythonw() -> str:
    """pythonw.exe arranca sin ventana negra; si no existe se usa el intérprete actual."""

    actual = Path(sys.executable)
    candidato = actual.with_name("pythonw.exe")

    return str(candidato if candidato.exists() else actual)


def comando(raiz: Path) -> str:
    return f'"{_pythonw()}" "{Path(raiz) / "main.py"}" --escritorio --segundo-plano'


def disponible() -> bool:
    return os.name == "nt"


def activado() -> bool:
    if not disponible():
        return False

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE) as clave:
            winreg.QueryValueEx(clave, NOMBRE)
            return True
    except OSError:
        return False


def activar(raiz: Path) -> bool:
    if not disponible():
        return False

    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE, 0, winreg.KEY_SET_VALUE) as clave:
        winreg.SetValueEx(clave, NOMBRE, 0, winreg.REG_SZ, comando(raiz))

    return True


def desactivar() -> bool:
    if not disponible():
        return False

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE, 0, winreg.KEY_SET_VALUE) as clave:
            winreg.DeleteValue(clave, NOMBRE)
    except OSError:
        pass

    return True
