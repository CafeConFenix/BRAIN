from brain.modules.avisos import Avisos
from brain.tools.decorators import tool

avisos = Avisos()


def _error(error):
    return {"error": str(error)}


@tool(
    descripcion=(
        "Programa un recordatorio que sonará como notificación a su hora. Úsala para 'recuérdame en 20 minutos "
        "sacar el pollo' o 'avísame mañana a las 9:00 de llamar al médico'. Indica en_minutos O fecha_hora."
    ),
    categoria="avisos",
    argumentos={
        "mensaje": "Qué hay que recordar",
        "en_minutos": "Minutos desde ahora. Omitir si das fecha_hora.",
        "fecha_hora": "AAAA-MM-DD HH:MM, o solo HH:MM (hoy, o mañana si ya pasó). Omitir si das en_minutos.",
    },
)
def crear_recordatorio(mensaje: str, en_minutos: float = None, fecha_hora: str = None):
    """Programa un recordatorio."""

    try:
        return {"programado": avisos.crear_recordatorio(mensaje, en_minutos, fecha_hora)}
    except ValueError as error:
        return _error(error)


@tool(descripcion="Muestra los recordatorios pendientes.", categoria="avisos")
def ver_recordatorios():
    """Lista los recordatorios pendientes."""

    pendientes = avisos.recordatorios()

    if not pendientes:
        return {"mensaje": "No hay recordatorios pendientes."}

    return {"recordatorios": pendientes}


@tool(
    descripcion="Cancela un recordatorio pendiente por su número (el id que da ver_recordatorios).",
    categoria="avisos",
    argumentos={"id": "Número del recordatorio"},
)
def cancelar_recordatorio(id: int):
    """Cancela un recordatorio."""

    if not avisos.borrar_recordatorio(id):
        return {"error": f"No hay ningún recordatorio pendiente con el número {id}."}

    return {"cancelado": id}


@tool(
    descripcion="Muestra los avisos recibidos (alertas, recordatorios, resúmenes). Por defecto solo los no leídos.",
    categoria="avisos",
    argumentos={"todos": "true para ver también los ya leídos"},
)
def ver_avisos(todos: bool = False):
    """Lista los avisos."""

    lista = avisos.listar(solo_no_leidos=not todos, limite=20)

    if not lista:
        return {"mensaje": "No hay avisos nuevos."}

    return {"avisos": [{k: a[k] for k in ("fecha", "tipo", "titulo", "mensaje", "nivel")} for a in lista]}


@tool(descripcion="Marca todos los avisos como leídos.", categoria="avisos")
def marcar_avisos_leidos():
    """Marca los avisos como leídos."""

    return {"marcados": avisos.marcar_leidos()}


@tool(
    descripcion=(
        "Muestra los sonidos disponibles para los avisos y cuál tiene cada tipo. El usuario añade sus sonidos "
        "(.wav, .mp3, .ogg) copiándolos en la carpeta que se indica."
    ),
    categoria="avisos",
)
def ver_sonidos():
    """Lista los sonidos de avisos."""

    return avisos.ver_sonidos()


@tool(
    descripcion=(
        "Asigna un sonido a un tipo de aviso (alerta, recordatorio, resumen, automatizacion, energia, info). "
        "Con archivo 'ninguno' vuelve al sonido por defecto."
    ),
    categoria="avisos",
    argumentos={
        "tipo": "alerta, recordatorio, resumen, automatizacion, energia o info",
        "archivo": "Nombre del sonido, por ejemplo 'campana.wav'",
    },
)
def asignar_sonido(tipo: str, archivo: str):
    """Asigna un sonido a un tipo de aviso."""

    try:
        return {"asignado": avisos.asignar_sonido(tipo, archivo)}
    except ValueError as error:
        return _error(error)


@tool(
    descripcion=(
        "Ajusta los avisos: silenciarlos del todo, activar o desactivar las notificaciones de Windows, o la franja de "
        "'no molestar' (solo suenan las alertas críticas). Para quitar la franja usa 'ninguno'."
    ),
    categoria="avisos",
    argumentos={
        "silencio": "true para silenciar todos los avisos, false para activarlos",
        "notificaciones_windows": "true/false para las notificaciones y sonidos de Windows",
        "no_molestar_desde": "Hora HH:MM de inicio, por ejemplo 23:00, o 'ninguno'",
        "no_molestar_hasta": "Hora HH:MM de fin, por ejemplo 07:00",
    },
)
def configurar_avisos(
    silencio: bool = None,
    notificaciones_windows: bool = None,
    no_molestar_desde: str = None,
    no_molestar_hasta: str = None,
):
    """Configura los avisos."""

    try:
        return {"configuracion": avisos.configurar(silencio, notificaciones_windows, no_molestar_desde, no_molestar_hasta)}
    except ValueError as error:
        return _error(error)


@tool(
    descripcion="Envía un aviso de prueba para que el usuario compruebe la notificación y el sonido.",
    categoria="avisos",
    argumentos={"tipo": "Tipo de aviso a probar (por defecto info)"},
)
def probar_aviso(tipo: str = "info"):
    """Envía un aviso de prueba."""

    try:
        return {"enviado": avisos.avisar("Aviso de prueba", "Si ves y oyes esto, los avisos funcionan.", tipo=tipo)}
    except ValueError as error:
        return _error(error)
