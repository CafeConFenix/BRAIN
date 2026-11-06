"""
BRAIN's background task scheduler (standard library only).

A single daemon thread runs periodic tasks. Any exception from a task
is caught and recorded in its status: it never stops the thread or the
application. Being a daemon, it does not prevent BRAIN from closing.
"""

import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from brain.core.config import Config
from brain.i18n import t

ENERGY_HISTORY_DAYS = 365

# Home Assistant sensor device classes that warn of hazards.
CRITICAL_CLASSES = ("smoke", "gas", "carbon_monoxide", "moisture", "safety", "heat", "problem")


class Task:
    """A periodic task and its status."""

    def __init__(self, name: str, function: Callable, interval: float, initial_delay: float = 0.0):
        self.name = name
        self.function = function
        self.interval = max(0.01, float(interval))
        self.next_due = time.monotonic() + max(0.0, float(initial_delay))
        self.active = True
        self.runs = 0
        self.errors = 0
        self.last_run: Optional[str] = None
        self.last_result = None
        self.last_error: Optional[str] = None

    def state(self) -> dict:
        return {
            "name": self.name,
            "every_seconds": self.interval,
            "active": self.active,
            "runs": self.runs,
            "errors": self.errors,
            "last_run": self.last_run,
            "last_error": self.last_error,
        }


class Scheduler:
    """Runs periodic tasks on a separate thread."""

    def __init__(self, thread_name: str = "brain-scheduler"):  # noqa: D107
        self._tasks: Dict[str, Task] = {}
        self._block_state = threading.RLock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thread_name = thread_name
        self.alerts: List[dict] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        function: Callable,
        seconds: Optional[float] = None,
        hours: Optional[float] = None,
        initial_delay: float = 0.0,
    ) -> Task:
        """
        Registers (or replaces) a periodic task. The interval is given in
        `seconds` and/or `hours` (they add up). `initial_delay` is the
        seconds until the first run.
        """

        interval = float(seconds or 0) + float(hours or 0) * 3600

        if interval <= 0:
            raise ValueError(t("The interval must be greater than zero (seconds or hours)."))

        task = Task(name, function, interval, initial_delay)

        with self._block_state:
            self._tasks[name] = task

        self._wake.set()

        return task

    def remove(self, name: str) -> bool:
        with self._block_state:
            return self._tasks.pop(name, None) is not None

    def state(self) -> List[dict]:
        with self._block_state:
            return [task.state() for task in self._tasks.values()]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @property
    def active(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Starts the thread (does nothing if it is already running). Does not block."""

        if self.active:
            return

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name=self._thread_name, daemon=True)
        self._thread.start()

    def stop(self, wait: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()

        if self._thread is not None:
            self._thread.join(timeout=wait)

    def run_now(self, name: str) -> dict:
        """Runs a task right now (on the calling thread) with the same error protection."""

        with self._block_state:
            task = self._tasks.get(name)

        if task is None:
            raise KeyError(t("Task '{0}' does not exist.", name))

        self._execute(task)

        return task.state()

    def _execute(self, task: Task) -> None:
        try:
            task.last_result = task.function()
            task.last_error = None
        except Exception as error:  # a task must never bring down the thread
            task.errors += 1
            task.last_error = f"{type(error).__name__}: {error}"

            if getattr(Config, "DEBUG", False):
                traceback.print_exc()
        finally:
            task.runs += 1
            task.last_run = datetime.now().isoformat(timespec="seconds")
            task.next_due = time.monotonic() + task.interval

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                with self._block_state:
                    tasks = list(self._tasks.values())

                now = time.monotonic()
                wait = 30.0

                for task in tasks:
                    if self._stop.is_set():
                        return

                    if not task.active:
                        continue

                    if task.next_due <= now:
                        self._execute(task)

                    wait = min(wait, max(0.05, task.next_due - time.monotonic()))

                self._wake.clear()
                self._wake.wait(timeout=wait)

            except Exception:  # last line of defense: the loop keeps going no matter what
                self._stop.wait(1.0)


# ----------------------------------------------------------------------
# Default tasks
# ----------------------------------------------------------------------


def daily_backup() -> str:
    """Creates a backup if the last one is more than 20 hours old."""

    from brain.modules.system import System

    backup = System().backup_if_due(hours=20)

    return t("backup created: {0}", backup["file"]) if backup else t("there was already a recent backup")


class HomeAssistantPoller:
    """
    Periodic Home Assistant poll (if configured): saves the energy
    reading to SQLite and watches the critical sensors (smoke, gas,
    water leak...). It is a callable so it can be used as a task.
    """

    def __init__(self):
        self.alerts: List[dict] = []
        self.last_check: Optional[str] = None
        self._notified: set = set()  # alerts already notified while they stay active

    def __call__(self) -> str:
        from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, read_config

        url, token = read_config()
        ha = HomeAssistant(url, token, timeout=8)

        if not ha.configured:
            self.alerts = []
            return t("Home Assistant is not configured")

        try:
            states = ha.states()
        except HomeAssistantError as error:
            raise RuntimeError(t("Home Assistant is not responding: {0}", error))

        alerts = []

        for state in states:
            entity = state.get("entity_id", "")
            attributes = state.get("attributes") or {}

            if entity.startswith("binary_sensor.") and attributes.get("device_class") in CRITICAL_CLASSES:
                if state.get("state") == "on":
                    alerts.append(
                        {
                            "entity": entity,
                            "name": attributes.get("friendly_name", entity),
                            "kind": attributes.get("device_class"),
                            "since": state.get("last_changed"),
                        }
                    )

        self.alerts = alerts
        self.last_check = datetime.now().isoformat(timespec="seconds")

        self._notify_new_alerts(alerts)

        from brain.modules.energy import Energy
        from brain.tools.builtin.energy import realtime

        energy = Energy()
        saved = energy.record_reading(realtime.read())

        # Maintenance: do not let the history grow without limit.
        limit = (datetime.now() - timedelta(days=ENERGY_HISTORY_DAYS)).isoformat(timespec="seconds")
        energy.db.purge_energy(limit)

        return t("{0} alerts, energy {1}", len(alerts), t("saved") if saved else t("no data"))

    def _notify_new_alerts(self, alerts: List[dict]) -> None:
        """Warns (with sound) of each new alert; if it clears and returns, it warns again."""

        from brain.modules.notices import Notices

        active = {a["entity"] for a in alerts}
        self._notified &= active

        for alert in alerts:
            if alert["entity"] in self._notified:
                continue

            self._notified.add(alert["entity"])
            label = ALERT_LABELS.get(alert.get("kind"), t("Alert"))
            Notices().notify(f"{label}: {alert['name']}", t("Check the house as soon as possible."), kind="alert", level="critical")


ALERT_LABELS = {
    "smoke": t("Smoke detected"),
    "gas": t("Gas detected"),
    "carbon_monoxide": t("Carbon monoxide"),
    "moisture": t("Water leak"),
    "safety": t("Safety alert"),
    "heat": t("Excessive heat"),
    "problem": t("Problem"),
}


def check_reminders() -> str:
    """Fires the reminders that are already due."""

    from brain.modules.notices import Notices

    return t("{0} reminders", Notices().check_reminders())


class NoticeEvents:
    """Warns of calendar events with a time, MINUTES_BEFORE they start."""

    MINUTES_BEFORE = 30

    def __init__(self):
        self._notified: set = set()

    def __call__(self) -> str:
        from brain.modules.notices import Notices
        from brain.modules.calendar import Calendar

        now = datetime.now()
        today = now.date().isoformat()
        sent = 0

        for event in Calendar().get_section("events"):
            if event.get("date") != today or not event.get("hour"):
                continue

            key = (event["date"], event["hour"], event.get("title"))

            if key in self._notified:
                continue

            try:
                start = datetime.strptime(f"{event['date']} {event['hour']}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            missing = (start - now).total_seconds() / 60

            if 0 <= missing <= self.MINUTES_BEFORE:
                self._notified.add(key)
                Notices().notify(
                    event.get("title", t("Event")),
                    t("Starts at {0} (in {1} min).", event["hour"], round(missing)),
                    kind="reminder",
                    level="important",
                )
                sent += 1

        return t("{0} calendar reminders", sent)


class AutomationEngine:
    """Evaluates automations (time, sensors and energy). Keeps state between checks."""

    def __init__(self):
        self._engine = None

    def __call__(self) -> str:
        if self._engine is None:
            from brain.modules.automations import Automations

            self._engine = Automations()

        done = self._engine.evaluate()

        return t("{0} run", len(done)) + (": " + "; ".join(done) if done else "")


def daily_summary() -> str:
    """Sends the morning summary (once a day, at its time)."""

    from brain.modules.summary import Summary

    return t("summary sent") if Summary().send_if_due() else t("nothing new")


def maintenance() -> str:
    """Daily cleanup of old notices."""

    from brain.modules.notices import Notices

    return t("{0} old notices deleted", Notices().purge(90))


def check_expiries() -> str:
    """Warns (once a day) of what expires soon."""

    from brain.modules.inventory import Inventory

    return t("expiry notice sent") if Inventory().warn_expiries() else t("nothing expiring")


def check_habits() -> str:
    """Reminds of the timed habits not yet done today."""

    from brain.modules.habits import Habits

    return t("{0} habit reminders", Habits().warn_pending())


def check_chores() -> str:
    """Warns of today's household chores (once a day)."""

    from brain.modules.chores import Chores

    return t("{0} household chores notified", Chores().warn_today())


scheduler = Scheduler()
poll = HomeAssistantPoller()


def register_default_tasks(plan: Scheduler) -> Scheduler:
    """Adds the daily backup and the Home Assistant poll."""

    plan.register("daily_backup", daily_backup, hours=24, initial_delay=60)
    plan.register("home_assistant_poll", poll, seconds=Config.POLL_SECONDS, initial_delay=15)
    plan.register("reminders", check_reminders, seconds=15, initial_delay=5)
    plan.register("event_reminders", NoticeEvents(), seconds=60, initial_delay=20)
    plan.register("automations", AutomationEngine(), seconds=30, initial_delay=10)
    plan.register("daily_summary", daily_summary, seconds=60, initial_delay=30)
    plan.register("maintenance", maintenance, hours=24, initial_delay=300)
    plan.register("expiries", check_expiries, seconds=1800, initial_delay=90)
    plan.register("habits", check_habits, seconds=60, initial_delay=45)
    plan.register("household_chores", check_chores, seconds=1800, initial_delay=120)

    return plan


def start_scheduler() -> Scheduler:
    """Starts the global scheduler with the default tasks (unless disabled)."""

    if Config.SCHEDULER and not scheduler.active:
        register_default_tasks(scheduler)
        scheduler.start()

    return scheduler
