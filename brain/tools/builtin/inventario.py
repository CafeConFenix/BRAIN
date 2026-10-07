from brain.modules.compras import Compras
from brain.modules.inventario import Inventario, parsear_lista
from brain.tools.decorators import tool

inventario = Inventario()
compras = Compras()


@tool(
    descripcion="Añade un producto al inventario de la casa (o suma unidades si ya existe).",
    categoria="inventario",
    argumentos={
        "nombre": "Nombre del producto, por ejemplo 'leche'",
        "cantidad": "Número de unidades. Por defecto 1.",
        "ubicacion": "frigorifico, congelador, despensa, herramientas o consumibles. Por defecto despensa.",
    },
)
def anadir_inventario(nombre: str, cantidad: float = 1, ubicacion: str = "despensa"):
    """Añade un producto al inventario."""

    return {"guardado": inventario.añadir(nombre, cantidad, ubicacion)}


@tool(
    descripcion=(
        "Añade VARIOS productos al inventario de una sola vez. Úsala SIEMPRE que el usuario te dé una lista "
        "o mencione dos o más productos; nunca llames a anadir_inventario muchas veces seguidas."
    ),
    categoria="inventario",
    argumentos={
        "productos": (
            "Todos los productos, uno por línea, tal como los dijo el usuario. Pueden llevar cantidad: "
            "'Leche entera, 2 unidades', '2 x leche', 'Pan x3'. Sin cantidad se entiende 1."
        ),
        "ubicacion": "frigorifico, congelador, despensa, herramientas o consumibles. Por defecto despensa.",
    },
)
def anadir_varios_inventario(productos: str, ubicacion: str = "despensa"):
    """Añade muchos productos al inventario."""

    pares = parsear_lista(productos)

    if not pares:
        return {"error": "No he entendido ningún producto en el texto."}

    resultado = inventario.añadir_varios(pares, ubicacion)

    return {
        "ubicacion": resultado["ubicacion"],
        "total_productos": len(resultado["añadidos"]),
        "añadidos": [f"{a['nombre']} (x{a['cantidad_total']})" for a in resultado["añadidos"]],
    }


@tool(
    descripcion=(
        "El usuario dice que algo SE HA ACABADO o que ya no queda (\"se ha acabado la leche\", \"no queda aceite\"). "
        "Lo quita del inventario y lo apunta en la lista de la compra automáticamente."
    ),
    categoria="inventario",
    argumentos={
        "producto": "Nombre del producto que se ha acabado",
        "cantidad_a_comprar": "Unidades que hay que comprar. Por defecto 1.",
    },
)
def se_ha_acabado(producto: str, cantidad_a_comprar: float = 1):
    """Quita un producto agotado del inventario y lo añade a la compra."""

    quitado = None

    try:
        existente = inventario.buscar(producto)

        if existente:
            quitado = inventario.quitar(
                existente[0]["nombre"], existente[0].get("cantidad", 1) or 1, existente[0]["ubicacion"]
            )
    except ValueError:
        pass

    # Se apunta con el nombre que ya tenía en el inventario, si lo había.
    nombre = quitado["nombre"] if quitado else str(producto).strip()

    en_compra = compras.añadir(nombre, cantidad_a_comprar)

    return {
        "añadido_a_la_compra": en_compra,
        "quitado_del_inventario": bool(quitado),
    }


@tool(
    descripcion="Quita unidades de un producto del inventario (porque se ha gastado o usado). Si llega a cero lo apunta en la lista de la compra.",
    categoria="inventario",
    argumentos={
        "nombre": "Nombre del producto",
        "cantidad": "Unidades que se quitan. Por defecto 1.",
        "ubicacion": "Ubicación concreta. Omitir para buscarlo en todas.",
    },
)
def quitar_inventario(nombre: str, cantidad: float = 1, ubicacion: str = None):
    """Quita un producto del inventario."""

    resultado = inventario.quitar(nombre, cantidad, ubicacion)

    # Si no queda nada, se apunta en la lista de la compra para reponerlo.
    if resultado.get("cantidad_restante") == 0:
        compras.añadir(resultado["nombre"], 1)
        resultado["añadido_a_la_compra"] = True

    return resultado


@tool(
    descripcion="Muestra lo que hay en el inventario, de todas las ubicaciones o de una concreta.",
    categoria="inventario",
    argumentos={"ubicacion": "frigorifico, congelador, despensa, herramientas o consumibles. Omitir para ver todo."},
)
def ver_inventario(ubicacion: str = None):
    """Lista el inventario."""

    contenido = inventario.listar(ubicacion)

    if not contenido or not any(contenido.values()):
        if ubicacion:
            # La IA a veces pide un sitio que no es el que usó al guardar.
            otros = inventario.listar()

            if any(otros.values()):
                return {
                    "mensaje": f"No hay nada en '{ubicacion}', pero sí en otras ubicaciones.",
                    "inventario": otros,
                }

        return {"mensaje": "El inventario está vacío."}

    return {sitio: [f"{p['nombre']} (x{p.get('cantidad', 1)})" for p in productos] for sitio, productos in contenido.items()}


@tool(
    descripcion="Busca un producto en el inventario y dice dónde está y cuántos hay.",
    categoria="inventario",
    argumentos={"texto": "Parte del nombre del producto"},
)
def buscar_inventario(texto: str):
    """Busca en el inventario."""

    encontrados = inventario.buscar(texto)

    if not encontrados:
        return {"mensaje": f"No hay nada parecido a '{texto}' en el inventario."}

    return {"encontrados": encontrados}
