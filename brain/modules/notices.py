"""
BRAIN's notice center: notifications, sounds and reminders.

Notices are saved in SQLite (history) and delivered through two routes:
the web interface (which polls them and plays a sound in the browser) and
Windows' native notifications (with their own sound). Sounds are .wav,
.mp3 or .ogg files the user drops into data/sounds/.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from brain.base.module import ModuleBase
from brain.core import notifier
from brain.core.config import Config
from brain.core.database import Database
from brain.i18n import t
from brain.modules.inventory import normalize

TYPES = ("alert", "reminder", "summary", "automation", "energy", "info")
LEVELS = ("info", "important", "critical")
SOUND_EXTENSIONS = (".wav", ".mp3", ".ogg")

DEFAULT_CONFIG = {
    "mute": False,  # True: no sound or notifications shown (still saved)
    "native": True,  # Windows' own notifications and sound
    "do_not_disturb": {"since": "23:00", "until": "07:00"},  # only critical notices sound
    "sounds": {},  # kind -> file in data/sounds/
}


def _hour_to_minutes(text) -> int:
    hours, minutes = str(text).strip().replace(".", ":").split(":")
    hours, minutes = int(hours), int(minutes)

    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError

    return hours * 60 + minutes


class Notices(ModuleBase):
    name = "notices"

    def __init__(self):
        super().__init__()
        self.db = Database()

    # ------------------------------------------------------------------
    # Configuration and sounds
    # ------------------------------------------------------------------

    @property
    def sounds_folder(self) -> Path:
        return Path(Config.DATA) / "sounds"

    def config(self) -> dict:
        saved = self.data.read_module(self.name)

        config = {**DEFAULT_CONFIG, **{k: v for k, v in saved.items() if k in DEFAULT_CONFIG}}
        config["sounds"] = dict(config.get("sounds") or {})

        return config

    def _save_config(self, config: dict) -> None:
        self.data.save_module(self.name, config)

    def sound_files(self) -> List[str]:
        folder = self.sounds_folder

        if not folder.exists():
            return []

        return sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SOUND_EXTENSIONS)

    def list_sounds(self) -> dict:
        return {
            "folder": str(self.sounds_folder),
            "files": self.sound_files(),
            "assigned": self.config()["sounds"],
            "kinds": list(TYPES),
        }

    def _resolve_sound(self, file) -> str:
        key = normalize(file)
        files = self.sound_files()

        for name in files:
            if normalize(name) == key or normalize(Path(name).stem) == key:
                return name

        matches = [n for n in files if key in normalize(n)]

        if len(matches) == 1:
            return matches[0]

        if not files:
            raise ValueError(t("There are no sounds. Copy .wav, .mp3 or .ogg files into {0}.", self.sounds_folder))

        raise ValueError(t("I can't find the sound '{0}'. Available: {1}.", file, ", ".join(files)))

    def assign_sound(self, kind, file) -> dict:
        """Assigns a sound to a notice kind. An empty `file` or 'none' removes it."""

        kind = self._valid_type(kind)
        config = self.config()

        if not file or normalize(file) in ("none", "ninguno", "ninguna", "remove", "quitar", "default", "por defecto", "defecto"):
            config["sounds"].pop(kind, None)
            self._save_config(config)

            return {"kind": kind, "sound": None}

        name = self._resolve_sound(file)
        config["sounds"][kind] = name
        self._save_config(config)

        return {"kind": kind, "sound": name}

    MAX_SOUND = 3 * 1024 * 1024

    def save_sound(self, name, content: bytes) -> str:
        """Saves a sound uploaded by the user into data/sounds/ and returns its name."""

        base = Path(str(name or "")).name
        extension = Path(base).suffix.lower()

        if extension not in SOUND_EXTENSIONS:
            raise ValueError(t("Only .wav, .mp3 or .ogg sounds are accepted."))

        if not content or len(content) > self.MAX_SOUND:
            raise ValueError(t("The sound is empty or is over 3 MB."))

        clean = "".join(c if (c.isalnum() or c in " ._-") else "_" for c in Path(base).stem).strip(" .")[:60] or "sound"
        destination = self.sounds_folder / f"{clean}{extension}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

        return destination.name

    def delete_sound(self, name) -> None:
        path = self.sound_path(name)

        if path is None:
            raise ValueError(t("That sound does not exist."))

        path.unlink()
        config = self.config()
        config["sounds"] = {kind: n for kind, n in config["sounds"].items() if n != path.name}
        self._save_config(config)

    def sound_path(self, name) -> Optional[Path]:
        """Safe path to a sound in the folder (or None)."""

        if not name or Path(name).name != name:
            return None

        path = self.sounds_folder / name

        return path if path.is_file() and path.suffix.lower() in SOUND_EXTENSIONS else None

    def sound_of(self, kind) -> Optional[str]:
        name = self.config()["sounds"].get(kind)

        return name if self.sound_path(name) else None

    def configure(self, mute=None, native=None, dnd_from=None, dnd_until=None) -> dict:
        config = self.config()

        if mute is not None:
            config["mute"] = bool(mute)

        if native is not None:
            config["native"] = bool(native)

        if dnd_from is not None or dnd_until is not None:
            current = config.get("do_not_disturb") or {"since": "23:00", "until": "07:00"}
            since = dnd_from if dnd_from not in (None, "") else current["since"]
            until = dnd_until if dnd_until not in (None, "") else current["until"]

            if str(since).lower() in ("none", "ninguno", "no", "off") or str(until).lower() in ("none", "ninguno", "no", "off"):
                config["do_not_disturb"] = None
            else:
                try:
                    _hour_to_minutes(since)
                    _hour_to_minutes(until)
                except ValueError:
                    raise ValueError(t("The 'do not disturb' times must be HH:MM, for example 23:00.")) from None

                config["do_not_disturb"] = {"since": str(since), "until": str(until)}

        self._save_config(config)

        return {k: config[k] for k in ("mute", "native", "do_not_disturb")}

    def in_do_not_disturb(self, now: Optional[datetime] = None) -> bool:
        window = self.config().get("do_not_disturb")

        if not window:
            return False

        now = now or datetime.now()
        minute = now.hour * 60 + now.minute

        try:
            since, until = _hour_to_minutes(window["since"]), _hour_to_minutes(window["until"])
        except (ValueError, KeyError):
            return False

        if since <= until:
            return since <= minute < until

        return minute >= since or minute < until  # a window that crosses midnight

    # ------------------------------------------------------------------
    # Notices
    # ------------------------------------------------------------------

    @staticmethod
    def _valid_type(kind) -> str:
        key = normalize(kind)

        if key not in TYPES:
            raise ValueError(t("The notice kind '{0}' does not exist. Options: {1}.", kind, ", ".join(TYPES)))

        return key

    def notify(self, title, message="", kind="info", level=None, quiet=False) -> dict:
        """
        Creates a notice, saves it and delivers it (Windows notification and sound).
        Critical notices always sound, even during "do not disturb".
        With `quiet=True` it is only logged in the history, without sounding.
        """

        kind = self._valid_type(kind)

        if level is None:
            level = "critical" if kind == "alert" else "info"

        if level not in LEVELS:
            level = "info"

        title = str(title).strip() or "BRAIN"
        message = str(message or "").strip()

        now = datetime.now().isoformat(timespec="seconds")
        notice_id = self.db.create_notice(now, kind, title, message, level)

        config = self.config()
        critical = level == "critical"

        if not quiet and config["native"] and not config["mute"] and (critical or not self.in_do_not_disturb()):
            name = self.sound_of(kind)
            notifier.notify(title, message, self.sound_path(name) if name else None)

        return {"id": notice_id, "date": now, "kind": kind, "title": title, "message": message, "level": level}

    def items(self, unread_only=False, after=0, limit=50) -> List[dict]:
        notices = self.db.notices(unread_only, after, limit)

        for notice in notices:
            notice["sound"] = self.sound_of(notice["kind"])

        return notices

    def mark_read(self, ids=None) -> int:
        return self.db.mark_notices_read(ids)

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------

    def create_reminder(self, message, in_minutes=None, date_time=None) -> dict:
        """
        Schedules a reminder. Give `in_minutes` (from now) or
        `date_time` ("YYYY-MM-DD HH:MM" or just "HH:MM": today, or tomorrow if it already passed).
        """

        message = str(message or "").strip()

        if not message:
            raise ValueError(t("The reminder text is missing."))

        now = datetime.now().replace(microsecond=0)

        if in_minutes not in (None, "", 0):
            minutes = float(in_minutes)

            if minutes <= 0:
                raise ValueError(t("The minutes must be more than zero."))

            due = now + timedelta(minutes=minutes)
        elif date_time:
            due = self._parse_datetime(str(date_time), now)
        else:
            raise ValueError(t("Say when: in how many minutes, or the date and time."))

        due = due.replace(second=0) if date_time and not in_minutes else due

        identifier = self.db.create_reminder(due.isoformat(timespec="seconds"), message)

        return {"id": identifier, "message": message, "due": due.isoformat(timespec="minutes").replace("T", " ")}

    @staticmethod
    def _parse_datetime(text: str, now: datetime) -> datetime:
        text = text.strip().replace("T", " ")

        hour_only = re.fullmatch(r"(\d{1,2})[:.](\d{2})", text)

        if hour_only:
            due = now.replace(hour=int(hour_only.group(1)), minute=int(hour_only.group(2)), second=0)

            if due <= now:
                due += timedelta(days=1)

            return due

        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                due = datetime.strptime(text, fmt)
            except ValueError:
                continue

            if due <= now:
                raise ValueError(t("That date and time have already passed."))

            return due

        raise ValueError(t("I don't understand '{0}'. Use YYYY-MM-DD HH:MM, for example 2026-10-12 18:30.", text))

    def reminders(self) -> List[dict]:
        return self.db.pending_reminders()

    def delete_reminder(self, reminder_id) -> bool:
        return bool(self.db.delete_reminder(reminder_id))

    def check_reminders(self) -> int:
        """Fires the reminders that are now due. Returns how many."""

        expired = self.db.take_due_reminders(datetime.now().isoformat(timespec="seconds"))

        for r in expired:
            self.notify(t("Reminder"), r["message"], kind="reminder", level="important")

        return len(expired)

    def purge(self, days=90) -> int:
        limit = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

        return self.db.purge_notices(limit)
