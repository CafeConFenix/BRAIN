"""Desktop program settings (data/desktop.json)."""

import json
from pathlib import Path

from brain.core.config import Config

DEFAULTS = {
    # False: closing the window shuts BRAIN down completely (and the tray icon disappears).
    # True: BRAIN keeps running in the background with the icon, so notices still sound.
    "background": False,
}


def _file() -> Path:
    return Path(Config.DATA) / "desktop.json"


def read() -> dict:
    data = dict(DEFAULTS)

    try:
        saved = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return data

    if isinstance(saved, dict):
        for key in DEFAULTS:
            if isinstance(saved.get(key), bool):
                data[key] = saved[key]

    return data


def save(**changes) -> dict:
    data = read()

    for key, value in changes.items():
        if key in DEFAULTS:
            data[key] = bool(value)

    try:
        _file().parent.mkdir(parents=True, exist_ok=True)
        _file().write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass

    return data
