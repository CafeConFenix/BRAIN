"""
Rutas de la web para lo que se hace "en casa": presupuesto, caducidades, hábitos,
tareas del hogar con turnos, personas, menú semanal, botones Salgo/Buenas noches,
coste de la luz, búsqueda global, manuales y copia en un segundo sitio.

`manejar` devuelve (código, respuesta) o None si la ruta no es de aquí.
"""

from urllib.parse import parse_qs, urlparse

from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.sistema import CopiaError
from brain.utils.buscador import buscar_todo

SOLO_LOCAL = ("/api/copia/destino", "/api/copia/traer", "/api/rutina/apagar")

RUTAS_GET = (
    "/api/presupuesto",
    "/api/caducidades",
    "/api/habitos",
    "/api/hogar",
    "/api/menu",
    "/api/rutina",
    "/api/buscar",
    "/api/documentos",
    "/api/energia/coste",
    "/api/copia/estado",
)

RUTAS_POST = (
    "/api/presupuesto/guardar",
    "/api/inventario/caducidad",
    "/api/habitos/crear",
    "/api/habitos/anotar",
    "/api/habitos/borrar",
    "/api/hogar/crear",
    "/api/hogar/hecha",
    "/api/hogar/saltar",
    "/api/hogar/borrar",
    "/api/personas/anadir",
    "/api/personas/borrar",
    "/api/menu/guardar",
    "/api/menu/compra",
    "/api/menu/vaciar",
    "/api/rutina/apagar",
    "/api/documentos/borrar",
    "/api/energia/tarifa",
    "/api/copia/destino",
    "/api/copia/traer",
)


def _consulta(camino, clave, defecto=None):
    return parse_qs(urlparse(camino).query).get(clave, [defecto])[0]


def _estado_copias(brain) -> dict:
    sistema = brain.modules.obtener("sistema")

    return {
        "destino": sistema.destino_extra(),
        "sugeridos": sistema.destinos_sugeridos(),
        "copias": sistema.listar_copias(),
        "copias_destino": sistema.copias_en_destino(),
    }


def _hogar(brain) -> dict:
    hogar = brain.modules.obtener("hogar")
    perfiles = brain.modules.obtener("perfiles")

    return {"tareas": hogar.listar(), "personas": perfiles.nombres()}


def manejar(brain, metodo, camino, datos, local):
    ruta = urlparse(camino).path

    if ruta not in (RUTAS_GET if metodo == "GET" else RUTAS_POST):
        return None

    if ruta in SOLO_LOCAL and not local:
        return 403, {"error": "Esto solo se hace desde el ordenador de casa."}

    m = brain.modules.obtener

    try:
        if metodo == "GET":
            if ruta == "/api/presupuesto":
                return 200, m("gastos").estado_presupuesto(_consulta(camino, "mes"))

            if ruta == "/api/caducidades":
                return 200, {"productos": m("inventario").por_caducar(int(_consulta(camino, "dias", "5") or 5))}

            if ruta == "/api/habitos":
                return 200, {**m("habitos").estado(persona=_consulta(camino, "persona", "")), "personas": m("perfiles").nombres()}

            if ruta == "/api/hogar":
                return 200, _hogar(brain)

            if ruta == "/api/menu":
                return 200, {**m("menu").ver(), "faltan": [{"nombre": n, "cantidad": c} for n, c in m("menu").faltan()]}

            if ruta == "/api/rutina":
                return 200, m("rutinas").revisar(_consulta(camino, "tipo", "salgo"))

            if ruta == "/api/buscar":
                return 200, buscar_todo(brain.modules, _consulta(camino, "q", ""))

            if ruta == "/api/documentos":
                return 200, {"documentos": m("documentos").listar()}

            if ruta == "/api/energia/coste":
                energia = m("energia")

                return 200, {"mes": energia.coste_mes(_consulta(camino, "mes")), "comparacion": energia.comparar_meses(), "tarifa": energia.tarifa(), "horas_baratas": energia.horas_baratas()}

            if ruta == "/api/copia/estado":
                return 200, _estado_copias(brain)

        # ------------------------------------------------------------ POST
        if ruta == "/api/presupuesto/guardar":
            m("gastos").configurar_presupuesto(datos.get("total"), datos.get("categoria", ""), datos.get("limite"))

            return 200, m("gastos").estado_presupuesto()

        if ruta == "/api/inventario/caducidad":
            return 200, {"actualizado": m("inventario").poner_caducidad(datos.get("nombre", ""), datos.get("fecha", ""))}

        if ruta == "/api/habitos/crear":
            return 200, {"habito": m("habitos").crear(datos.get("nombre"), datos.get("objetivo", 1), datos.get("unidad", ""), datos.get("hora", ""), datos.get("persona", ""))}

        if ruta == "/api/habitos/anotar":
            return 200, {"estado": m("habitos").anotar(datos.get("nombre"), datos.get("cantidad", 1))}

        if ruta == "/api/habitos/borrar":
            return 200, {"borrado": m("habitos").borrar(datos.get("nombre"))}

        if ruta == "/api/hogar/crear":
            return 200, {"tarea": m("hogar").crear(datos.get("nombre"), datos.get("personas", ""), datos.get("cada_dias", 7), datos.get("empieza") or None)}

        if ruta == "/api/hogar/hecha":
            return 200, {"tarea": m("hogar").hecha(datos.get("nombre"), datos.get("quien", ""))}

        if ruta == "/api/hogar/saltar":
            return 200, {"tarea": m("hogar").saltar_turno(datos.get("nombre"))}

        if ruta == "/api/hogar/borrar":
            return 200, {"borrada": m("hogar").borrar(datos.get("nombre"))}

        if ruta == "/api/personas/anadir":
            m("perfiles").añadir(datos.get("nombre"))

            return 200, _hogar(brain)

        if ruta == "/api/personas/borrar":
            m("perfiles").borrar(datos.get("nombre"))

            return 200, _hogar(brain)

        if ruta == "/api/menu/guardar":
            return 200, m("menu").guardar(datos.get("texto", ""))

        if ruta == "/api/menu/compra":
            return 200, m("menu").añadir_faltantes_a_compra()

        if ruta == "/api/menu/vaciar":
            return 200, {"borrados": m("menu").vaciar()}

        if ruta == "/api/rutina/apagar":
            return 200, m("rutinas").apagar(datos.get("entidades") or [])

        if ruta == "/api/documentos/borrar":
            return 200, {"borrado": m("documentos").borrar(datos.get("nombre", ""))}

        if ruta == "/api/energia/tarifa":
            energia = m("energia")

            if datos.get("compra") not in (None, "") or datos.get("venta") not in (None, ""):
                energia.configurar_tarifa(datos.get("compra"), datos.get("venta"))

            if datos.get("valle_desde") or datos.get("valle_hasta") or datos.get("valle_precio") not in (None, ""):
                energia.configurar_horas_baratas(datos.get("valle_desde"), datos.get("valle_hasta"), datos.get("valle_precio"))

            return 200, {"tarifa": energia.tarifa()}

        if ruta == "/api/copia/destino":
            m("sistema").configurar_destino(datos.get("ruta", ""))

            return 200, _estado_copias(brain)

        if ruta == "/api/copia/traer":
            m("sistema").traer_copia_del_destino(datos.get("nombre", ""))

            return 200, _estado_copias(brain)

    except HomeAssistantError as error:
        return 502, {"error": str(error)}

    except CopiaError as error:
        return 400, {"error": str(error)}

    except ValueError as error:
        return 400, {"error": str(error)}

    except Exception as error:
        # DocumentoError y similares heredan de ValueError; esto es lo imprevisto.
        from brain.core import logger

        logger.error(f"Web {ruta}: {error!r}")

        return 500, {"error": f"Error inesperado: {error}"}

    return None
