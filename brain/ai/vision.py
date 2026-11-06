"""
Reads screenshots of a smart scale with an Ollama vision model.

The user sends a screenshot of their scale's app; the model extracts the
weight (and, if shown, fat, BMI, water...) and BRAIN validates it before saving:
a number out of range or unreadable is rejected instead of being saved wrong.
"""

import base64
import json
import re
from datetime import date as Date
from typing import Optional

from brain.ai.ollama import Ollama, OllamaError
from brain.i18n import t

MAX_BYTES = 8 * 1024 * 1024

PROMPT = """This image is a screenshot of a smart scale's app.
Read ONLY what is visible. Do not make up or estimate anything: if a value does not appear, put null.
Reply ONLY with a JSON object in this format, with no text before or after:
{"weight_kg": number or null, "date": "YYYY-MM-DD" or null,
 "measurements": {"body_fat_pct": null, "bmi": null, "water_pct": null, "muscle_mass_kg": null,
             "bone_mass_kg": null, "visceral_fat": null, "basal_metabolism_kcal": null, "body_age": null}}
The weight must be in kilograms (convert if it is in pounds). Use a decimal point."""

# saved name -> (unit, plausible minimum, plausible maximum)
MEASUREMENTS = {
    "body_fat_pct": ("%", 2, 65),
    "bmi": ("", 10, 70),
    "water_pct": ("%", 20, 80),
    "muscle_mass_kg": ("kg", 10, 120),
    "bone_mass_kg": ("kg", 0.5, 8),
    "visceral_fat": ("", 1, 60),
    "basal_metabolism_kcal": ("kcal", 500, 4000),
    "body_age": ("years", 10, 100),
}

LABELS = {
    "body_fat_pct": "body fat",
    "bmi": "BMI",
    "water_pct": "water",
    "muscle_mass_kg": "muscle mass",
    "bone_mass_kg": "bone mass",
    "visceral_fat": "visceral fat",
    "basal_metabolism_kcal": "basal metabolism",
    "body_age": "body age",
}


class VisionError(RuntimeError):
    """Error with a message the user can understand."""


def image_type(data: bytes) -> Optional[str]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"

    return None


def _number(value) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))

    return float(match.group(0).replace(",", ".")) if match else None


def interpret_response(text: str, today: Optional[Date] = None) -> dict:
    """Turns the model's response into a validated {"weight", "date", "measurements"}."""

    today = today or Date.today()

    match = re.search(r"\{.*\}", text or "", re.DOTALL)

    if not match:
        raise VisionError(t("I could not read the screenshot. Try a clearer image showing the weight."))

    try:
        data = json.loads(match.group(0))
    except ValueError:
        raise VisionError(t("I could not read the screenshot. Try a clearer image showing the weight.")) from None

    weight = _number(data.get("weight_kg"))

    if weight is None:
        raise VisionError(t("I don't see any weight in the image. Is it the scale's screen with the result?"))

    if not 20 <= weight <= 500:
        raise VisionError(t("I read {0:g} kg, which does not look right, so I am not saving it. Tell me the weight by hand or try another screenshot.", weight))

    date = today

    try:
        read = Date.fromisoformat(str(data.get("date")))

        if read <= today and (today - read).days <= 366:
            date = read
    except (TypeError, ValueError):
        pass

    measurements = {}

    for name, value in (data.get("measurements") or {}).items():
        if name not in MEASUREMENTS:
            continue

        number = _number(value)
        _, minimum, maximum = MEASUREMENTS[name]

        if number is not None and minimum <= number <= maximum:
            measurements[name] = round(number, 1)

    return {"weight": round(weight, 1), "date": date.isoformat(), "measurements": measurements}


def read_scale(ollama: Ollama, image: bytes, today: Optional[Date] = None) -> dict:
    """Reads a scale screenshot. Raises VisionError if it can't."""

    if not image or len(image) > MAX_BYTES:
        raise VisionError(t("The image is not valid or is too large (8 MB maximum)."))

    if image_type(image) is None:
        raise VisionError(t("Unsupported image format. Use a JPG, PNG or WebP screenshot."))

    try:
        model = ollama.vision_model()
    except OllamaError as error:
        raise VisionError(str(error)) from None

    if model is None:
        raise VisionError(
            t(
                "None of your AI models can read images. Install one with vision (for example "
                "'ollama pull gemma3:4b') and send the screenshot again."
            )
        )

    try:
        response = ollama.chat_with_image(PROMPT, base64.b64encode(image).decode("ascii"), model=model)
    except OllamaError as error:
        raise VisionError(t("I could not analyze the image: {0}", error)) from None

    result = interpret_response(response, today)
    result["model"] = model

    return result


def save_reading(health, result: dict) -> str:
    """Saves what was read (weight and measurements) and returns a message for the user."""

    health.save_weight(result["weight"], result["date"])

    for name, value in result["measurements"].items():
        health.save_measurement(name, value, MEASUREMENTS[name][0] or None, result["date"])

    def fmt(number):
        return f"{number:g}"

    extras = ", ".join(
        f"{t(LABELS[n])} {fmt(v)}{(' ' + MEASUREMENTS[n][0]) if MEASUREMENTS[n][0] else ''}" for n, v in result["measurements"].items()
    )

    text = t("I read from the screenshot: {0} kg ({1})", fmt(result["weight"]), result["date"])

    if extras:
        text += f" · {extras}"

    return text + ". " + t("I have saved it. If anything is wrong, tell me and I'll fix it.")
