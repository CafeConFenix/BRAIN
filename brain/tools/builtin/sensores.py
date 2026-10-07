from brain.modules.sensores import Sensores
from brain.tools.decorators import tool

sensores = Sensores()


@tool(
    descripcion="Guarda una lectura de un sensor de la casa (temperatura, humedad, presencia, agua o luminosidad).",
    categoria="sensores",
    argumentos={
        "tipo": "temperatura, humedad, presencia, agua o luminosidad",
        "valor": "Valor medido, por ejemplo 21.5",
        "ubicacion": "Habitación o lugar. Opcional.",
    },
)
def guardar_sensor(tipo: str, valor: float, ubicacion: str = None):
    """Guarda una lectura de sensor."""

    return {"guardado": sensores.registrar(tipo, valor, ubicacion)}


@tool(
    descripcion="Obtiene la última lectura registrada de un sensor.",
    categoria="sensores",
    argumentos={"tipo": "temperatura, humedad, presencia, agua o luminosidad"},
)
def ver_sensor(tipo: str):
    """Última lectura de un sensor."""

    lectura = sensores.ultima(tipo)

    if lectura is None:
        return {"mensaje": f"No hay lecturas del sensor '{tipo}'."}

    return lectura
