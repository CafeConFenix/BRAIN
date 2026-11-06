"""Words used to describe automations: days, conditions, magnitudes, triggers and actions."""

VOCAB = {
    "en": {
        "every_day_words": ("", "all", "every day", "everyday", "daily", "each day"),
        "weekday_words": ("weekdays", "working days", "workdays", "monday to friday", "week days"),
        "weekend_words": ("weekend", "weekends", "at the weekend", "saturday and sunday"),
        "condition_words": {
            "above": "above", "over": "above", "greater": "above", "more": "above", "higher": "above",
            "below": "below", "under": "below", "less": "below", "lower": "below", "fewer": "below",
            "equal": "equal", "equals": "equal", "is": "equal",
        },
        "magnitude_words": {
            "production": "production", "consumption": "consumption", "grid": "grid", "surplus": "surplus",
            "battery": "battery",
        },
        "trigger_words": {"hour": "hour", "time": "hour", "sensor": "sensor", "energy": "energy"},
        "action_words": {
            "notice": "notice", "alert": "notice", "notify": "notice", "turn_on": "turn_on", "turn_off": "turn_off",
            "scene": "scene",
        },
    },
    "es": {
        "every_day_words": ("todos los dias", "cada dia", "diario", "diaria", "todo", "todos"),
        "weekday_words": ("laborables", "entre semana", "dias laborables", "de lunes a viernes"),
        "weekend_words": ("fin de semana", "finde", "fines de semana"),
        "condition_words": {
            "mayor": "above", "menor": "below", "igual": "equal", "supera": "above", "baja": "below",
        },
        "magnitude_words": {
            "produccion": "production", "consumo": "consumption", "red": "grid", "sobrante": "surplus",
            "bateria": "battery",
        },
        "trigger_words": {"hora": "hour", "energia": "energy"},
        "action_words": {"aviso": "notice", "avisar": "notice", "escena": "scene"},
    },
}
