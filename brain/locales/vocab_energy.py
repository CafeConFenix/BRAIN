"""Words used to recognise the sensors of a solar inverter and the electricity meter."""

VOCAB = {
    "en": {
        "energy_keywords_production": (
            "solar", "pv", "photovolt", "produc", "generat", "inverter", "panels", "huawei", "fronius",
            "solaredge", "growatt", "solax", "goodwe",
        ),
        "energy_support_production": ("total", "current", "power", "ac", "output"),
        "energy_keywords_consumption": ("consumption", "consum", "house", "home", "load", "demand"),
        "energy_support_consumption": ("total", "current", "power"),
        "energy_keywords_grid": ("grid", "import", "export", "meter", "feed", "buy", "sell"),
        "energy_support_grid": ("power", "current", "total"),
        "energy_discard": (
            "mppt", "string", "pv1", "pv2", "pv3", "pv4", "phase", "l1", "l2", "l3", "voltage", "current_a",
            "frequency", "daily", "today", "limit", "maximum", "rated", "nominal",
        ),
        "battery_words": ("battery", "soc"),
        "phone_words": ("phone", "mobile"),
    },
    "es": {
        "energy_keywords_production": ("fotovolt", "produc", "generac", "inversor", "placas"),
        "energy_support_production": ("actual", "potencia", "salida"),
        "energy_keywords_consumption": ("consumo", "casa", "hogar", "carga", "demanda", "vivienda"),
        "energy_support_consumption": ("actual", "potencia"),
        "energy_keywords_grid": ("red", "contador", "compra", "venta", "acometida"),
        "energy_support_grid": ("potencia", "actual"),
        "energy_discard": ("fase", "tension", "voltaje", "corriente", "frecuencia", "diaria", "hoy", "limite", "maxima"),
        "battery_words": ("bateria",),
        "phone_words": ("movil",),
    },
}
