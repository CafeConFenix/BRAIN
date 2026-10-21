"""
Cerrar BRAIN del todo desde fuera (CERRAR_BRAIN.bat / `main.py --cerrar`).

Primero se le pide que salga él mismo (así quita su icono y cierra su ventana
como es debido). Solo si no responde se le mata, y después se limpia lo que
pudiera haber quedado: el icono junto al reloj y la ventana.
"""

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Callable

from brain.core.config import Config
from brain.escritorio import instancia, ventana
from brain.utils.procesos import ejecutar


def _pid_registrado() -> int:
    try:
        return int(json.loads((Path(Config.DATOS) / "brain.instancia").read_text(encoding="utf-8")).get("pid", 0))
    except (OSError, ValueError, TypeError):
        return 0


def _pedir_salir(puerto: int) -> bool:
    try:
        peticion = urllib.request.Request(
            f"http://127.0.0.1:{puerto}/api/escritorio/salir",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def _matar(pid: int) -> None:
    if pid <= 0 or pid == os.getpid():
        return

    try:
        if os.name == "nt":
            ejecutar(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10)
        else:
            os.kill(pid, 9)
    except Exception:
        pass


def _copias_antiguas() -> None:
    """Windows: cierra copias de BRAIN que no se registraron (modo navegador, versiones antiguas)."""

    if os.name != "nt":
        return

    orden = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'pythonw.exe' OR Name = 'python.exe'\" | "
        "Where-Object { $_.ProcessId -ne " + str(os.getpid()) + " -and $_.CommandLine -like '*main.py*' -and "
        "$_.CommandLine -notlike '*--cerrar*' -and $_.CommandLine -match '--escritorio|--web|--consola|BRAIN' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )

    try:
        ejecutar(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", orden], capture_output=True, timeout=20)
    except Exception:
        pass


def cerrar_brain(decir: Callable[[str], None] = print, espera: float = 12.0) -> int:
    puerto = instancia.puerto_en_marcha()
    pid = _pid_registrado()

    if puerto:
        decir("Cerrando BRAIN...")
        _pedir_salir(puerto)
        limite = time.time() + espera

        while time.time() < limite and instancia.puerto_en_marcha():
            time.sleep(0.3)

        if instancia.puerto_en_marcha():
            decir("BRAIN no responde; lo cierro a la fuerza.")
            _matar(pid)
    elif pid:
        _matar(pid)

    _copias_antiguas()

    # Un icono huérfano se quita solo en cuanto ve la señal de parada.
    try:
        (Path(Config.DATOS) / "bandeja.parar").write_text("parar", encoding="utf-8")
        time.sleep(1.5)
        (Path(Config.DATOS) / "bandeja.parar").unlink()
    except OSError:
        pass

    ventana.cerrar_restos()
    instancia.olvidar()
    decir("BRAIN está cerrado.")

    return 0
