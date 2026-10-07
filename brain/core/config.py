import os
from pathlib import Path


def _entorno_bool(nombre, defecto=False):
    """Lee una variable de entorno como verdadero/falso."""

    valor = os.environ.get(nombre)

    if valor is None:
        return defecto

    return valor.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


def _entorno_int(nombre, defecto):
    """Lee una variable de entorno como número entero."""

    try:
        return int(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def _url_ollama():
    """
    Dirección de Ollama.

    Respeta BRAIN_OLLAMA_URL y, si no existe, la variable estándar
    OLLAMA_HOST (así BRAIN habla con el mismo Ollama que el comando
    `ollama` de la consola).
    """

    explicita = os.environ.get("BRAIN_OLLAMA_URL", "").strip()

    if explicita:
        return explicita

    host = os.environ.get("OLLAMA_HOST", "").strip()

    if not host:
        return "http://127.0.0.1:11434"

    esquema = "http"

    if "://" in host:
        esquema, host = host.split("://", 1)

    host = host.rstrip("/")

    nombre, _, puerto = host.partition(":")

    if nombre in ("", "0.0.0.0", "::", "[::]"):
        nombre = "127.0.0.1"

    return f"{esquema}://{nombre}:{puerto or '11434'}"


class Config:
    """
    Configuración global de BRAIN.

    Variables de entorno opcionales:

    - BRAIN_DATOS:       carpeta donde se guardan los datos.
    - BRAIN_OLLAMA_URL:  dirección de Ollama (por defecto 127.0.0.1:11434).
    - BRAIN_MODELO:      modelo a usar (por defecto, el mejor instalado).
    - BRAIN_PENSAR:      1 para activar el "modo pensar" de Qwen3 (más lento).
    - BRAIN_CONTEXTO:    tamaño de memoria de la IA en tokens (por defecto 8192).
    - BRAIN_PUERTO:      puerto de la interfaz web (por defecto 8765).
    """

    # Carpeta del paquete "brain"
    ROOT = Path(__file__).resolve().parent.parent

    # Carpeta del proyecto (donde está main.py)
    PROYECTO = ROOT.parent

    # Todos los datos viven en <proyecto>/datos, junto a la personalidad
    # y los logs. (Antes había una segunda carpeta brain/datos duplicada.)
    if os.environ.get("BRAIN_DATOS"):
        DATOS = Path(os.environ["BRAIN_DATOS"])
    else:
        DATOS = PROYECTO / "datos"

    LOGS = DATOS / "logs"

    PERSONALIDAD = PROYECTO / "datos" / "conocimiento" / "personalidad.md"

    # Personalidad que viene de fábrica con BRAIN. Si existe la de arriba
    # (la del usuario), manda esa.
    PERSONALIDAD_BASE = ROOT / "core" / "personalidad_base.md"

    # 127.0.0.1 en lugar de "localhost": en Windows "localhost" suele
    # resolverse primero a IPv6 (::1) y Ollama escucha en IPv4.
    OLLAMA_URL = _url_ollama()

    # Vacío = elegir automáticamente entre los modelos instalados.
    MODELO = os.environ.get("BRAIN_MODELO", "").strip()

    PENSAR = _entorno_bool("BRAIN_PENSAR", False)

    # Memoria de trabajo de la IA (tokens). Ollama usa 4096 por defecto,
    # que se queda corto con la personalidad y las herramientas de BRAIN.
    CONTEXTO = _entorno_int("BRAIN_CONTEXTO", 8192)

    PUERTO_WEB = _entorno_int("BRAIN_PUERTO", 8765)

    # Modelo que descarga el instalador / el asistente de primer uso.
    MODELO_POR_DEFECTO = "qwen3:4b"

    VERSION = "0.7.0"

    NOMBRE = "BRAIN"
