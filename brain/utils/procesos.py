"""
Lanzar programas externos sin que Windows abra una ventana negra de consola.

BRAIN de escritorio corre con pythonw.exe (sin consola). Cuando un programa sin
consola lanza otro programa de consola (nvidia-smi, tailscale, netstat...),
Windows abre una ventana negra para cada uno aunque solo dure un instante.
Con CREATE_NO_WINDOW eso no ocurre.
"""

import os
import subprocess
from typing import Any, Dict


def sin_ventana() -> Dict[str, Any]:
    """Argumentos extra para subprocess que ocultan la consola en Windows (y no hacen nada en otros sistemas)."""

    if os.name != "nt":
        return {}

    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


def ejecutar(comando, **opciones) -> subprocess.CompletedProcess:
    """subprocess.run sin ventana de consola."""

    for clave, valor in sin_ventana().items():
        opciones[clave] = opciones.get(clave, 0) | valor

    return subprocess.run(comando, **opciones)
