"""
Prueba rapida de BRAIN con tu Ollama REAL (no el simulado de los tests).

Usa una carpeta de datos temporal, asi que NO toca tus datos de verdad.

    python scripts/probar_ia.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["BRAIN_DATOS"] = tempfile.mkdtemp(prefix="brain_prueba_")

from brain.utils.consola import preparar_consola  # noqa: E402

preparar_consola()

from brain.ai.ollama import OllamaError  # noqa: E402
from brain.cli import preparar_ia  # noqa: E402
from brain.core import Brain  # noqa: E402

PREGUNTAS = [
    "Hola, ¿quién eres y qué sabes hacer?",
    "Hoy peso 88,4 kilos",
    "¿Cuál es mi peso actual?",
    "Apunta leche y pan en la lista de la compra",
    "¿Qué hay en la lista de la compra?",
    "Recuerda que mi color favorito es el azul",
    "¿Cuál es mi color favorito?",
]

brain = Brain(silencioso=True, historial_persistente=False)

listo, mensaje = preparar_ia(brain, interactivo=False)

if not listo:
    print(f"[BRAIN] {mensaje}")
    sys.exit(1)

print(f"Modelo: {brain.ai.ollama.resolver_modelo()}\n")

fallos = 0

for pregunta in PREGUNTAS:
    print(f"Tu    > {pregunta}")

    try:
        respuesta = brain.conversacion.preguntar(pregunta)
    except OllamaError as error:
        print(f"[Error] {error}")
        fallos += 1
        continue

    usadas = ", ".join(h["nombre"] for h in brain.ai.herramientas_usadas) or "ninguna"

    print(f"BRAIN > {respuesta}")
    print(f"        (herramientas: {usadas})\n")

print("Prueba terminada." if not fallos else f"Prueba terminada con {fallos} error(es).")
sys.exit(1 if fallos else 0)
