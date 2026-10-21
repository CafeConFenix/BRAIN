from brain.modules.gastos import Gastos
from brain.tools.decorators import tool

gastos = Gastos()


@tool(
    descripcion="Apunta un gasto (lo que se ha pagado en el súper, una factura, la gasolina...). Úsala para 'he gastado 23 euros en el súper'.",
    categoria="gastos",
    argumentos={
        "importe": "Cantidad en euros, por ejemplo 23.50",
        "concepto": "En qué se gastó, por ejemplo 'Mercadona' o 'factura de la luz'",
        "categoria": "supermercado, hogar, facturas, transporte, ocio, salud, ropa, restaurantes u otros. Omitir y se deduce del concepto.",
        "fecha": "AAAA-MM-DD. Omitir si es hoy.",
    },
)
def anadir_gasto(importe: str, concepto: str = "", categoria: str = "", fecha: str = None):
    """Apunta un gasto."""

    return {"apuntado": gastos.anadir(importe, concepto, categoria, fecha)}


@tool(
    descripcion="Resumen de gastos de un mes: total, reparto por categoría y los últimos gastos. Úsala para '¿cuánto he gastado este mes?'.",
    categoria="gastos",
    argumentos={"mes": "AAAA-MM, o 'octubre', 'este mes' o 'mes pasado'. Por defecto este mes."},
)
def ver_gastos(mes: str = None):
    """Resumen de gastos."""

    resultado = gastos.resumen(mes)

    if not resultado["n"]:
        return {"mensaje": f"No hay gastos apuntados en {resultado['mes']}.", "mes": resultado["mes"]}

    return resultado


@tool(
    descripcion="Borra un gasto apuntado por error.",
    categoria="gastos",
    argumentos={"id": "Número del gasto (sale en ver_gastos) o 'ultimo' para el último apuntado."},
)
def borrar_gasto(id: str = "ultimo"):
    """Borra un gasto."""

    return {"borrado": gastos.borrar(id)}


@tool(
    descripcion="Fija el presupuesto mensual de gastos (total y/o el límite de una categoría). BRAIN avisa al llegar al 80 % y al 100 %. Con 0 se quita.",
    categoria="gastos",
    argumentos={
        "total": "Presupuesto total del mes en euros, por ejemplo 900. Omitir si solo se limita una categoría.",
        "categoria": "Categoría a limitar (ocio, supermercado...). Omitir para el total.",
        "limite": "Límite en euros de esa categoría.",
    },
)
def fijar_presupuesto(total: str = None, categoria: str = "", limite: str = None):
    """Fija el presupuesto."""

    return {"presupuesto": gastos.configurar_presupuesto(total, categoria, limite)}


@tool(
    descripcion="Cómo va el presupuesto del mes: cuánto se ha gastado, cuánto queda y el porcentaje. Úsala para '¿cómo voy de presupuesto?'.",
    categoria="gastos",
    argumentos={"mes": "AAAA-MM, o 'este mes' / 'mes pasado'. Por defecto este mes."},
)
def ver_presupuesto(mes: str = None):
    """Estado del presupuesto."""

    estado = gastos.estado_presupuesto(mes)

    if not estado["configurado"]:
        return {"mensaje": "Todavía no hay presupuesto. Dime cuánto quieres gastar al mes como máximo.", **estado}

    return estado
