"""
BRAIN automations: "if X happens, do Y" rules created in natural language.

Triggers:
  - hour:   at a time and on certain days ("every day at 7:30")
  - sensor: the state of a Home Assistant sensor or device meets a condition
  - energy: inverter production, consumption, grid, surplus or battery meets a condition

Actions: notice (notification with sound), turn_on, turn_off and scene. The
home ones go through the smart home module, so they keep its safety limits
(never locks, garages or alarms).

The scheduler calls `evaluate()` every few seconds. Sensor and energy triggers
fire when the condition BECOMES true (not on every check) and respect a wait
time between runs.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from brain.base.module import ModuleBase
from brain.i18n import noop, t, vocab
from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, read_config
from brain.modules.notices import Notices
from brain.modules.smart_home import SmartHome
from brain.modules.inventory import normalize
from brain.utils.dates import valid_hour, weekday_index, weekday_names

MAX_RULES = 40
HOUR_WINDOW_MINUTES = 10  # if BRAIN was closed at the hour, it still runs the rule during these minutes

TRIGGERS = ("hour", "sensor", "energy")
ACTIONS = ("notice", "turn_on", "turn_off", "scene")
CONDITIONS = ("above", "below", "equal")
MAGNITUDES = ("production", "consumption", "grid", "surplus", "battery")

MAGNITUDE_NAMES = {
    "production": noop("production"),
    "consumption": noop("consumption"),
    "grid": noop("grid"),
    "surplus": noop("surplus"),
    "battery": noop("battery"),
}


def _canonical(table: str, text, allowed=None) -> str:
    """The standard name of a word: 'mayor' -> 'above'. Unknown words are returned normalized."""

    key = normalize(text or "")

    return vocab(table).get(key, key)


def interpret_days(text) -> List[int]:
    """'monday,friday' / 'weekdays' / 'weekend' / 'all' -> [0..6]."""

    key = normalize(text or "")

    if key in vocab("every_day_words"):
        return list(range(7))

    if key in vocab("weekday_words"):
        return [0, 1, 2, 3, 4]

    if key in vocab("weekend_words"):
        return [5, 6]

    found = {weekday_index(p) for p in re.findall(r"[a-z]+", key)}
    days = sorted(d for d in found if d is not None)

    if not days:
        raise ValueError(t("I do not understand the days '{0}'. Use 'all', 'weekdays', 'weekend' or names like 'monday, thursday'.", text))

    return days


def describe_days(days: List[int]) -> str:
    if days == list(range(7)):
        return t("every day")

    if days == [0, 1, 2, 3, 4]:
        return t("from Monday to Friday")

    if days == [5, 6]:
        return t("at weekends")

    names = weekday_names()

    return ", ".join(names[d] for d in days)


def _number(value):
    try:
        return float(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _meets(current, condition, expected) -> Optional[bool]:
    """Compare a current value with the expected one. None if they cannot be compared."""

    if current is None:
        return None

    if condition == "equal":
        a, e = _number(current), _number(expected)

        if a is not None and e is not None:
            return a == e

        return normalize(current) == normalize(expected)

    a, e = _number(current), _number(expected)

    if a is None or e is None:
        return None

    return a > e if condition == "above" else a < e


class Automations(ModuleBase):
    """Rules "if this happens, do that", created in natural language."""

    name = "automations"

    def __init__(self):
        super().__init__()
        self._active: Dict[str, Optional[bool]] = {}  # previous state of the condition (to detect the change)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def rules(self) -> List[dict]:
        return self.get_section("rules")

    def _save(self, rules: List[dict]) -> None:
        self.save_section("rules", rules)

    @staticmethod
    def _key(rule) -> str:
        return f"{rule['id']}:{rule.get('created')}"

    def _search(self, rules, name) -> dict:
        key = normalize(name)

        for r in rules:
            if normalize(r["name"]) == key or str(r["id"]) == str(name).strip():
                return r

        partial = [r for r in rules if key and key in normalize(r["name"])]

        if len(partial) == 1:
            return partial[0]

        if len(partial) > 1:
            raise ValueError(t("'{0}' matches several: {1}.", name, ", ".join(r["name"] for r in partial)))

        raise ValueError(t("I cannot find any automation called '{0}'.", name))

    # ------------------------------------------------------------------
    # Create, list, delete
    # ------------------------------------------------------------------

    def create(self, name, trigger: dict, actions: List[dict], wait_minutes=5) -> dict:
        name = str(name or "").strip()

        if not name:
            raise ValueError(t("The automation needs a name."))

        trigger = self._validate_trigger(trigger)
        actions = [self._validate_action(a) for a in actions]

        if not actions:
            raise ValueError(t("The automation needs at least one action."))

        rules = self.rules()

        if len(rules) >= MAX_RULES:
            raise ValueError(t("There are already {0} automations; delete one first.", MAX_RULES))

        if any(normalize(r["name"]) == normalize(name) for r in rules):
            raise ValueError(t("There is already an automation called '{0}'.", name))

        rule = {
            "id": max([r["id"] for r in rules] + [0]) + 1,
            "name": name,
            "active": True,
            "trigger": trigger,
            "actions": actions,
            "wait_minutes": max(0, float(wait_minutes if wait_minutes not in (None, "") else 5)),
            "created": datetime.now().isoformat(timespec="seconds"),
            "runs": 0,
            "last_run": None,
            "last_result": None,
        }

        rules.append(rule)
        self._save(rules)

        return {**rule, "summary": self.describe(rule)}

    def _validate_trigger(self, d: dict) -> dict:
        kind = _canonical("trigger_words", d.get("kind", ""))

        if kind not in TRIGGERS:
            raise ValueError(t("The trigger '{0}' does not exist. Options: {1}.", d.get("kind"), ", ".join(TRIGGERS)))

        if kind == "hour":
            try:
                hour = valid_hour(d.get("hour"))
            except ValueError:
                hour = None

            if hour is None:
                raise ValueError(t("The time '{0}' is not valid. Use HH:MM, for example 07:30.", d.get("hour")))

            return {"kind": "hour", "hour": hour, "days": interpret_days(d.get("days"))}

        condition = _canonical("condition_words", d.get("condition", ""))

        if condition not in CONDITIONS:
            raise ValueError(t("The condition '{0}' is not valid. Use above, below or equal.", d.get("condition")))

        value = d.get("value")

        if value in (None, ""):
            raise ValueError(t("The value to compare with is missing."))

        if kind == "energy":
            magnitude = _canonical("magnitude_words", d.get("magnitude", ""))

            if magnitude not in MAGNITUDES:
                raise ValueError(t("The magnitude '{0}' does not exist. Options: {1}.", d.get("magnitude"), ", ".join(MAGNITUDES)))

            if _number(value) is None or condition == "equal":
                raise ValueError(t("For energy use 'above' or 'below' with a number (watts; percentage for the battery)."))

            return {"kind": "energy", "magnitude": magnitude, "condition": condition, "value": _number(value)}

        if not d.get("entity"):
            raise ValueError(t("The sensor or device to watch is missing."))

        if condition != "equal" and _number(value) is None:
            raise ValueError(t("With 'above' or 'below' the value has to be a number."))

        return {
            "kind": "sensor",
            "entity": str(d["entity"]),
            "name": str(d.get("name") or d["entity"]),
            "condition": condition,
            "value": _number(value) if condition != "equal" or _number(value) is not None else str(value).strip(),
        }

    def _validate_action(self, a: dict) -> dict:
        kind = _canonical("action_words", a.get("kind", ""))

        if kind not in ACTIONS:
            raise ValueError(t("The action '{0}' does not exist. Options: {1}.", a.get("kind"), ", ".join(ACTIONS)))

        if kind == "notice":
            return {"kind": "notice", "message": str(a.get("message") or "").strip() or None}

        goal = str(a.get("goal") or "").strip()

        if not goal:
            raise ValueError(t("Say which scene to activate.") if kind == "scene" else t("Say which device to {0}.", kind))

        return {"kind": kind, "goal": goal}

    def resolve_sensor(self, text) -> dict:
        """Look in Home Assistant for the sensor or device the user named (exactly one)."""

        devices, _ = SmartHome().search(text, include_reading=True)

        if not devices:
            raise ValueError(t("I cannot find in Home Assistant any sensor or device matching '{0}'.", text))

        if len(devices) > 1:
            options = ", ".join(a["name"] for a in devices[:6])
            raise ValueError(t("'{0}' matches several: {1}. Tell me exactly which one.", text, options))

        return {"entity": devices[0]["entity"], "name": devices[0]["name"]}

    def check_goal(self, action: str, goal: str) -> None:
        """Check in Home Assistant that the device or scene exists and is exactly one (otherwise ValueError)."""

        action = _canonical("action_words", action)

        if action not in ("turn_on", "turn_off", "scene"):
            return

        _, problem = SmartHome()._resolve(goal, ["scene", "script"] if action == "scene" else None, False)

        if problem:
            if problem.get("ambiguous"):
                raise ValueError(t("'{0}' matches several: {1}. Tell me exactly which one.", goal, ", ".join(problem["options"])))

            raise ValueError(problem.get("error", t("I cannot find '{0}'.", goal)))

    def describe(self, rule: dict) -> str:
        d = rule["trigger"]

        if d["kind"] == "hour":
            due = t("at {0} {1}", d["hour"], describe_days(d["days"]))
        elif d["kind"] == "sensor":
            due = {
                "above": t("when {0} is above {1}", d["name"], d["value"]),
                "below": t("when {0} is below {1}", d["name"], d["value"]),
                "equal": t("when {0} is equal to {1}", d["name"], d["value"]),
            }[d["condition"]]
        else:
            unit = "%" if d["magnitude"] == "battery" else " W"
            magnitude = t(MAGNITUDE_NAMES[d["magnitude"]])
            value = f"{d['value']:g}{unit}"
            due = (
                t("when {0} is above {1}", magnitude, value)
                if d["condition"] == "above"
                else t("when {0} is below {1}", magnitude, value)
            )

        steps = []

        for a in rule["actions"]:
            if a["kind"] == "notice":
                steps.append(t("notify: {0}", a["message"]) if a.get("message") else t("notify"))
            elif a["kind"] == "scene":
                steps.append(t("activate the scene {0}", a["goal"]))
            else:
                steps.append(f"{a['kind']} {a['goal']}")

        return f"{due}: {', '.join(steps)}"

    def items(self) -> List[dict]:
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "active": r["active"],
                "rule": self.describe(r),
                "runs": r.get("runs", 0),
                "last_run": r.get("last_run"),
                "last_result": r.get("last_result"),
            }
            for r in self.rules()
        ]

    def delete(self, name) -> dict:
        rules = self.rules()
        rule = self._search(rules, name)

        self._save([r for r in rules if r["id"] != rule["id"]])
        self._active.pop(self._key(rule), None)

        return {"id": rule["id"], "name": rule["name"]}

    def enable(self, name, active=True) -> dict:
        rules = self.rules()
        rule = self._search(rules, name)

        rule["active"] = bool(active)
        self._active.pop(self._key(rule), None)
        self._save(rules)

        return {"name": rule["name"], "active": rule["active"]}

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _states(self) -> Dict[str, dict]:
        url, token = read_config()
        ha = HomeAssistant(url, token, timeout=8)

        if not ha.configured:
            raise HomeAssistantError(t("Home Assistant is not configured."))

        return {e.get("entity_id"): e for e in ha.states()}

    def _energy(self) -> dict:
        from brain.tools.builtin.energy import realtime

        return realtime.read()

    @staticmethod
    def _energy_value(reading: dict, magnitude: str):
        if not reading.get("configured") or reading.get("error"):
            return None

        if magnitude == "surplus":
            p, c = reading.get("production_w"), reading.get("consumption_w")

            return None if p is None or c is None else p - c

        key = {"production": "production_w", "consumption": "consumption_w", "grid": "grid_w", "battery": "battery_pct"}[magnitude]

        return reading.get(key)

    def evaluate(self, now: Optional[datetime] = None) -> List[str]:
        """Check all the active rules and run those that are due. Return what was run."""

        now = now or datetime.now()
        rules = self.rules()
        active = [r for r in rules if r.get("active")]

        if not active:
            return []

        states = reading = None
        source_errors = {}

        if any(r["trigger"]["kind"] == "sensor" for r in active):
            try:
                states = self._states()
            except Exception as error:  # no data from this source, the other rules go on
                source_errors["sensor"] = str(error)

        if any(r["trigger"]["kind"] == "energy" for r in active):
            try:
                reading = self._energy()
            except Exception as error:
                source_errors["energy"] = str(error)

        run, changed = [], False

        for rule in active:
            try:
                if self._should_run(rule, now, states, reading):
                    result = self._execute(rule)
                    rule["runs"] = rule.get("runs", 0) + 1
                    rule["last_run"] = now.isoformat(timespec="seconds")
                    rule["last_result"] = result
                    run.append(f"{rule['name']}: {result}")
                    changed = True
            except Exception as error:  # a broken rule does not stop the others
                rule["last_result"] = f"Error: {error}"
                changed = True

        if changed:
            self._save_run_state(rules)

        return run

    def _save_run_state(self, rules: List[dict]) -> None:
        """Save counters and last result without overwriting rules created or deleted in the meantime."""

        current_rules = {r["id"]: r for r in self.rules()}

        for rule in rules:
            if rule["id"] in current_rules:
                for field in ("runs", "last_run", "last_result"):
                    current_rules[rule["id"]][field] = rule.get(field)

        self._save(list(current_rules.values()))

    def _should_run(self, rule, now, states, reading) -> bool:
        d = rule["trigger"]

        if d["kind"] == "hour":
            return self._due_by_hour(rule, d, now)

        if d["kind"] == "sensor":
            state = (states or {}).get(d["entity"])
            current = state.get("state") if state else None

            if current in ("unavailable", "unknown"):
                current = None
        else:
            current = self._energy_value(reading, d["magnitude"]) if reading else None

        meets = _meets(current, d["condition"], d["value"])
        previous = self._active.get(self._key(rule))

        if meets is None:  # no data: the known state does not change
            return False

        self._active[self._key(rule)] = meets

        # Only when going from "not met" to "met". The first reading after
        # starting does not fire (so a restart does not repeat actions).
        if not meets or previous is not False:
            return False

        return self._outside_wait(rule, now)

    @staticmethod
    def _due_by_hour(rule, d, now) -> bool:
        if now.weekday() not in d["days"]:
            return False

        hours, minutes = (int(x) for x in d["hour"].split(":"))
        goal = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        if not goal <= now <= goal + timedelta(minutes=HOUR_WINDOW_MINUTES):
            return False

        last = rule.get("last_run")

        return not last or datetime.fromisoformat(last) < goal

    @staticmethod
    def _outside_wait(rule, now) -> bool:
        last = rule.get("last_run")

        if not last:
            return True

        return now - datetime.fromisoformat(last) >= timedelta(minutes=rule.get("wait_minutes", 5))

    def _execute(self, rule) -> str:
        notices = Notices()
        smart_home = SmartHome()
        results = []

        for action in rule["actions"]:
            if action["kind"] == "notice":
                text = action.get("message") or rule["name"]
                notices.notify(rule["name"], text, kind="automation", level="important")
                results.append(t("notice sent"))
                continue

            if action["kind"] == "turn_on":
                response = smart_home.turn_on(action["goal"])
            elif action["kind"] == "turn_off":
                response = smart_home.turn_off(action["goal"])
            else:
                response = smart_home.activate_scene(action["goal"])

            if isinstance(response, dict) and response.get("error"):
                results.append(f"{action['kind']} {action['goal']}: {response['error']}")
                notices.notify(t("'{0}' failed", rule["name"]), str(response["error"]), kind="automation", level="important")
            elif isinstance(response, dict) and response.get("ambiguous"):
                results.append(f"{action['kind']} {action['goal']}: {t('several devices match')}")
                notices.notify(t("'{0}' failed", rule["name"]), t("Several devices match; be more specific."), kind="automation")
            else:
                results.append(f"{action['kind']} {action['goal']}")
                notices.notify(rule["name"], t("Done: {0} {1}.", action["kind"], action["goal"]), kind="automation", quiet=True)

        return "; ".join(results)

    def run_now(self, name) -> dict:
        """Run an automation by hand (to test it), without waiting for the trigger."""

        rules = self.rules()
        rule = self._search(rules, name)
        result = self._execute(rule)

        rule["runs"] = rule.get("runs", 0) + 1
        rule["last_run"] = datetime.now().isoformat(timespec="seconds")
        rule["last_result"] = result
        self._save_run_state(rules)

        return {"name": rule["name"], "result": result}
