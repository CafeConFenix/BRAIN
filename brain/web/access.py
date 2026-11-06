"""
Protected access to BRAIN from outside the computer (phone or another PC).

BRAIN's window on the computer itself comes in through 127.0.0.1 and does
not ask for a password. Any other entry point (for example, Tailscale's
private address, "name.tailXXXX.ts.net") requires a password and, once
entered, it is saved in a signed cookie that expires after 30 days.

Standard library only: PBKDF2 for the password and HMAC for the cookies.
"""

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Optional

from brain.core.config import Config
from brain.i18n import t

ITERATIONS = 200_000
MIN_PASSWORD = 8
SESSION_DURATION = 30 * 24 * 3600
COOKIE_NAME = "brain_session"

# Brake against guessing the password: after 5 failures in a row it locks for 60 s.
MAX_FAILURES = 5
LOCK_SECONDS = 60


def _without_port(host: str) -> str:
    host = (host or "").strip().lower()

    if host.startswith("["):  # IPv6
        return host.split("]")[0].lstrip("[")

    return host.rsplit(":", 1)[0] if ":" in host else host


class Access:
    def __init__(self, path: Optional[Path] = None):
        self._path = Path(path) if path else Path(Config.DATA) / "access.json"
        self._lock = threading.Lock()
        self._failures = 0
        self._blocked_until = 0.0

    # ----------------------------------------------------------
    # Storage
    # ----------------------------------------------------------

    def _read(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = self._path.with_suffix(".tmp")
        tmp_dir.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp_dir, self._path)

    @staticmethod
    def _derive(key: str, salt: bytes, iterations: int) -> str:
        return hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt, iterations).hex()

    # ----------------------------------------------------------
    # Password
    # ----------------------------------------------------------

    def configured(self) -> bool:
        data = self._read()
        return bool(data.get("hash") and data.get("salt") and data.get("secret"))

    def set_password(self, key: str) -> None:
        key = str(key or "")

        if len(key) < MIN_PASSWORD:
            raise ValueError(t("The password must be at least {0} characters long.", MIN_PASSWORD))

        salt = secrets.token_bytes(16)
        data = self._read()
        data.update(
            {
                "hash": self._derive(key, salt, ITERATIONS),
                "salt": salt.hex(),
                "iterations": ITERATIONS,
                # Changing the password invalidates every open session.
                "secret": secrets.token_hex(32),
            }
        )
        self._save(data)

    def verify_password(self, key: str) -> bool:
        with self._lock:
            if time.time() < self._blocked_until:
                return False

        data = self._read()

        if not self.configured():
            return False

        try:
            expected = self._derive(str(key or ""), bytes.fromhex(data["salt"]), int(data.get("iterations", ITERATIONS)))
        except (ValueError, TypeError):
            return False

        correct = hmac.compare_digest(expected, data["hash"])

        with self._lock:
            if correct:
                self._failures = 0
            else:
                self._failures += 1

                if self._failures >= MAX_FAILURES:
                    self._blocked_until = time.time() + LOCK_SECONDS
                    self._failures = 0

        return correct

    def lock_seconds(self) -> int:
        with self._lock:
            return max(0, int(self._blocked_until - time.time()))

    # ----------------------------------------------------------
    # Sessions (signed cookie)
    # ----------------------------------------------------------

    def create_session(self) -> str:
        secret = self._read().get("secret")

        if not secret:
            raise ValueError(t("No password is configured."))

        expires = int(time.time()) + SESSION_DURATION
        body = f"{expires}.{secrets.token_hex(8)}"
        signature = hmac.new(bytes.fromhex(secret), body.encode(), hashlib.sha256).hexdigest()

        return f"{body}.{signature}"

    def valid_session(self, cookie: Optional[str]) -> bool:
        secret = self._read().get("secret")

        if not secret or not cookie:
            return False

        try:
            expires, nonce, signature = cookie.split(".")
            body = f"{expires}.{nonce}"
            expected = hmac.new(bytes.fromhex(secret), body.encode(), hashlib.sha256).hexdigest()

            return hmac.compare_digest(expected, signature) and int(expires) > time.time()
        except (ValueError, TypeError):
            return False

    # ----------------------------------------------------------
    # Which entry points are accepted
    # ----------------------------------------------------------

    @staticmethod
    def is_local(host: str, port: int) -> bool:
        return (host or "").strip().lower() in (f"127.0.0.1:{port}", f"localhost:{port}")

    def is_remote_allowed(self, host: str) -> bool:
        """Tailscale private addresses (*.ts.net) or others the user adds."""

        name = _without_port(host)

        if not name:
            return False

        if name.endswith(".ts.net"):
            return True

        return name in [str(h).lower() for h in self._read().get("hosts", [])]

    def add_host(self, host: str) -> None:
        host = _without_port(host)

        if not host:
            return

        data = self._read()
        hosts = [h for h in data.get("hosts", []) if h != host]
        hosts.append(host)
        data["hosts"] = hosts
        self._save(data)

    def state(self) -> dict:
        data = self._read()

        return {
            "configured": self.configured(),
            "address": data.get("address", ""),
        }

    def save_address(self, address: str) -> None:
        data = self._read()
        data["address"] = address
        self._save(data)
