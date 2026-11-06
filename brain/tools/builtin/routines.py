from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.routines import Routines
from brain.tools.decorators import tool

routines = Routines()


@tool(
    description=(
        "Review the house before leaving or going to sleep: list what is on and what is pending. It does NOT turn "
        "anything off. Then ask the user whether they want it turned off and, only if they say yes, use turn_off_everything_on."
    ),
    category="smart_home",
    arguments={"moment": "'leaving' (leaving home) or 'night' (good night). Default leaving."},
)
def check_house(moment: str = "leaving"):
    """Review the house."""

    try:
        return routines.review("night" if any(w in str(moment).lower() for w in ("night", "noche", "sleep")) else "leaving")
    except HomeAssistantError as error:
        return {"error": str(error)}


@tool(
    description="Turn off EVERYTHING that is on in the home (lights, plugs, fans, TV...). Use it only after the user has confirmed.",
    category="smart_home",
)
def turn_off_everything_on():
    """Turn off everything that is on."""

    try:
        on = routines.review("leaving")["on"]

        return routines.turn_off([e["entity"] for e in on])
    except HomeAssistantError as error:
        return {"error": str(error)}
