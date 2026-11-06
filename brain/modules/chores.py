import re
from datetime import date as Date, timedelta

from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.inventory import normalize
from brain.utils.dates import validate_date


class Chores(ModuleBase):
    """
    Recurring household chores (taking out the trash, washing up, walking the dog...)
    with turns: every time someone does one, it is the next person's turn.
    """

    name = "chores"

    def _search(self, name, tasks):
        key = normalize(name)

        if not key:
            raise ValueError(t("The name of the chore is missing."))

        exact = [x for x in tasks if normalize(x["name"]) == key]
        similar = exact or [x for x in tasks if key in normalize(x["name"]) or normalize(x["name"]) in key]

        if len(similar) == 1:
            return similar[0]

        if len(similar) > 1:
            raise ValueError(t("Several chores match: {0}. Tell me which one.", ", ".join(task["name"] for task in similar)))

        raise ValueError(t("I have no chore '{0}'.", name))

    def create(self, name, people="", every_days=7, starts=None) -> dict:
        name = str(name or "").strip()[:50]

        if not name:
            raise ValueError(t("The name of the chore is missing."))

        if isinstance(people, str):
            people = [p.strip() for p in re.split(r"[,;]|\s+(?:and|y)\s+", people)]

        people = [str(p).strip()[:30] for p in people if str(p).strip()]

        try:
            every_days = int(float(every_days))
        except (TypeError, ValueError):
            raise ValueError(t("The number of days between repeats must be a number.")) from None

        if not 1 <= every_days <= 365:
            raise ValueError(t("The repeat interval must be between 1 and 365 days."))

        tasks = self.get_section("tasks")
        existing = next((x for x in tasks if normalize(x["name"]) == normalize(name)), None)
        if people:
            from brain.modules.profiles import Profiles

            for person in people:
                Profiles().add(person)

        task = existing if existing is not None else {"name": name, "turn": 0, "history": []}

        task.update({"people": people, "every_days": every_days, "next_due": validate_date(starts)})
        task["turn"] = task.get("turn", 0) % len(people) if people else 0

        if existing is None:
            tasks.append(task)

        self.save_section("tasks", tasks)

        return self._view(task)

    @staticmethod
    def _view(task, today=None) -> dict:
        today = today or Date.today()
        people = task.get("people") or []
        next_due = task.get("next_due") or today.isoformat()

        return {
            "name": task["name"],
            "turn_of": people[task.get("turn", 0) % len(people)] if people else "",
            "people": people,
            "every_days": task.get("every_days", 7),
            "next_due": next_due,
            "due_today": next_due <= today.isoformat(),
            "last": (task.get("history") or [{}])[-1] if task.get("history") else None,
        }

    def items(self) -> list:
        return sorted((self._view(x) for x in self.get_section("tasks")), key=lambda x: (x["next_due"], normalize(x["name"])))

    def done(self, name, who="", date=None) -> dict:
        """Record that it was done, pass the turn to the next person and schedule the next time."""

        tasks = self.get_section("tasks")
        task = self._search(name, tasks)
        people = task.get("people") or []
        day = Date.fromisoformat(validate_date(date))
        did = str(who or "").strip()

        if not did and people:
            did = people[task.get("turn", 0) % len(people)]

        if people:
            if did and normalize(did) in [normalize(p) for p in people]:
                index = [normalize(p) for p in people].index(normalize(did))
            else:
                index = task.get("turn", 0)

            task["turn"] = (index + 1) % len(people)

        task.setdefault("history", []).append({"date": day.isoformat(), "who": did})
        task["history"] = task["history"][-30:]
        task["next_due"] = (day + timedelta(days=task.get("every_days", 7))).isoformat()
        self.save_section("tasks", tasks)

        return self._view(task)

    def skip_turn(self, name) -> dict:
        tasks = self.get_section("tasks")
        task = self._search(name, tasks)
        people = task.get("people") or []

        if len(people) < 2:
            raise ValueError(t("That chore has no other people to pass the turn to."))

        task["turn"] = (task.get("turn", 0) + 1) % len(people)
        self.save_section("tasks", tasks)

        return self._view(task)

    def delete(self, name) -> dict:
        tasks = self.get_section("tasks")
        task = self._search(name, tasks)
        tasks.remove(task)
        self.save_section("tasks", tasks)

        return {"name": task["name"]}

    def todays(self, person="") -> list:
        items = [x for x in self.items() if x["due_today"]]

        if person:
            items = [x for x in items if not x["turn_of"] or normalize(x["turn_of"]) == normalize(person)]

        return items

    def warn_today(self) -> int:
        """One notice a day for every chore that is due (to whoever's turn it is)."""

        today = Date.today().isoformat()
        notified = [a for a in self.get_section("notified") if str(a).startswith(today)]
        sent = 0

        for task in self.todays():
            key = f"{today}|{task['name']}|{task['next_due']}"

            if key in notified:
                continue

            notified.append(key)
            sent += 1

            from brain.modules.notices import Notices

            who = t("It is {0}'s turn.", task["turn_of"]) if task["turn_of"] else t("It is due today.")
            Notices().notify(t("Household chore: {0}", task["name"]), who, kind="reminder")

        self.save_section("notified", notified)

        return sent
