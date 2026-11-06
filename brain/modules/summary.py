"""
Proactive daily summary: every morning BRAIN gathers what matters for the day
(agenda, reminders, shopping, energy, alerts, warranties and weight) and sends
it as a notice. It can also be requested at any time.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.notices import Notices, _hour_to_minutes
from brain.utils.dates import long_date

DEFAULT_CONFIG = {"active": True, "hour": "08:30", "last_sent": None}

# After this hour the late "morning" summary is no longer sent.
CUTOFF_HOUR = "21:00"


def _items(items: List[str], maximum=6) -> str:
    if len(items) <= maximum:
        return ", ".join(items)

    return ", ".join(items[:maximum]) + " " + t("and {0} more", len(items) - maximum)


class Summary(ModuleBase):
    name = "summary"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def config(self) -> dict:
        saved = self.data.read_module(self.name)

        return {**DEFAULT_CONFIG, **{k: v for k, v in saved.items() if k in DEFAULT_CONFIG}}

    def configure(self, active=None, hour=None) -> dict:
        config = self.config()

        if active is not None:
            config["active"] = bool(active)

        if hour not in (None, ""):
            try:
                _hour_to_minutes(hour)
            except ValueError:
                raise ValueError(t("The summary time must be HH:MM, for example 08:30.")) from None

            hours, minutes = str(hour).replace(".", ":").split(":")
            config["hour"] = f"{int(hours):02d}:{int(minutes):02d}"

        self.data.save_module(self.name, config)

        return {"active": config["active"], "hour": config["hour"]}

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def compose(self, today: Optional[date] = None) -> dict:
        """Return {"title", "text", "sections"} with what matters for the day."""

        from brain.core.scheduler import poll
        from brain.modules.calendar import Calendar
        from brain.modules.shopping import Shopping
        from brain.modules.appliances import Appliances
        from brain.modules.health import Health

        today = today or date.today()
        sections = {}

        # Agenda for today and tomorrow + tasks
        agenda = Calendar().agenda(1)
        tomorrow_text = (today + timedelta(days=1)).isoformat()
        events_today = [e for e in agenda["events"] if e.get("date") == today.isoformat()]
        events_tomorrow = [e for e in agenda["events"] if e.get("date") == tomorrow_text]

        def event(e):
            return f"{e['hour']} {e['title']}" if e.get("hour") else e["title"]

        lines = []

        if events_today:
            lines.append(t("Today: {0}.", _items([event(e) for e in events_today])))

        if events_tomorrow:
            lines.append(t("Tomorrow: {0}.", _items([event(e) for e in events_tomorrow])))

        if agenda["pending_tasks"]:
            lines.append(t("Pending tasks: {0}.", _items([task["title"] for task in agenda["pending_tasks"]])))

        sections["agenda"] = lines or [t("You have nothing on the agenda for today or tomorrow.")]

        # Today's reminders
        reminders = [r for r in Notices().reminders() if r["due"].startswith(today.isoformat())]

        if reminders:
            sections["reminders"] = [
                t("Today's reminders: {0}.", _items([f"{r['due'][11:16]} {r['message']}" for r in reminders]))
            ]

        # Shopping list
        shopping = Shopping().items()

        if shopping:
            sections["shopping"] = [t("Shopping list ({0}): {1}.", len(shopping), _items([i["product"] for i in shopping]))]

        # Yesterday's energy
        yesterday = (today - timedelta(days=1)).isoformat()
        production = [r for r in self._production() if r["date"] == yesterday]

        if production:
            sections["energy"] = [t("Yesterday the panels produced {0} kWh.", f"{production[0]['production']:g}")]

        # Active Home Assistant alerts
        if poll.alerts:
            sections["alerts"] = [
                t("ATTENTION, sensors in alert: {0}.", _items([a["name"] for a in poll.alerts]))
            ]

        # Warranties
        warranties = Appliances().expiring_warranties(30, today)

        if warranties:
            sections["warranties"] = [
                t("Warranties expiring soon: {0}.", _items([f"{a['name']} ({a['warranty_until']})" for a in warranties]))
            ]

        # Weight
        history = Health().weight_history()

        if history:
            last = history[-1]
            phrase = t("Last weight: {0} kg ({1}).", f"{last['weight']:g}", last["date"])
            week = [r for r in history if r["date"] <= (today - timedelta(days=7)).isoformat()]

            if week:
                difference = round(last["weight"] - week[-1]["weight"], 1)

                if difference:
                    phrase += " " + t("{0} kg compared with a week ago.", f"{difference:+g}")

            sections["weight"] = [phrase]

        title = t("Good morning: {0}", long_date(today))
        text = "\n".join(line for lines in sections.values() for line in lines)

        return {"title": title, "text": text, "sections": sections}

    @staticmethod
    def _production():
        from brain.modules.energy import Energy

        return Energy().db.production(3)

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    def send(self) -> dict:
        """Compose the summary and send it as a notice (with the 'summary' sound)."""

        summary = self.compose()
        has_alert = "alerts" in summary["sections"]

        Notices().notify(summary["title"], summary["text"], kind="summary", level="important" if has_alert else "info")

        config = self.config()
        config["last_sent"] = date.today().isoformat()
        self.data.save_module(self.name, config)

        return summary

    def send_if_due(self, now: Optional[datetime] = None) -> Optional[dict]:
        """Send it once a day, at its hour (or at start-up if BRAIN was off at that hour)."""

        now = now or datetime.now()
        config = self.config()

        if not config["active"] or config["last_sent"] == now.date().isoformat():
            return None

        minute = now.hour * 60 + now.minute

        if not (_hour_to_minutes(config["hour"]) <= minute < _hour_to_minutes(CUTOFF_HOUR)):
            return None

        return self.send()
