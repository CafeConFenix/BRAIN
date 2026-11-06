from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.automations import Automations
from brain.tools.decorators import tool

automations = Automations()


@tool(
    description=(
        "Create an automation: an 'if this happens, do that' rule that BRAIN watches by itself. "
        "trigger 'hour': every day (or certain days) at a time ('turn on the living room light at 20:00'). "
        "trigger 'sensor': when a sensor or device of the home meets a condition ('if the living room temperature "
        "drops below 18, tell me'). trigger 'energy': when production, consumption, grid (W), solar surplus (W) "
        "or battery (%) meet a condition ('when more than 1500 W are spare, tell me so I can run the washing machine'). "
        "action: 'notice' (notification with sound), 'turn_on', 'turn_off' or 'scene'. It never controls locks, garages or alarms. "
        "Before creating it, summarise to the user the rule you understood."
    ),
    category="automations",
    arguments={
        "name": "Short name of the automation, for example 'Living room light at night'",
        "trigger": "hour, sensor or energy",
        "hour": "Only for 'hour': HH:MM, for example 20:00",
        "days": "Only for 'hour': 'all' (default), 'weekdays', 'weekend' or names like 'monday, thursday'",
        "sensor": "Only for 'sensor': sensor or device to watch, as the user would say it, for example 'living room temperature'",
        "magnitude": "Only for 'energy': production, consumption, grid, surplus or battery",
        "condition": "For 'sensor' and 'energy': above, below or equal",
        "value": "For 'sensor' and 'energy': the value to compare with (a number; for 'equal' on sensors it can be text like 'on')",
        "action": "notice, turn_on, turn_off or scene",
        "goal": "For turn_on, turn_off or scene: the device or the scene, as the user would say it",
        "message": "For 'notice': the text of the notification",
        "wait_minutes": "Minimum minutes between two runs (sensor and energy). Default 5.",
    },
)
def create_automation(
    name: str,
    trigger: str,
    action: str,
    hour: str = None,
    days: str = None,
    sensor: str = None,
    magnitude: str = None,
    condition: str = None,
    value: str = None,
    goal: str = None,
    message: str = None,
    wait_minutes: float = 5,
):
    """Create an automation."""

    try:
        spec = {"kind": trigger, "hour": hour, "days": days, "magnitude": magnitude, "condition": condition, "value": value}

        if str(trigger).strip().lower() == "sensor":
            spec.update(automations.resolve_sensor(sensor or ""))
            spec = {**spec, "entity": spec["entity"], "name": spec["name"]}

        automations.check_goal(action, goal or "")

        created = automations.create(
            name,
            spec,
            [{"kind": action, "goal": goal, "message": message}],
            wait_minutes,
        )

        return {"created": {"id": created["id"], "name": created["name"], "rule": created["summary"]}}
    except (ValueError, HomeAssistantError) as error:
        return {"error": str(error)}


@tool(description="Show the automations created, whether they are active and when they last ran.", category="automations")
def list_automations():
    """List the automations."""

    items = automations.items()

    if not items:
        return {"message": "There are no automations created."}

    return {"automations": items}


@tool(
    description="Delete an automation by its name.",
    category="automations",
    arguments={"name": "Name (or number) of the automation"},
)
def delete_automation(name: str):
    """Delete an automation."""

    try:
        return {"deleted": automations.delete(name)}
    except ValueError as error:
        return {"error": str(error)}


@tool(
    description="Activate or deactivate (pause) an automation without deleting it.",
    category="automations",
    arguments={"name": "Name (or number) of the automation", "active": "true to activate it, false to pause it"},
)
def enable_automation(name: str, active: bool = True):
    """Activate or pause an automation."""

    try:
        return automations.enable(name, active)
    except ValueError as error:
        return {"error": str(error)}


@tool(
    description="Run an automation right now, to test it, without waiting for its trigger.",
    category="automations",
    arguments={"name": "Name (or number) of the automation"},
)
def run_automation(name: str):
    """Run an automation now."""

    try:
        return automations.run_now(name)
    except (ValueError, HomeAssistantError) as error:
        return {"error": str(error)}
