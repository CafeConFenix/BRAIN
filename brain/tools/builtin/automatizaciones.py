from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.automatizaciones import Automatizaciones
from brain.tools.decorators import tool

automatizaciones = Automatizaciones()


@tool(
    descripcion=(
        "Crea una automatización: una regla 'si pasa esto, haz aquello' que BRAIN vigila solo. "
        "disparador 'hora': cada día (o ciertos días) a una hora ('enciende la luz del salón a las 20:00'). "
        "disparador 'sensor': cuando un sensor o aparato de la casa cumple una condición ('si la temperatura del salón "
        "baja de 18, avísame'). disparador 'energia': cuando la producción, el consumo, la red (W), el sobrante solar (W) "
        "o la batería (%) cumplen una condición ('cuando sobren más de 1500 W avísame para poner la lavadora'). "
        "accion: 'aviso' (notificación con sonido), 'encender', 'apagar' o 'escena'. Nunca controla cerraduras, garajes ni alarmas. "
        "Antes de crearla, resume al usuario la regla que has entendido."
    ),
    categoria="automatizaciones",
    argumentos={
        "nombre": "Nombre corto de la automatización, por ejemplo 'Luz del salón por la noche'",
        "disparador": "hora, sensor o energia",
        "hora": "Solo para 'hora': HH:MM, por ejemplo 20:00",
        "dias": "Solo para 'hora': 'todos' (por defecto), 'laborables', 'fin de semana' o nombres como 'lunes, jueves'",
        "sensor": "Solo para 'sensor': sensor o aparato a vigilar, como lo diría el usuario, por ejemplo 'temperatura del salón'",
        "magnitud": "Solo para 'energia': produccion, consumo, red, sobrante o bateria",
        "condicion": "Para 'sensor' y 'energia': mayor, menor o igual",
        "valor": "Para 'sensor' y 'energia': el valor con el que comparar (número; para 'igual' en sensores puede ser texto como 'on')",
        "accion": "aviso, encender, apagar o escena",
        "objetivo": "Para encender, apagar o escena: el aparato o la escena, como lo diría el usuario",
        "mensaje": "Para 'aviso': el texto de la notificación",
        "espera_minutos": "Minutos mínimos entre dos ejecuciones (sensor y energía). Por defecto 5.",
    },
)
def crear_automatizacion(
    nombre: str,
    disparador: str,
    accion: str,
    hora: str = None,
    dias: str = None,
    sensor: str = None,
    magnitud: str = None,
    condicion: str = None,
    valor: str = None,
    objetivo: str = None,
    mensaje: str = None,
    espera_minutos: float = 5,
):
    """Crea una automatización."""

    try:
        trigger = {"tipo": disparador, "hora": hora, "dias": dias, "magnitud": magnitud, "condicion": condicion, "valor": valor}

        if str(disparador).strip().lower() == "sensor":
            trigger.update(automatizaciones.resolver_sensor(sensor or ""))
            trigger = {**trigger, "entidad": trigger["entidad"], "nombre": trigger["nombre"]}

        automatizaciones.comprobar_objetivo(accion, objetivo or "")

        creada = automatizaciones.crear(
            nombre,
            trigger,
            [{"tipo": accion, "objetivo": objetivo, "mensaje": mensaje}],
            espera_minutos,
        )

        return {"creada": {"id": creada["id"], "nombre": creada["nombre"], "regla": creada["resumen"]}}
    except (ValueError, HomeAssistantError) as error:
        return {"error": str(error)}


@tool(descripcion="Muestra las automatizaciones creadas, si están activas y cuándo se ejecutaron por última vez.", categoria="automatizaciones")
def ver_automatizaciones():
    """Lista las automatizaciones."""

    lista = automatizaciones.listar()

    if not lista:
        return {"mensaje": "No hay automatizaciones creadas."}

    return {"automatizaciones": lista}


@tool(
    descripcion="Borra una automatización por su nombre.",
    categoria="automatizaciones",
    argumentos={"nombre": "Nombre (o número) de la automatización"},
)
def borrar_automatizacion(nombre: str):
    """Borra una automatización."""

    try:
        return {"borrada": automatizaciones.borrar(nombre)}
    except ValueError as error:
        return {"error": str(error)}


@tool(
    descripcion="Activa o desactiva (pausa) una automatización sin borrarla.",
    categoria="automatizaciones",
    argumentos={"nombre": "Nombre (o número) de la automatización", "activa": "true para activarla, false para pausarla"},
)
def activar_automatizacion(nombre: str, activa: bool = True):
    """Activa o pausa una automatización."""

    try:
        return automatizaciones.activar(nombre, activa)
    except ValueError as error:
        return {"error": str(error)}


@tool(
    descripcion="Ejecuta una automatización ahora mismo, para probarla, sin esperar a su disparador.",
    categoria="automatizaciones",
    argumentos={"nombre": "Nombre (o número) de la automatización"},
)
def ejecutar_automatizacion(nombre: str):
    """Ejecuta una automatización ya."""

    try:
        return automatizaciones.ejecutar_ahora(nombre)
    except (ValueError, HomeAssistantError) as error:
        return {"error": str(error)}
