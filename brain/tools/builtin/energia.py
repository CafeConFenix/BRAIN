from brain.modules.energia import Energia, EnergiaTiempoReal, describir
from brain.tools.decorators import tool

energia = Energia()
tiempo_real = EnergiaTiempoReal()


@tool(
    descripcion="Guarda la producción de las placas solares de un día, en kWh.",
    categoria="energia",
    argumentos={
        "kwh": "Energía producida en kWh, por ejemplo 32.5",
        "fecha": "Fecha AAAA-MM-DD. Omitir si es hoy.",
    },
)
def guardar_produccion_solar(kwh: float, fecha: str = None):
    """Guarda la producción solar."""

    return {"guardado": energia.registrar_produccion(kwh, fecha)}


@tool(
    descripcion="Consulta la producción solar de los últimos días, con el total y la media en kWh.",
    categoria="energia",
    argumentos={"dias": "Cuántos registros recientes mirar. Por defecto 7."},
)
def ver_produccion_solar(dias: int = 7):
    """Consulta la producción solar."""

    resultado = energia.produccion(dias)

    if not resultado["registros"]:
        return {"mensaje": "No hay producción solar registrada."}

    return resultado


@tool(
    descripcion=(
        "Lee EN DIRECTO el inversor solar y el contador: cuánta electricidad producen ahora las placas, "
        "cuánto consume la casa ahora mismo y si se está comprando o vendiendo a la red. "
        "Úsala para preguntas como '¿cuánto estoy consumiendo?' o '¿cuánto producen las placas ahora?'."
    ),
    categoria="energia",
)
def ver_energia_ahora():
    """Producción, consumo y red en tiempo real."""

    lectura = tiempo_real.leer()

    return {**lectura, "resumen": describir(lectura)}
