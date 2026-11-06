"""Words for the pantry: places at home, units, quantities, staples and meals."""

VOCAB = {
    "en": {
        "location_synonyms": {
            "fridge": "fridge", "refrigerator": "fridge", "icebox": "fridge",
            "freezer": "freezer", "deep freezer": "freezer",
            "pantry": "pantry", "cupboard": "pantry", "cupboards": "pantry", "cabinet": "pantry", "cabinets": "pantry",
            "kitchen": "pantry", "cellar": "pantry", "larder": "pantry",
            "tool": "tools", "tools": "tools", "garage": "tools", "shed": "tools", "workshop": "tools", "toolbox": "tools",
            "supplies": "supplies", "supply": "supplies", "consumable": "supplies", "consumables": "supplies",
            "cleaning": "supplies", "bathroom": "supplies", "first aid": "supplies",
        },
        # Regex pieces (alternatives) for the units that may follow a quantity: "2 packs", "3 cans".
        "units": ("units", "unit", "pieces", "piece", "pcs?\\.?", "packs?", "packages?", "bottles?", "cans?", "cartons?", "boxes", "box"),
        # Units of a recipe measure: "200 g of flour", "2 tablespoons of oil".
        "measure_units": (
            "kg", "kilos?", "kilograms?", "g", "grams?", "oz", "ounces?", "lbs?", "pounds?", "ml", "cl", "dl", "l",
            "liters?", "litres?", "tablespoons?", "tbsp", "teaspoons?", "tsp", "cups?", "glass(?:es)?", "cloves?",
            "pinch(?:es)?", "sprigs?", "leaf", "leaves", "slices?", "fillets?",
        ),
        "of_words": ("of",),
        "approx_words": ("approx(?:imately)?", "about"),
        "stopwords": ("of", "the", "a", "an", "and", "in", "with", "for", "some"),
        "staples": (
            "water", "olive oil", "salt", "sugar", "flour", "pepper", "paprika", "oregano", "cumin",
            "garlic powder", "cinnamon", "vinegar", "bay leaf",
        ),
        # Words that say where a pasted list goes.
        "fridge_words": ("fridge", "refrigerator"),
        "freezer_words": ("freezer",),
        "pantry_words": ("pantry", "inventory", "cupboard"),
        "shopping_words": ("shopping", "to buy", "supermarket", "i need", "we need", "grocery", "groceries"),
        "dinner_words": ("dinner", "supper"),
        "none_words": ("none", "remove"),
    },
    "es": {
        "location_synonyms": {
            "nevera": "fridge", "frigorifica": "fridge", "frigorifico": "fridge", "frigo": "fridge", "refrigerador": "fridge",
            "congelador": "freezer", "arcon": "freezer",
            "despensa": "pantry", "armario": "pantry", "armarios": "pantry", "almacen": "pantry", "bodega": "pantry",
            "alacena": "pantry", "cocina": "pantry",
            "herramienta": "tools", "herramientas": "tools", "garaje": "tools", "trastero": "tools", "taller": "tools",
            "consumible": "supplies", "consumibles": "supplies", "limpieza": "supplies", "botiquin": "supplies", "bano": "supplies",
        },
        "units": ("unidades", "unidad", "unids?\\.?", "unds?\\.?", "uds?\\.?", "u\\.?", "piezas?", "pzs?\\.?", "paquetes?", "botellas?", "latas?", "briks?", "packs?"),
        "measure_units": (
            "kg", "kilos?", "gr?", "gramos?", "ml", "cl", "dl", "l", "litros?", "cucharad(?:a|ita)s?", "cdas?\\.?",
            "cdtas?\\.?", "tazas?", "vasos?", "dientes?", "pizcas?", "ramitas?", "hojas?", "lonchas?", "rodajas?", "filetes?",
        ),
        "of_words": ("de",),
        "approx_words": ("aprox(?:imad[ao]s?)?",),
        "stopwords": ("de", "del", "la", "el", "los", "las", "y", "en", "al", "con", "para", "un", "una", "unos", "unas"),
        "staples": (
            "agua", "aceite de oliva", "sal", "azúcar", "harina", "pimienta", "pimentón", "orégano", "comino",
            "ajo en polvo", "canela", "vinagre", "laurel",
        ),
        "fridge_words": ("nevera", "frigorifico"),
        "freezer_words": ("congelador",),
        "pantry_words": ("despensa", "inventario"),
        "shopping_words": ("compra", "comprar", "supermercado", "me falta", "me faltan", "hace falta"),
        "dinner_words": ("cena", "cenar"),
        "none_words": ("ninguna", "quitar"),
    },
}
