from brain.modules.perfiles import Perfiles
from brain.tools.decorators import tool

perfiles = Perfiles()


@tool(
    descripcion="Añade una persona a la casa para repartir hábitos, tareas y recordatorios (por ejemplo 'Ana').",
    categoria="hogar",
    argumentos={"nombre": "Nombre de la persona"},
)
def anadir_persona(nombre: str):
    """Añade una persona."""

    return {"personas": perfiles.añadir(nombre)}


@tool(descripcion="Lista las personas de la casa.", categoria="hogar")
def ver_personas():
    """Personas de la casa."""

    lista = perfiles.listar()

    return {"personas": lista} if lista else {"mensaje": "Todavía no hay personas. Puedo añadirlas para repartir tareas y hábitos."}


@tool(descripcion="Quita a una persona de la lista de la casa.", categoria="hogar", argumentos={"nombre": "Nombre de la persona"})
def quitar_persona(nombre: str):
    """Quita una persona."""

    return {"personas": perfiles.quitar(nombre)}
