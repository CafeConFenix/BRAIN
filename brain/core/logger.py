from datetime import datetime

from brain.core.config import Config


def log_line(file, message):
    """
    Appends a dated line to the given log (system, errors...).

    Never raises: a failure to write the log must never break BRAIN.
    """

    try:
        Config.LOGS.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(Config.LOGS / f"{file}.log", "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")

    except OSError:
        pass


def error(message):
    log_line("errors", message)


def system(message):
    log_line("system", message)
