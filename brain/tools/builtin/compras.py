from brain.modules.compras import Compras
from brain.modules.inventario import parsear_lista
from brain.tools.decorators import tool

compras = Compras()


@tool(
    descripcion="Añade un producto a la lista de la compra.",
    categoria="compras",
    argumentos={
        "producto": "Nombre del producto",
        "cantidad": "Unidades. Por defecto 1.",
    },
)
def anadir_a_compra(producto: str, cantidad: float = 1):
    """Añade a la lista de la compra."""

    return {"guardado": compras.añadir(producto, cantidad)}


@tool(
    descripcion=(
        "Añade VARIOS productos a la lista de la compra de una sola vez. Úsala siempre que el usuario "
        "mencione dos o más productos (\"apunta leche, pan y huevos\")."
    ),
    categoria="compras",
    argumentos={
        "productos": "Los productos, uno por línea o separados por comas/punto y coma. Pueden llevar cantidad: '2 x leche', 'pan, 3'.",
    },
)
def anadir_varias_a_compra(productos: str):
    """Añade varios productos a la lista de la compra."""

    # Aquí la coma separa productos si no hay saltos de línea ni cantidades.
    texto = str(productos)

    if "\n" not in texto and ";" not in texto and "," in texto:
        texto = texto.replace(",", "\n")

    pares = parsear_lista(texto)

    if not pares:
        return {"error": "No he entendido ningún producto en el texto."}

    return {"añadidos": compras.añadir_varios(pares), "total_productos": len(pares)}


@tool(
    descripcion="Muestra la lista de la compra pendiente.",
    categoria="compras",
)
def ver_lista_compra():
    """Muestra la lista de la compra."""

    lista = compras.lista()

    if not lista:
        return {"mensaje": "La lista de la compra está vacía."}

    return {"lista_compra": lista}


@tool(
    descripcion="Marca un producto como comprado y lo quita de la lista de la compra.",
    categoria="compras",
    argumentos={"producto": "Nombre del producto comprado"},
)
def marcar_comprado(producto: str):
    """Marca un producto como comprado."""

    return {"comprado": compras.comprado(producto)}
