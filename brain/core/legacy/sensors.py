"""Sensors: Spanish names used before 2.0.0."""

_KINDS = {"humedad": "humidity", "presencia": "presence", "agua": "water", "luminosidad": "light"}

# sensors.json keeps one list of readings per kind of sensor.
KEYS = dict(_KINDS)

SQL_VALUES = {("sensors", "kind"): dict(_KINDS)}
