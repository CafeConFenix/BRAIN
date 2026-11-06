"""
Launch external programs without Windows opening a black console window.

The desktop version of BRAIN runs with pythonw.exe (no console). When a
console-less program launches another console program (nvidia-smi, tailscale,
netstat...), Windows opens a black window for each one even if it only lasts
an instant. CREATE_NO_WINDOW prevents that.
"""

import os
import subprocess
from typing import Any, Dict


def no_window() -> Dict[str, Any]:
    """Extra subprocess arguments that hide the console on Windows (and do nothing on other systems)."""

    if os.name != "nt":
        return {}

    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


def execute(command, **options) -> subprocess.CompletedProcess:
    """subprocess.run with no console window."""

    for key, value in no_window().items():
        options[key] = options.get(key, 0) | value

    return subprocess.run(command, **options)
