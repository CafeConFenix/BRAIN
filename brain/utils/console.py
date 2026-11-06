import os
import sys


def prepare_console():
    """
    Gets the console ready to print accented and non-English characters.

    On Windows, the classic console uses an encoding (cp1252 / cp850)
    that does not support some characters and makes `print` fail with
    UnicodeEncodeError. This forces UTF-8 and, if a character still
    cannot be shown, replaces it instead of breaking the program.
    """

    os.environ.setdefault("PYTHONUTF8", "1")

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is None:
            continue

        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

    if os.name == "nt":
        # Turns on UTF-8 output for the Windows console (equivalent to chcp 65001).
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
