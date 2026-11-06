from datetime import date as Date, datetime, timedelta

from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.inventory import normalize
from brain.utils.dates import validate_date


def _hour(value) -> str:
    try:
        h, m = str(value).strip().replace(".", ":").split(":")
        h, m = int(h), int(m)
    except ValueError:
        raise ValueError(t("The time '{0}' is not valid. Use HH:MM, for example 21:30.", value)) from None

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(t("The time '{0}' is not valid.", value))

    return f"{h:02d}:{m:02d}"


class Habits(ModuleBase):
    """
    Daily habits with a goal and a streak: drinking water, taking a medicine,
    walking, reading... Every habit has a goal per day (for example 8 glasses)
    and the streak counts the consecutive days the goal was met.
    """

    name = "habits"

    # ------------------------------------------------------------------

    def _search(self, name):
        key = normalize(name)

        if not key:
            raise ValueError(t("The name of the habit is missing."))

        habits = self.get_section("habits")

        for habit in habits:
            if normalize(habit["name"]) == key:
                return habit

        # Approximate: "water" finds "drink water".
        similar = [h for h in habits if key in normalize(h["name"]) or normalize(h["name"]) in key]

        if len(similar) == 1:
            return similar[0]

        if len(similar) > 1:
            raise ValueError(t("Several habits match: {0}. Tell me which one.", ", ".join(h["name"] for h in similar)))

        raise ValueError(t("I have no habit '{0}'. Create it first.", name))

    def create(self, name, goal=1, unit="", hour="", person="") -> dict:
        name = str(name or "").strip()[:40]

        if not name:
            raise ValueError(t("The name of the habit is missing."))

        try:
            goal = int(float(goal))
        except (TypeError, ValueError):
            raise ValueError(t("The daily goal must be a number.")) from None

        if not 1 <= goal <= 1000:
            raise ValueError(t("The daily goal must be between 1 and 1000."))

        habits = self.get_section("habits")
        existing = next((h for h in habits if normalize(h["name"]) == normalize(name)), None)

        if existing:
            existing["goal"] = goal
            existing["unit"] = str(unit or existing.get("unit", ""))[:20]

            if hour not in (None, ""):
                existing["hour"] = _hour(hour)

            if person:
                existing["person"] = str(person).strip()[:30]

            self.save_section("habits", habits)

            return existing

        habit = {"name": name, "goal": goal, "unit": str(unit or "")[:20], "created": Date.today().isoformat()}

        if hour not in (None, ""):
            habit["hour"] = _hour(hour)

        if person:
            habit["person"] = str(person).strip()[:30]

        habits.append(habit)
        self.save_section("habits", habits)

        return habit

    def log(self, name, quantity=1, date=None) -> dict:
        habit = self._search(name)

        try:
            quantity = int(float(quantity))
        except (TypeError, ValueError):
            raise ValueError(t("The quantity must be a number.")) from None

        if not -1000 <= quantity <= 1000 or quantity == 0:
            raise ValueError(t("The quantity must be non-zero and reasonable."))

        day = validate_date(date)
        records = self.get_section("records")
        records.append({"date": day, "habit": habit["name"], "quantity": quantity})
        self.save_section("records", records)

        return self._state_of(habit, records, Date.fromisoformat(day))

    def _totals(self, habit, records) -> dict:
        totals = {}

        for record in records:
            if record.get("habit") == habit["name"]:
                totals[record["date"]] = totals.get(record["date"], 0) + int(record.get("quantity", 0))

        return totals

    def _state_of(self, habit, records, day) -> dict:
        totals = self._totals(habit, records)
        total_today = max(0, totals.get(day.isoformat(), 0))
        goal = habit["goal"]

        # Streak: consecutive days meeting the goal. If today is not met yet, yesterday's streak is not broken.
        cursor = day if total_today >= goal else day - timedelta(days=1)
        streak = 0

        while totals.get(cursor.isoformat(), 0) >= goal:
            streak += 1
            cursor -= timedelta(days=1)

        return {
            "habit": habit["name"],
            "today": total_today,
            "goal": goal,
            "unit": habit.get("unit", ""),
            "hour": habit.get("hour", ""),
            "person": habit.get("person", ""),
            "met": total_today >= goal,
            "streak_days": streak,
        }

    def state(self, date=None, person=None) -> dict:
        day = Date.fromisoformat(validate_date(date))
        records = self.get_section("records")
        habits = self.get_section("habits")

        if person:
            key = normalize(person)
            habits = [h for h in habits if not h.get("person") or normalize(h["person"]) == key]

        items = [self._state_of(h, records, day) for h in habits]

        return {
            "date": day.isoformat(),
            "habits": items,
            "met": sum(1 for h in items if h["met"]),
            "total": len(items),
        }

    def delete(self, name) -> dict:
        habit = self._search(name)
        self.save_section("habits", [h for h in self.get_section("habits") if h["name"] != habit["name"]])
        self.save_section("records", [r for r in self.get_section("records") if r.get("habit") != habit["name"]])

        return habit

    def warn_pending(self, now=None) -> int:
        """Remind (once a day per habit) of timed habits whose hour has passed and are still not met."""

        now = now or datetime.now()
        today = now.date().isoformat()
        data = self.data.read_module(self.name)
        notified = {k: v for k, v in (data.get("_notified") or {}).items() if v == today}
        pending = [h for h in self.state(today)["habits"] if h["hour"] and h["hour"] <= now.strftime("%H:%M") and not h["met"] and h["habit"] not in notified]

        if not pending:
            return 0

        from brain.modules.notices import Notices

        notices = Notices()

        for h in pending:
            notified[h["habit"]] = today
            who = f" ({h['person']})" if h["person"] else ""
            progress = f"{h['today']} / {h['goal']} {h['unit']}".strip()
            notices.notify(t("Habit: {0}", h["habit"]) + who, t("Today you are at {0}.", progress), kind="reminder")

        data["_notified"] = notified
        self.data.save_module(self.name, data)

        return len(pending)
