"""Pantry, shopping and menu: Spanish names used before 2.0.0."""

# The inventory file stores one list per location, so locations are JSON keys.
KEYS = {
    "frigorifico": "fridge",
    "congelador": "freezer",
    "despensa": "pantry",
    "consumibles": "supplies",
    "herramientas": "tools",
    "basicos": "staples",
    "_caducidades_avisadas": "_expiries_notified",
}

VALUES = {
    "location": {
        "frigorifico": "fridge",
        "congelador": "freezer",
        "despensa": "pantry",
        "consumibles": "supplies",
        "herramientas": "tools",
    },
    "moment": {"comida": "lunch", "cena": "dinner"},
}
