"""
Ventana propia de BRAIN.

Se usa Microsoft Edge (viene con Windows) o Chrome en "modo aplicación": una
ventana sin pestañas ni barra de direcciones, con su propio perfil, separada
de tu navegador habitual y de Brave. No hay que instalar nada.

Aquí también está todo lo necesario para que la ventana se comporte bien:
detectar si sigue abierta, traerla al frente y cerrarla del todo (Edge lanza
varios procesos y, si se mata solo el primero, la ventana puede quedarse viva).
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from brain.core.config import Config
from brain.utils.procesos import ejecutar, sin_ventana

# Título de la ventana: es el <title> de la página.
TITULO = "BRAIN"


def _candidatos() -> List[Path]:
    rutas: List[Path] = []

    for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(variable)

        if base:
            rutas.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)

        if base:
            rutas.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")

    for nombre in ("msedge", "chrome", "google-chrome", "chromium"):
        encontrado = shutil.which(nombre)

        if encontrado:
            rutas.append(Path(encontrado))

    return rutas


def buscar_navegador() -> Optional[Path]:
    for ruta in _candidatos():
        if ruta.exists():
            return ruta

    return None


def carpeta_perfil() -> Path:
    return Path(Config.DATOS) / "ventana"


def argumentos(navegador: Path, url: str, perfil: Path) -> List[str]:
    return [
        str(navegador),
        f"--app={url}",
        f"--user-data-dir={perfil}",
        "--window-size=1320,860",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate",
        # Sin esto Edge/Chrome pueden quedarse vivos en segundo plano al cerrar la ventana.
        "--disable-background-mode",
        "--disable-session-crashed-bubble",
        "--hide-crash-restore-bubble",
    ]


def abrir(url: str) -> Optional[subprocess.Popen]:
    """Abre la ventana de BRAIN. Devuelve el proceso, o None si no hay Edge ni Chrome."""

    navegador = buscar_navegador()

    if navegador is None:
        return None

    perfil = carpeta_perfil()
    perfil.mkdir(parents=True, exist_ok=True)

    return subprocess.Popen(
        argumentos(navegador, url, perfil),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        **sin_ventana(),
    )


# ---------------------------------------------------------------- Windows


def _buscar_hwnd() -> int:
    """Manejador de la ventana de BRAIN (0 si no existe o no es Windows)."""

    if os.name != "nt":
        return 0

    try:
        import ctypes

        usuario = ctypes.windll.user32
        usuario.FindWindowW.restype = ctypes.c_void_p

        return int(usuario.FindWindowW("Chrome_WidgetWin_1", TITULO) or 0)
    except Exception:
        return 0


def hay_ventana() -> bool:
    """True si la ventana de BRAIN está abierta (aunque esté minimizada)."""

    return _buscar_hwnd() != 0


def traer_al_frente() -> bool:
    """Restaura la ventana si está minimizada y la pone delante. False si no se ha podido."""

    hwnd = _buscar_hwnd()

    if not hwnd:
        return False

    try:
        import ctypes

        usuario = ctypes.windll.user32
        usuario.IsIconic.argtypes = [ctypes.c_void_p]
        usuario.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        usuario.SetForegroundWindow.argtypes = [ctypes.c_void_p]

        if usuario.IsIconic(hwnd):
            usuario.ShowWindow(hwnd, 9)  # SW_RESTORE

        return bool(usuario.SetForegroundWindow(hwnd))
    except Exception:
        return False


def cerrar(proceso: Optional[subprocess.Popen]) -> None:
    """Cierra la ventana y todos los procesos que haya lanzado el navegador."""

    if proceso is not None:
        try:
            if os.name == "nt":
                ejecutar(["taskkill", "/PID", str(proceso.pid), "/T", "/F"], capture_output=True, timeout=10)
            else:
                proceso.terminate()
        except Exception:
            pass

    cerrar_restos()


def cerrar_restos() -> None:
    """
    Mata cualquier Edge/Chrome que use el perfil propio de BRAIN.

    Cubre el caso de una ventana que se quedó viva de una ejecución anterior:
    Edge reutiliza el proceso del mismo perfil y el que lanzamos termina al
    instante, así que no hay un PID que cerrar.
    """

    if os.name != "nt":
        return

    perfil = str(carpeta_perfil()).replace("'", "''")
    orden = (
        "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and "
        f"$_.CommandLine.Contains('{perfil}') }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )

    try:
        ejecutar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", orden], capture_output=True, timeout=15)
    except Exception:
        pass
