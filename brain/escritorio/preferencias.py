"""Ajustes del programa de escritorio (datos/escritorio.json)."""

import json
from pathlib import Path

from brain.core.config import Config

PREDETERMINADAS = {
    # False: al cerrar la ventana, BRAIN se cierra del todo (y el icono junto al reloj desaparece).
    # True: BRAIN sigue en segundo plano con el icono, para que los avisos suenen.
    "segundo_plano": False,
}


def _archivo() -> Path:
    return Path(Config.DATOS) / "escritorio.json"


def leer() -> dict:
    datos = dict(PREDETERMINADAS)

    try:
        guardado = json.loads(_archivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return datos

    if isinstance(guardado, dict):
        for clave in PREDETERMINADAS:
            if isinstance(guardado.get(clave), bool):
                datos[clave] = guardado[clave]

    return datos


def guardar(**cambios) -> dict:
    datos = leer()

    for clave, valor in cambios.items():
        if clave in PREDETERMINADAS:
            datos[clave] = bool(valor)

    try:
        _archivo().parent.mkdir(parents=True, exist_ok=True)
        _archivo().write_text(json.dumps(datos, indent=2), encoding="utf-8")
    except OSError:
        pass

    return datos
