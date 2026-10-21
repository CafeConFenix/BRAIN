from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.rutinas import Rutinas
from brain.tools.decorators import tool

rutinas = Rutinas()


@tool(
    descripcion=(
        "Revisa la casa antes de salir o de dormir: lista lo que está encendido y lo pendiente. NO apaga nada. "
        "Después pregunta al usuario si quiere apagarlo y, solo si dice que sí, usa apagar_lo_encendido."
    ),
    categoria="domotica",
    argumentos={"momento": "'salgo' (salgo de casa) o 'noches' (buenas noches). Por defecto salgo."},
)
def revisar_casa(momento: str = "salgo"):
    """Revisa la casa."""

    try:
        return rutinas.revisar("noches" if "noche" in str(momento) else "salgo")
    except HomeAssistantError as error:
        return {"error": str(error)}


@tool(
    descripcion="Apaga TODO lo que está encendido en la casa (luces, enchufes, ventiladores, tele...). Úsala solo después de que el usuario lo haya confirmado.",
    categoria="domotica",
)
def apagar_lo_encendido():
    """Apaga todo lo encendido."""

    try:
        encendidos = rutinas.revisar("salgo")["encendidos"]

        return rutinas.apagar([e["entidad"] for e in encendidos])
    except HomeAssistantError as error:
        return {"error": str(error)}
