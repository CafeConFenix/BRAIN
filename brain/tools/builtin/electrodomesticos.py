from brain.modules.electrodomesticos import Electrodomesticos
from brain.tools.decorators import tool

electrodomesticos = Electrodomesticos()


@tool(
    descripcion=(
        "Guarda un electrodoméstico de la casa con su marca, modelo, fecha de compra y garantía. Úsala cuando el usuario "
        "diga que tiene o ha comprado un aparato ('tengo una lavadora Bosch WAN28258ES comprada en marzo, con 3 años de "
        "garantía'). Si el aparato ya estaba, completa los datos nuevos sin borrar los anteriores."
    ),
    categoria="electrodomesticos",
    argumentos={
        "nombre": "Qué es: lavadora, nevera, horno, lavavajillas, aire acondicionado...",
        "marca": "Marca, por ejemplo Bosch",
        "modelo": "Modelo exacto, por ejemplo WAN28258ES",
        "ubicacion": "Dónde está: cocina, lavadero...",
        "fecha_compra": "Fecha de compra (AAAA-MM-DD)",
        "garantia_meses": "Meses de garantía desde la compra",
        "notas": "Cualquier dato útil (color, instalador, número de serie...)",
    },
)
def anadir_electrodomestico(
    nombre: str,
    marca: str = None,
    modelo: str = None,
    ubicacion: str = None,
    fecha_compra: str = None,
    garantia_meses: int = None,
    notas: str = None,
):
    """Guarda o actualiza un electrodoméstico."""

    try:
        return {"guardado": electrodomesticos.guardar(nombre, marca, modelo, ubicacion, fecha_compra, garantia_meses, notas)}
    except ValueError as error:
        return {"error": str(error)}


@tool(descripcion="Muestra los electrodomésticos registrados, con su modelo y el estado de la garantía.", categoria="electrodomesticos")
def ver_electrodomesticos():
    """Lista los electrodomésticos."""

    lista = electrodomesticos.listar()

    if not lista:
        return {"mensaje": "No hay electrodomésticos registrados todavía."}

    return {"electrodomesticos": lista}


@tool(
    descripcion="Borra un electrodoméstico del registro.",
    categoria="electrodomesticos",
    argumentos={"nombre": "Nombre del electrodoméstico"},
)
def quitar_electrodomestico(nombre: str):
    """Quita un electrodoméstico."""

    try:
        return {"quitado": electrodomesticos.quitar(nombre)["nombre"]}
    except ValueError as error:
        return {"error": str(error)}


@tool(
    descripcion=(
        "Cuando el usuario cuenta un fallo o hace una pregunta sobre un electrodoméstico suyo ('la lavadora no centrifuga', "
        "'el horno da el error E3'), úsala: devuelve su marca y modelo y los pasajes de sus manuales guardados. "
        "Con eso, explica qué le pasa y cómo arreglarlo: si hay manual, básate en él y dilo; si no, usa lo que sepas de "
        "ese modelo concreto y avisa de que no sale del manual. Si es de gas, electricidad o hay riesgo, recomienda "
        "un técnico. Si el aparato no está registrado, pide marca y modelo y guárdalos."
    ),
    categoria="electrodomesticos",
    argumentos={
        "nombre": "Qué aparato es (lavadora, horno...)",
        "problema": "El fallo o el código de error, con las palabras del usuario",
    },
)
def consultar_electrodomestico(nombre: str, problema: str = None):
    """Ficha y manuales de un electrodoméstico para diagnosticar un fallo."""

    try:
        return electrodomesticos.consultar(nombre, problema)
    except ValueError as error:
        return {"error": str(error)}
