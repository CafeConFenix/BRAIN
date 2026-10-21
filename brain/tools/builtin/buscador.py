from brain.core.module_loader import ModuleLoader
from brain.utils.buscador import buscar_todo
from brain.tools.decorators import tool

_modulos = None


@tool(
    descripcion="Busca una palabra en TODO a la vez: despensa, lista de la compra, agenda, gastos, manuales, tareas del hogar y recuerdos. Úsala para '¿dónde puse...?' o 'busca la garantía de la lavadora'.",
    categoria="buscar",
    argumentos={"texto": "Qué buscar, por ejemplo 'lavadora' o 'wifi'"},
)
def buscar_en_todo(texto: str):
    """Búsqueda global."""

    global _modulos

    if _modulos is None:
        _modulos = ModuleLoader()

    return buscar_todo(_modulos, texto)
