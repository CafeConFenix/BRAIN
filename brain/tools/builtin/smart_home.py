from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.smart_home import SmartHome
from brain.tools.decorators import tool

smart_home = SmartHome()

NAME = (
    "Name of the device or room, as the user would say it. "
    "Examples: 'living room light', 'bedroom blind', 'TV plug', 'kitchen lights'."
)
ALL = "true only if the user wants ALL the devices that match (for example 'all the living room lights'). Default false."


def _safe(function, *args, **kwargs):
    """Turn Home Assistant errors into a message for the AI."""

    try:
        return function(*args, **kwargs)
    except HomeAssistantError as error:
        return {"error": str(error)}


@tool(
    description=(
        "Turn on a device in the home (light, plug, fan, television...). "
        "A blind or curtain is opened. It also activates a scene."
    ),
    category="smart_home",
    arguments={"device": NAME, "all_items": ALL},
)
def turn_on(device: str, all_items: bool = False):
    """Turn a device on."""

    return _safe(smart_home.turn_on, device, all_items)


@tool(
    description=(
        "Turn off a device in the home (light, plug, fan, television, heating...). "
        "A blind or curtain is closed."
    ),
    category="smart_home",
    arguments={"device": NAME, "all_items": ALL},
)
def turn_off(device: str, all_items: bool = False):
    """Turn a device off."""

    return _safe(smart_home.turn_off, device, all_items)


@tool(
    description="Change the brightness, the color or the color temperature of a light (and turn it on if it was off).",
    category="smart_home",
    arguments={
        "device": NAME,
        "brightness": "Brightness from 1 to 100 (percentage). Optional.",
        "color": "Color: red, green, blue, yellow, orange, pink, purple, violet, lilac, cyan, turquoise or white. Optional.",
        "temperature": "Shade of the white light: warm, neutral or cool. Optional.",
        "all_items": ALL,
    },
)
def adjust_light(device: str, brightness: float = None, color: str = None, temperature: str = None, all_items: bool = False):
    """Adjust a light."""

    return _safe(smart_home.adjust_light, device, brightness, color, temperature, all_items)


@tool(
    description="Put a blind, curtain or awning at a specific position (0 = closed, 100 = fully open).",
    category="smart_home",
    arguments={"device": NAME, "position": "Opening percentage from 0 to 100.", "all_items": ALL},
)
def move_blind(device: str, position: float, all_items: bool = False):
    """Position a blind."""

    return _safe(smart_home.blind_position, device, position, all_items)


@tool(
    description="Set the temperature of a thermostat, air conditioner or heating.",
    category="smart_home",
    arguments={"device": NAME, "degrees": "Desired temperature in degrees Celsius (5 to 35).", "all_items": ALL},
)
def set_temperature(device: str, degrees: float, all_items: bool = False):
    """Set a temperature."""

    return _safe(smart_home.set_temperature, device, degrees, all_items)


@tool(
    description="Activate a scene or a script of the home (for example 'night', 'cinema', 'leaving home').",
    category="smart_home",
    arguments={"scene": "Name of the scene as the user says it."},
)
def activate_scene(scene: str):
    """Activate a scene."""

    return _safe(smart_home.activate_scene, scene)


@tool(
    description=(
        "List the devices of the home and their current state (lights on, blinds, thermostats, sensors...). "
        "Use it to know which lights are on or which devices exist."
    ),
    category="smart_home",
    arguments={
        "kind": "Kind of device: lights, plugs, blinds, thermostats, sensors, scenes... Optional.",
        "room": "Room to filter by, for example 'living room'. Optional.",
    },
)
def list_devices(kind: str = "", room: str = ""):
    """List devices and their state."""

    return _safe(smart_home.items, kind, room)


@tool(
    description="Check the state of a specific device or sensor (whether a light is on, the temperature of a room, whether a window is open...).",
    category="smart_home",
    arguments={"device": NAME},
)
def device_state(device: str):
    """State of a device."""

    return _safe(smart_home.state_of, device)


@tool(
    description="Say what is on right now in the home (lights, plugs, fans, television, climate control). Use it for 'what is on?' or before leaving home.",
    category="smart_home",
)
def whats_on():
    """List what is on."""

    return _safe(smart_home.on)


@tool(
    description="Look for offline devices in the home and sensors with a low battery. Use it for 'is anything broken or out of batteries at home?'.",
    category="smart_home",
    arguments={"battery_minimum": "Percentage below which the battery counts as low. Default 20."},
)
def devices_with_problems(battery_minimum: float = 20):
    """Devices with problems."""

    return _safe(smart_home.with_problems, float(battery_minimum))
