"""
Importación de listas de productos pegadas como texto.

Lo usan el chat (cuando el usuario pega una lista larga), el diálogo
"Importar lista" de la web y las herramientas de la IA. Así una lista de 40
productos se guarda siempre igual, sin depender de que el modelo de IA la
copie bien.
"""

from brain.modules.inventario import UBICACIONES, normalizar, parsear_lineas

# Sitios que se pueden elegir al importar ("compra" es la lista de la compra).
DESTINOS = ("compra",) + UBICACIONES

MIN_LINEAS_LISTA = 4

PALABRAS_COMPRA = ("compra", "comprar", "supermercado", "me falta", "me faltan", "hace falta")


def _destino_desde_texto(texto):
    """Adivina a dónde va la lista según lo que dice el usuario."""

    claro = normalizar(texto)

    if "nevera" in claro or "frigorifico" in claro:
        return "frigorifico"

    if "congelador" in claro:
        return "congelador"

    if any(p in claro for p in PALABRAS_COMPRA) and "despensa" not in claro and "inventario" not in claro:
        return "compra"

    return "despensa"


def interpretar_lista(texto, destino=None):
    """
    Entiende un texto con varios productos.

    Devuelve {"destino", "productos": [(nombre, cantidad)], "titulo"} o None
    si el texto no parece una lista de productos.

    Si `destino` es None se deduce del propio texto y, sin pistas, es la
    despensa (nunca la lista de la compra por sorpresa).
    """

    lineas = parsear_lineas(texto)

    if not lineas:
        return None

    titulo = ""

    # Una primera línea sin cantidad delante de otras con cantidad es un
    # título o una frase de introducción ("Añade esto a la despensa").
    if len(lineas) > 2 and not lineas[0][2]:
        resto = lineas[1:]

        if sum(1 for _, _, explicita in resto if explicita) >= 0.8 * len(resto):
            titulo = lineas[0][0]
            lineas = resto

    if destino is None:
        destino = _destino_desde_texto(f"{titulo}\n{texto[:300]}")

    if destino not in DESTINOS:
        destino = "despensa"

    return {
        "destino": destino,
        "titulo": titulo,
        "productos": [(nombre, cantidad) for nombre, cantidad, _ in lineas],
        "con_cantidad": sum(1 for _, _, explicita in lineas if explicita),
    }


def parece_lista_pegada(texto):
    """
    True si el mensaje es una lista larga de productos con sus cantidades
    (y no una pregunta o una orden normal).
    """

    lineas = [l for l in str(texto).splitlines() if l.strip()]

    if len(lineas) < MIN_LINEAS_LISTA:
        return False

    interpretada = interpretar_lista(texto)

    if not interpretada:
        return False

    productos = len(interpretada["productos"])

    return productos >= MIN_LINEAS_LISTA - 1 and interpretada["con_cantidad"] >= 0.6 * productos


def aplicar_lista(interpretada, inventario, compras):
    """Guarda la lista interpretada. Devuelve un resumen."""

    destino = interpretada["destino"]
    productos = interpretada["productos"]

    if destino == "compra":
        compras.añadir_varios(productos)
        sitio = "la lista de la compra"
    else:
        inventario.añadir_varios(productos, destino)
        sitio = {"despensa": "la despensa", "frigorifico": "el frigorífico", "congelador": "el congelador"}.get(
            destino, destino
        )

    return {
        "destino": destino,
        "total": len(productos),
        "unidades": sum(c for _, c in productos),
        "texto": f"Hecho: he añadido {len(productos)} productos a {sitio}.",
    }
