from brain.modules.habitos import Habitos
from brain.tools.decorators import tool

habitos = Habitos()


@tool(
    descripcion="Crea un hábito diario con objetivo (beber agua, tomar una pastilla, pasear...). Si ya existe, cambia su objetivo.",
    categoria="habitos",
    argumentos={
        "nombre": "Nombre del hábito, por ejemplo 'beber agua'",
        "objetivo": "Veces o cantidad por día para cumplirlo (por defecto 1), por ejemplo 8",
        "unidad": "Unidad opcional, por ejemplo 'vasos' o 'minutos'",
        "hora": "Hora HH:MM a la que BRAIN avisa si aún no se ha cumplido (opcional)",
        "persona": "Persona a la que pertenece el hábito (opcional)",
    },
)
def crear_habito(nombre: str, objetivo: int = 1, unidad: str = "", hora: str = "", persona: str = ""):
    """Crea un hábito."""

    return {"habito": habitos.crear(nombre, objetivo, unidad, hora, persona)}


@tool(
    descripcion="Apunta que se ha hecho un hábito hoy (o en otra fecha). Úsala para 'me he bebido un vaso de agua' o 'ya me he tomado la pastilla'. Devuelve el progreso del día y la racha.",
    categoria="habitos",
    argumentos={
        "nombre": "Nombre del hábito",
        "cantidad": "Cuánto se ha hecho (por defecto 1; negativo para corregir)",
        "fecha": "AAAA-MM-DD. Omitir si es hoy.",
    },
)
def anotar_habito(nombre: str, cantidad: int = 1, fecha: str = None):
    """Apunta un hábito."""

    return habitos.anotar(nombre, cantidad, fecha)


@tool(
    descripcion="Muestra los hábitos del día: progreso, si están cumplidos y la racha de días seguidos. Úsala para '¿cómo voy con mis hábitos?'.",
    categoria="habitos",
    argumentos={"fecha": "AAAA-MM-DD. Omitir para hoy."},
)
def ver_habitos(fecha: str = None):
    """Progreso de los hábitos."""

    resultado = habitos.estado(fecha)

    if not resultado["total"]:
        return {"mensaje": "Todavía no hay hábitos. Puedes crear uno, por ejemplo 'beber agua' con objetivo 8."}

    return resultado


@tool(
    descripcion="Borra un hábito y todo su historial.",
    categoria="habitos",
    argumentos={"nombre": "Nombre del hábito"},
)
def borrar_habito(nombre: str):
    """Borra un hábito."""

    return {"borrado": habitos.borrar(nombre)}
