import os
import sys


def preparar_consola():
    """
    Deja la consola lista para escribir en español.

    En Windows la consola clásica usa una codificación (cp1252 / cp850)
    que no admite algunos caracteres y hace que `print` falle con
    UnicodeEncodeError. Aquí se fuerza UTF-8 y, si aun así un carácter no
    se puede mostrar, se sustituye en lugar de romper el programa.
    """

    os.environ.setdefault("PYTHONUTF8", "1")

    for flujo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)

        if reconfigurar is None:
            continue

        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

    if os.name == "nt":
        # Activa la salida UTF-8 de la consola de Windows (equivale a chcp 65001).
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
