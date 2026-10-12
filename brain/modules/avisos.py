"""
Centro de avisos de BRAIN: notificaciones, sonidos y recordatorios.

Los avisos se guardan en SQLite (histórico) y se entregan por dos vías:
la interfaz web (que los consulta y suena en el navegador) y las
notificaciones nativas de Windows (con sonido propio). Los sonidos son
archivos .wav, .mp3 u .ogg que el usuario deja en datos/sonidos/.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from brain.base.modulo import ModuloBase
from brain.core import notificador
from brain.core.config import Config
from brain.core.database import Database
from brain.modules.inventario import normalizar

TIPOS = ("alerta", "recordatorio", "resumen", "automatizacion", "energia", "info")
NIVELES = ("info", "importante", "critico")
EXTENSIONES_SONIDO = (".wav", ".mp3", ".ogg")

CONFIG_POR_DEFECTO = {
    "silencio": False,  # True: no sonar ni mostrar notificaciones (se siguen guardando)
    "nativo": True,  # notificaciones y sonido propios de Windows
    "no_molestar": {"desde": "23:00", "hasta": "07:00"},  # solo suenan los avisos críticos
    "sonidos": {},  # tipo -> archivo de datos/sonidos/
}


def _hora_a_minutos(texto) -> int:
    horas, minutos = str(texto).strip().replace(".", ":").split(":")
    horas, minutos = int(horas), int(minutos)

    if not (0 <= horas <= 23 and 0 <= minutos <= 59):
        raise ValueError

    return horas * 60 + minutos


class Avisos(ModuloBase):
    nombre = "avisos"

    def __init__(self):
        super().__init__()
        self.db = Database()

    # ------------------------------------------------------------------
    # Configuración y sonidos
    # ------------------------------------------------------------------

    @property
    def carpeta_sonidos(self) -> Path:
        return Path(Config.DATOS) / "sonidos"

    def configuracion(self) -> dict:
        guardada = self.data.leer_modulo(self.nombre)

        config = {**CONFIG_POR_DEFECTO, **{k: v for k, v in guardada.items() if k in CONFIG_POR_DEFECTO}}
        config["sonidos"] = dict(config.get("sonidos") or {})

        return config

    def _guardar_config(self, config: dict) -> None:
        self.data.guardar_modulo(self.nombre, config)

    def archivos_sonido(self) -> List[str]:
        carpeta = self.carpeta_sonidos

        if not carpeta.exists():
            return []

        return sorted(p.name for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONES_SONIDO)

    def ver_sonidos(self) -> dict:
        return {
            "carpeta": str(self.carpeta_sonidos),
            "archivos": self.archivos_sonido(),
            "asignados": self.configuracion()["sonidos"],
            "tipos": list(TIPOS),
        }

    def _resolver_sonido(self, archivo) -> str:
        clave = normalizar(archivo)
        archivos = self.archivos_sonido()

        for nombre in archivos:
            if normalizar(nombre) == clave or normalizar(Path(nombre).stem) == clave:
                return nombre

        coincidentes = [n for n in archivos if clave in normalizar(n)]

        if len(coincidentes) == 1:
            return coincidentes[0]

        if not archivos:
            raise ValueError(f"No hay sonidos. Copia archivos .wav, .mp3 u .ogg en {self.carpeta_sonidos}.")

        raise ValueError(f"No encuentro el sonido '{archivo}'. Disponibles: {', '.join(archivos)}.")

    def asignar_sonido(self, tipo, archivo) -> dict:
        """Asigna un sonido a un tipo de aviso. `archivo` vacío o 'ninguno' lo quita."""

        tipo = self._tipo_valido(tipo)
        config = self.configuracion()

        if not archivo or normalizar(archivo) in ("ninguno", "ninguna", "quitar", "por defecto", "defecto"):
            config["sonidos"].pop(tipo, None)
            self._guardar_config(config)

            return {"tipo": tipo, "sonido": None}

        nombre = self._resolver_sonido(archivo)
        config["sonidos"][tipo] = nombre
        self._guardar_config(config)

        return {"tipo": tipo, "sonido": nombre}

    def ruta_sonido(self, nombre) -> Optional[Path]:
        """Ruta segura de un sonido de la carpeta (o None)."""

        if not nombre or Path(nombre).name != nombre:
            return None

        ruta = self.carpeta_sonidos / nombre

        return ruta if ruta.is_file() and ruta.suffix.lower() in EXTENSIONES_SONIDO else None

    def sonido_de(self, tipo) -> Optional[str]:
        nombre = self.configuracion()["sonidos"].get(tipo)

        return nombre if self.ruta_sonido(nombre) else None

    def configurar(self, silencio=None, nativo=None, no_molestar_desde=None, no_molestar_hasta=None) -> dict:
        config = self.configuracion()

        if silencio is not None:
            config["silencio"] = bool(silencio)

        if nativo is not None:
            config["nativo"] = bool(nativo)

        if no_molestar_desde is not None or no_molestar_hasta is not None:
            actual = config.get("no_molestar") or {"desde": "23:00", "hasta": "07:00"}
            desde = no_molestar_desde if no_molestar_desde not in (None, "") else actual["desde"]
            hasta = no_molestar_hasta if no_molestar_hasta not in (None, "") else actual["hasta"]

            if str(desde).lower() in ("ninguno", "no", "off") or str(hasta).lower() in ("ninguno", "no", "off"):
                config["no_molestar"] = None
            else:
                try:
                    _hora_a_minutos(desde)
                    _hora_a_minutos(hasta)
                except ValueError:
                    raise ValueError("Las horas de 'no molestar' deben ser HH:MM, por ejemplo 23:00.") from None

                config["no_molestar"] = {"desde": str(desde), "hasta": str(hasta)}

        self._guardar_config(config)

        return {k: config[k] for k in ("silencio", "nativo", "no_molestar")}

    def en_no_molestar(self, ahora: Optional[datetime] = None) -> bool:
        franja = self.configuracion().get("no_molestar")

        if not franja:
            return False

        ahora = ahora or datetime.now()
        minuto = ahora.hour * 60 + ahora.minute

        try:
            desde, hasta = _hora_a_minutos(franja["desde"]), _hora_a_minutos(franja["hasta"])
        except (ValueError, KeyError):
            return False

        if desde <= hasta:
            return desde <= minuto < hasta

        return minuto >= desde or minuto < hasta  # franja que cruza la medianoche

    # ------------------------------------------------------------------
    # Avisos
    # ------------------------------------------------------------------

    @staticmethod
    def _tipo_valido(tipo) -> str:
        clave = normalizar(tipo)

        if clave not in TIPOS:
            raise ValueError(f"El tipo de aviso '{tipo}' no existe. Opciones: {', '.join(TIPOS)}.")

        return clave

    def avisar(self, titulo, mensaje="", tipo="info", nivel=None, silencioso=False) -> dict:
        """
        Crea un aviso, lo guarda y lo entrega (notificación y sonido de
        Windows). Los avisos críticos suenan siempre, también en "no molestar".
        Con `silencioso=True` solo queda anotado en el histórico, sin sonar.
        """

        tipo = self._tipo_valido(tipo)

        if nivel is None:
            nivel = "critico" if tipo == "alerta" else "info"

        if nivel not in NIVELES:
            nivel = "info"

        titulo = str(titulo).strip() or "BRAIN"
        mensaje = str(mensaje or "").strip()

        ahora = datetime.now().isoformat(timespec="seconds")
        id_aviso = self.db.crear_aviso(ahora, tipo, titulo, mensaje, nivel)

        config = self.configuracion()
        critico = nivel == "critico"

        if not silencioso and config["nativo"] and not config["silencio"] and (critico or not self.en_no_molestar()):
            nombre = self.sonido_de(tipo)
            notificador.notificar(titulo, mensaje, self.ruta_sonido(nombre) if nombre else None)

        return {"id": id_aviso, "fecha": ahora, "tipo": tipo, "titulo": titulo, "mensaje": mensaje, "nivel": nivel}

    def listar(self, solo_no_leidos=False, despues_de=0, limite=50) -> List[dict]:
        avisos = self.db.avisos(solo_no_leidos, despues_de, limite)

        for aviso in avisos:
            aviso["sonido"] = self.sonido_de(aviso["tipo"])

        return avisos

    def marcar_leidos(self, ids=None) -> int:
        return self.db.marcar_avisos_leidos(ids)

    # ------------------------------------------------------------------
    # Recordatorios
    # ------------------------------------------------------------------

    def crear_recordatorio(self, mensaje, en_minutos=None, fecha_hora=None) -> dict:
        """
        Programa un recordatorio. Indica `en_minutos` (desde ahora) o
        `fecha_hora` ("AAAA-MM-DD HH:MM" o solo "HH:MM": hoy, o mañana si ya pasó).
        """

        mensaje = str(mensaje or "").strip()

        if not mensaje:
            raise ValueError("Falta el texto del recordatorio.")

        ahora = datetime.now().replace(microsecond=0)

        if en_minutos not in (None, "", 0):
            minutos = float(en_minutos)

            if minutos <= 0:
                raise ValueError("Los minutos deben ser más de cero.")

            cuando = ahora + timedelta(minutes=minutos)
        elif fecha_hora:
            cuando = self._interpretar_fecha_hora(str(fecha_hora), ahora)
        else:
            raise ValueError("Indica cuándo: en cuántos minutos o la fecha y hora.")

        cuando = cuando.replace(second=0) if fecha_hora and not en_minutos else cuando

        identificador = self.db.crear_recordatorio(cuando.isoformat(timespec="seconds"), mensaje)

        return {"id": identificador, "mensaje": mensaje, "cuando": cuando.isoformat(timespec="minutes").replace("T", " ")}

    @staticmethod
    def _interpretar_fecha_hora(texto: str, ahora: datetime) -> datetime:
        texto = texto.strip().replace("T", " ")

        solo_hora = re.fullmatch(r"(\d{1,2})[:.](\d{2})", texto)

        if solo_hora:
            cuando = ahora.replace(hour=int(solo_hora.group(1)), minute=int(solo_hora.group(2)), second=0)

            if cuando <= ahora:
                cuando += timedelta(days=1)

            return cuando

        for formato in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                cuando = datetime.strptime(texto, formato)
            except ValueError:
                continue

            if cuando <= ahora:
                raise ValueError("Esa fecha y hora ya han pasado.")

            return cuando

        raise ValueError(f"No entiendo '{texto}'. Usa AAAA-MM-DD HH:MM, por ejemplo 2026-10-12 18:30.")

    def recordatorios(self) -> List[dict]:
        return self.db.recordatorios_pendientes()

    def borrar_recordatorio(self, id_recordatorio) -> bool:
        return bool(self.db.borrar_recordatorio(id_recordatorio))

    def revisar_recordatorios(self) -> int:
        """Lanza los recordatorios que ya tocan. Devuelve cuántos."""

        vencidos = self.db.tomar_recordatorios_vencidos(datetime.now().isoformat(timespec="seconds"))

        for r in vencidos:
            self.avisar("Recordatorio", r["mensaje"], tipo="recordatorio", nivel="importante")

        return len(vencidos)

    def depurar(self, dias=90) -> int:
        limite = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")

        return self.db.depurar_avisos(limite)
