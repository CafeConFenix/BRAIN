from brain.modules.resumen import Resumen
from brain.tools.decorators import tool

resumen = Resumen()


@tool(
    descripcion=(
        "Da el resumen del día: agenda de hoy y mañana, tareas, recordatorios, lista de la compra, producción solar de "
        "ayer, alertas de sensores, garantías por caducar y peso. Úsala para '¿qué tengo hoy?' o 'dame el resumen'."
    ),
    categoria="resumen",
    argumentos={"enviar_como_aviso": "true para enviarlo también como notificación"},
)
def ver_resumen_diario(enviar_como_aviso: bool = False):
    """Resumen del día."""

    datos = resumen.enviar() if enviar_como_aviso else resumen.componer()

    return {"titulo": datos["titulo"], "resumen": datos["texto"]}


@tool(
    descripcion=(
        "Configura el resumen diario automático: la hora a la que llega cada mañana o desactivarlo. "
        "Ejemplo: 'mándame el resumen a las 7:45'."
    ),
    categoria="resumen",
    argumentos={
        "hora": "Hora HH:MM, por ejemplo 08:30",
        "activo": "false para desactivar el resumen diario, true para activarlo",
    },
)
def configurar_resumen_diario(hora: str = None, activo: bool = None):
    """Configura el resumen diario."""

    try:
        return {"configuracion": resumen.configurar(activo, hora)}
    except ValueError as error:
        return {"error": str(error)}
