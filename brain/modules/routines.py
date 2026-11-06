from datetime import date

from brain.base.module import ModuleBase
from brain.i18n import t
from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.calendar import Calendar
from brain.modules.smart_home import SmartHome

TYPES = ("leaving", "night")


class Routines(ModuleBase):
    """
    The "Leaving home" and "Good night" buttons: first what is on and what is
    pending is REVIEWED; only what the person confirms is turned off.
    """

    name = "routines"

    def __init__(self):
        super().__init__()
        self.smart_home = SmartHome()

    def review(self, kind="leaving") -> dict:
        if kind not in TYPES:
            raise ValueError(t("The routine must be 'leaving' or 'night'."))

        result = {"kind": kind, "connected": bool(self.smart_home.connected()), "on": [], "reminders": []}

        if result["connected"]:
            try:
                result["on"] = self.smart_home.on()["on"]
            except HomeAssistantError as error:
                result["error"] = str(error)

        calendar = Calendar()
        today = date.today().isoformat()

        if kind == "leaving":
            tasks = [task["title"] for task in calendar.pending_tasks() if task.get("date") in (None, "", today) or task.get("date", "") < today]
            result["reminders"] = tasks[:5]
        else:
            tomorrow = calendar.agenda(2)["events"]
            result["reminders"] = [f"{e['date']} {e.get('hour') or ''} {e['title']}".replace("  ", " ").strip() for e in tomorrow if e["date"] > today][:5]

        return result

    def turn_off(self, entities) -> dict:
        """Turn off the given entities (only those BRAIN can control). Returns what was turned off and what failed."""

        turned_off, failures = [], []

        for entity in list(entities or [])[:100]:
            try:
                self.smart_home.toggle(str(entity), False)
                turned_off.append(entity)
            except HomeAssistantError as error:
                failures.append({"entity": entity, "error": str(error)})

        return {"turned_off": turned_off, "failures": failures}
