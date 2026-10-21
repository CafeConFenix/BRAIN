from brain.modules.hogar import Hogar
from brain.modules.perfiles import Perfiles
from brain.tools.decorators import tool

hogar = Hogar()
perfiles = Perfiles()


@tool(
    descripcion="Crea una tarea del hogar que se repite con turnos entre personas (basura, fregar, bajar al perro...). Si ya existe, la actualiza.",
    categoria="hogar",
    argumentos={
        "nombre": "Nombre de la tarea, por ejemplo 'sacar la basura'",
        "personas": "Quién se turna, separado por comas: 'Ana, Luis, Marta'. Vacío si la hace cualquiera.",
        "cada_dias": "Cada cuántos días se repite (1 = diaria, 7 = semanal). Por defecto 7.",
        "empieza": "Primera fecha AAAA-MM-DD. Omitir si es hoy.",
    },
)
def crear_tarea_hogar(nombre: str, personas: str = "", cada_dias: int = 7, empieza: str = None):
    """Crea una tarea del hogar con turnos."""

    return {"tarea": hogar.crear(nombre, personas, cada_dias, empieza)}


@tool(
    descripcion="Lista las tareas del hogar con a quién le toca y cuándo. Úsala para '¿a quién le toca la basura?' o '¿qué tareas hay hoy?'.",
    categoria="hogar",
    argumentos={"solo_hoy": "true para ver solo las que tocan hoy", "persona": "Filtrar por persona (opcional)"},
)
def ver_tareas_hogar(solo_hoy: bool = False, persona: str = ""):
    """Lista las tareas del hogar."""

    lista = hogar.de_hoy(persona) if solo_hoy else hogar.listar()

    return {"tareas": lista} if lista else {"mensaje": "No hay tareas del hogar" + (" para hoy." if solo_hoy else " todavía.")}


@tool(
    descripcion="Apunta que una tarea del hogar ya está hecha; el turno pasa a la siguiente persona. Úsala para 'ya he sacado la basura'.",
    categoria="hogar",
    argumentos={"nombre": "Nombre de la tarea", "quien": "Quién la ha hecho (omitir si es a quien le tocaba)", "fecha": "AAAA-MM-DD. Omitir si es hoy."},
)
def tarea_hogar_hecha(nombre: str, quien: str = "", fecha: str = None):
    """Marca una tarea del hogar como hecha."""

    return {"hecha": hogar.hecha(nombre, quien, fecha)}


@tool(
    descripcion="Pasa el turno de una tarea del hogar a la siguiente persona sin hacerla (por ejemplo, si no puede).",
    categoria="hogar",
    argumentos={"nombre": "Nombre de la tarea"},
)
def saltar_turno_hogar(nombre: str):
    """Pasa el turno."""

    return {"tarea": hogar.saltar_turno(nombre)}


@tool(
    descripcion="Borra una tarea del hogar.",
    categoria="hogar",
    argumentos={"nombre": "Nombre de la tarea"},
)
def borrar_tarea_hogar(nombre: str):
    """Borra una tarea del hogar."""

    return {"borrada": hogar.borrar(nombre)}


@tool(
    descripcion="Añade una persona a la casa (para repartir tareas y hábitos). Sin argumentos, lista las personas.",
    categoria="hogar",
    argumentos={"nombre": "Nombre de la persona. Omitir para listarlas."},
)
def personas_casa(nombre: str = ""):
    """Gestiona las personas de la casa."""

    if nombre:
        perfiles.añadir(nombre)

    return {"personas": perfiles.nombres()}
