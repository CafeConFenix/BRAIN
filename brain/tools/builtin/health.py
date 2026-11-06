from brain.i18n import t
from brain.modules.health import Health
from brain.tools.decorators import tool

health = Health()


@tool(
    description=(
        "Save the user's weight in kilos. If no date is given, today is used. "
        "If there was already a weight for that day, it is replaced."
    ),
    category="health",
    arguments={
        "weight": "Weight in kilos, for example 88.5",
        "date": "Date YYYY-MM-DD. Omit if it is today.",
    },
)
def save_weight(weight: float, date: str = None):
    """Save the user's weight."""

    saved = health.save_weight(weight=weight, date=date)

    return {"saved": saved}


@tool(
    description="Get the most recently recorded weight.",
    category="health",
)
def get_weight():
    """Get the current weight."""

    return health.current_weight()


@tool(
    description=(
        "Look up what the user weighed on a specific date. If there is no record for that day, "
        "returns the latest earlier one and marks it as approximate."
    ),
    category="health",
    arguments={"date": "Date YYYY-MM-DD (for example 2026-08-05)"},
)
def weight_on_date(date: str):
    """Weight on a date."""

    result = health.weight_at(date)

    if result is None:
        return {"message": t("There is no weight recorded on that date or earlier.")}

    return result


@tool(
    description="Return the weight history (oldest to most recent) to see how it has changed.",
    category="health",
    arguments={"quantity": "How many records to return at most. Default 10."},
)
def weight_history(quantity: int = 10):
    """Weight history."""

    records = health.weight_history(quantity)

    result = {"records": records}

    if len(records) >= 2:
        result["change_kg"] = round(records[-1]["weight"] - records[0]["weight"], 2)

    return result
