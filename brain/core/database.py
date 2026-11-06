"""
BRAIN's SQLite storage (standard library only).

Saves, in data/brain.db, the records that keep growing without limit:
weight, sensor readings, daily solar production and real-time energy
readings. Small data (settings, inventory, shopping list, memory,
calendar) stays in JSON.

Each operation opens its own connection, uses `with sqlite3.connect(...)`
(automatic commit if all goes well, rollback on error) and closes it when
done, so Windows doesn't leave the file locked.
"""

import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from brain.core import migrate
from brain.core.config import Config
from brain.i18n import t

FILENAME = "brain.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS weight (
    date TEXT PRIMARY KEY,
    weight  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sensors (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    kind      TEXT NOT NULL,
    value     TEXT,
    location TEXT,
    date     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensors_type_date ON sensors (kind, date);
CREATE INDEX IF NOT EXISTS idx_sensors_date ON sensors (date);

CREATE TABLE IF NOT EXISTS production_solar (
    date TEXT PRIMARY KEY,
    kwh   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS energy_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    production_w REAL,
    consumption_w    REAL,
    grid_w        REAL,
    battery_pct  REAL
);
CREATE INDEX IF NOT EXISTS idx_energy_date ON energy_records (date);

CREATE TABLE IF NOT EXISTS notices (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date   TEXT NOT NULL,
    kind    TEXT NOT NULL,
    title  TEXT NOT NULL,
    message TEXT,
    level   TEXT NOT NULL DEFAULT 'info',
    read   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notices_date ON notices (date);
CREATE INDEX IF NOT EXISTS idx_notices_read ON notices (read, id);

CREATE TABLE IF NOT EXISTS reminders (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    due  TEXT NOT NULL,
    message TEXT NOT NULL,
    done   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_reminders_when ON reminders (done, due);

CREATE TABLE IF NOT EXISTS measurements (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date  TEXT NOT NULL,
    name TEXT NOT NULL,
    value  REAL NOT NULL,
    unit TEXT
);
CREATE INDEX IF NOT EXISTS idx_measurements_name_date ON measurements (name, date);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

_initialized = set()
_lock = threading.Lock()


class Database:
    """Access to data/brain.db. The path is computed on every use (Config.DATA)."""

    @property
    def path(self) -> Path:
        return Path(Config.DATA) / FILENAME

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _open(self):
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(str(path), timeout=15)
        connection.row_factory = sqlite3.Row

        return connection

    def connect(self):
        """
        Returns a connection ready to use with:

            with closing(db.connect()) as connection, connection:
                connection.execute(...)
        """

        migrate.run(Config.DATA)
        self._prepare()

        return self._open()

    def _prepare(self):
        key = str(self.path)

        if key in _initialized and self.path.exists():
            return

        with _lock:
            if key in _initialized and self.path.exists():
                return

            with closing(self._open()) as connection, connection:
                connection.executescript(SCHEMA)

            _initialized.add(key)

            try:
                self._migrate_json()
            except Exception as error:  # a failed migration must never stop BRAIN from starting
                print(t("[BRAIN] Could not migrate the old data to SQLite: {0}", error))

    # ------------------------------------------------------------------
    # Migration from the old JSON files
    # ------------------------------------------------------------------

    def _migrate_json(self):
        """
        Moves into SQLite whatever was in the JSON files of earlier versions
        (health.weight, sensors.*, energy.solar_panels) in ONE transaction.
        Before touching anything it leaves a "<file>.json.premigration" copy.
        """

        with closing(self._open()) as connection:
            done = connection.execute("SELECT value FROM meta WHERE key = 'migrated_json'").fetchone()

        if done:
            return

        base = Path(Config.DATA)

        sources = {
            "health": base / "health" / "health.json",
            "sensors": base / "sensors" / "sensors.json",
            "energy": base / "energy" / "energy.json",
        }

        content = {}

        for module, path in sources.items():
            if not path.exists():
                continue

            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue

            if isinstance(data, dict):
                content[module] = data

        with closing(self._open()) as connection, connection:
            for r in content.get("health", {}).get("weight", []) or []:
                try:
                    connection.execute(
                        "INSERT OR REPLACE INTO weight (date, weight) VALUES (?, ?)",
                        (str(r["date"]), float(r["weight"])),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            for kind, readings in content.get("sensors", {}).items():
                if not isinstance(readings, list):
                    continue

                for r in readings:
                    try:
                        connection.execute(
                            "INSERT INTO sensors (kind, value, location, date) VALUES (?, ?, ?, ?)",
                            (kind, json.dumps(r.get("value")), r.get("location"), str(r.get("date", ""))),
                        )
                    except (AttributeError, TypeError):
                        continue

            for r in content.get("energy", {}).get("solar_panels", []) or []:
                try:
                    connection.execute(
                        "INSERT OR REPLACE INTO production_solar (date, kwh) VALUES (?, ?)",
                        (str(r["date"]), float(r["production"])),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            connection.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('migrated_json', '1')")

        # With the transaction committed, the migrated sections are removed
        # from the JSON files (keeping a backup copy of the original).
        sections = {
            "health": ("weight",),
            "sensors": None,  # the whole file is readings
            "energy": ("solar_panels",),
        }

        for module, keys in sections.items():
            path = sources[module]

            if module not in content:
                continue

            try:
                os.replace(path, path.with_name(path.name + ".premigration"))

                if keys is not None:
                    remaining = {k: v for k, v in content[module].items() if k not in keys}

                    if remaining:
                        with open(path, "w", encoding="utf-8") as f:
                            json.dump(remaining, f, indent=4, ensure_ascii=False)
            except OSError:
                continue

    # ------------------------------------------------------------------
    # Peso
    # ------------------------------------------------------------------

    def save_weight(self, date, weight):
        with closing(self.connect()) as connection, connection:
            connection.execute("INSERT OR REPLACE INTO weight (date, weight) VALUES (?, ?)", (date, float(weight)))

    def weight_history(self, limit=None):
        query = "SELECT date, weight FROM weight ORDER BY date"

        with closing(self.connect()) as connection:
            rows = connection.execute(query).fetchall()

        records = [{"weight": f["weight"], "date": f["date"]} for f in rows]

        if limit:
            records = records[-int(limit) :]

        return records

    def exact_weight(self, date):
        with closing(self.connect()) as connection:
            row = connection.execute("SELECT date, weight FROM weight WHERE date = ?", (date,)).fetchone()

        return {"weight": row["weight"], "date": row["date"]} if row else None

    def previous_weight(self, date):
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT date, weight FROM weight WHERE date < ? ORDER BY date DESC LIMIT 1", (date,)
            ).fetchone()

        return {"weight": row["weight"], "date": row["date"]} if row else None

    # ------------------------------------------------------------------
    # Sensores
    # ------------------------------------------------------------------

    def save_sensor_reading(self, kind, value, location, date):
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "INSERT INTO sensors (kind, value, location, date) VALUES (?, ?, ?, ?)",
                (kind, json.dumps(value), location, date),
            )

    def sensor_readings(self, kind, limit=None):
        """A sensor's readings, oldest to most recent."""

        query = "SELECT value, location, date FROM sensors WHERE kind = ? ORDER BY date DESC, id DESC"
        parameters = [kind]

        if limit:
            query += " LIMIT ?"
            parameters.append(int(limit))

        with closing(self.connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()

        readings = [
            {"value": _from_json(f["value"]), "location": f["location"], "date": f["date"]} for f in rows
        ]

        return readings[::-1]

    # ------------------------------------------------------------------
    # Daily solar production
    # ------------------------------------------------------------------

    def save_production(self, date, kwh):
        with closing(self.connect()) as connection, connection:
            connection.execute("INSERT OR REPLACE INTO production_solar (date, kwh) VALUES (?, ?)", (date, float(kwh)))

    def production(self, limit=7):
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT date, kwh FROM production_solar ORDER BY date DESC LIMIT ?", (int(limit),)
            ).fetchall()

        return [{"production": f["kwh"], "date": f["date"]} for f in rows][::-1]

    # ------------------------------------------------------------------
    # Real-time energy (reading history)
    # ------------------------------------------------------------------

    def save_energy_reading(self, date, production_w=None, consumption_w=None, grid_w=None, battery_pct=None):
        with closing(self.connect()) as connection, connection:
            connection.execute(
                "INSERT INTO energy_records (date, production_w, consumption_w, grid_w, battery_pct) "
                "VALUES (?, ?, ?, ?, ?)",
                (date, production_w, consumption_w, grid_w, battery_pct),
            )

    def energy_readings(self, since=None, limit=500):
        query = "SELECT date, production_w, consumption_w, grid_w, battery_pct FROM energy_records"
        parameters = []

        if since:
            query += " WHERE date >= ?"
            parameters.append(since)

        query += " ORDER BY date DESC LIMIT ?"
        parameters.append(int(limit))

        with closing(self.connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [dict(f) for f in rows][::-1]

    def purge_energy(self, before):
        """Deletes energy readings before an ISO date. Returns how many."""

        with closing(self.connect()) as connection, connection:
            return connection.execute("DELETE FROM energy_records WHERE date < ?", (before,)).rowcount

    # ------------------------------------------------------------------
    # Avisos y recordatorios
    # ------------------------------------------------------------------

    def create_notice(self, date, kind, title, message="", level="info"):
        with closing(self.connect()) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO notices (date, kind, title, message, level) VALUES (?, ?, ?, ?, ?)",
                (date, kind, title, message, level),
            )

            return cursor.lastrowid

    def notices(self, unread_only=False, after=0, limit=50):
        """Notices oldest to most recent (the last `limit`)."""

        query = "SELECT id, date, kind, title, message, level, read FROM notices WHERE id > ?"
        parameters = [int(after)]

        if unread_only:
            query += " AND read = 0"

        query += " ORDER BY id DESC LIMIT ?"
        parameters.append(int(limit))

        with closing(self.connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [{**dict(f), "read": bool(f["read"])} for f in rows][::-1]

    def mark_notices_read(self, ids=None):
        with closing(self.connect()) as connection, connection:
            if ids:
                placeholders = ",".join("?" for _ in ids)
                return connection.execute(f"UPDATE notices SET read = 1 WHERE read = 0 AND id IN ({placeholders})", list(ids)).rowcount

            return connection.execute("UPDATE notices SET read = 1 WHERE read = 0").rowcount

    def purge_notices(self, before):
        with closing(self.connect()) as connection, connection:
            return connection.execute("DELETE FROM notices WHERE date < ?", (before,)).rowcount

    def create_reminder(self, due, message):
        with closing(self.connect()) as connection, connection:
            return connection.execute("INSERT INTO reminders (due, message) VALUES (?, ?)", (due, message)).lastrowid

    def pending_reminders(self):
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT id, due, message FROM reminders WHERE done = 0 ORDER BY due"
            ).fetchall()

        return [dict(f) for f in rows]

    def take_due_reminders(self, now):
        """Returns the due reminders and marks them as done (in one transaction)."""

        with closing(self.connect()) as connection, connection:
            rows = connection.execute(
                "SELECT id, due, message FROM reminders WHERE done = 0 AND due <= ? ORDER BY due", (now,)
            ).fetchall()

            for f in rows:
                connection.execute("UPDATE reminders SET done = 1 WHERE id = ?", (f["id"],))

        return [dict(f) for f in rows]

    def delete_reminder(self, reminder_id):
        with closing(self.connect()) as connection, connection:
            return connection.execute("DELETE FROM reminders WHERE id = ? AND done = 0", (int(reminder_id),)).rowcount

    # ------------------------------------------------------------------
    # Body measurements (fat, BMI, water... besides weight)
    # ------------------------------------------------------------------

    def save_measurement(self, date, name, value, unit=None):
        with closing(self.connect()) as connection, connection:
            connection.execute("DELETE FROM measurements WHERE date = ? AND name = ?", (date, name))
            connection.execute(
                "INSERT INTO measurements (date, name, value, unit) VALUES (?, ?, ?, ?)", (date, name, float(value), unit)
            )

    def measurements(self, name=None, limit=60):
        query = "SELECT date, name, value, unit FROM measurements"
        parameters = []

        if name:
            query += " WHERE name = ?"
            parameters.append(name)

        query += " ORDER BY date DESC, id DESC LIMIT ?"
        parameters.append(int(limit))

        with closing(self.connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [dict(f) for f in rows][::-1]

    # ------------------------------------------------------------------
    # Energy analysis
    # ------------------------------------------------------------------

    def energy_by_hour(self, since):
        """Average per hour of the day (0-23) of production, consumption and grid since an ISO date."""

        query = (
            "SELECT CAST(substr(date, 12, 2) AS INTEGER) AS hour, "
            "AVG(production_w) AS production, AVG(consumption_w) AS consumption, AVG(grid_w) AS grid, COUNT(*) AS n "
            "FROM energy_records WHERE date >= ? GROUP BY hour ORDER BY hour"
        )

        with closing(self.connect()) as connection:
            rows = connection.execute(query, (since,)).fetchall()

        return [dict(f) for f in rows]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def copy_to(self, destination):
        """Consistent copy of the database (SQLite backup API)."""

        self._prepare()

        with closing(self._open()) as source, closing(sqlite3.connect(str(destination))) as backup:
            source.backup(backup)

    def indices(self):
        with closing(self.connect()) as connection:
            rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'").fetchall()

        return sorted(f["name"] for f in rows)


def _from_json(text):
    if text is None:
        return None

    try:
        return json.loads(text)
    except ValueError:
        return text
