import time

from brain.base.module import ModuleBase
from brain.core import logger
from brain.i18n import noop, t, vocab
from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, read_config
from brain.modules.inventory import normalize

# Kinds of device BRAIN can control.
CONTROLLABLE = (
    "light",
    "switch",
    "fan",
    "cover",
    "climate",
    "scene",
    "script",
    "input_boolean",
    "media_player",
    "humidifier",
    "vacuum",
)

# Kinds BRAIN can only READ (never control): for safety, a conversation
# must not open locks or disarm alarms.
READ_ONLY = ("sensor", "binary_sensor", "lock", "alarm_control_panel", "weather", "person", "device_tracker")

# Covers that are never opened by voice or chat (garages, gates, doors).
FORBIDDEN_COVERS = ("garage", "gate", "door")

DOMAIN_NAMES = {
    "light": noop("lights"),
    "switch": noop("plugs and switches"),
    "fan": noop("fans"),
    "cover": noop("blinds and curtains"),
    "climate": noop("climate control"),
    "scene": noop("scenes"),
    "script": noop("scripts"),
    "input_boolean": noop("virtual switches"),
    "media_player": noop("players and televisions"),
    "humidifier": noop("humidifiers"),
    "vacuum": noop("vacuum cleaners"),
    "sensor": noop("sensors"),
    "binary_sensor": noop("presence sensors, doors and windows"),
    "lock": noop("locks"),
    "alarm_control_panel": noop("alarms"),
}

CATALOG_CACHE_SECONDS = 60

# Kinds shown with a switch in the web panel.
SWITCH_PANEL = ("light", "switch", "fan", "cover", "climate", "input_boolean", "media_player", "humidifier")


def _device_words():
    return vocab("device_words")


def _padding():
    return set(vocab("padding_words")) | set(vocab("all_words"))


def _no_room():
    return t("No room")


def _root(word):
    """Strip simple plurals (lights -> light, rooms -> room)."""

    if len(word) > 4 and word.endswith("es"):
        return word[:-2]

    if len(word) > 3 and word.endswith("s"):
        return word[:-1]

    return word


def _words(text):
    clean = "".join(c if c.isalnum() else " " for c in normalize(text))

    return clean.split()


class SmartHome(ModuleBase):
    """
    Control of the home through Home Assistant: lights, plugs, blinds,
    climate control, scenes and sensor readings.

    BRAIN's own data (hidden devices...) stays in smart_home.json; the real
    devices are managed by Home Assistant.
    """

    name = "smart_home"

    def __init__(self):
        super().__init__()

        self._ha = None
        self._catalog = None
        self._catalog_hour = 0.0
        self._areas = None
        self._areas_time = 0.0

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def ha(self):
        """Home Assistant client (the configuration is read again every time)."""

        url, token = read_config()

        if self._ha is None or (self._ha.url, self._ha.token) != (url, token):
            self._ha = HomeAssistant(url, token)
            self.forget_catalog()
            self._areas = None

        return self._ha

    def connected(self):
        return self.ha.configured

    def forget_catalog(self):
        """Force the states to be requested again next time (the rooms are kept)."""

        self._catalog = None
        self._catalog_hour = 0.0

    # ------------------------------------------------------------------
    # Devices the user does not want to see
    # ------------------------------------------------------------------

    def hidden(self):
        """Identifiers of the devices the user has hidden."""

        value = self.data.read_module(self.name).get("hidden", [])

        return {str(e) for e in value} if isinstance(value, list) else set()

    def save_hidden(self, entities):
        """Replace the list of hidden devices. Hidden ones disappear from the panel and from the AI."""

        clean = sorted({str(e).strip() for e in entities if str(e).strip() and "." in str(e)})
        data = self.data.read_module(self.name)
        data["hidden"] = clean
        self.data.save_module(self.name, data)
        self.forget_catalog()

        return clean

    def configurable_devices(self):
        """
        All the controllable devices (and scenes), grouped by room, with
        `visible` True/False, so the user can choose which ones to have in BRAIN.
        """

        hidden = self.hidden()
        groups = {}

        for gadget in self._load_catalog(ttl=15, include_hidden=True):
            if gadget["domain"] not in CONTROLLABLE:
                continue

            room = gadget["room"] or _no_room()
            groups.setdefault(room, []).append(
                {
                    "entity": gadget["entity"],
                    "name": gadget["name"],
                    "kind": gadget["domain"],
                    "visible": gadget["entity"] not in hidden,
                }
            )

        items = [
            {"room": h, "devices": sorted(groups[h], key=lambda d: normalize(d["name"]))}
            for h in sorted(groups, key=lambda h: (h == _no_room(), normalize(h)))
        ]

        return {
            "groups": items,
            "total": sum(len(g["devices"]) for g in items),
            "hidden": len(hidden),
        }

    def _load_catalog(self, ttl=CATALOG_CACHE_SECONDS, include_hidden=False):
        """Visible devices (without the ones the user hid), with name, kind, room and state."""

        catalog = self._full_catalog(ttl)

        if include_hidden:
            return catalog

        hidden = self.hidden()

        return [a for a in catalog if a["entity"] not in hidden] if hidden else catalog

    def _full_catalog(self, ttl=CATALOG_CACHE_SECONDS):
        """List of devices with name, kind, room and state (reuses what was read less than `ttl` s ago)."""

        now = time.time()

        client = self.ha  # if the configuration changed, this empties the catalog

        if self._catalog is not None and now - self._catalog_hour < ttl:
            return self._catalog

        states = client.states()

        # Rooms almost never change: they are requested at most every 5 minutes.
        if self._areas is None or now - self._areas_time > 300:
            self._areas = client.areas()
            self._areas_time = now

        areas = self._areas

        catalog = []

        for state in states:
            entity = state.get("entity_id", "")
            domain = entity.split(".", 1)[0]

            if domain not in CONTROLLABLE and domain not in READ_ONLY:
                continue

            attributes = state.get("attributes") or {}

            if attributes.get("hidden"):
                continue

            if domain == "cover" and attributes.get("device_class") in FORBIDDEN_COVERS:
                continue

            name = attributes.get("friendly_name") or entity

            catalog.append(
                {
                    "entity": entity,
                    "domain": domain,
                    "name": name,
                    "room": areas.get(entity, ""),
                    "state": state.get("state", ""),
                    "attributes": attributes,
                    "_words_name": {_root(p) for p in _words(name)},
                    "_keywords": {
                        _root(p) for p in _words(name) if p not in _device_words() and p not in _padding()
                    },
                    "_words_area": {_root(p) for p in _words(areas.get(entity, ""))},
                }
            )

        self._catalog = catalog
        self._catalog_hour = now

        return catalog

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @staticmethod
    def _analyze(text):
        """
        Split what the user says into: kind of device asked for, words that
        identify the device and whether they speak in the plural / "all".
        """

        domains = set()
        keys = []
        plural = False

        for word in _words(text):
            if word in vocab("all_words"):
                plural = True
                continue

            if word in _padding():
                continue

            if word in _device_words():
                domains.add(_device_words()[word])

                if word in vocab("plural_words"):
                    plural = True

                continue

            keys.append(_root(word))

        return domains, keys, plural

    def search(self, text, domains=None, include_reading=False):
        """
        Look for devices matching what the user said ("living room light",
        "bedroom blind"...).

        Returns (devices, plural): `plural` is True if the user spoke about
        several at once ("all the living room lights").
        """

        requested, keys, plural = self._analyze(text)

        if domains:
            # The tool limits the kinds; if the user named another kind that does
            # not fit, the tool wins.
            requested = (requested & set(domains)) or set(domains)

        candidates = []

        for gadget in self._load_catalog():
            if gadget["domain"] not in CONTROLLABLE and not include_reading:
                continue

            if requested and gadget["domain"] not in requested:
                continue

            candidates.append(gadget)

        if not keys:
            return (candidates if requested else []), plural

        key_set = set(keys)

        # 1) Those with all the words in their own name.
        by_name = [a for a in candidates if key_set <= a["_words_name"]]

        if by_name:
            # "the living room light" -> the one named exactly that, even if
            # there are others like "Living room ceiling light". If plural, all.
            exact = [a for a in by_name if a["_keywords"] == key_set]

            if len(exact) > 1:
                # "the living room light": between "Living room light" and "Living room lamp",
                # the one that carries the word the user said.
                said = {_root(p) for p in _words(text) if p in _device_words()}
                with_word = [a for a in exact if said and said <= a["_words_name"]]

                if len(with_word) == 1:
                    exact = with_word

            if len(exact) == 1 and not plural:
                return exact, plural

            return by_name, plural

        # 2) Words spread between the name and the room.
        by_set = [a for a in candidates if key_set <= (a["_words_name"] | a["_words_area"])]

        if by_set:
            return by_set, plural

        # 3) Only the room ("the living room lights").
        by_room = [a for a in candidates if a["_words_area"] and key_set <= a["_words_area"]]

        if by_room:
            return by_room, True

        return [], plural

    def _resolve(self, text, domains, all_items=False):
        """
        Find the devices of a command. Returns (devices, error_response): if there
        is a problem (nothing found or ambiguity) `error_response` is a dictionary
        ready to return to the AI.
        """

        try:
            devices, plural = self.search(text, domains)
        except HomeAssistantError as e:
            return [], {"error": str(e)}

        if not devices:
            if any(p in normalize(text) for p in vocab("safety_words")):
                return [], {
                    "error": "For safety I do not control locks, doors, garages or alarms. You will have to do it yourself."
                }

            examples = ", ".join(sorted({a["name"] for a in self._load_catalog() if a["domain"] in (domains or CONTROLLABLE)})[:12])

            return [], {
                "error": f"I cannot find any device matching '{text}'.",
                "devices_available": examples or "none",
            }

        if len(devices) > 1 and not (all_items or plural):
            options = [f"{a['name']}" + (f" ({a['room']})" if a["room"] else "") for a in devices[:10]]

            return [], {
                "ambiguous": True,
                "message": "Several devices match. Ask the user which one they mean, or repeat the command with all_items=true if they want all of them.",
                "options": options,
            }

        return devices, None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _execute(self, devices, service_by_domain, extra_data=None):
        facts = []
        failures = []

        for gadget in devices:
            service = service_by_domain.get(gadget["domain"])

            if service is None:
                failures.append(f"{gadget['name']}: does not support that action")
                continue

            data = {"entity_id": gadget["entity"]}

            if extra_data:
                data.update(extra_data.get(gadget["domain"], {}))

            try:
                self.ha.service(gadget["domain"], service, data)
                facts.append(gadget["name"])
                logger.system(f"Smart home: {gadget['domain']}.{service} -> {gadget['entity']}")
            except HomeAssistantError as e:
                failures.append(f"{gadget['name']}: {e}")

        self.forget_catalog()

        result = {"done_at": facts}

        if failures:
            result["failures"] = failures

        return result

    def turn_on(self, text, all_items=False):
        devices, problem = self._resolve(text, None, all_items)

        if problem:
            return problem

        return self._execute(
            devices,
            {
                "light": "turn_on",
                "switch": "turn_on",
                "fan": "turn_on",
                "cover": "open_cover",
                "climate": "turn_on",
                "scene": "turn_on",
                "script": "turn_on",
                "input_boolean": "turn_on",
                "media_player": "turn_on",
                "humidifier": "turn_on",
                "vacuum": "start",
            },
        )

    def turn_off(self, text, all_items=False):
        devices, problem = self._resolve(text, None, all_items)

        if problem:
            return problem

        return self._execute(
            devices,
            {
                "light": "turn_off",
                "switch": "turn_off",
                "fan": "turn_off",
                "cover": "close_cover",
                "climate": "turn_off",
                "input_boolean": "turn_off",
                "media_player": "turn_off",
                "humidifier": "turn_off",
                "vacuum": "return_to_base",
            },
        )

    def adjust_light(self, text, brightness=None, color=None, temperature=None, all_items=False):
        devices, problem = self._resolve(text, ["light"], all_items)

        if problem:
            return problem

        data = {}

        if brightness is not None:
            data["brightness_pct"] = max(1, min(100, int(round(float(brightness)))))

        if color:
            key = normalize(color)

            colors = vocab("colors")

            if key not in colors:
                return {"error": f"I do not know the color '{color}'. Colors: {', '.join(vocab('colors', 'en'))}."}

            data["rgb_color"] = list(colors[key])

        if temperature:
            key = normalize(temperature)

            temperatures = vocab("color_temperatures")

            if key not in temperatures:
                return {"error": "The light temperature can be: warm, neutral or cool."}

            data["color_temp_kelvin"] = temperatures[key]

        if not data:
            return {"error": "Give the brightness (0-100), a color or a light temperature."}

        return self._execute(devices, {"light": "turn_on"}, {"light": data})

    def blind_position(self, text, position, all_items=False):
        devices, problem = self._resolve(text, ["cover"], all_items)

        if problem:
            return problem

        position = max(0, min(100, int(round(float(position)))))

        return self._execute(devices, {"cover": "set_cover_position"}, {"cover": {"position": position}})

    def set_temperature(self, text, degrees, all_items=False):
        devices, problem = self._resolve(text, ["climate"], all_items)

        if problem:
            return problem

        degrees = float(degrees)

        if not 5 <= degrees <= 35:
            return {"error": "The temperature must be between 5 and 35 degrees."}

        return self._execute(devices, {"climate": "set_temperature"}, {"climate": {"temperature": degrees}})

    def activate_scene(self, text):
        devices, problem = self._resolve(text, ["scene", "script"], False)

        if problem:
            return problem

        return self._execute(devices, {"scene": "turn_on", "script": "turn_on"})

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize(gadget):
        data = {"name": gadget["name"], "state": gadget["state"]}

        if gadget["room"]:
            data["room"] = gadget["room"]

        attributes = gadget["attributes"]

        if gadget["domain"] == "light" and gadget["state"] == "on" and attributes.get("brightness") is not None:
            data["brightness_pct"] = round(attributes["brightness"] * 100 / 255)

        if gadget["domain"] == "cover" and attributes.get("current_position") is not None:
            data["position_pct"] = attributes["current_position"]

        if gadget["domain"] == "climate":
            for key, name in (("current_temperature", "current_temperature"), ("temperature", "target_temperature")):
                if attributes.get(key) is not None:
                    data[name] = attributes[key]

        if gadget["domain"] in ("sensor", "binary_sensor") and attributes.get("unit_of_measurement"):
            data["unit"] = attributes["unit_of_measurement"]

        return data

    def items(self, kind="", room="", limit=40):
        """Devices of the home, optionally filtered by kind and room."""

        domains = set()

        if kind:
            domains, _, _ = self._analyze(kind)

            if not domains and normalize(kind) in vocab("sensor_words"):
                domains = {"sensor", "binary_sensor"}

        catalog = self._load_catalog()

        if domains:
            catalog = [a for a in catalog if a["domain"] in domains]
        else:
            catalog = [a for a in catalog if a["domain"] in CONTROLLABLE]

        if room:
            keys = {_root(p) for p in _words(room)} - _padding()
            catalog = [a for a in catalog if keys <= (a["_words_area"] | a["_words_name"])]

        catalog = sorted(catalog, key=lambda a: (a["room"], a["name"]))

        result = {"total": len(catalog), "devices": [self._summarize(a) for a in catalog[:limit]]}

        if len(catalog) > limit:
            result["notice"] = "There are more; filter by kind or room to see the rest."

        return result

    def on(self):
        """What is on right now in the home (lights, plugs, fans, TV, climate...)."""

        devices = [
            a
            for a in self._load_catalog(ttl=10)
            if a["domain"] in ("light", "switch", "fan", "media_player", "climate", "humidifier", "input_boolean") and self._on(a) is True
        ]
        devices.sort(key=lambda a: (a["room"] or "~", normalize(a["name"])))

        return {
            "total": len(devices),
            "on": [{"entity": a["entity"], "name": a["name"], "kind": a["domain"], "room": a["room"]} for a in devices],
        }

    def with_problems(self, battery_minimum=20):
        """Offline devices and sensors with a low battery."""

        offline = []
        battery_low = []

        for a in self._load_catalog(ttl=30):
            if a["domain"] in ("scene", "script", "person", "device_tracker", "weather"):
                continue

            if a["state"] == "unavailable":
                offline.append({"name": a["name"], "room": a["room"]})
                continue

            attributes = a["attributes"]

            if a["domain"] == "sensor" and attributes.get("device_class") == "battery" and attributes.get("unit_of_measurement") == "%":
                try:
                    level = float(a["state"])
                except (TypeError, ValueError):
                    continue

                if level <= battery_minimum:
                    battery_low.append({"name": a["name"], "battery_pct": round(level), "room": a["room"]})

        battery_low.sort(key=lambda b: b["battery_pct"])

        return {
            "offline": offline[:30],
            "battery_low": battery_low[:30],
            "all_good": not offline and not battery_low,
        }

    def state_of(self, text):
        try:
            devices, _ = self.search(text, None, include_reading=True)
        except HomeAssistantError as e:
            return {"error": str(e)}

        if not devices:
            return {"error": f"I cannot find any device matching '{text}'."}

        return {"devices": [self._summarize(a) for a in devices[:10]]}


    # ------------------------------------------------------------------
    # Web panel: switches
    # ------------------------------------------------------------------

    @staticmethod
    def _on(gadget):
        """True/False according to the state, or None if it cannot be known."""

        state = gadget["state"]

        if state in ("unavailable", "unknown", ""):
            return None

        if gadget["domain"] == "cover":
            return state in ("open", "opening")

        if gadget["domain"] == "climate":
            return state != "off"

        if gadget["domain"] == "media_player":
            return state not in ("off", "standby")

        return state == "on"

    def panel(self):
        """
        Devices for the web panel, grouped by room, and the scenes apart. Each
        device carries `on` (True/False/None).
        """

        catalog = self._load_catalog(ttl=4)

        groups = {}
        scenes = []

        for gadget in catalog:
            domain = gadget["domain"]

            if domain in ("scene", "script"):
                scenes.append({"entity": gadget["entity"], "name": gadget["name"], "kind": domain})
                continue

            if domain not in SWITCH_PANEL:
                continue

            room = gadget["room"] or _no_room()

            device = {
                "entity": gadget["entity"],
                "name": gadget["name"],
                "kind": domain,
                "on": self._on(gadget),
                "state": gadget["state"],
            }

            detail = self._summarize(gadget)

            for key in ("brightness_pct", "position_pct", "current_temperature", "target_temperature"):
                if key in detail:
                    device[key] = detail[key]

            groups.setdefault(room, []).append(device)

        items = []

        for room in sorted(groups, key=lambda h: (h == _no_room(), normalize(h))):
            items.append(
                {"room": room, "devices": sorted(groups[room], key=lambda d: normalize(d["name"]))}
            )

        return {
            "groups": items,
            "scenes": sorted(scenes, key=lambda e: normalize(e["name"])),
            "total": sum(len(g["devices"]) for g in items),
        }

    def _controllable_device(self, entity):
        """The catalog device with that identifier, only if BRAIN can control it."""

        for gadget in self._load_catalog(ttl=30):
            if gadget["entity"] == entity and gadget["domain"] in CONTROLLABLE:
                return gadget

        return None

    def toggle(self, entity, turn_on):
        """
        Turn a panel device on or off (or open/close a blind).

        It only works with devices already in the controllable catalog: no
        commands can be sent to locks, garages or alarms.
        """

        gadget = self._controllable_device(str(entity))

        if gadget is None or gadget["domain"] not in SWITCH_PANEL:
            raise HomeAssistantError(t("I cannot control that device from BRAIN."))

        services = {
            "cover": ("open_cover", "close_cover"),
        }

        on, off = services.get(gadget["domain"], ("turn_on", "turn_off"))

        self.ha.service(gadget["domain"], on if turn_on else off, {"entity_id": gadget["entity"]})

        logger.system(f"Smart home (panel): {gadget['entity']} -> {'turn_on' if turn_on else 'turn_off'}")

        self.forget_catalog()

        return {"entity": gadget["entity"], "on": bool(turn_on)}

    def run_scene(self, entity):
        gadget = self._controllable_device(str(entity))

        if gadget is None or gadget["domain"] not in ("scene", "script"):
            raise HomeAssistantError(t("That scene does not exist."))

        self.ha.service(gadget["domain"], "turn_on", {"entity_id": gadget["entity"]})

        logger.system(f"Smart home (panel): scene {gadget['entity']}")

        self.forget_catalog()

        return {"entity": gadget["entity"], "launched": True}
