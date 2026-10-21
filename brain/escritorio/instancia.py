"""
Una sola copia de BRAIN a la vez.

La primera copia que arranca escribe su puerto en datos/brain.instancia. Si
el usuario abre BRAIN otra vez, la segunda copia detecta que la primera sigue
viva, le pide que muestre la ventana y se cierra.
"""

import json
import os
import urllib.request
from pathlib import Path
from typing import Optional

from brain.core.config import Config


def _archivo() -> Path:
    return Path(Config.DATOS) / "brain.instancia"


def puerto_en_marcha() -> Optional[int]:
    """Puerto de la copia de BRAIN que ya está funcionando, o None."""

    try:
        puerto = int(json.loads(_archivo().read_text(encoding="utf-8")).get("puerto", 0))
    except (OSError, ValueError, TypeError):
        return None

    if not puerto:
        return None

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/api/estado", timeout=2) as r:
            return puerto if r.status == 200 else None
    except Exception:
        return None


def registrar(puerto: int) -> None:
    archivo = _archivo()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({"puerto": puerto, "pid": os.getpid()}), encoding="utf-8")


def olvidar() -> None:
    try:
        _archivo().unlink()
    except OSError:
        pass


def pedir_mostrar(puerto: int) -> bool:
    """Pide a la copia en marcha que enseñe su ventana."""

    try:
        peticion = urllib.request.Request(
            f"http://127.0.0.1:{puerto}/api/escritorio/mostrar",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(peticion, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False
