from brain.base.module import ModuleBase
from brain.core.database import Database
from brain.i18n import t
from brain.utils.dates import validate_date


class Health(ModuleBase):
    name = "health"

    def __init__(self):
        super().__init__()
        self.db = Database()

    def save_weight(self, weight, date=None):
        """
        Saves the weight for a day. If there was already one for that day, it
        updates it instead of duplicating it.
        """

        weight = float(weight)

        if not 20 <= weight <= 500:
            raise ValueError(t("The weight {0} does not look right (it should be between 20 and 500).", weight))

        date = validate_date(date)

        self.db.save_weight(date, weight)

        return {"weight": weight, "date": date}

    def weight_history(self, limit=None):
        """Returns the weights, oldest to most recent."""

        return self.db.weight_history(limit)

    def current_weight(self):
        """Returns the most recent weight record (or None)."""

        records = self.weight_history()

        if not records:
            return None

        return records[-1]

    def weight_at(self, date):
        """
        Returns the weight for a date. If there is no record for that day,
        returns the latest earlier one and marks it as approximate.
        """

        date = validate_date(date)

        exact = self.db.exact_weight(date)

        if exact:
            return {**exact, "exact": True}

        previous = self.db.previous_weight(date)

        if previous:
            return {**previous, "exact": False, "searched": date}

        return None

    # ------------------------------------------------------------------
    # Other scale measurements (fat, BMI, water...)
    # ------------------------------------------------------------------

    def save_measurement(self, name, value, unit=None, date=None):
        """Saves a body measurement for a day (replaces one with that name on the same day)."""

        date = validate_date(date)

        self.db.save_measurement(date, str(name), float(value), unit)

        return {"name": name, "value": float(value), "unit": unit, "date": date}

    def measurements(self, name=None, limit=30):
        return self.db.measurements(name, limit)
