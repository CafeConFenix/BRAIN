import json
import os
import tempfile
import time
from pathlib import Path

from brain.core import migrate
from brain.core.config import Config
from brain.i18n import t


def _retry(action, attempts=8, pause=0.05):
    """
    Retries a file operation if Windows locks it for a moment.

    On Windows, an antivirus, OneDrive or a simultaneous read can
    lock a file for a few milliseconds and raise a PermissionError
    that goes away on retry.
    """

    for attempt in range(attempts):
        try:
            return action()

        except PermissionError:
            if attempt == attempts - 1:
                raise

            time.sleep(pause * (attempt + 1))


class DataManager:
    """
    BRAIN's central persistence manager.

    No module should read or write files directly.

    - Writes are atomic: if the program closes mid-save, the previous
      file is not corrupted.
    - A damaged JSON file is set aside as ".corrupt" instead of
      crashing BRAIN.
    - Files with a BOM are accepted (Windows Notepad adds one).
    """

    def __init__(self):
        migrate.run(self.base)

    @property
    def base(self):
        return Path(Config.DATA)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _write(self, path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)

        descriptor, tmp_dir = tempfile.mkstemp(
            dir=path.parent,
            prefix=f"{path.stem}_",
            suffix=".tmp",
        )

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    indent=4,
                    ensure_ascii=False,
                )

            _retry(lambda: os.replace(tmp_dir, path))

        except BaseException:
            try:
                os.unlink(tmp_dir)
            except OSError:
                pass

            raise

    def _read(self, path: Path, default):
        if not path.exists():
            return default

        try:
            def read_file():
                with open(path, "r", encoding="utf-8-sig") as f:
                    return f.read()

            content = _retry(read_file)

            if not content.strip():
                return default

            return json.loads(content)

        except json.JSONDecodeError:
            backup = path.with_name(path.name + ".corrupt")

            try:
                os.replace(path, backup)
            except OSError:
                pass

            print(t("[BRAIN] The file {0} was damaged. A copy was saved as {1}.", path.name, backup.name))

            return default

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, category: str, file: str, data: dict):
        path = self.base / category / f"{file}.json"
        self._write(path, data)

    def read(self, category: str, file: str):
        path = self.base / category / f"{file}.json"
        return self._read(path, None)

    def exists(self, category: str, file: str):
        path = self.base / category / f"{file}.json"
        return path.exists()

    def remove(self, category: str, file: str):
        path = self.base / category / f"{file}.json"

        if path.exists():
            path.unlink()

    def read_module(self, module: str):
        path = self.base / module / f"{module}.json"

        data = self._read(path, {})

        if not isinstance(data, dict):
            return {}

        return data

    def save_module(self, module: str, data: dict):
        path = self.base / module / f"{module}.json"
        self._write(path, data)

    def add_record(
        self,
        module: str,
        section: str,
        record: dict,
    ):
        data = self.read_module(module)

        data.setdefault(section, [])
        data[section].append(record)

        self.save_module(module, data)
