"""Words for dates: weekdays, months and relative days, in every language."""

VOCAB = {
    "en": {
        "weekday_names": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "weekday_aliases": {
            "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        },
        "month_names": (
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ),
        "month_aliases": {
            "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
            "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        },
        "today_words": ("today",),
        "yesterday_words": ("yesterday",),
        "tomorrow_words": ("tomorrow",),
        "date_connectors": ("of",),
    },
    "es": {
        "weekday_names": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
        "weekday_aliases": {
            "lunes": 0, "lun": 0, "martes": 1, "mar": 1, "miercoles": 2, "mie": 2, "jueves": 3, "jue": 3,
            "viernes": 4, "vie": 4, "sabado": 5, "sab": 5, "domingo": 6, "dom": 6,
        },
        "month_names": (
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ),
        "month_aliases": {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
        },
        "today_words": ("hoy",),
        "yesterday_words": ("ayer",),
        "tomorrow_words": ("mañana", "manana"),
        "date_connectors": ("de",),
    },
}
