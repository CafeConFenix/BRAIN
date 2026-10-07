from datetime import datetime

from brain.core.config import Config


def registrar(archivo, mensaje):
    """
    Añade una línea con fecha al log indicado (sistema, errores...).

    Nunca lanza errores: un fallo al escribir el log no debe romper BRAIN.
    """

    try:
        Config.LOGS.mkdir(parents=True, exist_ok=True)

        marca = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(Config.LOGS / f"{archivo}.log", "a", encoding="utf-8") as f:
            f.write(f"[{marca}] {mensaje}\n")

    except OSError:
        pass


def error(mensaje):
    registrar("errores", mensaje)


def sistema(mensaje):
    registrar("sistema", mensaje)
