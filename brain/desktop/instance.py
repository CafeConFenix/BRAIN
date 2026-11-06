"""
Only one copy of BRAIN at a time.

The first copy that starts writes its port to data/brain.instance. If the
user opens BRAIN again, the second copy detects that the first one is still
alive, asks it to show its window, and closes itself.
"""

import json
import os
import urllib.request
from pathlib import Path
from typing import Optional

from brain.core.config import Config


def _file() -> Path:
    return Path(Config.DATA) / "brain.instance"


def port_running() -> Optional[int]:
    """Port of the already running copy of BRAIN, or None."""

    try:
        port = int(json.loads(_file().read_text(encoding="utf-8")).get("port", 0))
    except (OSError, ValueError, TypeError):
        return None

    if not port:
        return None

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=2) as r:
            return port if r.status == 200 else None
    except Exception:
        return None


def register(port: int) -> None:
    file = _file()
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps({"port": port, "pid": os.getpid()}), encoding="utf-8")


def forget() -> None:
    try:
        _file().unlink()
    except OSError:
        pass


def ask_show(port: int) -> bool:
    """Asks the running copy to show its window."""

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/desktop/show",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False
