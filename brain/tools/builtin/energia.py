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
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80


@tool(
    descripcion=(
        "Aconseja cómo aprovechar mejor la energía solar: a qué horas sobra producción (las mejores para lavadora, "
        "lavavajillas o termo), cuándo consume más la casa y si ahora es buen momento para poner un aparato. "
        "Usa el histórico del inversor que BRAIN guarda. Úsala para '¿cuándo pongo la lavadora?' o '¿cómo ahorro luz?'."
    ),
    categoria="energia",
    argumentos={"dias": "Días de histórico a analizar. Por defecto 14."},
)
def ver_consejo_energia(dias: int = 14):
    """Consejo de aprovechamiento solar."""

    analisis = energia.analizar(dias)

    ahora = energia.momento_ahora(tiempo_real.leer())

    if ahora:
        analisis["ahora"] = ahora

    return analisis
<<<<<<< HEAD


@tool(
    descripcion="Guarda el precio de la electricidad (euros por kWh) para calcular cuánto valen las placas solares. 'Pago 0,15 y me pagan 0,06 por los excedentes'.",
    categoria="energia",
    argumentos={
        "compra": "Euros por kWh que pagas por la electricidad, por ejemplo 0.15",
        "venta": "Euros por kWh que te pagan por los excedentes. Opcional.",
    },
)
def configurar_tarifa_luz(compra: float = None, venta: float = None):
    """Guarda la tarifa de la luz."""

    return {"tarifa": energia.configurar_tarifa(compra, venta)}


@tool(
    descripcion="Calcula cuánto dinero han valido, aproximadamente, las placas solares en los últimos días. Úsala para '¿cuánto he ahorrado con las placas?'.",
    categoria="energia",
    argumentos={"dias": "Cuántos registros diarios recientes usar. Por defecto 30."},
)
def ver_ahorro_solar(dias: int = 30):
    """Ahorro estimado con las placas."""

    return energia.ahorro_solar(dias)


@tool(
    descripcion="Cuánto cuesta la luz de un mes (estimado con las lecturas del inversor): euros pagados a la red, ingresos por excedentes y lo que ahorran las placas. Úsala para '¿cuánto llevo gastado de luz?'.",
    categoria="energia",
    argumentos={"mes": "AAAA-MM, 'este mes' o 'mes pasado'. Por defecto este mes."},
)
def ver_coste_luz(mes: str = None):
    """Coste de la luz del mes."""

    return energia.coste_mes(mes)


@tool(
    descripcion="Compara lo que cuesta la luz este mes con el mes pasado.",
    categoria="energia",
)
def comparar_coste_luz():
    """Compara el coste de la luz."""

    return energia.comparar_meses()


@tool(
    descripcion="Guarda la franja horaria barata de la tarifa (valle), por ejemplo de 00:00 a 08:00 a 0,08 €/kWh. BRAIN la usa para calcular el coste y para decir cuándo poner aparatos.",
    categoria="energia",
    argumentos={"desde": "Hora de inicio HH:MM", "hasta": "Hora de fin HH:MM", "precio": "Euros por kWh en esa franja, por ejemplo 0.08"},
)
def configurar_horas_baratas(desde: str = None, hasta: str = None, precio: str = None):
    """Guarda las horas baratas."""

    return {"tarifa": energia.configurar_horas_baratas(desde, hasta, precio)}


@tool(
    descripcion="Dice cuál es la franja barata de la luz y si ahora mismo es barata. Úsala para '¿es buen momento para poner la lavadora?'.",
    categoria="energia",
)
def ver_horas_baratas():
    """Horas baratas de la luz."""

    return energia.horas_baratas()
=======
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
