from brain.modules.salud import Salud
from brain.tools.decorators import tool

salud = Salud()


@tool(
    descripcion=(
        "Muestra las medidas corporales guardadas desde la báscula (grasa corporal, IMC, agua, masa muscular, "
        "masa ósea, grasa visceral, metabolismo basal, edad corporal), de la más antigua a la más reciente."
    ),
    categoria="salud",
    argumentos={
        "nombre": "Una medida concreta, por ejemplo grasa_corporal_pct o imc. Omitir para todas.",
        "limite": "Cuántos registros recientes. Por defecto 14.",
    },
)
def ver_medidas_corporales(nombre: str = None, limite: int = 14):
    """Lista las medidas corporales guardadas."""

    registros = salud.medidas(nombre, limite)

    if not registros:
        return {"mensaje": "No hay medidas corporales guardadas. El usuario puede enviar una captura de su báscula en el chat."}

    return {"medidas": registros}
