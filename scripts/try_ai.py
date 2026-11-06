"""
Quick test of BRAIN with your REAL Ollama (not the simulated one from the tests).

Uses a temporary data folder, so it does NOT touch your real data.

    python scripts/try_ai.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ["BRAIN_DATA"] = tempfile.mkdtemp(prefix="brain_try_")

from brain.utils.console import prepare_console  # noqa: E402

prepare_console()

from brain.ai.ollama import OllamaError  # noqa: E402
from brain.cli import prepare_ai  # noqa: E402
from brain.core import Brain  # noqa: E402

QUESTIONS = [
    "Hi, who are you and what can you do?",
    "Today I weigh 88.4 kilos",
    "What is my current weight?",
    "Add milk and bread to the shopping list",
    "What is on the shopping list?",
    "Remember that my favorite color is blue",
    "What is my favorite color?",
]

brain = Brain(quiet=True, persistent_history=False)

ready, message = prepare_ai(brain, interactive=False)

if not ready:
    print(f"[BRAIN] {message}")
    sys.exit(1)

print(f"Model: {brain.ai.ollama.resolve_model()}\n")

failures = 0

for question in QUESTIONS:
    print(f"You   > {question}")

    try:
        response = brain.conversation.ask(question)
    except OllamaError as error:
        print(f"[Error] {error}")
        failures += 1
        continue

    used = ", ".join(h["name"] for h in brain.ai.tools_used) or "none"

    print(f"BRAIN > {response}")
    print(f"        (tools: {used})\n")

print("Test finished." if not failures else f"Test finished with {failures} error(s).")
sys.exit(1 if failures else 0)
