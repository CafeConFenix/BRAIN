"""
Almacenamiento SQLite de BRAIN (solo biblioteca estándar).

Guarda en datos/brain.db los registros que crecen sin parar:
peso, lecturas de sensores, producción solar diaria y lecturas de
energía en tiempo real. Los datos pequeños (configuración, inventario,
lista de la compra, memoria, agenda) siguen en JSON.

Cada operación abre su conexión, usa `with sqlite3.connect(...)` (commit
automático si todo va bien, rollback si hay un error) y la cierra al
terminar, para que Windows no deje el archivo bloqueado.
"""

import json
import os
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from brain.core.config import Config

NOMBRE_ARCHIVO = "brain.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS peso (
    fecha TEXT PRIMARY KEY,
    peso  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sensores (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo      TEXT NOT NULL,
    valor     TEXT,
    ubicacion TEXT,
    fecha     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensores_tipo_fecha ON sensores (tipo, fecha);
CREATE INDEX IF NOT EXISTS idx_sensores_fecha ON sensores (fecha);

CREATE TABLE IF NOT EXISTS produccion_solar (
    fecha TEXT PRIMARY KEY,
    kwh   REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS energia_registros (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha        TEXT NOT NULL,
    produccion_w REAL,
    consumo_w    REAL,
    red_w        REAL,
    bateria_pct  REAL
);
CREATE INDEX IF NOT EXISTS idx_energia_fecha ON energia_registros (fecha);

CREATE TABLE IF NOT EXISTS avisos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha   TEXT NOT NULL,
    tipo    TEXT NOT NULL,
    titulo  TEXT NOT NULL,
    mensaje TEXT,
    nivel   TEXT NOT NULL DEFAULT 'info',
    leido   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_avisos_fecha ON avisos (fecha);
CREATE INDEX IF NOT EXISTS idx_avisos_leido ON avisos (leido, id);

CREATE TABLE IF NOT EXISTS recordatorios (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cuando  TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    hecho   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_recordatorios_cuando ON recordatorios (hecho, cuando);

CREATE TABLE IF NOT EXISTS medidas (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha  TEXT NOT NULL,
    nombre TEXT NOT NULL,
    valor  REAL NOT NULL,
    unidad TEXT
);
CREATE INDEX IF NOT EXISTS idx_medidas_nombre_fecha ON medidas (nombre, fecha);

CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""

_inicializadas = set()
_bloqueo = threading.Lock()


class Database:
    """Acceso a datos/brain.db. La ruta se calcula en cada uso (Config.DATOS)."""

    @property
    def ruta(self) -> Path:
        return Path(Config.DATOS) / NOMBRE_ARCHIVO

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    def _abrir(self):
        ruta = self.ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)

        conexion = sqlite3.connect(str(ruta), timeout=15)
        conexion.row_factory = sqlite3.Row

        return conexion

    def conectar(self):
        """
        Devuelve una conexión lista para usar con:

            with closing(db.conectar()) as con, con:
                con.execute(...)
        """

        self._preparar()

        return self._abrir()

    def _preparar(self):
        clave = str(self.ruta)

        if clave in _inicializadas and self.ruta.exists():
            return

        with _bloqueo:
            if clave in _inicializadas and self.ruta.exists():
                return

            with closing(self._abrir()) as con, con:
                con.executescript(ESQUEMA)

            _inicializadas.add(clave)

            try:
                self._migrar_json()
            except Exception as error:  # la migración nunca debe impedir arrancar
                print(f"[BRAIN] No se pudieron migrar los datos antiguos a SQLite: {error}")

    # ------------------------------------------------------------------
    # Migración desde los JSON antiguos
    # ------------------------------------------------------------------

    def _migrar_json(self):
        """
        Pasa a SQLite lo que hubiera en los JSON de versiones anteriores
        (salud.peso, sensores.*, energia.placas_solares) en UNA transacción.
        Antes de tocar nada deja una copia "<archivo>.json.premigracion".
        """

        with closing(self._abrir()) as con:
            hecho = con.execute("SELECT valor FROM meta WHERE clave = 'migrado_json'").fetchone()

        if hecho:
            return

        base = Path(Config.DATOS)

        origenes = {
            "salud": base / "salud" / "salud.json",
            "sensores": base / "sensores" / "sensores.json",
            "energia": base / "energia" / "energia.json",
        }

        contenido = {}

        for modulo, ruta in origenes.items():
            if not ruta.exists():
                continue

            try:
                with open(ruta, "r", encoding="utf-8-sig") as f:
                    datos = json.load(f)
            except (OSError, ValueError):
                continue

            if isinstance(datos, dict):
                contenido[modulo] = datos

        with closing(self._abrir()) as con, con:
            for r in contenido.get("salud", {}).get("peso", []) or []:
                try:
                    con.execute(
                        "INSERT OR REPLACE INTO peso (fecha, peso) VALUES (?, ?)",
                        (str(r["fecha"]), float(r["peso"])),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            for tipo, lecturas in contenido.get("sensores", {}).items():
                if not isinstance(lecturas, list):
                    continue

                for r in lecturas:
                    try:
                        con.execute(
                            "INSERT INTO sensores (tipo, valor, ubicacion, fecha) VALUES (?, ?, ?, ?)",
                            (tipo, json.dumps(r.get("valor")), r.get("ubicacion"), str(r.get("fecha", ""))),
                        )
                    except (AttributeError, TypeError):
                        continue

            for r in contenido.get("energia", {}).get("placas_solares", []) or []:
                try:
                    con.execute(
                        "INSERT OR REPLACE INTO produccion_solar (fecha, kwh) VALUES (?, ?)",
                        (str(r["fecha"]), float(r["produccion"])),
                    )
                except (KeyError, TypeError, ValueError):
                    continue

            con.execute("INSERT OR REPLACE INTO meta (clave, valor) VALUES ('migrado_json', '1')")

        # Con la transacción confirmada, se retiran las secciones migradas
        # de los JSON (dejando copia de seguridad del original).
        secciones = {
            "salud": ("peso",),
            "sensores": None,  # todo el archivo son lecturas
            "energia": ("placas_solares",),
        }

        for modulo, claves in secciones.items():
            ruta = origenes[modulo]

            if modulo not in contenido:
                continue

            try:
                os.replace(ruta, ruta.with_name(ruta.name + ".premigracion"))

                if claves is not None:
                    restante = {k: v for k, v in contenido[modulo].items() if k not in claves}

                    if restante:
                        with open(ruta, "w", encoding="utf-8") as f:
                            json.dump(restante, f, indent=4, ensure_ascii=False)
            except OSError:
                continue

    # ------------------------------------------------------------------
    # Peso
    # ------------------------------------------------------------------

    def guardar_peso(self, fecha, peso):
        with closing(self.conectar()) as con, con:
            con.execute("INSERT OR REPLACE INTO peso (fecha, peso) VALUES (?, ?)", (fecha, float(peso)))

    def historial_peso(self, limite=None):
        consulta = "SELECT fecha, peso FROM peso ORDER BY fecha"

        with closing(self.conectar()) as con:
            filas = con.execute(consulta).fetchall()

        registros = [{"peso": f["peso"], "fecha": f["fecha"]} for f in filas]

        if limite:
            registros = registros[-int(limite) :]

        return registros

    def peso_exacto(self, fecha):
        with closing(self.conectar()) as con:
            fila = con.execute("SELECT fecha, peso FROM peso WHERE fecha = ?", (fecha,)).fetchone()

        return {"peso": fila["peso"], "fecha": fila["fecha"]} if fila else None

    def peso_anterior(self, fecha):
        with closing(self.conectar()) as con:
            fila = con.execute(
                "SELECT fecha, peso FROM peso WHERE fecha < ? ORDER BY fecha DESC LIMIT 1", (fecha,)
            ).fetchone()

        return {"peso": fila["peso"], "fecha": fila["fecha"]} if fila else None

    # ------------------------------------------------------------------
    # Sensores
    # ------------------------------------------------------------------

    def guardar_lectura_sensor(self, tipo, valor, ubicacion, fecha):
        with closing(self.conectar()) as con, con:
            con.execute(
                "INSERT INTO sensores (tipo, valor, ubicacion, fecha) VALUES (?, ?, ?, ?)",
                (tipo, json.dumps(valor), ubicacion, fecha),
            )

    def lecturas_sensor(self, tipo, limite=None):
        """Lecturas de un sensor, de la más antigua a la más reciente."""

        consulta = "SELECT valor, ubicacion, fecha FROM sensores WHERE tipo = ? ORDER BY fecha DESC, id DESC"
        parametros = [tipo]

        if limite:
            consulta += " LIMIT ?"
            parametros.append(int(limite))

        with closing(self.conectar()) as con:
            filas = con.execute(consulta, parametros).fetchall()

        lecturas = [
            {"valor": _desde_json(f["valor"]), "ubicacion": f["ubicacion"], "fecha": f["fecha"]} for f in filas
        ]

        return lecturas[::-1]

    # ------------------------------------------------------------------
    # Producción solar diaria
    # ------------------------------------------------------------------

    def guardar_produccion(self, fecha, kwh):
        with closing(self.conectar()) as con, con:
            con.execute("INSERT OR REPLACE INTO produccion_solar (fecha, kwh) VALUES (?, ?)", (fecha, float(kwh)))

    def produccion(self, limite=7):
        with closing(self.conectar()) as con:
            filas = con.execute(
                "SELECT fecha, kwh FROM produccion_solar ORDER BY fecha DESC LIMIT ?", (int(limite),)
            ).fetchall()

        return [{"produccion": f["kwh"], "fecha": f["fecha"]} for f in filas][::-1]

    # ------------------------------------------------------------------
    # Energía en tiempo real (histórico de lecturas)
    # ------------------------------------------------------------------

    def guardar_lectura_energia(self, fecha, produccion_w=None, consumo_w=None, red_w=None, bateria_pct=None):
        with closing(self.conectar()) as con, con:
            con.execute(
                "INSERT INTO energia_registros (fecha, produccion_w, consumo_w, red_w, bateria_pct) "
                "VALUES (?, ?, ?, ?, ?)",
                (fecha, produccion_w, consumo_w, red_w, bateria_pct),
            )

    def lecturas_energia(self, desde=None, limite=500):
        consulta = "SELECT fecha, produccion_w, consumo_w, red_w, bateria_pct FROM energia_registros"
        parametros = []

        if desde:
            consulta += " WHERE fecha >= ?"
            parametros.append(desde)

        consulta += " ORDER BY fecha DESC LIMIT ?"
        parametros.append(int(limite))

        with closing(self.conectar()) as con:
            filas = con.execute(consulta, parametros).fetchall()

        return [dict(f) for f in filas][::-1]

    def depurar_energia(self, antes_de):
        """Borra lecturas de energía anteriores a una fecha ISO. Devuelve cuántas."""

        with closing(self.conectar()) as con, con:
            return con.execute("DELETE FROM energia_registros WHERE fecha < ?", (antes_de,)).rowcount

    # ------------------------------------------------------------------
    # Avisos y recordatorios
    # ------------------------------------------------------------------

    def crear_aviso(self, fecha, tipo, titulo, mensaje="", nivel="info"):
        with closing(self.conectar()) as con, con:
            cursor = con.execute(
                "INSERT INTO avisos (fecha, tipo, titulo, mensaje, nivel) VALUES (?, ?, ?, ?, ?)",
                (fecha, tipo, titulo, mensaje, nivel),
            )

            return cursor.lastrowid

    def avisos(self, solo_no_leidos=False, despues_de=0, limite=50):
        """Avisos de más antiguo a más reciente (los últimos `limite`)."""

        consulta = "SELECT id, fecha, tipo, titulo, mensaje, nivel, leido FROM avisos WHERE id > ?"
        parametros = [int(despues_de)]

        if solo_no_leidos:
            consulta += " AND leido = 0"

        consulta += " ORDER BY id DESC LIMIT ?"
        parametros.append(int(limite))

        with closing(self.conectar()) as con:
            filas = con.execute(consulta, parametros).fetchall()

        return [{**dict(f), "leido": bool(f["leido"])} for f in filas][::-1]

    def marcar_avisos_leidos(self, ids=None):
        with closing(self.conectar()) as con, con:
            if ids:
                marcas = ",".join("?" for _ in ids)
                return con.execute(f"UPDATE avisos SET leido = 1 WHERE leido = 0 AND id IN ({marcas})", list(ids)).rowcount

            return con.execute("UPDATE avisos SET leido = 1 WHERE leido = 0").rowcount

    def depurar_avisos(self, antes_de):
        with closing(self.conectar()) as con, con:
            return con.execute("DELETE FROM avisos WHERE fecha < ?", (antes_de,)).rowcount

    def crear_recordatorio(self, cuando, mensaje):
        with closing(self.conectar()) as con, con:
            return con.execute("INSERT INTO recordatorios (cuando, mensaje) VALUES (?, ?)", (cuando, mensaje)).lastrowid

    def recordatorios_pendientes(self):
        with closing(self.conectar()) as con:
            filas = con.execute(
                "SELECT id, cuando, mensaje FROM recordatorios WHERE hecho = 0 ORDER BY cuando"
            ).fetchall()

        return [dict(f) for f in filas]

    def tomar_recordatorios_vencidos(self, ahora):
        """Devuelve los recordatorios vencidos y los marca como hechos (en una transacción)."""

        with closing(self.conectar()) as con, con:
            filas = con.execute(
                "SELECT id, cuando, mensaje FROM recordatorios WHERE hecho = 0 AND cuando <= ? ORDER BY cuando", (ahora,)
            ).fetchall()

            for f in filas:
                con.execute("UPDATE recordatorios SET hecho = 1 WHERE id = ?", (f["id"],))

        return [dict(f) for f in filas]

    def borrar_recordatorio(self, id_recordatorio):
        with closing(self.conectar()) as con, con:
            return con.execute("DELETE FROM recordatorios WHERE id = ? AND hecho = 0", (int(id_recordatorio),)).rowcount

    # ------------------------------------------------------------------
    # Medidas corporales (grasa, IMC, agua... además del peso)
    # ------------------------------------------------------------------

    def guardar_medida(self, fecha, nombre, valor, unidad=None):
        with closing(self.conectar()) as con, con:
            con.execute("DELETE FROM medidas WHERE fecha = ? AND nombre = ?", (fecha, nombre))
            con.execute(
                "INSERT INTO medidas (fecha, nombre, valor, unidad) VALUES (?, ?, ?, ?)", (fecha, nombre, float(valor), unidad)
            )

    def medidas(self, nombre=None, limite=60):
        consulta = "SELECT fecha, nombre, valor, unidad FROM medidas"
        parametros = []

        if nombre:
            consulta += " WHERE nombre = ?"
            parametros.append(nombre)

        consulta += " ORDER BY fecha DESC, id DESC LIMIT ?"
        parametros.append(int(limite))

        with closing(self.conectar()) as con:
            filas = con.execute(consulta, parametros).fetchall()

        return [dict(f) for f in filas][::-1]

    # ------------------------------------------------------------------
    # Análisis de energía
    # ------------------------------------------------------------------

    def energia_por_hora(self, desde):
        """Media por hora del día (0-23) de producción, consumo y red desde una fecha ISO."""

        consulta = (
            "SELECT CAST(substr(fecha, 12, 2) AS INTEGER) AS hora, "
            "AVG(produccion_w) AS produccion, AVG(consumo_w) AS consumo, AVG(red_w) AS red, COUNT(*) AS n "
            "FROM energia_registros WHERE fecha >= ? GROUP BY hora ORDER BY hora"
        )

        with closing(self.conectar()) as con:
            filas = con.execute(consulta, (desde,)).fetchall()

        return [dict(f) for f in filas]

    # ------------------------------------------------------------------
    # Mantenimiento
    # ------------------------------------------------------------------

    def copiar_a(self, destino):
        """Copia consistente de la base de datos (API de backup de SQLite)."""

        self._preparar()

        with closing(self._abrir()) as origen, closing(sqlite3.connect(str(destino))) as copia:
            origen.backup(copia)

    def indices(self):
        with closing(self.conectar()) as con:
            filas = con.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_%'").fetchall()

        return sorted(f["name"] for f in filas)


def _desde_json(texto):
    if texto is None:
        return None

    try:
        return json.loads(texto)
    except ValueError:
        return texto
