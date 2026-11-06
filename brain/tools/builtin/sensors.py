from brain.modules.sensors import Sensors
from brain.tools.decorators import tool

sensors = Sensors()

KINDS = "temperature, humidity, presence, water or light"


@tool(
    description="Save a reading of a home sensor (temperature, humidity, presence, water or light).",
    category="sensors",
    arguments={
        "kind": KINDS,
        "value": "Measured value, for example 21.5",
        "location": "Room or place. Optional.",
    },
)
def save_sensor(kind: str, value: float, location: str = None):
    """Save a sensor reading."""

    return {"saved": sensors.record(kind, value, location)}


@tool(
    description="Get the last recorded reading of a sensor.",
    category="sensors",
    arguments={"kind": KINDS},
)
def show_sensor(kind: str):
    """Last reading of a sensor."""

    reading = sensors.last(kind)

    if reading is None:
        return {"message": f"There are no readings for the sensor '{kind}'."}

    return reading
