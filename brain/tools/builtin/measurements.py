from brain.i18n import t
from brain.modules.health import Health
from brain.tools.decorators import tool

health = Health()


@tool(
    description=(
        "Show the body measurements saved from the scale (body fat, BMI, water, muscle mass, "
        "bone mass, visceral fat, basal metabolism, body age), oldest to most recent."
    ),
    category="health",
    arguments={
        "name": "A specific measurement, for example body_fat_pct or bmi. Omit for all of them.",
        "limit": "How many recent records. Default 14.",
    },
)
def show_body_measurements(name: str = None, limit: int = 14):
    """List the saved body measurements."""

    records = health.measurements(name, limit)

    if not records:
        return {"message": t("There are no body measurements saved. The user can send a photo of their scale in the chat.")}

    return {"measurements": records}
