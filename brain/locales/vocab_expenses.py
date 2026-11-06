"""Expense categories: the words that reveal a category and the names it is known by."""

VOCAB = {
    "en": {
        "expense_hints": {
            "groceries": ("supermarket", "walmart", "tesco", "aldi", "lidl", "costco", "grocery", "groceries", "fruit", "vegetables", "meat", "fish"),
            "bills": ("electricity", "water bill", "gas bill", "internet", "broadband", "phone", "insurance", "rent", "mortgage", "bill", "tax"),
            "transport": ("petrol", "gasoline", "diesel", "fuel", "bus", "metro", "train", "taxi", "uber", "parking", "toll", "ticket", "car"),
            "leisure": ("cinema", "movie", "theatre", "theater", "concert", "netflix", "spotify", "game", "book", "trip", "hotel", "gym", "sport"),
            "health": ("pharmacy", "doctor", "dentist", "glasses", "physio", "medicine", "lab test"),
            "clothing": ("clothes", "shoes", "shirt", "trousers", "pants", "zara", "coat"),
            "restaurants": ("restaurant", "dinner out", "cafe", "coffee", "bar", "pizza", "burger", "brunch", "beer"),
            "home": ("ikea", "furniture", "repair", "diy", "hardware", "cleaning", "decoration", "appliance"),
        },
        "expense_categories": {},
    },
    "es": {
        "expense_hints": {
            "groceries": ("super", "mercadona", "lidl", "carrefour", "dia ", "aldi", "alcampo", "compra", "fruta", "verdura", "carne", "pescado"),
            "bills": ("luz", "agua", "gas", "internet", "fibra", "movil", "telefono", "seguro", "alquiler", "hipoteca", "comunidad", "factura", "impuesto"),
            "transport": ("gasolina", "diesel", "gasoil", "bus", "metro", "tren", "taxi", "uber", "parking", "peaje", "billete", "coche"),
            "leisure": ("cine", "teatro", "concierto", "netflix", "spotify", "juego", "libro", "viaje", "hotel", "gimnasio", "deporte"),
            "health": ("farmacia", "medico", "dentista", "gafas", "fisio", "medicina", "analitica"),
            "clothing": ("ropa", "zapatos", "camiseta", "pantalon", "zara", "abrigo"),
            "restaurants": ("restaurante", "cena", "comida fuera", "cafe", "bar", "pizza", "hamburguesa", "menu", "desayuno fuera", "cerveza"),
            "home": ("ikea", "muebles", "reparacion", "bricolaje", "leroy", "limpieza", "ferreteria", "decoracion", "electrodomestico"),
        },
        "expense_categories": {
            "supermercado": "groceries", "hogar": "home", "facturas": "bills", "transporte": "transport",
            "ocio": "leisure", "salud": "health", "ropa": "clothing", "restaurantes": "restaurants", "otros": "other",
        },
    },
}
