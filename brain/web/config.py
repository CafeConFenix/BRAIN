"""
Configuration from the web itself: first-run wizard (Home Assistant and
energy) and choosing which smart-home devices to show.

It does the same thing CONFIGURE_SMART_HOME.bat and CONFIGURE_ENERGY.bat did,
but with screens instead of questions in a console. The Home Assistant key
is never sent back to the web page.
"""

import json
from pathlib import Path

from brain.core.config import Config
from brain.i18n import t
from brain.integrations.home_assistant import (
    HomeAssistant,
    HomeAssistantError,
    find_home_assistant,
    save_config,
    read_config,
    normalize_url,
)
from brain.modules.energy import (
    ROLE_NAMES,
    ROLES,
    RealtimeEnergy,
    _to_watts,
    _is_power,
    describe,
    detect_sensors,
    save_energy_sensors,
    read_energy_sensors,
)

# Routes only served from the computer itself (they touch the Home Assistant key).
LOCAL_ONLY = (
    "/api/config/state",
    "/api/config/ha/search",
    "/api/config/ha/save",
    "/api/config/energy",
    "/api/config/energy/save",
    "/api/config/skip",
)

GET_ROUTES = ("/api/config/state", "/api/config/energy", "/api/config/devices")
POST_ROUTES = (
    "/api/config/ha/search",
    "/api/config/ha/save",
    "/api/config/energy/save",
    "/api/config/skip",
    "/api/config/devices/save",
)

DOMAIN_NAMES = (
    ("light", "lights"),
    ("switch", "plugs and switches"),
    ("cover", "blinds and curtains"),
    ("climate", "thermostats"),
    ("scene", "scenes"),
    ("media_player", "players"),
)


def _file() -> Path:
    return Path(Config.DATA) / "assistant.json"


def assistant_seen() -> bool:
    try:
        return bool(json.loads(_file().read_text(encoding="utf-8")).get("seen"))
    except (OSError, ValueError, AttributeError):
        return False


def mark_assistant_seen(seen=True) -> None:
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps({"seen": bool(seen)}), encoding="utf-8")


def saved_sensors() -> dict:
    return {role: read_energy_sensors().get(role, "") for role in ROLES}


def config_state() -> dict:
    url, token = read_config()
    connected = bool(url and token)
    energy = read_energy_sensors()

    return {
        "ha": {"configured": connected, "url": url, "token_saved": bool(token)},
        "energy": {"configured": any(energy.get(role) for role in ROLES), "sensors": saved_sensors()},
        "assistant_seen": assistant_seen(),
        # The wizard only appears the first time, while nothing is configured yet.
        "first_time": not connected and not assistant_seen(),
    }


def find_ha() -> dict:
    return {"found": find_home_assistant()}


def save_ha(url, token) -> dict:
    """Tests the connection and, if it works, saves the address and the key."""

    url = normalize_url(url)

    if not url:
        raise ValueError(t("Type the Home Assistant address (for example 192.168.1.50:8123)."))

    token = (token or "").strip() or read_config()[1]

    if not token:
        raise ValueError(t("Paste the Home Assistant access key (token)."))

    client = HomeAssistant(url, token, timeout=10)
    client.check()
    states = client.states()
    save_config(url, token)

    accounts = {}

    for state in states:
        domain = state.get("entity_id", "").split(".", 1)[0]
        accounts[domain] = accounts.get(domain, 0) + 1

    return {
        "ok": True,
        "url": url,
        "summary": [{"kind": t(name), "total": accounts[domain]} for domain, name in DOMAIN_NAMES if accounts.get(domain)],
        "energy_detected": bool(detect_sensors(states)["production"]),
    }


def _powers(states) -> list:
    items = [
        {
            "entity": e["entity_id"],
            "name": (e.get("attributes") or {}).get("friendly_name", e["entity_id"]),
            "value_w": round(_to_watts(e)),
        }
        for e in states
        if _is_power(e) and _to_watts(e) is not None
    ]

    return sorted(items, key=lambda p: p["name"].lower())


def energy_candidates() -> dict:
    ha = HomeAssistant()

    if not ha.configured:
        raise HomeAssistantError(t("First connect Home Assistant."))

    states = ha.states()
    candidates = detect_sensors(states)
    chosen = saved_sensors()

    return {
        "roles": [
            {"role": role, "name": ROLE_NAMES[role], "candidates": candidates[role], "chosen": chosen.get(role, "")}
            for role in ROLES
        ],
        "powers": _powers(states),
        "grid_inverted": bool(read_energy_sensors().get("grid_inverted")),
    }


def save_energy(data) -> dict:
    ha = HomeAssistant()

    if not ha.configured:
        raise HomeAssistantError(t("First connect Home Assistant."))

    states = {e.get("entity_id"): e for e in ha.states()}
    chosen = {}

    for role in ROLES:
        entity = str(data.get(role) or "").strip()

        if not entity:
            continue

        state = states.get(entity)

        if state is None:
            raise ValueError(t("Home Assistant does not have the sensor {0}.", entity))

        if role != "battery_pct" and (not _is_power(state) or _to_watts(state) is None):
            raise ValueError(t("{0} is not a power sensor (W or kW).", entity))

        chosen[role] = entity

    if not chosen:
        raise ValueError(t("Choose at least one sensor."))

    # The sign of the grid sensor depends on the device: it is worked out from what the user sees now.
    now = str(data.get("grid_now") or "").strip().lower()

    if chosen.get("grid") and now in ("buying", "selling"):
        current = _to_watts(states[chosen["grid"]])

        if current is not None and abs(current) > 50:
            if (now == "buying" and current < 0) or (now == "selling" and current > 0):
                chosen["grid_inverted"] = True
    elif data.get("grid_inverted") and chosen.get("grid"):
        chosen["grid_inverted"] = True

    save_energy_sensors(chosen)

    return {"ok": True, "reading": describe(RealtimeEnergy().read())}


def devices(brain) -> dict:
    smart_home = brain.modules.get("smart_home")

    if smart_home is None or not smart_home.connected():
        return {"connected": False, "groups": [], "total": 0, "hidden": 0}

    return {"connected": True, **smart_home.configurable_devices()}


def save_devices(brain, data) -> dict:
    smart_home = brain.modules.get("smart_home")

    if smart_home is None:
        raise ValueError(t("Smart home is not available."))

    hidden = data.get("hidden")

    if not isinstance(hidden, list):
        raise ValueError(t("The list of hidden devices is missing."))

    saved = smart_home.save_hidden(hidden)

    return {"ok": True, "hidden": len(saved)}


def handle(brain, method, path, data, local):
    """
    Serves a configuration route. Returns (code, response), or None if
    the route does not belong to this module.
    """

    if path not in (GET_ROUTES if method == "GET" else POST_ROUTES):
        return None

    if path in LOCAL_ONLY and not local:
        return 403, {"error": t("This can only be configured from the home computer.")}

    try:
        if path == "/api/config/state":
            return 200, config_state()

        if path == "/api/config/ha/search":
            return 200, find_ha()

        if path == "/api/config/ha/save":
            return 200, save_ha(data.get("url"), data.get("token"))

        if path == "/api/config/energy" and method == "GET":
            return 200, energy_candidates()

        if path == "/api/config/energy/save":
            return 200, save_energy(data)

        if path == "/api/config/skip":
            mark_assistant_seen(True)

            return 200, {"ok": True}

        if path == "/api/config/devices":
            return 200, devices(brain)

        if path == "/api/config/devices/save":
            return 200, save_devices(brain, data)

    except HomeAssistantError as error:
        return 502, {"error": str(error)}

    except ValueError as error:
        return 400, {"error": str(error)}

    return None
