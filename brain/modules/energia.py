from brain.base.modulo import ModuloBase
from brain.core.database import Database
from brain.utils.fechas import validar_fecha


class Energia(ModuloBase):
    nombre = "energia"

    def __init__(self):
        super().__init__()
        self.db = Database()

    def registrar_produccion(self, kwh, fecha=None):
        """Guarda la producción solar de un día (actualiza si ya existía)."""

        kwh = float(kwh)

        if not 0 <= kwh <= 10000:
            raise ValueError(f"La producción {kwh} kWh no parece correcta.")

        fecha = validar_fecha(fecha)

        self.db.guardar_produccion(fecha, kwh)

        return {"produccion": kwh, "fecha": fecha}

    def produccion(self, limite=7):
        """Últimos registros de producción solar y su total y media."""

        registros = self.db.produccion(limite)

        total = round(sum(r.get("produccion", 0) for r in registros), 2)

        media = round(total / len(registros), 2) if registros else 0

        return {
            "registros": registros,
            "total_kwh": total,
            "media_kwh": media,
        }

    def registrar_lectura(self, lectura):
        """
        Guarda en SQLite una lectura de EnergiaTiempoReal.leer() para tener
        histórico. Devuelve True si había datos que guardar.
        """

        if not isinstance(lectura, dict) or not lectura.get("configurado") or lectura.get("error"):
            return False

        campos = ("produccion_w", "consumo_w", "red_w", "bateria_pct")

        if all(lectura.get(c) is None for c in campos):
            return False

        self.db.guardar_lectura_energia(
            datetime.now().isoformat(timespec="seconds"),
            lectura.get("produccion_w"),
            lectura.get("consumo_w"),
            lectura.get("red_w"),
            lectura.get("bateria_pct"),
        )

        return True

    def historial_lecturas(self, limite=200):
        return self.db.lecturas_energia(limite=limite)

    def analizar(self, dias=14):
        """
        Analiza el histórico de lecturas: a qué horas sobra producción solar
        (las mejores para lavadora, lavavajillas, termo...), cuándo consume más
        la casa y cómo va la producción diaria.
        """

        dias = max(1, int(dias))
        desde = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")

        horas = self.db.energia_por_hora(desde)
        muestras = sum(h["n"] for h in horas)

        resultado = {"dias_analizados": dias, "muestras": muestras}

        if muestras < 20:
            resultado["mensaje"] = (
                "Todavía hay pocos datos del inversor para aconsejarte. BRAIN los va guardando cada pocos minutos "
                "mientras esté abierto y Home Assistant conectado; vuelve a preguntar en un par de días."
            )

            return self._con_produccion_diaria(resultado)

        tabla = []

        for h in horas:
            produccion = h["produccion"] or 0
            consumo = h["consumo"] if h["consumo"] is not None else None
            sobrante = produccion - consumo if consumo is not None else produccion

            tabla.append(
                {
                    "hora": h["hora"],
                    "produccion_w": round(produccion),
                    "consumo_w": None if consumo is None else round(consumo),
                    "sobrante_w": round(sobrante),
                }
            )

        resultado["por_hora"] = tabla

        con_sol = [t for t in tabla if t["produccion_w"] > 100]

        if con_sol:
            mejores = sorted(con_sol, key=lambda t: t["sobrante_w"], reverse=True)[:4]
            mejores.sort(key=lambda t: t["hora"])
            resultado["mejores_horas"] = [t["hora"] for t in mejores]
            resultado["sobrante_medio_w"] = round(sum(t["sobrante_w"] for t in mejores) / len(mejores))

        consumos = [t for t in tabla if t["consumo_w"] is not None]

        if consumos:
            pico = max(consumos, key=lambda t: t["consumo_w"])
            resultado["hora_de_mas_consumo"] = pico["hora"]
            resultado["consumo_en_pico_w"] = pico["consumo_w"]

        resultado["consejo"] = self._redactar_consejo(resultado)

        return self._con_produccion_diaria(resultado)

    @staticmethod
    def _redactar_consejo(r):
        partes = []

        mejores = r.get("mejores_horas")

        if mejores and r.get("sobrante_medio_w", 0) > 200:
            partes.append(
                f"Las horas con más sol sobrante son {', '.join(f'{h}:00' for h in mejores)} "
                f"(unos {round(r['sobrante_medio_w'] / 1000, 1)} kW de excedente de media): programa ahí la lavadora, "
                "el lavavajillas o el termo."
            )
        elif mejores:
            partes.append("Tu casa consume casi todo lo que producen las placas; no hay un gran excedente que aprovechar.")
        else:
            partes.append("No veo producción solar relevante en el periodo analizado.")

        if r.get("hora_de_mas_consumo") is not None:
            partes.append(f"Tu hora de mayor consumo es sobre las {r['hora_de_mas_consumo']}:00 ({r['consumo_en_pico_w']} W de media).")

        return " ".join(partes)

    def _con_produccion_diaria(self, resultado):
        registros = self.db.produccion(14)

        if registros:
            ultimos = registros[-7:]
            resultado["produccion_diaria"] = {
                "media_7_dias_kwh": round(sum(r["produccion"] for r in ultimos) / len(ultimos), 1),
                "mejor_dia": max(registros, key=lambda r: r["produccion"]),
            }

        return resultado

    def momento_ahora(self, lectura):
        """Consejo inmediato según la lectura en directo (¿es buen momento de poner un aparato?)."""

        if not isinstance(lectura, dict) or not lectura.get("configurado") or lectura.get("error"):
            return None

        produccion, consumo = lectura.get("produccion_w"), lectura.get("consumo_w")

        if produccion is None or consumo is None:
            return None

        sobrante = produccion - consumo

        if sobrante >= 800:
            return f"Ahora sobran unos {round(sobrante)} W de sol: buen momento para poner la lavadora o el lavavajillas."

        if produccion < 100:
            return "Ahora mismo no hay sol: mejor esperar a las horas de más producción para los aparatos grandes."

        return "Las placas cubren poco más que el consumo actual; si puedes, espera a que sobre más sol."


# ----------------------------------------------------------------------
# Energía en tiempo real (inversor solar y contador, vía Home Assistant)
# ----------------------------------------------------------------------

import json
import time
from datetime import datetime, timedelta

from brain.core.config import Config
from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, leer_configuracion
from brain.modules.inventario import normalizar

ROLES = ("produccion", "consumo", "red", "bateria_pct")

NOMBRES_ROL = {
    "produccion": "producción solar (lo que generan las placas ahora)",
    "consumo": "consumo de la casa",
    "red": "intercambio con la red eléctrica",
    "bateria_pct": "carga de la batería (%)",
}

# Palabras que sugieren cada tipo de sensor y palabras que lo descartan
# (por ejemplo, los sensores de cada "string" de placas o de cada fase).
PISTAS = {
    "produccion": (
        ("solar", "pv", "fotovolt", "produc", "generac", "inversor", "inverter", "placas", "huawei", "fronius", "solaredge", "growatt", "solax", "goodwe"),
        ("total", "actual", "current", "potencia", "power", "ac", "salida", "output"),
    ),
    "consumo": (
        ("consumo", "consum", "casa", "hogar", "house", "home", "load", "carga", "demanda", "vivienda"),
        ("total", "actual", "current", "potencia", "power"),
    ),
    "red": (
        ("red", "grid", "import", "export", "contador", "meter", "feed", "compra", "venta", "acometida"),
        ("potencia", "power", "actual", "current", "total"),
    ),
}

DESCARTAR = ("mppt", "string", "pv1", "pv2", "pv3", "pv4", "fase", "phase", "l1", "l2", "l3", "voltage", "tension", "voltaje", "corriente", "current_a", "frecuencia", "frequency", "daily", "diaria", "today", "hoy", "limit", "limite", "maxima", "rated", "nominal")

UNIDADES_POTENCIA = {"w": 1.0, "kw": 1000.0, "mw": 1_000_000.0}

SEGUNDOS_CACHE_DETECCION = 60


def _archivo_inversor():
    return Config.DATOS / "energia" / "inversor.json"


def leer_sensores_energia():
    """Sensores elegidos por el usuario ({} si no hay)."""

    try:
        datos = json.loads(_archivo_inversor().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    return datos if isinstance(datos, dict) else {}


def guardar_sensores_energia(sensores):
    archivo = _archivo_inversor()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(sensores, indent=4, ensure_ascii=False), encoding="utf-8")


def _a_vatios(estado):
    """Valor de un sensor de potencia en vatios (None si no es un número)."""

    try:
        valor = float(estado.get("state"))
    except (TypeError, ValueError):
        return None

    unidad = str((estado.get("attributes") or {}).get("unit_of_measurement", "W")).strip().lower()

    return valor * UNIDADES_POTENCIA.get(unidad, 1.0)


def _es_potencia(estado):
    atributos = estado.get("attributes") or {}
    unidad = str(atributos.get("unit_of_measurement", "")).strip().lower()

    if unidad not in UNIDADES_POTENCIA:
        return False

    return estado.get("entity_id", "").startswith("sensor.")


def _puntuar(rol, texto):
    """Cuánto encaja un sensor (por su nombre) con un rol. 0 = nada."""

    palabras_clave, refuerzo = PISTAS[rol]

    if any(d in texto for d in DESCARTAR):
        return 0

    puntos = sum(2 for p in palabras_clave if p in texto)

    if not puntos:
        return 0

    return puntos + sum(1 for p in refuerzo if p in texto)


def detectar_sensores(estados):
    """
    Busca en Home Assistant los sensores que parecen del inversor, de la
    casa o del contador.

    Devuelve {rol: [candidatos]} con los mejores primero. Cada candidato es
    {entidad, nombre, valor_w}.
    """

    resultado = {rol: [] for rol in ROLES}

    for estado in estados:
        entidad = estado.get("entity_id", "")
        atributos = estado.get("attributes") or {}
        nombre = atributos.get("friendly_name") or entidad
        texto = normalizar(f"{nombre} {entidad}").replace("_", " ")

        if estado.get("state") in ("unavailable", "unknown", None):
            continue

        if _es_potencia(estado):
            vatios = _a_vatios(estado)

            if vatios is None:
                continue

            for rol in ("produccion", "consumo", "red"):
                puntos = _puntuar(rol, texto)

                if puntos:
                    resultado[rol].append({"entidad": entidad, "nombre": nombre, "valor_w": round(vatios), "_p": puntos})

        elif atributos.get("device_class") == "battery" or (
            entidad.startswith("sensor.") and str(atributos.get("unit_of_measurement", "")) == "%" and "bater" in texto
        ):
            if any(p in texto for p in ("bateria", "battery", "soc")) and "movil" not in texto and "phone" not in texto:
                resultado["bateria_pct"].append({"entidad": entidad, "nombre": nombre, "valor_w": None, "_p": 1})

    for rol in ROLES:
        resultado[rol].sort(key=lambda c: -c["_p"])

        for candidato in resultado[rol]:
            candidato.pop("_p", None)

        resultado[rol] = resultado[rol][:6]

    return resultado


class EnergiaTiempoReal:
    """Lectura en directo de producción, consumo y red desde Home Assistant."""

    def __init__(self):
        self._cliente = None
        self._deteccion = None
        self._deteccion_hasta = 0.0

    def _ha(self):
        url, token = leer_configuracion()

        if self._cliente is None or (self._cliente.url, self._cliente.token) != (url, token):
            self._cliente = HomeAssistant(url, token, timeout=8)
            self._deteccion = None

        return self._cliente

    def _sensores(self, ha):
        """Sensores a usar: los guardados o, si no hay, los detectados solos."""

        guardados = leer_sensores_energia()

        if any(guardados.get(rol) for rol in ROLES):
            return guardados, False

        ahora = time.time()

        if self._deteccion is None or ahora > self._deteccion_hasta:
            candidatos = detectar_sensores(ha.estados())
            self._deteccion = {rol: (c[0]["entidad"] if c else "") for rol, c in candidatos.items()}
            self._deteccion_hasta = ahora + SEGUNDOS_CACHE_DETECCION

        return self._deteccion, True

    def leer(self):
        """
        Estado actual de la energía de la casa.

        Devuelve siempre un diccionario; si algo falla, trae "error" o
        "configurado": False con una explicación.
        """

        ha = self._ha()

        if not ha.configurado:
            return {
                "configurado": False,
                "mensaje": "Conecta primero Home Assistant (CONFIGURAR_DOMOTICA.bat) para ver el inversor en tiempo real.",
            }

        try:
            sensores, automatico = self._sensores(ha)

            valores = {}

            for rol in ROLES:
                entidad = sensores.get(rol)

                if not entidad:
                    continue

                estado = ha.estado(entidad)

                if rol == "bateria_pct":
                    try:
                        valores[rol] = round(float(estado.get("state")))
                    except (TypeError, ValueError):
                        pass
                else:
                    vatios = _a_vatios(estado)

                    if vatios is not None:
                        valores[rol] = vatios

        except HomeAssistantError as error:
            return {"configurado": True, "error": str(error)}

        if not valores:
            return {
                "configurado": False,
                "mensaje": (
                    "No he encontrado el inversor en Home Assistant. Ejecuta CONFIGURAR_ENERGIA.bat para elegir "
                    "los sensores (primero tiene que aparecer el inversor en Home Assistant)."
                ),
            }

        produccion = valores.get("produccion")
        red = valores.get("red")

        if red is not None and sensores.get("red_invertida"):
            red = -red

        consumo = valores.get("consumo")
        calculado = False

        # Sin sensor de consumo: casa = lo que producen las placas + lo que se compra a la red.
        if consumo is None and produccion is not None and red is not None:
            consumo = max(0.0, produccion + red)
            calculado = True

        if red is None:
            estado_red = None
        elif red > 50:
            estado_red = "comprando"
        elif red < -50:
            estado_red = "vendiendo"
        else:
            estado_red = "equilibrio"

        resultado = {
            "configurado": True,
            "automatico": automatico,
            "produccion_w": None if produccion is None else round(produccion),
            "consumo_w": None if consumo is None else round(consumo),
            "consumo_calculado": calculado,
            "red_w": None if red is None else round(red),
            "estado_red": estado_red,
            "bateria_pct": valores.get("bateria_pct"),
            "hora": datetime.now().strftime("%H:%M:%S"),
        }

        if produccion is not None and consumo:
            resultado["cubierto_por_solar_pct"] = min(100, round(produccion * 100 / consumo)) if consumo > 0 else 0

        return resultado


def _formato_potencia(vatios):
    if vatios is None:
        return "sin dato"

    if abs(vatios) >= 1000:
        return f"{vatios / 1000:.2f} kW"

    return f"{vatios:.0f} W"


def describir(lectura):
    """Resumen en español de una lectura (para la IA y la consola)."""

    if not lectura.get("configurado") or "error" in lectura:
        return lectura.get("error") or lectura.get("mensaje", "No hay datos del inversor.")

    partes = []

    if lectura.get("produccion_w") is not None:
        partes.append(f"Las placas producen {_formato_potencia(lectura['produccion_w'])}")

    if lectura.get("consumo_w") is not None:
        partes.append(f"la casa consume {_formato_potencia(lectura['consumo_w'])}")

    red = lectura.get("red_w")

    if red is not None:
        if lectura["estado_red"] == "comprando":
            partes.append(f"se compran {_formato_potencia(red)} a la red")
        elif lectura["estado_red"] == "vendiendo":
            partes.append(f"se vierten {_formato_potencia(-red)} a la red")
        else:
            partes.append("no hay intercambio con la red")

    if lectura.get("bateria_pct") is not None:
        partes.append(f"batería al {lectura['bateria_pct']} %")

    texto = ", ".join(partes)

    return texto[:1].upper() + texto[1:] + "."
