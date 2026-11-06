from datetime import date as Date, timedelta

from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.inventory import normalize
from brain.utils.dates import today, valid_hour, validate_date


class Calendar(ModuleBase):
    """Events and pending tasks."""

    name = "calendar"

    def add_event(self, title, date=None, hour=None):
        event = {
            "title": str(title).strip(),
            "date": validate_date(date),
            "hour": valid_hour(hour),
        }

        self.add_record("events", event)

        return event

    def add_task(self, title, date=None):
        task = {
            "title": str(title).strip(),
            "date": validate_date(date, default_today=False),
            "done": False,
        }

        self.add_record("tasks", task)

        return task

    def complete_task(self, title):
        tasks = self.get_section("tasks")

        for task in tasks:
            if not task.get("done") and normalize(title) in normalize(task.get("title", "")):
                task["done"] = True
                task["completed"] = today()

                self.save_section("tasks", tasks)

                return task

        raise ValueError(t("I cannot find any pending task called '{0}'.", title))

    def pending_tasks(self):
        return [task for task in self.get_section("tasks") if not task.get("done")]

    def agenda(self, days=7):
        """Events of the next N days and pending tasks."""

        days = int(days)

        start = Date.today()
        end = start + timedelta(days=days)

        events = [e for e in self.get_section("events") if start.isoformat() <= e.get("date", "") <= end.isoformat()]

        events.sort(key=lambda e: (e.get("date", ""), e.get("hour") or ""))

        return {
            "since": start.isoformat(),
            "until": end.isoformat(),
            "events": events,
            "pending_tasks": self.pending_tasks(),
        }
