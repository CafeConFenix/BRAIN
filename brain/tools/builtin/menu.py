from brain.modules.menu import Menu
from brain.tools.decorators import tool

_menu = Menu()


@tool(
    descripcion=(
        "Guarda el menú semanal que has pensado (comidas y cenas) y apunta en la lista de la compra SOLO lo que falta en casa. "
        "Antes de llamarla, mira la despensa (ver_inventario / ver_caducidades) y piensa los platos tú mismo; no preguntes al usuario qué quiere salvo que lo pida."
    ),
    categoria="menu",
    argumentos={
        "platos": (
            "Una línea por plato con este formato: 'lunes comida: Lentejas | lentejas, chorizo, zanahoria'. "
            "Días lunes a domingo, comida o cena (por defecto comida), ingredientes tras la barra."
        ),
        "comprar_faltantes": "true para apuntar en la compra lo que falta (por defecto true)",
    },
)
def guardar_menu_semanal(platos: str, comprar_faltantes: bool = True):
    """Guarda el menú de la semana."""

    resultado = _menu.guardar(platos)

    if comprar_faltantes:
        resultado["compra"] = _menu.añadir_faltantes_a_compra()

    return resultado


@tool(
    descripcion="Muestra el menú semanal guardado. Úsala para '¿qué toca cenar hoy?' o '¿qué hay en el menú?'.",
    categoria="menu",
)
def ver_menu_semanal():
    """Menú de la semana."""

    resultado = _menu.ver()

    return resultado if resultado["total_platos"] else {"mensaje": "No hay menú semanal. Puedo prepararlo con lo que tienes en casa."}


@tool(
    descripcion="Apunta en la lista de la compra los ingredientes del menú semanal que faltan en casa.",
    categoria="menu",
)
def comprar_lo_del_menu():
    """Añade a la compra lo que falta del menú."""

    return _menu.añadir_faltantes_a_compra()
