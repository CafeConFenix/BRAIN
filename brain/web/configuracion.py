"""
Configuración desde la propia web: asistente de primer uso (Home Assistant y
energía) y elección de los dispositivos de domótica que se quieren ver.

Es lo mismo que hacían CONFIGURAR_DOMOTICA.bat y CONFIGURAR_ENERGIA.bat, pero
con pantallas en vez de preguntas en una consola. La llave de Home Assistant
nunca se devuelve a la web.
"""

import json
from pathlib import Path

from brain.core.config import Config
from brain.integrations.home_assistant import (
    HomeAssistant,
    HomeAssistantError,
    encontrar_home_assistant,
    guardar_configuracion,
    leer_configuracion,
    normalizar_url,
)
from brain.modules.energia import (
    NOMBRES_ROL,
    ROLES,
    EnergiaTiempoReal,
    _a_vatios,
    _es_potencia,
    describir,
    detectar_sensores,
    guardar_sensores_energia,
    leer_sensores_energia,
)

# Rutas que solo se atienden desde el propio ordenador (tocan la llave de Home Assistant).
SOLO_LOCAL = (
    "/api/config/estado",
    "/api/config/ha/buscar",
    "/api/config/ha/guardar",
    "/api/config/energia",
    "/api/config/energia/guardar",
    "/api/config/omitir",
)

RUTAS_GET = ("/api/config/estado", "/api/config/energia", "/api/config/dispositivos")
RUTAS_POST = (
    "/api/config/ha/buscar",
    "/api/config/ha/guardar",
    "/api/config/energia/guardar",
    "/api/config/omitir",
    "/api/config/dispositivos/guardar",
)

NOMBRES_DOMINIO = (
    ("light", "luces"),
    ("switch", "enchufes e interruptores"),
    ("cover", "persianas y cortinas"),
    ("climate", "termostatos"),
    ("scene", "escenas"),
    ("media_player", "reproductores"),
)


def _archivo() -> Path:
    return Path(Config.DATOS) / "asistente.json"


def asistente_visto() -> bool:
    try:
        return bool(json.loads(_archivo().read_text(encoding="utf-8")).get("visto"))
    except (OSError, ValueError, AttributeError):
        return False


def marcar_asistente_visto(visto=True) -> None:
    _archivo().parent.mkdir(parents=True, exist_ok=True)
    _archivo().write_text(json.dumps({"visto": bool(visto)}), encoding="utf-8")


def sensores_guardados() -> dict:
    return {rol: leer_sensores_energia().get(rol, "") for rol in ROLES}


def estado_configuracion() -> dict:
    url, token = leer_configuracion()
    conectada = bool(url and token)
    energia = leer_sensores_energia()

    return {
        "ha": {"configurado": conectada, "url": url, "token_guardado": bool(token)},
        "energia": {"configurada": any(energia.get(rol) for rol in ROLES), "sensores": sensores_guardados()},
        "asistente_visto": asistente_visto(),
        # El asistente aparece solo la primera vez, mientras no haya nada configurado.
        "primera_vez": not conectada and not asistente_visto(),
    }


def buscar_ha() -> dict:
    return {"encontrada": encontrar_home_assistant()}


def guardar_ha(url, token) -> dict:
    """Prueba la conexión y, si funciona, guarda la dirección y la llave."""

    url = normalizar_url(url)

    if not url:
        raise ValueError("Escribe la dirección de Home Assistant (por ejemplo 192.168.1.50:8123).")

    token = (token or "").strip() or leer_configuracion()[1]

    if not token:
        raise ValueError("Pega la llave de acceso (token) de Home Assistant.")

    cliente = HomeAssistant(url, token, timeout=10)
    cliente.comprobar()
    estados = cliente.estados()
    guardar_configuracion(url, token)

    cuentas = {}

    for estado in estados:
        dominio = estado.get("entity_id", "").split(".", 1)[0]
        cuentas[dominio] = cuentas.get(dominio, 0) + 1

    return {
        "ok": True,
        "url": url,
        "resumen": [{"tipo": nombre, "total": cuentas[dominio]} for dominio, nombre in NOMBRES_DOMINIO if cuentas.get(dominio)],
        "energia_detectada": bool(detectar_sensores(estados)["produccion"]),
    }


def _potencias(estados) -> list:
    lista = [
        {
            "entidad": e["entity_id"],
            "nombre": (e.get("attributes") or {}).get("friendly_name", e["entity_id"]),
            "valor_w": round(_a_vatios(e)),
        }
        for e in estados
        if _es_potencia(e) and _a_vatios(e) is not None
    ]

    return sorted(lista, key=lambda p: p["nombre"].lower())


def candidatos_energia() -> dict:
    ha = HomeAssistant()

    if not ha.configurado:
        raise HomeAssistantError("Primero conecta Home Assistant.")

    estados = ha.estados()
    candidatos = detectar_sensores(estados)
    elegidos = sensores_guardados()

    return {
        "roles": [
            {"rol": rol, "nombre": NOMBRES_ROL[rol], "candidatos": candidatos[rol], "elegido": elegidos.get(rol, "")}
            for rol in ROLES
        ],
        "potencias": _potencias(estados),
        "red_invertida": bool(leer_sensores_energia().get("red_invertida")),
    }


def guardar_energia(datos) -> dict:
    ha = HomeAssistant()

    if not ha.configurado:
        raise HomeAssistantError("Primero conecta Home Assistant.")

    estados = {e.get("entity_id"): e for e in ha.estados()}
    elegidos = {}

    for rol in ROLES:
        entidad = str(datos.get(rol) or "").strip()

        if not entidad:
            continue

        estado = estados.get(entidad)

        if estado is None:
            raise ValueError(f"Home Assistant no tiene el sensor {entidad}.")

        if rol != "bateria_pct" and (not _es_potencia(estado) or _a_vatios(estado) is None):
            raise ValueError(f"{entidad} no es un sensor de potencia (W o kW).")

        elegidos[rol] = entidad

    if not elegidos:
        raise ValueError("Elige al menos un sensor.")

    # El signo del sensor de red depende del aparato: se averigua con lo que el usuario ve ahora.
    ahora = str(datos.get("red_ahora") or "").strip().lower()

    if elegidos.get("red") and ahora in ("comprando", "vendiendo"):
        actual = _a_vatios(estados[elegidos["red"]])

        if actual is not None and abs(actual) > 50:
            if (ahora == "comprando" and actual < 0) or (ahora == "vendiendo" and actual > 0):
                elegidos["red_invertida"] = True
    elif datos.get("red_invertida") and elegidos.get("red"):
        elegidos["red_invertida"] = True

    guardar_sensores_energia(elegidos)

    return {"ok": True, "lectura": describir(EnergiaTiempoReal().leer())}


def dispositivos(brain) -> dict:
    domotica = brain.modules.obtener("domotica")

    if domotica is None or not domotica.conectado():
        return {"conectado": False, "grupos": [], "total": 0, "ocultos": 0}

    return {"conectado": True, **domotica.dispositivos_configurables()}


def guardar_dispositivos(brain, datos) -> dict:
    domotica = brain.modules.obtener("domotica")

    if domotica is None:
        raise ValueError("La domótica no está disponible.")

    ocultos = datos.get("ocultos")

    if not isinstance(ocultos, list):
        raise ValueError("Falta la lista de dispositivos ocultos.")

    guardados = domotica.guardar_ocultos(ocultos)

    return {"ok": True, "ocultos": len(guardados)}


def manejar(brain, metodo, ruta, datos, local):
    """
    Atiende una ruta de configuración. Devuelve (código, respuesta), o None si
    la ruta no es de este módulo.
    """

    if ruta not in (RUTAS_GET if metodo == "GET" else RUTAS_POST):
        return None

    if ruta in SOLO_LOCAL and not local:
        return 403, {"error": "Esto solo se configura desde el ordenador de casa."}

    try:
        if ruta == "/api/config/estado":
            return 200, estado_configuracion()

        if ruta == "/api/config/ha/buscar":
            return 200, buscar_ha()

        if ruta == "/api/config/ha/guardar":
            return 200, guardar_ha(datos.get("url"), datos.get("token"))

        if ruta == "/api/config/energia" and metodo == "GET":
            return 200, candidatos_energia()

        if ruta == "/api/config/energia/guardar":
            return 200, guardar_energia(datos)

        if ruta == "/api/config/omitir":
            marcar_asistente_visto(True)

            return 200, {"ok": True}

        if ruta == "/api/config/dispositivos":
            return 200, dispositivos(brain)

        if ruta == "/api/config/dispositivos/guardar":
            return 200, guardar_dispositivos(brain, datos)

    except HomeAssistantError as error:
        return 502, {"error": str(error)}

    except ValueError as error:
        return 400, {"error": str(error)}

    return None
