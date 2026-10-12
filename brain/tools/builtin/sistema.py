from brain.modules.sistema import CopiaError, Sistema
from brain.tools.decorators import tool

sistema = Sistema()


@tool(
    descripcion=(
        "Crea una copia de seguridad (ZIP) de todos los datos de BRAIN: despensa, compra, peso, "
        "memoria, agenda, energía, documentos... Se guardan solo las 5 últimas."
    ),
    categoria="sistema",
)
def crear_copia_seguridad():
    """Crea una copia de seguridad de datos/."""

    return {"copia": sistema.crear_copia()}


@tool(
    descripcion="Lista las copias de seguridad disponibles, de la más reciente a la más antigua.",
    categoria="sistema",
)
def ver_copias_seguridad():
    """Lista las copias de seguridad."""

    copias = sistema.listar_copias()

    if not copias:
        return {"mensaje": "Todavía no hay copias de seguridad."}

    return {"copias": copias}


@tool(
    descripcion=(
        "Restaura los datos de BRAIN desde una copia de seguridad, tras comprobar que no está dañada. "
        "Sustituye los datos actuales (antes guarda una copia de seguridad previa por si hay que volver atrás). "
        "Pide confirmación al usuario antes de usarla."
    ),
    categoria="sistema",
    argumentos={
        "nombre": "Nombre de la copia (backup_AAAAMMDD_HHMMSS.zip). Omitir o 'ultima' para la más reciente.",
    },
)
def restaurar_copia_seguridad(nombre: str = None):
    """Restaura una copia de seguridad."""

    try:
        return {"restaurado": sistema.restaurar_copia(nombre)}
    except CopiaError as error:
        return {"error": str(error)}
