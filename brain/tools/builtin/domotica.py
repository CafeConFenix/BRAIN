from brain.modules.domotica import Domotica
from brain.integrations.home_assistant import HomeAssistantError
from brain.tools.decorators import tool

domotica = Domotica()

NOMBRE = "Nombre del aparato o habitación, como lo diría el usuario. Ejemplos: 'luz del salón', 'persiana del dormitorio', 'enchufe de la tele', 'luces de la cocina'."
TODOS = "true solo si el usuario quiere TODOS los aparatos que encajen (por ejemplo 'todas las luces del salón'). Por defecto false."


def _seguro(funcion, *args, **kwargs):
    """Convierte los errores de Home Assistant en un mensaje para la IA."""

    try:
        return funcion(*args, **kwargs)
    except HomeAssistantError as error:
        return {"error": str(error)}


@tool(
    descripcion=(
        "Enciende un aparato de la casa (luz, enchufe, ventilador, televisión...). "
        "En una persiana o cortina la abre. También activa una escena."
    ),
    categoria="domotica",
    argumentos={"dispositivo": NOMBRE, "todos": TODOS},
)
def encender(dispositivo: str, todos: bool = False):
    """Enciende un aparato."""

    return _seguro(domotica.encender, dispositivo, todos)


@tool(
    descripcion=(
        "Apaga un aparato de la casa (luz, enchufe, ventilador, televisión, calefacción...). "
        "En una persiana o cortina la cierra."
    ),
    categoria="domotica",
    argumentos={"dispositivo": NOMBRE, "todos": TODOS},
)
def apagar(dispositivo: str, todos: bool = False):
    """Apaga un aparato."""

    return _seguro(domotica.apagar, dispositivo, todos)


@tool(
    descripcion="Cambia el brillo, el color o la temperatura de color de una luz (y la enciende si estaba apagada).",
    categoria="domotica",
    argumentos={
        "dispositivo": NOMBRE,
        "brillo": "Brillo de 1 a 100 (porcentaje). Opcional.",
        "color": "Color: rojo, verde, azul, amarillo, naranja, rosa, morado, violeta, lila, cian, turquesa o blanco. Opcional.",
        "temperatura": "Tono de la luz blanca: calida, neutra o fria. Opcional.",
        "todos": TODOS,
    },
)
def regular_luz(dispositivo: str, brillo: float = None, color: str = None, temperatura: str = None, todos: bool = False):
    """Regula una luz."""

    return _seguro(domotica.regular_luz, dispositivo, brillo, color, temperatura, todos)


@tool(
    descripcion="Pone una persiana, cortina o toldo en una posición concreta (0 = cerrada, 100 = abierta del todo).",
    categoria="domotica",
    argumentos={"dispositivo": NOMBRE, "posicion": "Porcentaje de apertura de 0 a 100.", "todos": TODOS},
)
def mover_persiana(dispositivo: str, posicion: float, todos: bool = False):
    """Posiciona una persiana."""

    return _seguro(domotica.posicion_persiana, dispositivo, posicion, todos)


@tool(
    descripcion="Fija la temperatura de un termostato, aire acondicionado o calefacción.",
    categoria="domotica",
    argumentos={"dispositivo": NOMBRE, "grados": "Temperatura deseada en grados centígrados (5 a 35).", "todos": TODOS},
)
def poner_temperatura(dispositivo: str, grados: float, todos: bool = False):
    """Fija una temperatura."""

    return _seguro(domotica.poner_temperatura, dispositivo, grados, todos)


@tool(
    descripcion="Activa una escena o un script de la casa (por ejemplo 'noche', 'cine', 'salgo de casa').",
    categoria="domotica",
    argumentos={"escena": "Nombre de la escena tal y como la dice el usuario."},
)
def activar_escena(escena: str):
    """Activa una escena."""

    return _seguro(domotica.activar_escena, escena)


@tool(
    descripcion=(
        "Lista los aparatos de la casa y su estado actual (luces encendidas, persianas, termostatos, sensores...). "
        "Úsala para saber qué luces hay encendidas o qué aparatos existen."
    ),
    categoria="domotica",
    argumentos={
        "tipo": "Tipo de aparato: luces, enchufes, persianas, termostatos, sensores, escenas... Opcional.",
        "habitacion": "Habitación para filtrar, por ejemplo 'salón'. Opcional.",
    },
)
def ver_dispositivos(tipo: str = "", habitacion: str = ""):
    """Lista aparatos y su estado."""

    return _seguro(domotica.listar, tipo, habitacion)


@tool(
    descripcion="Consulta el estado de un aparato o sensor concreto (si una luz está encendida, la temperatura de una habitación, si una ventana está abierta...).",
    categoria="domotica",
    argumentos={"dispositivo": NOMBRE},
)
def estado_dispositivo(dispositivo: str):
    """Estado de un aparato."""

    return _seguro(domotica.estado_de, dispositivo)
