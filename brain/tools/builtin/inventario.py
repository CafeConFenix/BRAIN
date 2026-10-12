from brain.modules.compras import Compras
from brain.modules.inventario import Inventario, mismo_producto, parsear_lista
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


@tool(
    descripcion=(
        "Elimina por completo un producto del inventario (todas sus unidades), por ejemplo porque se añadió por error."
    ),
    categoria="inventario",
    argumentos={
        "nombre": "Nombre del producto",
        "ubicacion": "Ubicación concreta. Omitir para buscarlo en todas.",
    },
)
def borrar_del_inventario(nombre: str, ubicacion: str = None):
    """Borra un producto del inventario."""

    return {"borrados": [f"{p['nombre']} ({p['ubicacion']})" for p in inventario.borrar(nombre, ubicacion)]}


@tool(
    descripcion=(
        "BORRA TODO el inventario o todo lo de una ubicación. Úsala solo si el usuario lo pide expresamente "
        "(\"vacía la despensa\", \"borra todo el inventario\")."
    ),
    categoria="inventario",
    argumentos={"ubicacion": "frigorifico, congelador, despensa, herramientas o consumibles. Omitir para vaciar todo."},
)
def vaciar_inventario(ubicacion: str = None):
    """Vacía el inventario."""

    return {"borrados": inventario.vaciar(ubicacion)}


@tool(
    descripcion=(
        "Da la lista de ingredientes con los que se puede cocinar en casa: lo que hay en la despensa, la nevera y el "
        "congelador MÁS los básicos de cualquier cocina (aceite, sal, agua, harina, azúcar, especias...). "
        "LLÁMALA SIEMPRE ANTES de proponer una receta o decir qué se puede cocinar o cenar."
    ),
    categoria="recetas",
)
def ingredientes_disponibles():
    """Ingredientes para cocinar."""

    ingredientes = inventario.ingredientes_para_cocinar()

    return {
        **ingredientes,
        "como_usarlo": (
            "Propón recetas usando SOLO estos ingredientes. Los básicos se dan por supuestos (no hay que comprarlos). "
            "Si a la receta le falta algo que no está, dilo y ofrece apuntarlo en la lista de la compra. "
            "Si el inventario está vacío, dilo y propón algo hecho solo con los básicos."
        ),
    }


@tool(
    descripcion="Muestra los básicos de casa que BRAIN da por supuestos para las recetas (aceite, sal, especias...).",
    categoria="recetas",
)
def ver_basicos():
    """Lista de básicos."""

    return {"basicos": inventario.basicos()}


@tool(
    descripcion="Añade un ingrediente a los básicos de casa (algo que siempre hay: vino blanco, caldo, leche...).",
    categoria="recetas",
    argumentos={"nombre": "Ingrediente básico, por ejemplo 'caldo de pollo'"},
)
def anadir_basico(nombre: str):
    """Añade un básico."""

    return {"basicos": inventario.anadir_basico(nombre)}


@tool(
    descripcion="Quita un ingrediente de los básicos de casa (algo que ya no hay siempre en la cocina).",
    categoria="recetas",
    argumentos={"nombre": "Ingrediente que se quita de los básicos"},
)
def quitar_basico(nombre: str):
    """Quita un básico."""

    return {"basicos": inventario.quitar_basico(nombre)}


@tool(
    descripcion=(
        "Cuando el usuario quiera cocinar una receta: compara sus ingredientes con el frigorífico, el congelador, "
        "la despensa y los básicos de casa, y apunta en la lista de la compra, de una sola vez, solo los que "
        "faltan o están agotados. Los que ya hay o ya estaban en la lista no se duplican. "
        "Devuelve qué se ha añadido y qué ya estaba disponible."
    ),
    categoria="recetas",
    argumentos={
        "ingredientes": "Todos los ingredientes de la receta, uno por línea o separados por comas. Pueden llevar cantidad: '2 huevos', '200 g harina'.",
        "receta": "Nombre de la receta, solo para el resumen. Opcional.",
    },
)
def anadir_faltantes_receta_a_compra(ingredientes: str, receta: str = None):
    """Añade a la compra los ingredientes de una receta que no hay."""

    texto = ingredientes

    if isinstance(texto, str) and "\n" not in texto and ";" not in texto and "," in texto:
        texto = texto.replace(",", "\n")

    if not parsear_lista(texto):
        return {"error": "No he entendido ningún ingrediente en el texto."}

    comparacion = inventario.comparar_receta(texto)

    en_lista = [i.get("producto", "") for i in compras.lista()]

    def apuntado(nombre):
        return any(mismo_producto(nombre, p) for p in en_lista)

    nuevos = [(n, c) for n, c in comparacion["faltan"] if not apuntado(n)]
    ya_apuntados = [n for n, _ in comparacion["faltan"] if apuntado(n)]

    if nuevos:
        compras.añadir_varios(nuevos)  # una sola escritura: o se apuntan todos o ninguno

    disponibles = [f"{d['ingrediente']} ({d['en']})" for d in comparacion["disponibles"]]
    añadidos = [n for n, _ in nuevos]

    partes = []

    if añadidos:
        partes.append(f"Añadido a la compra: {', '.join(añadidos)}.")

    if ya_apuntados:
        partes.append(f"Ya estaba en la lista: {', '.join(ya_apuntados)}.")

    if disponibles:
        partes.append(f"Ya tienes: {', '.join(disponibles)}.")

    if not añadidos and not ya_apuntados:
        partes = ["No falta nada: tienes todos los ingredientes."]

    return {
        "receta": receta,
        "añadidos_a_compra": [{"producto": n, "cantidad": c} for n, c in nuevos],
        "ya_estaban_en_la_lista": ya_apuntados,
        "ya_disponibles": comparacion["disponibles"],
        "agotados": comparacion["agotados"],
        "resumen": " ".join(partes),
    }
