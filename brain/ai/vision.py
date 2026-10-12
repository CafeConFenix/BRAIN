"""
Lectura de capturas de la báscula inteligente con un modelo de visión de Ollama.

El usuario pasa una captura de la app de su báscula; el modelo extrae el
peso (y, si salen, grasa, IMC, agua...) y BRAIN lo valida antes de guardarlo:
un número fuera de rango o ilegible se rechaza en vez de guardarse mal.
"""

import base64
import json
import re
from datetime import date
from typing import Optional

from brain.ai.ollama import Ollama, OllamaError

MAX_BYTES = 8 * 1024 * 1024

PROMPT = """Esta imagen es una captura de pantalla de la app de una báscula inteligente.
Lee SOLO lo que se ve. No inventes ni estimes nada: si un dato no aparece, pon null.
Responde ÚNICAMENTE con un JSON con este formato, sin texto antes ni después:
{"peso_kg": numero o null, "fecha": "AAAA-MM-DD" o null,
 "medidas": {"grasa_corporal_pct": null, "imc": null, "agua_pct": null, "masa_muscular_kg": null,
             "masa_osea_kg": null, "grasa_visceral": null, "metabolismo_basal_kcal": null, "edad_corporal": null}}
El peso debe ir en kilogramos (convierte si está en libras). Usa punto decimal."""

# nombre guardado -> (unidad, mínimo, máximo plausibles)
MEDIDAS = {
    "grasa_corporal_pct": ("%", 2, 65),
    "imc": ("", 10, 70),
    "agua_pct": ("%", 20, 80),
    "masa_muscular_kg": ("kg", 10, 120),
    "masa_osea_kg": ("kg", 0.5, 8),
    "grasa_visceral": ("", 1, 60),
    "metabolismo_basal_kcal": ("kcal", 500, 4000),
    "edad_corporal": ("años", 10, 100),
}

ETIQUETAS = {
    "grasa_corporal_pct": "grasa corporal",
    "imc": "IMC",
    "agua_pct": "agua",
    "masa_muscular_kg": "masa muscular",
    "masa_osea_kg": "masa ósea",
    "grasa_visceral": "grasa visceral",
    "metabolismo_basal_kcal": "metabolismo basal",
    "edad_corporal": "edad corporal",
}


class VisionError(RuntimeError):
    """Error con un mensaje entendible para el usuario."""


def tipo_de_imagen(datos: bytes) -> Optional[str]:
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    if datos[:3] == b"\xff\xd8\xff":
        return "jpeg"

    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "webp"

    return None


def _numero(valor) -> Optional[float]:
    if isinstance(valor, bool) or valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    coincidencia = re.search(r"-?\d+(?:[.,]\d+)?", str(valor))

    return float(coincidencia.group(0).replace(",", ".")) if coincidencia else None


def interpretar_respuesta(texto: str, hoy: Optional[date] = None) -> dict:
    """Convierte la respuesta del modelo en {"peso", "fecha", "medidas"} validado."""

    hoy = hoy or date.today()

    coincidencia = re.search(r"\{.*\}", texto or "", re.DOTALL)

    if not coincidencia:
        raise VisionError("No he podido leer la captura. Prueba con una imagen más nítida donde se vea el peso.")

    try:
        datos = json.loads(coincidencia.group(0))
    except ValueError:
        raise VisionError("No he podido leer la captura. Prueba con una imagen más nítida donde se vea el peso.") from None

    peso = _numero(datos.get("peso_kg"))

    if peso is None:
        raise VisionError("No veo ningún peso en la imagen. ¿Es la pantalla de la báscula con el resultado?")

    if not 20 <= peso <= 500:
        raise VisionError(f"He leído {peso:g} kg, que no parece correcto, y no lo guardo. Dime el peso a mano o prueba con otra captura.")

    fecha = hoy

    try:
        leida = date.fromisoformat(str(datos.get("fecha")))

        if leida <= hoy and (hoy - leida).days <= 366:
            fecha = leida
    except (TypeError, ValueError):
        pass

    medidas = {}

    for nombre, valor in (datos.get("medidas") or {}).items():
        if nombre not in MEDIDAS:
            continue

        numero = _numero(valor)
        _, minimo, maximo = MEDIDAS[nombre]

        if numero is not None and minimo <= numero <= maximo:
            medidas[nombre] = round(numero, 1)

    return {"peso": round(peso, 1), "fecha": fecha.isoformat(), "medidas": medidas}


def leer_bascula(ollama: Ollama, imagen: bytes, hoy: Optional[date] = None) -> dict:
    """Lee una captura de báscula. Lanza VisionError si no se puede."""

    if not imagen or len(imagen) > MAX_BYTES:
        raise VisionError("La imagen no es válida o es demasiado grande (máximo 8 MB).")

    if tipo_de_imagen(imagen) is None:
        raise VisionError("Formato de imagen no admitido. Usa una captura en JPG, PNG o WebP.")

    try:
        modelo = ollama.modelo_con_vision()
    except OllamaError as error:
        raise VisionError(str(error)) from None

    if modelo is None:
        raise VisionError(
            "Ninguno de tus modelos de IA sabe leer imágenes. Instala uno con visión (por ejemplo "
            "'ollama pull gemma3:4b') y vuelve a enviar la captura."
        )

    try:
        respuesta = ollama.chat_con_imagen(PROMPT, base64.b64encode(imagen).decode("ascii"), modelo=modelo)
    except OllamaError as error:
        raise VisionError(f"No he podido analizar la imagen: {error}") from None

    resultado = interpretar_respuesta(respuesta, hoy)
    resultado["modelo"] = modelo

    return resultado


def guardar_lectura(salud, resultado: dict) -> str:
    """Guarda lo leído (peso y medidas) y devuelve un texto para el usuario."""

    salud.guardar_peso(resultado["peso"], resultado["fecha"])

    for nombre, valor in resultado["medidas"].items():
        salud.guardar_medida(nombre, valor, MEDIDAS[nombre][0] or None, resultado["fecha"])

    def formato(numero):
        return f"{numero:g}".replace(".", ",")

    extras = ", ".join(
        f"{ETIQUETAS[n]} {formato(v)}{(' ' + MEDIDAS[n][0]) if MEDIDAS[n][0] else ''}" for n, v in resultado["medidas"].items()
    )

    texto = f"He leído en la captura: {formato(resultado['peso'])} kg ({resultado['fecha']})"

    if extras:
        texto += f" · {extras}"

    return texto + ". Lo he guardado. Si algún dato no es correcto, dímelo y lo corrijo."
