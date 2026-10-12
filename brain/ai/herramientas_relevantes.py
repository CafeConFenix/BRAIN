"""
Elige qué herramientas se le enseñan a la IA en cada pregunta.

Las descripciones de todas las herramientas de BRAIN ocupan más de 10.000
tokens, casi toda la memoria de trabajo del modelo: si se mandan todas, la IA
pierde sus instrucciones y contesta vacío. Por eso en cada pregunta solo se
envían las de los temas de los que se habla (la frase actual y lo último de la
conversación). Las herramientas que no se envían siguen existiendo.
"""

import re
import unicodedata
from typing import Iterable, List, Optional, Set

# categoría -> fragmentos de palabras (sin acentos, minúsculas) que la activan
PALABRAS = {
    "salud": ["peso", "pesa", "kilo", " kg", "bascula", "grasa", "imc", "adelgaz", "engord", "masa muscular", "medida"],
    "inventario": [
        "despensa", "nevera", "frigor", "congelador", "inventario", "tengo", "queda", "quedan", "acab", "agot", "stock",
        "producto", "alimento", "ingrediente", "guardar", "borrar", "vaciar",
    ],
    "compras": ["compra", "lista", "super", "comprar", "falta", "faltan", "apunta", "mercadona", "carrito"],
    "recetas": [
        "receta", "cocin", "cenar", "cena", "comer", "comida", "almuerzo", "desayun", "plato", "ingrediente", "basico",
        "preparar", "hacer de",
    ],
    "calendario": ["agenda", "evento", "cita", "tarea", "reunion", "calendario", "pendiente", "semana", "tengo hoy", "manana"],
    "energia": [
        "energia", "solar", "placa", "consumo", "consum", "inversor", "kwh", "produc", "red electrica", "bateria",
        "factura", "vatio", "gasto de luz", "ahorro",
    ],
    "memoria": ["recuerd", "acuerd", "olvid", "sabes que", "memoria", "te dije", "me gusta", "prefiero"],
    "sensores": ["sensor", "temperatura", "humedad", "presencia", "luminosidad"],
    "domotica": [
        "enciend", "apag", "luz", "luces", "persiana", "clima", "escena", "lampara", "enchufe", "dispositivo",
        "termostato", "ventilador", "aire", "calefa",
    ],
    "avisos": [
        "avisa", "aviso", "recuerdame", "recordatorio", "alarma", "notific", "sonido", "molestar", "silenci", "alerta",
        "avisame", "campana",
    ],
    "automatizaciones": [
        "automatiz", "cuando", "regla", "cada vez", "todos los dias", "todas las noches", "todas las mananas",
        "si llego", "si hay", "si pasa", "programa", "rutina",
    ],
    "electrodomesticos": [
        "electrodomestic", "lavadora", "lavavajillas", "horno", "garantia", "modelo", "averia", "falla", "no funciona",
        "caldera", "secadora", "microondas", "aparato", "marca", "error", "se ha roto", "no arranca", "no enciende",
    ],
    "sistema": ["copia", "backup", "restaur", "seguridad", "respaldo"],
    "documentos": ["manual", "documento", "nota", "apunte", "instruccion", "wifi", "clave", "contrasena", "guia", "como se"],
    "resumen": ["resumen", "que tengo hoy", "buenos dias", "mi dia", "novedades"],
}

# Si no se reconoce ningún tema se envía este conjunto (lo más habitual).
BASICAS = ("inventario", "compras", "calendario", "domotica", "salud")

# Siempre disponible (es pequeña y útil en cualquier charla).
SIEMPRE = ("memoria",)

MENSAJES_DE_CONTEXTO = 3


def _normalizar(texto: str) -> str:
    sin_acentos = "".join(c for c in unicodedata.normalize("NFD", str(texto)) if unicodedata.category(c) != "Mn")

    return " " + re.sub(r"\s+", " ", sin_acentos.lower()) + " "


def _temas_de(texto: str) -> Set[str]:
    limpio = _normalizar(texto)

    return {tema for tema, claves in PALABRAS.items() if any(clave in limpio for clave in claves)}


def categorias_relevantes(mensaje: str, historial: Optional[Iterable[dict]] = None) -> Set[str]:
    """Categorías de herramientas que hay que enseñar para esta pregunta."""

    temas = _temas_de(mensaje)

    for anterior in list(historial or [])[-MENSAJES_DE_CONTEXTO:]:
        temas |= _temas_de(anterior.get("content", ""))

    if not temas:
        temas = set(BASICAS)

    return temas | set(SIEMPRE)


def filtrar(herramientas: List[dict], categorias: Optional[Set[str]]) -> List[dict]:
    if not categorias:
        return list(herramientas)

    return [h for h in herramientas if h["categoria"] in categorias]
