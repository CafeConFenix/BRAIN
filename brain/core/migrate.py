"""
Brings the data of a BRAIN installation older than 2.0.0 to the current layout.

Version 2.0.0 renamed the data folder, the files, the JSON keys and the SQLite
tables from Spanish to English. ``run()`` converts an existing installation once
(it is safe to call again) after saving a copy of the small data files.
The old names live in ``brain/core/legacy/``.
"""

import importlib
import json
import os
import pkgutil
import shutil
import sqlite3
import time
import zipfile
from contextlib import closing
from pathlib import Path

from brain.core import legacy

MARKER = ".layout"
LAYOUT = 2

_done = set()


def _tables():
    """The legacy tables of every area merged into one."""

    merged = {"FOLDERS": {}, "FILES": {}, "KEYS": {}, "VALUES": {}, "RAW": set(), "SQL_TABLES": {}, "SQL_COLUMNS": {}, "SQL_VALUES": {}}

    for info in pkgutil.iter_modules(legacy.__path__):
        module = importlib.import_module(f"{legacy.__name__}.{info.name}")

        for name, table in merged.items():
            found = getattr(module, name, None)

            if not found:
                continue

            if isinstance(table, set):
                table.update(found)
            elif name in ("VALUES", "SQL_COLUMNS", "SQL_VALUES"):
                for key, value in found.items():
                    table.setdefault(key, {}).update(value)
            else:
                table.update(found)

    merged["FOLDERS"].update(merged.pop("FILES"))

    return merged


USER_FOLDERS = ("documentos", "documents", "sonidos", "sounds", "backups", "copias")


def _candidates(base: Path):
    """Files and folders at most two levels deep, never inside the folders that hold the user's own files."""

    for path in base.rglob("*"):
        parts = path.relative_to(base).parts

        if len(parts) <= 2 and (len(parts) == 1 or parts[0] not in USER_FOLDERS):
            yield path


def _rename_tree(base: Path, names: dict) -> None:
    """Rename the files and folders whose name (or stem) is an old name."""

    for path in sorted(_candidates(base), key=lambda p: len(p.parts), reverse=True):
        new = names.get(path.name)

        if new is None and path.is_file():
            stem = names.get(path.stem)
            new = stem + path.suffix if stem else None

        if new is None and ".corrupto" in path.name:
            new = path.name.replace(".corrupto", ".corrupt")

        if new is None or new == path.name:
            continue

        target = path.with_name(new)

        if target.exists():
            continue

        try:
            path.rename(target)
        except OSError:
            pass


def _convert(value, keys: dict, values: dict, raw: set):
    if isinstance(value, list):
        return [_convert(item, keys, values, raw) for item in value]

    if not isinstance(value, dict):
        return value

    result = {}

    for key, item in value.items():
        new = keys.get(key, key) if isinstance(key, str) else key

        if new in raw or key in raw:
            result[new] = item
            continue

        mapping = values.get(new)

        if mapping:
            if isinstance(item, str):
                item = mapping.get(item, item)
            elif isinstance(item, list):
                item = [mapping.get(x, x) if isinstance(x, str) else x for x in item]

        result[new] = _convert(item, keys, values, raw)

    return result


def _migrate_json(base: Path, tables: dict) -> None:
    for path in base.rglob("*.json"):
        parts = path.relative_to(base).parts

        if path.name == MARKER or parts[0] in USER_FOLDERS or path.name == "language.json":
            continue

        try:
            original = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue

        converted = _convert(original, tables["KEYS"], tables["VALUES"], tables["RAW"])

        if converted != original:
            try:
                path.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass


def _migrate_sqlite(database: Path, tables: dict) -> None:
    if not database.exists():
        return

    try:
        with closing(sqlite3.connect(str(database), timeout=15)) as con, con:
            existing = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

            for old, new in tables["SQL_TABLES"].items():
                if old in existing and new not in existing:
                    con.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')
                    existing.discard(old)
                    existing.add(new)

            for table, columns in tables["SQL_COLUMNS"].items():
                if table not in existing:
                    continue

                present = {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}

                for old, new in columns.items():
                    if old in present and new not in present:
                        con.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old}" TO "{new}"')

            for index in [row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'")]:
                con.execute(f'DROP INDEX IF EXISTS "{index}"')

            for (table, column), mapping in tables["SQL_VALUES"].items():
                if table not in existing:
                    continue

                for old, new in mapping.items():
                    con.execute(f'UPDATE "{table}" SET "{column}" = ? WHERE "{column}" = ?', (new, old))
    except sqlite3.Error:
        pass


def _save_copy(base: Path) -> None:
    """A zip with the JSON files and the database as they were, just in case."""

    folder = base / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"before_2.0.0_{time.strftime('%Y%m%d_%H%M%S')}.zip"

    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in base.rglob("*"):
                relative = path.relative_to(base)

                if path.is_file() and "backups" not in relative.parts and (path.suffix in (".json", ".md", ".db") or path.name == "brain.instancia"):
                    archive.write(path, str(relative))
    except OSError:
        pass


def _looks_old(base: Path, tables: dict) -> bool:
    """True if the folder has a file or folder with an old name, or a database with old tables."""

    old_names = {old for old, new in tables["FOLDERS"].items() if old != new}

    for path in _candidates(base):
        if path.name in old_names or path.stem in old_names or ".corrupto" in path.name:
            return True

    database = base / "brain.db"

    if database.exists():
        try:
            with closing(sqlite3.connect(str(database), timeout=15)) as con:
                existing = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

            return bool(existing & set(tables["SQL_TABLES"]))
        except sqlite3.Error:
            return False

    return False


def move_old_folder(project: Path, data: Path) -> None:
    """Version 1.x kept everything in ``datos``; 2.x uses ``data``."""

    old = project / "datos"

    if old.is_dir() and not data.exists() and data == project / "data":
        try:
            old.rename(data)
        except OSError:
            pass


def run(base) -> bool:
    """Convert the data folder ``base`` if it comes from an old version. True if something was converted."""

    base = Path(base)
    key = str(base)

    if key in _done:
        return False

    _done.add(key)

    if not base.is_dir() or (base / MARKER).exists():
        return False

    tables = _tables()

    if not _looks_old(base, tables):
        try:
            (base / MARKER).write_text(json.dumps({"layout": LAYOUT}), encoding="utf-8")
        except OSError:
            pass

        return False

    _save_copy(base)
    _rename_tree(base, tables["FOLDERS"])
    _migrate_json(base, tables)
    _migrate_sqlite(base / "brain.db", tables)

    try:
        (base / MARKER).write_text(json.dumps({"layout": LAYOUT}), encoding="utf-8")
    except OSError:
        pass

    return True
