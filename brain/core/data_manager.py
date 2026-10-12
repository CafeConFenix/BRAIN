import json
import os
import tempfile
import time
from pathlib import Path

from brain.core.config import Config


def _reintentar(accion, intentos=8, pausa=0.05):
    """
    Repite una operación de archivo si Windows la bloquea un instante.

    En Windows, un antivirus, OneDrive o una lectura simultánea pueden
    bloquear un archivo durante unos milisegundos y provocar un
    PermissionError que desaparece al reintentar.
    """

    for intento in range(intentos):
        try:
            return accion()

        except PermissionError:
            if intento == intentos - 1:
                raise

            time.sleep(pausa * (intento + 1))


class DataManager:
    """
    Gestor central de persistencia de BRAIN.

    Ningún módulo debe leer o escribir archivos directamente.

    Mejoras respecto a la versión anterior:
    - La escritura es atómica: si el programa se cierra a mitad de guardar,
      el archivo anterior no se corrompe.
    - Si un JSON está dañado se aparta como ".corrupto" en lugar de
      hacer fallar a BRAIN.
    - Se aceptan archivos con BOM (el Bloc de notas de Windows lo añade).
    """

    @property
    def base(self):
        return Path(Config.DATOS)

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------

    def _escribir(self, ruta: Path, datos):
        ruta.parent.mkdir(parents=True, exist_ok=True)

        descriptor, temporal = tempfile.mkstemp(
            dir=ruta.parent,
            prefix=f"{ruta.stem}_",
            suffix=".tmp",
        )

        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as f:
                json.dump(
                    datos,
                    f,
                    indent=4,
                    ensure_ascii=False,
                )

            _reintentar(lambda: os.replace(temporal, ruta))

        except BaseException:
            try:
                os.unlink(temporal)
            except OSError:
                pass

            raise

    def _leer(self, ruta: Path, defecto):
        if not ruta.exists():
            return defecto

        try:
            def leer_archivo():
                with open(ruta, "r", encoding="utf-8-sig") as f:
                    return f.read()

            contenido = _reintentar(leer_archivo)

            if not contenido.strip():
                return defecto

            return json.loads(contenido)

        except json.JSONDecodeError:
            copia = ruta.with_name(ruta.name + ".corrupto")

            try:
                os.replace(ruta, copia)
            except OSError:
                pass

            print(
                f"[BRAIN] El archivo {ruta.name} estaba dañado. "
                f"Se ha guardado una copia como {copia.name}."
            )

            return defecto

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def guardar(self, categoria: str, archivo: str, datos: dict):
        ruta = self.base / categoria / f"{archivo}.json"
        self._escribir(ruta, datos)

    def leer(self, categoria: str, archivo: str):
        ruta = self.base / categoria / f"{archivo}.json"
        return self._leer(ruta, None)

    def existe(self, categoria: str, archivo: str):
        ruta = self.base / categoria / f"{archivo}.json"
        return ruta.exists()

    def eliminar(self, categoria: str, archivo: str):
        ruta = self.base / categoria / f"{archivo}.json"

        if ruta.exists():
            ruta.unlink()

    def leer_modulo(self, modulo: str):
        ruta = self.base / modulo / f"{modulo}.json"

        datos = self._leer(ruta, {})

        if not isinstance(datos, dict):
            return {}

        return datos

    def guardar_modulo(self, modulo: str, datos: dict):
        ruta = self.base / modulo / f"{modulo}.json"
        self._escribir(ruta, datos)

    def añadir_registro(
        self,
        modulo: str,
        seccion: str,
        registro: dict,
    ):
        datos = self.leer_modulo(modulo)

        datos.setdefault(seccion, [])
        datos[seccion].append(registro)

        self.guardar_modulo(modulo, datos)
