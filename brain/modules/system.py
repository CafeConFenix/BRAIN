"""
BRAIN's backups.

Creates a ZIP with the whole contents of data/ (including the SQLite database,
copied in a consistent way), keeps only the last 5 and allows restoring one
after checking its integrity with a SHA-256 checksum manifest.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from brain.base.module import ModuleBase
from brain.core import logger
from brain.core.config import Config
from brain.core.database import FILENAME, Database
from brain.i18n import t
from brain.modules.inventory import normalize

BACKUPS_TO_KEEP = 5
BACKUP_FOLDER = "backups"
MANIFEST = "MANIFEST.json"
BACKUP_PATTERN = re.compile(r"^backup_\d{8}_\d{6}\.zip$")
SAFETY_PATTERN = re.compile(r"^pre_restore_\d{8}_\d{6}\.zip$")
OLD_SAFETY_PATTERN = re.compile(r"^prerestauracion_\d{8}_\d{6}\.zip$")

# Data folders that are not copied: the backups themselves (so they don't copy
# themselves) and the voice models (hundreds of MB that can be downloaded again).
EXCLUDED = (BACKUP_FOLDER, "voice", "voz", ".restoring", ".restaurando")
TEMP_SUFFIXES = (".tmp", ".corrupt")


class BackupError(ValueError):
    """Error with a message the user can understand."""


def _sha256(path):
    total_sum = hashlib.sha256()

    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            total_sum.update(block)

    return total_sum.hexdigest()


class System(ModuleBase):
    name = "system"

    @property
    def backup_folder(self) -> Path:
        return Path(Config.DATA) / BACKUP_FOLDER

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_backups(self):
        """Existing backups, most recent first."""

        folder = self.backup_folder

        if not folder.exists():
            return []

        backups = []

        for path in sorted(folder.iterdir(), reverse=True):
            if BACKUP_PATTERN.match(path.name):
                backups.append(
                    {
                        "name": path.name,
                        "date": datetime.strptime(path.name[7:22], "%Y%m%d_%H%M%S").isoformat(timespec="seconds"),
                        "size_kb": round(path.stat().st_size / 1024),
                    }
                )

        return backups

    def last_backup(self):
        backups = self.list_backups()

        return backups[0] if backups else None

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def _files_to_copy(self):
        base = Path(Config.DATA)

        if not base.exists():
            return []

        files = []

        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue

            relative = path.relative_to(base)

            if relative.parts[0] in EXCLUDED or relative.parts[0].startswith("."):
                continue

            if path.name.endswith(TEMP_SUFFIXES) or path.name.startswith(FILENAME):
                continue  # the database is added separately, already consistent

            files.append((path, relative.as_posix()))

        return files

    def _write_zip(self, destination, rotation_pattern=None):
        base = Path(Config.DATA)
        base.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=base, prefix=".backup_") as tmp_dir:
            files = self._files_to_copy()

            if (base / FILENAME).exists():
                db_backup = Path(tmp_dir) / FILENAME
                Database().copy_to(db_backup)
                files.append((db_backup, FILENAME))

            manifest = {
                "brain": Config.VERSION,
                "created": datetime.now().isoformat(timespec="seconds"),
                "files": {},
            }

            partial = destination.with_name(destination.name + ".partial")

            try:
                with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as z:
                    for path, name in files:
                        z.write(path, name)
                        manifest["files"][name] = {"sha256": _sha256(path), "bytes": path.stat().st_size}

                    z.writestr(MANIFEST, json.dumps(manifest, indent=2))

                os.replace(partial, destination)

            except BaseException:
                try:
                    partial.unlink()
                except OSError:
                    pass

                raise

        return len(files)

    def create_backup(self):
        """Creates backup_YYYYMMDD_HHMMSS.zip and applies the rotation."""

        now = datetime.now().replace(microsecond=0)
        folder = self.backup_folder

        # The name is always later than the last backup's (rotation sorts by
        # name), even if several are created within the same second.
        last = self.last_backup()

        if last:
            now = max(now, datetime.fromisoformat(last["date"]) + timedelta(seconds=1))

        destination = folder / f"backup_{now:%Y%m%d_%H%M%S}.zip"

        total = self._write_zip(destination)

        removed = self._rotate()
        extra = self.copy_to_destination(destination)

        return {
            "extra_destination": extra,
            "file": destination.name,
            "included_files": total,
            "size_kb": round(destination.stat().st_size / 1024),
            "deleted_backups": removed,
            "saved_backups": len(self.list_backups()),
        }

    # ------------------------------------------------------------------
    # Second destination (folder, USB, OneDrive...)
    # ------------------------------------------------------------------

    def extra_destination(self) -> str:
        value = self.data.read_module(self.name).get("extra_destination")

        return str(value) if value else ""

    def suggested_destinations(self) -> list:
        """Common places to keep a second copy: OneDrive, Dropbox, Google Drive and external drives."""

        candidates = []
        home = Path.home()

        for name in ("OneDrive", "Dropbox", "Google Drive", "iCloudDrive"):
            if (home / name).is_dir():
                candidates.append({"name": name, "path": str(home / name / "BRAIN-backups")})

        if os.name == "nt":
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                unit = Path(f"{letter}:\\")

                if unit.exists():
                    candidates.append({"name": t("Drive {0}: (USB or disk)", letter), "path": str(unit / "BRAIN-backups")})

        return candidates

    def configure_destination(self, path) -> dict:
        """Chooses (or, with an empty path, removes) the folder where a second automatic backup is kept."""

        data = self.data.read_module(self.name)

        if not str(path or "").strip():
            data.pop("extra_destination", None)
            self.data.save_module(self.name, data)

            return {"extra_destination": ""}

        folder = Path(str(path).strip().strip('"')).expanduser()

        try:
            folder.mkdir(parents=True, exist_ok=True)
            test = folder / ".brain_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink()
        except OSError as error:
            raise BackupError(t("I can't save to that folder ({0}). Choose another one or check that the disk is connected.", error.strerror or error)) from None

        data["extra_destination"] = str(folder)
        self.data.save_module(self.name, data)

        return {"extra_destination": str(folder)}

    def copy_to_destination(self, file):
        """Copies a newly made backup to the second destination. Never raises: returns the result."""

        folder = self.extra_destination()

        if not folder:
            return None

        try:
            destination = Path(folder)
            destination.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, destination / Path(file).name)
            backups = sorted(p for p in destination.iterdir() if BACKUP_PATTERN.match(p.name))

            for old in backups[: max(0, len(backups) - BACKUPS_TO_KEEP)]:
                try:
                    old.unlink()
                except OSError:
                    pass

            return {"ok": True, "folder": folder}
        except OSError as error:
            logger.error(f"Copy to the second destination: {error!r}")

            return {"ok": False, "folder": folder, "error": t("I could not copy to {0}. Is the disk connected?", folder)}

    def backups_at_destination(self) -> list:
        folder = self.extra_destination()

        if not folder or not Path(folder).is_dir():
            return []

        return [
            {"name": p.name, "date": datetime.strptime(p.name[7:22], "%Y%m%d_%H%M%S").isoformat(timespec="seconds"), "size_kb": round(p.stat().st_size / 1024)}
            for p in sorted(Path(folder).iterdir(), reverse=True)
            if BACKUP_PATTERN.match(p.name)
        ]

    def fetch_backup_from_destination(self, name) -> dict:
        """Guided restore from the second destination: validates it and brings it to the backup folder so it can be restored."""

        folder = self.extra_destination()
        name = Path(str(name or "")).name

        if not folder or not BACKUP_PATTERN.match(name) or not (Path(folder) / name).is_file():
            raise BackupError(t("That backup is not in the second destination."))

        self.validate_backup(Path(folder) / name)
        self.backup_folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(folder) / name, self.backup_folder / name)

        return {"fetched": name}

    def _rotate(self):
        backups = sorted(p for p in self.backup_folder.iterdir() if BACKUP_PATTERN.match(p.name))
        left_over = backups[: max(0, len(backups) - BACKUPS_TO_KEEP)]

        for path in left_over:
            try:
                path.unlink()
            except OSError:
                pass

        return [p.name for p in left_over]

    def backup_if_due(self, hours=20):
        """Creates a backup only if the last one is more than `hours` hours old."""

        last = self.last_backup()

        if last:
            age = datetime.now() - datetime.fromisoformat(last["date"])

            if age < timedelta(hours=hours):
                return None

        return self.create_backup()

    # ------------------------------------------------------------------
    # Validate and restore
    # ------------------------------------------------------------------

    def _resolve(self, name):
        """Turns whatever the user asks for into the path of an existing backup."""

        backups = self.list_backups()

        if not backups:
            raise BackupError(t("There are no backups. Create one first."))

        text = (name or "").strip()
        key = normalize(text)

        if not key or key in ("last", "latest", "recent", "ultima", "reciente", "la ultima"):
            return self.backup_folder / backups[0]["name"]

        text = Path(text).name  # never leave the backup folder

        if not text.endswith(".zip"):
            text += ".zip"

        if not BACKUP_PATTERN.match(text) or not (self.backup_folder / text).exists():
            available = ", ".join(c["name"] for c in backups)
            raise BackupError(t("The backup '{0}' does not exist. Available: {1}.", name, available))

        return self.backup_folder / text

    def validate_backup(self, path):
        """
        Checks a ZIP: format, CRC, safe paths and the manifest's SHA-256
        checksums. Returns the manifest or raises BackupError.
        """

        path = Path(path)

        if not zipfile.is_zipfile(path):
            raise BackupError(t("{0} is not a valid ZIP.", path.name))

        with zipfile.ZipFile(path) as z:
            bad = z.testzip()

            if bad:
                raise BackupError(t("{0} is damaged ({1} fails).", path.name, bad))

            names = set(z.namelist())

            if MANIFEST not in names:
                raise BackupError(t("{0} has no manifest: it is not a BRAIN backup.", path.name))

            for name in names:
                parts = Path(name).parts

                if name.startswith(("/", "\\")) or ".." in parts or (parts and ":" in parts[0]):
                    raise BackupError(t("{0} contains an unsafe path ({1}).", path.name, name))

            try:
                manifest = json.loads(z.read(MANIFEST).decode("utf-8"))
                expected = manifest["files"]
            except (ValueError, KeyError, TypeError):
                raise BackupError(t("The manifest of {0} is damaged.", path.name))

            if set(expected) != names - {MANIFEST}:
                raise BackupError(t("The contents of {0} do not match its manifest.", path.name))

            for name, info in expected.items():
                total_sum = hashlib.sha256(z.read(name)).hexdigest()

                if total_sum != info.get("sha256"):
                    raise BackupError(t("Integrity check failed for {0} in {1}.", name, path.name))

        return manifest

    def restore_backup_file(self, name=None):
        """
        Restores a backup (the latest one by default). First validates it and
        extracts it separately; before replacing anything it saves the current
        state to pre_restore_*.zip in case it needs to be undone.
        """

        path = self._resolve(name)
        manifest = self.validate_backup(path)

        base = Path(Config.DATA)
        preparation = base / ".restoring"

        shutil.rmtree(preparation, ignore_errors=True)
        preparation.mkdir(parents=True)

        try:
            with zipfile.ZipFile(path) as z:
                for file_name in manifest["files"]:
                    z.extract(file_name, preparation)

            safety = self.backup_folder / f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.zip"
            self._write_zip(safety)

            for old in sorted(self.backup_folder.glob("pre_restore_*.zip")) + sorted(self.backup_folder.glob("prerestauracion_*.zip")):
                if old != safety and (SAFETY_PATTERN.match(old.name) or OLD_SAFETY_PATTERN.match(old.name)):
                    old.unlink()

            try:
                self._replace_data(preparation, manifest)
            except Exception:
                self._replace_data_from_zip(safety)
                raise

        finally:
            shutil.rmtree(preparation, ignore_errors=True)

        return {
            "restored": path.name,
            "restored_files": len(manifest["files"]),
            "previous_backup": safety.name,
            "created_at": manifest.get("created") or manifest.get("creado"),
        }

    def _replace_data(self, origin, manifest):
        base = Path(Config.DATA)

        for path, relative in self._files_to_copy():
            path.unlink()

        (base / FILENAME).unlink(missing_ok=True)

        for relative in manifest["files"]:
            destination = base / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(origin / relative, destination)

    def _replace_data_from_zip(self, backup_zip):
        """Undoes a failed restore with the previous backup."""

        with tempfile.TemporaryDirectory(dir=Config.DATA, prefix=".undo_") as tmp_dir:
            manifest = self.validate_backup(backup_zip)

            with zipfile.ZipFile(backup_zip) as z:
                for name in manifest["files"]:
                    z.extract(name, tmp_dir)

            self._replace_data(Path(tmp_dir), manifest)
