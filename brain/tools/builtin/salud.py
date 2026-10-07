from brain.modules.salud import Salud
from brain.tools.decorators import tool

salud = Salud()


@tool(
    descripcion=(
        "Guarda el peso del usuario en kilos. Si no se indica fecha se usa hoy. "
        "Si ya había un peso ese día, lo sustituye."
    ),
    categoria="salud",
    argumentos={
        "peso": "Peso en kilos, por ejemplo 88.5",
        "fecha": "Fecha AAAA-MM-DD. Omitir si es hoy.",
    },
)
def guardar_peso(peso: float, fecha: str = None):
    """Guarda el peso del usuario."""

    guardado = salud.guardar_peso(peso=peso, fecha=fecha)

    return {"guardado": guardado}


@tool(
    descripcion="Obtiene el peso registrado más recientemente.",
    categoria="salud",
)
def obtener_peso():
    """Obtiene el peso actual."""

    return salud.peso_actual()


@tool(
    descripcion=(
        "Consulta cuánto pesaba el usuario en una fecha concreta. Si ese día no hay "
        "registro devuelve el último anterior e indica que es aproximado."
    ),
    categoria="salud",
    argumentos={"fecha": "Fecha AAAA-MM-DD (por ejemplo 2026-08-05)"},
)
def peso_en_fecha(fecha: str):
    """Peso en una fecha."""

    resultado = salud.peso_en(fecha)

    if resultado is None:
        return {"mensaje": "No hay ningún peso registrado en esa fecha ni antes."}

    return resultado


@tool(
    descripcion="Devuelve el historial de pesos (del más antiguo al más reciente) para ver la evolución.",
    categoria="salud",
    argumentos={"cantidad": "Cuántos registros devolver como máximo. Por defecto 10."},
)
def historial_peso(cantidad: int = 10):
    """Historial de peso."""

    registros = salud.historial_peso(cantidad)

    resultado = {"registros": registros}

    if len(registros) >= 2:
        resultado["variacion_kg"] = round(registros[-1]["peso"] - registros[0]["peso"], 2)

    return resultado
