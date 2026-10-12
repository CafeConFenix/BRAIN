"""
Automatizaciones de BRAIN: reglas "si pasa X, haz Y" creadas en lenguaje natural.

Disparadores:
  - hora:    a una hora y en ciertos días ("cada día a las 7:30")
  - sensor:  el estado de un sensor o aparato de Home Assistant cumple una condición
  - energia: producción, consumo, red, sobrante o batería del inversor cumple una condición

Acciones: aviso (notificación con sonido), encender, apagar y escena. Las de
casa pasan por el módulo de domótica, así que conservan sus límites de
seguridad (nunca cerraduras, garajes ni alarmas).

El planificador llama a `evaluar()` cada pocos segundos. Los disparadores de
sensor y energía se activan al PASAR a cumplirse la condición (no en cada
comprobación) y respetan un tiempo de espera entre ejecuciones.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from brain.base.modulo import ModuloBase
from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, leer_configuracion
from brain.modules.avisos import Avisos
from brain.modules.domotica import Domotica
from brain.modules.inventario import normalizar

MAX_REGLAS = 40
VENTANA_HORA_MINUTOS = 10  # si BRAIN estaba cerrado a la hora, aún la ejecuta durante estos minutos

DISPARADORES = ("hora", "sensor", "energia")
ACCIONES = ("aviso", "encender", "apagar", "escena")
CONDICIONES = ("mayor", "menor", "igual")
MAGNITUDES = ("produccion", "consumo", "red", "sobrante", "bateria")

DIAS = {
    "lunes": 0, "lun": 0, "martes": 1, "mar": 1, "miercoles": 2, "mie": 2, "jueves": 3, "jue": 3,
    "viernes": 4, "vie": 4, "sabado": 5, "sab": 5, "domingo": 6, "dom": 6,
}
NOMBRES_DIA = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def interpretar_dias(texto) -> List[int]:
    """'lunes,viernes' / 'laborables' / 'fin de semana' / 'todos' -> [0..6]."""

    clave = normalizar(texto or "todos")

    if clave in ("", "todos", "todos los dias", "cada dia", "diario", "diaria"):
        return list(range(7))

    if clave in ("laborables", "entre semana", "dias laborables", "de lunes a viernes"):
        return [0, 1, 2, 3, 4]

    if clave in ("fin de semana", "finde", "fines de semana"):
        return [5, 6]

    dias = sorted({DIAS[p] for p in re.findall(r"[a-z]+", clave) if p in DIAS})

    if not dias:
        raise ValueError(f"No entiendo los días '{texto}'. Usa 'todos', 'laborables', 'fin de semana' o nombres como 'lunes, jueves'.")

    return dias


def describir_dias(dias: List[int]) -> str:
    if dias == list(range(7)):
        return "todos los días"

    if dias == [0, 1, 2, 3, 4]:
        return "de lunes a viernes"

    if dias == [5, 6]:
        return "fines de semana"

    return ", ".join(NOMBRES_DIA[d] for d in dias)


def _numero(valor):
    try:
        return float(str(valor).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def _cumple(actual, condicion, esperado) -> Optional[bool]:
    """Compara un valor actual con el esperado. None si no se puede comparar."""

    if actual is None:
        return None

    if condicion == "igual":
        a, e = _numero(actual), _numero(esperado)

        if a is not None and e is not None:
            return a == e

        return normalizar(actual) == normalizar(esperado)

    a, e = _numero(actual), _numero(esperado)

    if a is None or e is None:
        return None

    return a > e if condicion == "mayor" else a < e


class Automatizaciones(ModuloBase):
    nombre = "automatizaciones"

    def __init__(self):
        super().__init__()
        self._activas: Dict[str, Optional[bool]] = {}  # estado anterior de la condición (para detectar el cambio)

    # ------------------------------------------------------------------
    # Almacén
    # ------------------------------------------------------------------

    def reglas(self) -> List[dict]:
        return self.obtener_seccion("reglas")

    def _guardar(self, reglas: List[dict]) -> None:
        self.guardar_seccion("reglas", reglas)

    @staticmethod
    def _clave(regla) -> str:
        return f"{regla['id']}:{regla.get('creada')}"

    def _buscar(self, reglas, nombre) -> dict:
        clave = normalizar(nombre)

        for r in reglas:
            if normalizar(r["nombre"]) == clave or str(r["id"]) == str(nombre).strip():
                return r

        parciales = [r for r in reglas if clave and clave in normalizar(r["nombre"])]

        if len(parciales) == 1:
            return parciales[0]

        if len(parciales) > 1:
            raise ValueError(f"'{nombre}' encaja con varias: {', '.join(r['nombre'] for r in parciales)}.")

        raise ValueError(f"No encuentro ninguna automatización llamada '{nombre}'.")

    # ------------------------------------------------------------------
    # Crear, listar, borrar
    # ------------------------------------------------------------------

    def crear(self, nombre, disparador: dict, acciones: List[dict], espera_minutos=5) -> dict:
        nombre = str(nombre or "").strip()

        if not nombre:
            raise ValueError("Falta un nombre para la automatización.")

        disparador = self._validar_disparador(disparador)
        acciones = [self._validar_accion(a) for a in acciones]

        if not acciones:
            raise ValueError("La automatización necesita al menos una acción.")

        reglas = self.reglas()

        if len(reglas) >= MAX_REGLAS:
            raise ValueError(f"Ya hay {MAX_REGLAS} automatizaciones; borra alguna antes.")

        if any(normalizar(r["nombre"]) == normalizar(nombre) for r in reglas):
            raise ValueError(f"Ya existe una automatización llamada '{nombre}'.")

        regla = {
            "id": max([r["id"] for r in reglas] + [0]) + 1,
            "nombre": nombre,
            "activa": True,
            "disparador": disparador,
            "acciones": acciones,
            "espera_minutos": max(0, float(espera_minutos if espera_minutos not in (None, "") else 5)),
            "creada": datetime.now().isoformat(timespec="seconds"),
            "ejecuciones": 0,
            "ultima_ejecucion": None,
            "ultimo_resultado": None,
        }

        reglas.append(regla)
        self._guardar(reglas)

        return {**regla, "resumen": self.describir(regla)}

    def _validar_disparador(self, d: dict) -> dict:
        tipo = normalizar(d.get("tipo", ""))

        if tipo not in DISPARADORES:
            raise ValueError(f"El disparador '{d.get('tipo')}' no existe. Opciones: {', '.join(DISPARADORES)}.")

        if tipo == "hora":
            try:
                horas, minutos = str(d.get("hora", "")).strip().replace(".", ":").split(":")
                horas, minutos = int(horas), int(minutos)
                assert 0 <= horas <= 23 and 0 <= minutos <= 59
            except (ValueError, AssertionError):
                raise ValueError(f"La hora '{d.get('hora')}' no es válida. Usa HH:MM, por ejemplo 07:30.") from None

            return {"tipo": "hora", "hora": f"{horas:02d}:{minutos:02d}", "dias": interpretar_dias(d.get("dias"))}

        condicion = normalizar(d.get("condicion", ""))

        if condicion not in CONDICIONES:
            raise ValueError(f"La condición '{d.get('condicion')}' no es válida. Usa mayor, menor o igual.")

        valor = d.get("valor")

        if valor in (None, ""):
            raise ValueError("Falta el valor con el que comparar.")

        if tipo == "energia":
            magnitud = normalizar(d.get("magnitud", ""))

            if magnitud not in MAGNITUDES:
                raise ValueError(f"La magnitud '{d.get('magnitud')}' no existe. Opciones: {', '.join(MAGNITUDES)}.")

            if _numero(valor) is None or condicion == "igual":
                raise ValueError("Para la energía usa 'mayor' o 'menor' con un número (vatios; porcentaje para la batería).")

            return {"tipo": "energia", "magnitud": magnitud, "condicion": condicion, "valor": _numero(valor)}

        if not d.get("entidad"):
            raise ValueError("Falta el sensor o aparato a vigilar.")

        if condicion != "igual" and _numero(valor) is None:
            raise ValueError("Con 'mayor' o 'menor' el valor tiene que ser un número.")

        return {
            "tipo": "sensor",
            "entidad": str(d["entidad"]),
            "nombre": str(d.get("nombre") or d["entidad"]),
            "condicion": condicion,
            "valor": _numero(valor) if condicion != "igual" or _numero(valor) is not None else str(valor).strip(),
        }

    def _validar_accion(self, a: dict) -> dict:
        tipo = normalizar(a.get("tipo", ""))

        if tipo not in ACCIONES:
            raise ValueError(f"La acción '{a.get('tipo')}' no existe. Opciones: {', '.join(ACCIONES)}.")

        if tipo == "aviso":
            return {"tipo": "aviso", "mensaje": str(a.get("mensaje") or "").strip() or None}

        objetivo = str(a.get("objetivo") or "").strip()

        if not objetivo:
            raise ValueError(f"Falta indicar qué {'escena activar' if tipo == 'escena' else 'aparato ' + tipo}.")

        return {"tipo": tipo, "objetivo": objetivo}

    def resolver_sensor(self, texto) -> dict:
        """Busca en Home Assistant el sensor o aparato que el usuario nombró (uno solo)."""

        aparatos, _ = Domotica().buscar(texto, incluir_lectura=True)

        if not aparatos:
            raise ValueError(f"No encuentro en Home Assistant ningún sensor o aparato que encaje con '{texto}'.")

        if len(aparatos) > 1:
            opciones = ", ".join(a["nombre"] for a in aparatos[:6])
            raise ValueError(f"'{texto}' encaja con varios: {opciones}. Dime cuál exactamente.")

        return {"entidad": aparatos[0]["entidad"], "nombre": aparatos[0]["nombre"]}

    def comprobar_objetivo(self, accion: str, objetivo: str) -> None:
        """Verifica en Home Assistant que el aparato o escena existe y es uno solo (si no, ValueError)."""

        accion = normalizar(accion)

        if accion not in ("encender", "apagar", "escena"):
            return

        _, problema = Domotica()._resolver(objetivo, ["scene", "script"] if accion == "escena" else None, False)

        if problema:
            if problema.get("ambiguo"):
                raise ValueError(f"'{objetivo}' encaja con varios: {', '.join(problema['opciones'])}. Dime cuál exactamente.")

            raise ValueError(problema.get("error", f"No encuentro '{objetivo}'."))

    def describir(self, regla: dict) -> str:
        d = regla["disparador"]

        if d["tipo"] == "hora":
            cuando = f"a las {d['hora']} {describir_dias(d['dias'])}"
        elif d["tipo"] == "sensor":
            cuando = f"cuando {d['nombre']} sea {d['condicion']}{' que' if d['condicion'] != 'igual' else ' a'} {d['valor']}"
        else:
            unidad = "%" if d["magnitud"] == "bateria" else " W"
            cuando = f"cuando {d['magnitud']} sea {d['condicion']} que {d['valor']:g}{unidad}"

        hace = []

        for a in regla["acciones"]:
            if a["tipo"] == "aviso":
                hace.append(f"avisar{': ' + a['mensaje'] if a.get('mensaje') else ''}")
            elif a["tipo"] == "escena":
                hace.append(f"activar la escena {a['objetivo']}")
            else:
                hace.append(f"{a['tipo']} {a['objetivo']}")

        return f"{cuando}: {', '.join(hace)}"

    def listar(self) -> List[dict]:
        return [
            {
                "id": r["id"],
                "nombre": r["nombre"],
                "activa": r["activa"],
                "regla": self.describir(r),
                "ejecuciones": r.get("ejecuciones", 0),
                "ultima_ejecucion": r.get("ultima_ejecucion"),
                "ultimo_resultado": r.get("ultimo_resultado"),
            }
            for r in self.reglas()
        ]

    def borrar(self, nombre) -> dict:
        reglas = self.reglas()
        regla = self._buscar(reglas, nombre)

        self._guardar([r for r in reglas if r["id"] != regla["id"]])
        self._activas.pop(self._clave(regla), None)

        return {"id": regla["id"], "nombre": regla["nombre"]}

    def activar(self, nombre, activa=True) -> dict:
        reglas = self.reglas()
        regla = self._buscar(reglas, nombre)

        regla["activa"] = bool(activa)
        self._activas.pop(self._clave(regla), None)
        self._guardar(reglas)

        return {"nombre": regla["nombre"], "activa": regla["activa"]}

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    def _estados(self) -> Dict[str, dict]:
        url, token = leer_configuracion()
        ha = HomeAssistant(url, token, timeout=8)

        if not ha.configurado:
            raise HomeAssistantError("Home Assistant no está configurado.")

        return {e.get("entity_id"): e for e in ha.estados()}

    def _energia(self) -> dict:
        from brain.tools.builtin.energia import tiempo_real

        return tiempo_real.leer()

    @staticmethod
    def _valor_energia(lectura: dict, magnitud: str):
        if not lectura.get("configurado") or lectura.get("error"):
            return None

        if magnitud == "sobrante":
            p, c = lectura.get("produccion_w"), lectura.get("consumo_w")

            return None if p is None or c is None else p - c

        clave = {"produccion": "produccion_w", "consumo": "consumo_w", "red": "red_w", "bateria": "bateria_pct"}[magnitud]

        return lectura.get(clave)

    def evaluar(self, ahora: Optional[datetime] = None) -> List[str]:
        """Comprueba todas las reglas activas y ejecuta las que toquen. Devuelve lo ejecutado."""

        ahora = ahora or datetime.now()
        reglas = self.reglas()
        activas = [r for r in reglas if r.get("activa")]

        if not activas:
            return []

        estados = lectura = None
        errores_fuente = {}

        if any(r["disparador"]["tipo"] == "sensor" for r in activas):
            try:
                estados = self._estados()
            except Exception as error:  # sin datos de esta fuente, las demás reglas siguen
                errores_fuente["sensor"] = str(error)

        if any(r["disparador"]["tipo"] == "energia" for r in activas):
            try:
                lectura = self._energia()
            except Exception as error:
                errores_fuente["energia"] = str(error)

        ejecutadas, cambiado = [], False

        for regla in activas:
            try:
                if self._debe_ejecutarse(regla, ahora, estados, lectura):
                    resultado = self._ejecutar(regla)
                    regla["ejecuciones"] = regla.get("ejecuciones", 0) + 1
                    regla["ultima_ejecucion"] = ahora.isoformat(timespec="seconds")
                    regla["ultimo_resultado"] = resultado
                    ejecutadas.append(f"{regla['nombre']}: {resultado}")
                    cambiado = True
            except Exception as error:  # una regla rota no impide las demás
                regla["ultimo_resultado"] = f"Error: {error}"
                cambiado = True

        if cambiado:
            self._guardar_estado_ejecucion(reglas)

        return ejecutadas

    def _guardar_estado_ejecucion(self, reglas: List[dict]) -> None:
        """Guarda contadores y último resultado sin pisar reglas creadas/borradas mientras tanto."""

        actuales = {r["id"]: r for r in self.reglas()}

        for regla in reglas:
            if regla["id"] in actuales:
                for campo in ("ejecuciones", "ultima_ejecucion", "ultimo_resultado"):
                    actuales[regla["id"]][campo] = regla.get(campo)

        self._guardar(list(actuales.values()))

    def _debe_ejecutarse(self, regla, ahora, estados, lectura) -> bool:
        d = regla["disparador"]

        if d["tipo"] == "hora":
            return self._toca_por_hora(regla, d, ahora)

        if d["tipo"] == "sensor":
            estado = (estados or {}).get(d["entidad"])
            actual = estado.get("state") if estado else None

            if actual in ("unavailable", "unknown"):
                actual = None
        else:
            actual = self._valor_energia(lectura, d["magnitud"]) if lectura else None

        cumple = _cumple(actual, d["condicion"], d["valor"])
        anterior = self._activas.get(self._clave(regla))

        if cumple is None:  # sin dato: no cambia el estado conocido
            return False

        self._activas[self._clave(regla)] = cumple

        # Solo al pasar de "no se cumple" a "se cumple". La primera lectura tras
        # arrancar no dispara (así un reinicio no repite acciones).
        if not cumple or anterior is not False:
            return False

        return self._fuera_de_espera(regla, ahora)

    @staticmethod
    def _toca_por_hora(regla, d, ahora) -> bool:
        if ahora.weekday() not in d["dias"]:
            return False

        horas, minutos = (int(x) for x in d["hora"].split(":"))
        objetivo = ahora.replace(hour=horas, minute=minutos, second=0, microsecond=0)

        if not objetivo <= ahora <= objetivo + timedelta(minutes=VENTANA_HORA_MINUTOS):
            return False

        ultima = regla.get("ultima_ejecucion")

        return not ultima or datetime.fromisoformat(ultima) < objetivo

    @staticmethod
    def _fuera_de_espera(regla, ahora) -> bool:
        ultima = regla.get("ultima_ejecucion")

        if not ultima:
            return True

        return ahora - datetime.fromisoformat(ultima) >= timedelta(minutes=regla.get("espera_minutos", 5))

    def _ejecutar(self, regla) -> str:
        avisos = Avisos()
        domotica = Domotica()
        resultados = []

        for accion in regla["acciones"]:
            if accion["tipo"] == "aviso":
                texto = accion.get("mensaje") or regla["nombre"]
                avisos.avisar(regla["nombre"], texto, tipo="automatizacion", nivel="importante")
                resultados.append("aviso enviado")
                continue

            if accion["tipo"] == "encender":
                respuesta = domotica.encender(accion["objetivo"])
            elif accion["tipo"] == "apagar":
                respuesta = domotica.apagar(accion["objetivo"])
            else:
                respuesta = domotica.activar_escena(accion["objetivo"])

            if isinstance(respuesta, dict) and respuesta.get("error"):
                resultados.append(f"{accion['tipo']} {accion['objetivo']}: {respuesta['error']}")
                avisos.avisar(f"Falló «{regla['nombre']}»", str(respuesta["error"]), tipo="automatizacion", nivel="importante")
            elif isinstance(respuesta, dict) and respuesta.get("ambiguo"):
                resultados.append(f"{accion['tipo']} {accion['objetivo']}: hay varios aparatos que encajan")
                avisos.avisar(f"Falló «{regla['nombre']}»", "Hay varios aparatos que encajan; sé más concreto.", tipo="automatizacion")
            else:
                resultados.append(f"{accion['tipo']} {accion['objetivo']}")
                avisos.avisar(regla["nombre"], f"Hecho: {accion['tipo']} {accion['objetivo']}.", tipo="automatizacion", silencioso=True)

        return "; ".join(resultados)

    def ejecutar_ahora(self, nombre) -> dict:
        """Ejecuta una automatización a mano (para probarla), sin esperar al disparador."""

        reglas = self.reglas()
        regla = self._buscar(reglas, nombre)
        resultado = self._ejecutar(regla)

        regla["ejecuciones"] = regla.get("ejecuciones", 0) + 1
        regla["ultima_ejecucion"] = datetime.now().isoformat(timespec="seconds")
        regla["ultimo_resultado"] = resultado
        self._guardar_estado_ejecucion(reglas)

        return {"nombre": regla["nombre"], "resultado": resultado}
