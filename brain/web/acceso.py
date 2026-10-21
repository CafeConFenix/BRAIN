"""
Acceso protegido a BRAIN desde fuera del ordenador (móvil u otro PC).

La ventana de BRAIN en el propio ordenador entra por 127.0.0.1 y no pide
contraseña. Cualquier otra entrada (por ejemplo, la dirección privada de
Tailscale, "nombre.tailXXXX.ts.net") exige una contraseña y, una vez
introducida, se guarda en una cookie firmada que caduca a los 30 días.

Solo biblioteca estándar: PBKDF2 para la contraseña y HMAC para las cookies.
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

ITERACIONES = 200_000
MIN_CLAVE = 8
DURACION_SESION = 30 * 24 * 3600
NOMBRE_COOKIE = "brain_sesion"

# Freno contra adivinar la contraseña: tras 5 fallos seguidos se bloquea 60 s.
MAX_FALLOS = 5
BLOQUEO_SEGUNDOS = 60


def _sin_puerto(host: str) -> str:
    host = (host or "").strip().lower()

    if host.startswith("["):  # IPv6
        return host.split("]")[0].lstrip("[")

    return host.rsplit(":", 1)[0] if ":" in host else host


class Acceso:
    def __init__(self, ruta: Optional[Path] = None):
        self._ruta = Path(ruta) if ruta else Path(Config.DATOS) / "acceso.json"
        self._cerrojo = threading.Lock()
        self._fallos = 0
        self._bloqueado_hasta = 0.0

    # ----------------------------------------------------------
    # Almacenamiento
    # ----------------------------------------------------------

    def _leer(self) -> dict:
        try:
            datos = json.loads(self._ruta.read_text(encoding="utf-8"))
            return datos if isinstance(datos, dict) else {}
        except (OSError, ValueError):
            return {}

    def _guardar(self, datos: dict) -> None:
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self._ruta.with_suffix(".tmp")
        temporal.write_text(json.dumps(datos, indent=2), encoding="utf-8")
        os.replace(temporal, self._ruta)

    @staticmethod
    def _derivar(clave: str, sal: bytes, iteraciones: int) -> str:
        return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones).hex()

    # ----------------------------------------------------------
    # Contraseña
    # ----------------------------------------------------------

    def configurada(self) -> bool:
        datos = self._leer()
        return bool(datos.get("hash") and datos.get("sal") and datos.get("secreto"))

    def establecer_clave(self, clave: str) -> None:
        clave = str(clave or "")

        if len(clave) < MIN_CLAVE:
            raise ValueError(f"La contraseña debe tener al menos {MIN_CLAVE} caracteres.")

        sal = secrets.token_bytes(16)
        datos = self._leer()
        datos.update(
            {
                "hash": self._derivar(clave, sal, ITERACIONES),
                "sal": sal.hex(),
                "iteraciones": ITERACIONES,
                # Cambiar la contraseña invalida todas las sesiones abiertas.
                "secreto": secrets.token_hex(32),
            }
        )
        self._guardar(datos)

    def verificar_clave(self, clave: str) -> bool:
        with self._cerrojo:
            if time.time() < self._bloqueado_hasta:
                return False

        datos = self._leer()

        if not self.configurada():
            return False

        try:
            esperado = self._derivar(str(clave or ""), bytes.fromhex(datos["sal"]), int(datos.get("iteraciones", ITERACIONES)))
        except (ValueError, TypeError):
            return False

        correcta = hmac.compare_digest(esperado, datos["hash"])

        with self._cerrojo:
            if correcta:
                self._fallos = 0
            else:
                self._fallos += 1

                if self._fallos >= MAX_FALLOS:
                    self._bloqueado_hasta = time.time() + BLOQUEO_SEGUNDOS
                    self._fallos = 0

        return correcta

    def segundos_de_bloqueo(self) -> int:
        with self._cerrojo:
            return max(0, int(self._bloqueado_hasta - time.time()))

    # ----------------------------------------------------------
    # Sesiones (cookie firmada)
    # ----------------------------------------------------------

    def crear_sesion(self) -> str:
        secreto = self._leer().get("secreto")

        if not secreto:
            raise ValueError("No hay contraseña configurada.")

        caduca = int(time.time()) + DURACION_SESION
        cuerpo = f"{caduca}.{secrets.token_hex(8)}"
        firma = hmac.new(bytes.fromhex(secreto), cuerpo.encode(), hashlib.sha256).hexdigest()

        return f"{cuerpo}.{firma}"

    def sesion_valida(self, cookie: Optional[str]) -> bool:
        secreto = self._leer().get("secreto")

        if not secreto or not cookie:
            return False

        try:
            caduca, nonce, firma = cookie.split(".")
            cuerpo = f"{caduca}.{nonce}"
            esperada = hmac.new(bytes.fromhex(secreto), cuerpo.encode(), hashlib.sha256).hexdigest()

            return hmac.compare_digest(esperada, firma) and int(caduca) > time.time()
        except (ValueError, TypeError):
            return False

    # ----------------------------------------------------------
    # Qué entradas se aceptan
    # ----------------------------------------------------------

    @staticmethod
    def es_local(host: str, puerto: int) -> bool:
        return (host or "").strip().lower() in (f"127.0.0.1:{puerto}", f"localhost:{puerto}")

    def es_remoto_permitido(self, host: str) -> bool:
        """Direcciones privadas de Tailscale (*.ts.net) u otras que el usuario añada."""

        nombre = _sin_puerto(host)

        if not nombre:
            return False

        if nombre.endswith(".ts.net"):
            return True

        return nombre in [str(h).lower() for h in self._leer().get("hosts", [])]

    def anadir_host(self, host: str) -> None:
        host = _sin_puerto(host)

        if not host:
            return

        datos = self._leer()
        hosts = [h for h in datos.get("hosts", []) if h != host]
        hosts.append(host)
        datos["hosts"] = hosts
        self._guardar(datos)

    def estado(self) -> dict:
        datos = self._leer()

        return {
            "configurada": self.configurada(),
            "direccion": datos.get("direccion", ""),
        }

    def guardar_direccion(self, direccion: str) -> None:
        datos = self._leer()
        datos["direccion"] = direccion
        self._guardar(datos)
