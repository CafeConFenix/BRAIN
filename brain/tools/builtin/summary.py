from brain.modules.summary import Summary
from brain.tools.decorators import tool

summary = Summary()


@tool(
    description=(
        "Give the summary of the day: agenda for today and tomorrow, tasks, reminders, shopping list, yesterday's "
        "solar production, sensor alerts, warranties about to expire and weight. Use it for 'what do I have today?' "
        "or 'give me the summary'."
    ),
    category="summary",
    arguments={"send_as_notice": "true to also send it as a notification"},
)
def show_daily_summary(send_as_notice: bool = False):
    """Summary of the day."""

    data = summary.send() if send_as_notice else summary.compose()

    return {"title": data["title"], "summary": data["text"]}


@tool(
    description=(
        "Configure the automatic daily summary: the hour it arrives every morning, or turn it off. "
        "Example: 'send me the summary at 7:45'."
    ),
    category="summary",
    arguments={
        "hour": "Time HH:MM, for example 08:30",
        "active": "false to turn the daily summary off, true to turn it on",
    },
)
def set_daily_summary(hour: str = None, active: bool = None):
    """Configure the daily summary."""

    try:
        return {"config": summary.configure(active, hour)}
    except ValueError as error:
        return {"error": str(error)}
