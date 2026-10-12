"""
Copias de seguridad de BRAIN.

Crea ZIP con todo el contenido de datos/ (incluida la base SQLite, copiada
de forma consistente), guarda solo las últimas 5 y permite restaurar una
tras verificar su integridad con un manifiesto de sumas SHA-256.
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

from brain.base.modulo import ModuloBase
from brain.core.config import Config
from brain.core.database import NOMBRE_ARCHIVO, Database

COPIAS_A_CONSERVAR = 5
CARPETA_COPIAS = "backups"
MANIFIESTO = "MANIFEST.json"
PATRON = re.compile(r"^backup_\d{8}_\d{6}\.zip$")
PATRON_SEGURIDAD = re.compile(r"^prerestauracion_\d{8}_\d{6}\.zip$")

# Carpetas de datos que no se copian: las copias (para no copiarse a sí
# mismas) y los modelos de voz (cientos de MB que se pueden volver a descargar).
EXCLUIDAS = (CARPETA_COPIAS, "voz", ".restaurando")
TEMPORALES = (".tmp", ".corrupto")


class CopiaError(ValueError):
    """Error con mensaje entendible para el usuario."""


def _sha256(ruta):
    suma = hashlib.sha256()

    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            suma.update(bloque)

    return suma.hexdigest()


class Sistema(ModuloBase):
    nombre = "sistema"

    @property
    def carpeta_copias(self) -> Path:
        return Path(Config.DATOS) / CARPETA_COPIAS

    # ------------------------------------------------------------------
    # Listado
    # ------------------------------------------------------------------

    def listar_copias(self):
        """Copias existentes, de la más reciente a la más antigua."""

        carpeta = self.carpeta_copias

        if not carpeta.exists():
            return []

        copias = []

        for ruta in sorted(carpeta.iterdir(), reverse=True):
            if PATRON.match(ruta.name):
                copias.append(
                    {
                        "nombre": ruta.name,
                        "fecha": datetime.strptime(ruta.name[7:22], "%Y%m%d_%H%M%S").isoformat(timespec="seconds"),
                        "tamano_kb": round(ruta.stat().st_size / 1024),
                    }
                )

        return copias

    def ultima_copia(self):
        copias = self.listar_copias()

        return copias[0] if copias else None

    # ------------------------------------------------------------------
    # Crear
    # ------------------------------------------------------------------

    def _archivos_a_copiar(self):
        base = Path(Config.DATOS)

        if not base.exists():
            return []

        archivos = []

        for ruta in sorted(base.rglob("*")):
            if not ruta.is_file():
                continue

            relativa = ruta.relative_to(base)

            if relativa.parts[0] in EXCLUIDAS or relativa.parts[0].startswith("."):
                continue

            if ruta.name.endswith(TEMPORALES) or ruta.name.startswith(NOMBRE_ARCHIVO):
                continue  # la base de datos se añade aparte, ya consistente

            archivos.append((ruta, relativa.as_posix()))

        return archivos

    def _escribir_zip(self, destino, patron_rotacion=None):
        base = Path(Config.DATOS)
        base.mkdir(parents=True, exist_ok=True)
        destino.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=base, prefix=".copia_") as temporal:
            archivos = self._archivos_a_copiar()

            if (base / NOMBRE_ARCHIVO).exists():
                copia_db = Path(temporal) / NOMBRE_ARCHIVO
                Database().copiar_a(copia_db)
                archivos.append((copia_db, NOMBRE_ARCHIVO))

            manifiesto = {
                "brain": Config.VERSION,
                "creado": datetime.now().isoformat(timespec="seconds"),
                "archivos": {},
            }

            parcial = destino.with_name(destino.name + ".parcial")

            try:
                with zipfile.ZipFile(parcial, "w", zipfile.ZIP_DEFLATED) as z:
                    for ruta, nombre in archivos:
                        z.write(ruta, nombre)
                        manifiesto["archivos"][nombre] = {"sha256": _sha256(ruta), "bytes": ruta.stat().st_size}

                    z.writestr(MANIFIESTO, json.dumps(manifiesto, indent=2))

                os.replace(parcial, destino)

            except BaseException:
                try:
                    parcial.unlink()
                except OSError:
                    pass

                raise

        return len(archivos)

    def crear_copia(self):
        """Crea backup_YYYYMMDD_HHMMSS.zip y aplica la rotación."""

        ahora = datetime.now().replace(microsecond=0)
        carpeta = self.carpeta_copias

        # El nombre siempre es posterior al de la última copia (la rotación
        # ordena por nombre), aunque se creen varias en el mismo segundo.
        ultima = self.ultima_copia()

        if ultima:
            ahora = max(ahora, datetime.fromisoformat(ultima["fecha"]) + timedelta(seconds=1))

        destino = carpeta / f"backup_{ahora:%Y%m%d_%H%M%S}.zip"

        total = self._escribir_zip(destino)

        eliminadas = self._rotar()

        return {
            "archivo": destino.name,
            "archivos_incluidos": total,
            "tamano_kb": round(destino.stat().st_size / 1024),
            "copias_eliminadas": eliminadas,
            "copias_guardadas": len(self.listar_copias()),
        }

    def _rotar(self):
        copias = sorted(p for p in self.carpeta_copias.iterdir() if PATRON.match(p.name))
        sobran = copias[: max(0, len(copias) - COPIAS_A_CONSERVAR)]

        for ruta in sobran:
            try:
                ruta.unlink()
            except OSError:
                pass

        return [p.name for p in sobran]

    def copia_si_toca(self, horas=20):
        """Crea una copia solo si la última tiene más de `horas` horas."""

        ultima = self.ultima_copia()

        if ultima:
            edad = datetime.now() - datetime.fromisoformat(ultima["fecha"])

            if edad < timedelta(hours=horas):
                return None

        return self.crear_copia()

    # ------------------------------------------------------------------
    # Validar y restaurar
    # ------------------------------------------------------------------

    def _resolver(self, nombre):
        """Convierte lo que pida el usuario en la ruta de una copia existente."""

        copias = self.listar_copias()

        if not copias:
            raise CopiaError("No hay copias de seguridad. Crea una primero.")

        texto = (nombre or "").strip()

        if not texto or texto.lower() in ("ultima", "última", "reciente", "la ultima", "la última"):
            return self.carpeta_copias / copias[0]["nombre"]

        texto = Path(texto).name  # nunca salir de la carpeta de copias

        if not texto.endswith(".zip"):
            texto += ".zip"

        if not PATRON.match(texto) or not (self.carpeta_copias / texto).exists():
            disponibles = ", ".join(c["nombre"] for c in copias)
            raise CopiaError(f"No existe la copia '{nombre}'. Disponibles: {disponibles}.")

        return self.carpeta_copias / texto

    def validar_copia(self, ruta):
        """
        Verifica un ZIP: formato, CRC, rutas seguras y sumas SHA-256 del
        manifiesto. Devuelve el manifiesto o lanza CopiaError.
        """

        ruta = Path(ruta)

        if not zipfile.is_zipfile(ruta):
            raise CopiaError(f"{ruta.name} no es un ZIP válido.")

        with zipfile.ZipFile(ruta) as z:
            malo = z.testzip()

            if malo:
                raise CopiaError(f"{ruta.name} está dañado (falla {malo}).")

            nombres = set(z.namelist())

            if MANIFIESTO not in nombres:
                raise CopiaError(f"{ruta.name} no tiene manifiesto: no es una copia de BRAIN.")

            for nombre in nombres:
                partes = Path(nombre).parts

                if nombre.startswith(("/", "\\")) or ".." in partes or (partes and ":" in partes[0]):
                    raise CopiaError(f"{ruta.name} contiene una ruta insegura ({nombre}).")

            try:
                manifiesto = json.loads(z.read(MANIFIESTO).decode("utf-8"))
                esperados = manifiesto["archivos"]
            except (ValueError, KeyError, TypeError):
                raise CopiaError(f"El manifiesto de {ruta.name} está dañado.")

            if set(esperados) != nombres - {MANIFIESTO}:
                raise CopiaError(f"El contenido de {ruta.name} no coincide con su manifiesto.")

            for nombre, info in esperados.items():
                suma = hashlib.sha256(z.read(nombre)).hexdigest()

                if suma != info.get("sha256"):
                    raise CopiaError(f"Falla la verificación de integridad de {nombre} en {ruta.name}.")

        return manifiesto

    def restaurar_copia(self, nombre=None):
        """
        Restaura una copia (por defecto la última). Primero la valida y la
        extrae aparte; antes de sustituir nada guarda el estado actual en
        prerestauracion_*.zip por si hay que volver atrás.
        """

        ruta = self._resolver(nombre)
        manifiesto = self.validar_copia(ruta)

        base = Path(Config.DATOS)
        preparacion = base / ".restaurando"

        shutil.rmtree(preparacion, ignore_errors=True)
        preparacion.mkdir(parents=True)

        try:
            with zipfile.ZipFile(ruta) as z:
                for nombre_archivo in manifiesto["archivos"]:
                    z.extract(nombre_archivo, preparacion)

            seguridad = self.carpeta_copias / f"prerestauracion_{datetime.now():%Y%m%d_%H%M%S}.zip"
            self._escribir_zip(seguridad)

            for vieja in sorted(self.carpeta_copias.glob("prerestauracion_*.zip"))[:-1]:
                if PATRON_SEGURIDAD.match(vieja.name):
                    vieja.unlink()

            try:
                self._sustituir_datos(preparacion, manifiesto)
            except Exception:
                self._sustituir_datos_desde_zip(seguridad)
                raise

        finally:
            shutil.rmtree(preparacion, ignore_errors=True)

        return {
            "restaurada": ruta.name,
            "archivos_restaurados": len(manifiesto["archivos"]),
            "copia_de_seguridad_previa": seguridad.name,
            "creada_el": manifiesto.get("creado"),
        }

    def _sustituir_datos(self, origen, manifiesto):
        base = Path(Config.DATOS)

        for ruta, relativa in self._archivos_a_copiar():
            ruta.unlink()

        (base / NOMBRE_ARCHIVO).unlink(missing_ok=True)

        for relativa in manifiesto["archivos"]:
            destino = base / relativa
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.replace(origen / relativa, destino)

    def _sustituir_datos_desde_zip(self, zip_seguridad):
        """Deshace una restauración fallida con la copia previa."""

        with tempfile.TemporaryDirectory(dir=Config.DATOS, prefix=".deshacer_") as temporal:
            manifiesto = self.validar_copia(zip_seguridad)

            with zipfile.ZipFile(zip_seguridad) as z:
                for nombre in manifiesto["archivos"]:
                    z.extract(nombre, temporal)

            self._sustituir_datos(Path(temporal), manifiesto)
