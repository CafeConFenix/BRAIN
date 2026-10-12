from brain.modules.calendario import Calendario
from brain.tools.decorators import tool

calendario = Calendario()


@tool(
    descripcion="Apunta un evento o cita en el calendario.",
    categoria="calendario",
    argumentos={
        "titulo": "Qué es el evento, por ejemplo 'Dentista'",
        "fecha": "Fecha AAAA-MM-DD. Omitir si es hoy.",
        "hora": "Hora HH:MM en formato 24 horas (por ejemplo 18:30). Opcional.",
    },
)
def anadir_evento(titulo: str, fecha: str = None, hora: str = None):
    """Añade un evento al calendario."""

    return {"guardado": calendario.añadir_evento(titulo, fecha, hora)}


@tool(
    descripcion="Apunta una tarea pendiente (opcionalmente con fecha límite).",
    categoria="calendario",
    argumentos={
        "titulo": "Qué hay que hacer",
        "fecha": "Fecha límite AAAA-MM-DD. Opcional.",
    },
)
def anadir_tarea(titulo: str, fecha: str = None):
    """Añade una tarea."""

    return {"guardado": calendario.añadir_tarea(titulo, fecha)}


@tool(
    descripcion="Marca una tarea pendiente como hecha.",
    categoria="calendario",
    argumentos={"titulo": "Nombre (o parte del nombre) de la tarea"},
)
def completar_tarea(titulo: str):
    """Completa una tarea."""

    return {"completada": calendario.completar_tarea(titulo)}


@tool(
    descripcion="Muestra la agenda: eventos de los próximos días y tareas pendientes.",
    categoria="calendario",
    argumentos={"dias": "Cuántos días hacia delante mirar. Por defecto 7."},
)
def ver_agenda(dias: int = 7):
    """Muestra la agenda."""

    return calendario.agenda(dias)
