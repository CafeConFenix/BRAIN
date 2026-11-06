from datetime import datetime

from brain.base.module import ModuleBase
from brain.core.database import Database
from brain.i18n import t, vocab
from brain.modules.inventory import normalize

TYPES = ("temperature", "humidity", "presence", "water", "light")


class Sensors(ModuleBase):
    """Readings of the home sensors, kept in the database."""

    name = "sensors"

    def __init__(self):
        super().__init__()
        self.db = Database()

    def normalize_type(self, kind):
        key = normalize(kind)
        key = vocab("sensor_synonyms").get(key, key)

        if key not in TYPES:
            raise ValueError(t("The sensor '{0}' does not exist. Options: {1}.", kind, ", ".join(TYPES)))

        return key

    def record(self, kind, value, location=None):
        kind = self.normalize_type(kind)

        reading = {
            "value": value,
            "location": location,
            "date": datetime.now().isoformat(timespec="seconds"),
        }

        self.db.save_sensor_reading(kind, value, location, reading["date"])

        return {"sensor": kind, **reading}

    def last(self, kind):
        kind = self.normalize_type(kind)

        readings = self.db.sensor_readings(kind, limit=1)

        if not readings:
            return None

        return {"sensor": kind, **readings[-1]}
