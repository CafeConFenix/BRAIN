"""
Register of home appliances: which appliances are at home, their brand and
model, when they were bought and how long the warranty lasts. If the user
keeps the manuals in data/documents/, BRAIN consults them to diagnose faults.
"""

import calendar
from datetime import date as Date, timedelta
from typing import List, Optional

from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.documents import DocumentError, Documents
from brain.modules.inventory import same_product, normalize
from brain.utils.dates import validate_date


def add_months(date: Date, months: int) -> Date:
    month = date.month - 1 + int(months)
    year = date.year + month // 12
    month = month % 12 + 1

    return Date(year, month, min(date.day, calendar.monthrange(year, month)[1]))


class Appliances(ModuleBase):
    name = "appliances"

    def devices(self) -> List[dict]:
        return self.get_section("devices")

    def _search(self, devices, name) -> dict:
        key = normalize(name)

        for a in devices:
            if normalize(a["name"]) == key:
                return a

        partial = [a for a in devices if same_product(name, a["name"]) or (key and key in normalize(f"{a['name']} {a.get('brand') or ''} {a.get('model') or ''}"))]

        if len(partial) == 1:
            return partial[0]

        if len(partial) > 1:
            raise ValueError(t("'{0}' matches several: {1}. Tell me which one.", name, ", ".join(a["name"] for a in partial)))

        registered = ", ".join(a["name"] for a in devices) or t("none")
        raise ValueError(t("I have no appliance '{0}' registered. Registered: {1}.", name, registered))

    def save(self, name, brand=None, model=None, location=None, purchase_date=None, warranty_months=None, notes=None) -> dict:
        """Register an appliance or, if it already existed, complete its data (without erasing what is not mentioned)."""

        name = str(name or "").strip()

        if not name:
            raise ValueError(t("The name of the appliance is missing (washing machine, fridge, oven...)."))

        devices = self.devices()
        existing = next((a for a in devices if normalize(a["name"]) == normalize(name)), None)

        gadget = existing or {"name": name, "added": Date.today().isoformat()}

        for field, value in (("brand", brand), ("model", model), ("location", location), ("notes", notes)):
            if value not in (None, ""):
                gadget[field] = str(value).strip()

        if purchase_date not in (None, ""):
            gadget["purchase_date"] = validate_date(purchase_date)

        if warranty_months not in (None, ""):
            months = int(float(warranty_months))

            if not 0 < months <= 600:
                raise ValueError(t("The warranty months do not look right."))

            if not gadget.get("purchase_date"):
                gadget["purchase_date"] = Date.today().isoformat()

            gadget["warranty_until"] = add_months(Date.fromisoformat(gadget["purchase_date"]), months).isoformat()

        if existing is None:
            devices.append(gadget)

        self.save_section("devices", devices)

        return {**gadget, "updated": existing is not None}

    def remove(self, name) -> dict:
        devices = self.devices()
        gadget = self._search(devices, name)

        self.save_section("devices", [a for a in devices if a is not gadget])

        return gadget

    @staticmethod
    def warranty_state(gadget, today: Optional[Date] = None) -> Optional[str]:
        until = gadget.get("warranty_until")

        if not until:
            return None

        days = (Date.fromisoformat(until) - (today or Date.today())).days

        if days < 0:
            return t("expired on {0}", until)

        if days <= 60:
            return t("expires in {0} days ({1})", days, until)

        return t("under warranty until {0}", until)

    def items(self) -> List[dict]:
        return [{**a, "warranty": self.warranty_state(a)} for a in sorted(self.devices(), key=lambda a: normalize(a["name"]))]

    def expiring_warranties(self, days=30, today: Optional[Date] = None) -> List[dict]:
        today = today or Date.today()
        limit = today + timedelta(days=days)

        return [
            a
            for a in self.devices()
            if a.get("warranty_until") and today <= Date.fromisoformat(a["warranty_until"]) <= limit
        ]

    def query(self, name, problem=None) -> dict:
        """Card of the appliance and fragments of its manuals (if any) related to the problem."""

        gadget = self._search(self.devices(), name)
        record = {**gadget, "warranty": self.warranty_state(gadget)}

        query = " ".join(str(x) for x in (gadget["name"], gadget.get("brand"), gadget.get("model"), problem) if x)

        try:
            fragments = Documents().search(query, 4)
        except DocumentError:
            fragments = []

        return {
            "gadget": record,
            "problem": problem,
            "manual_fragments": fragments,
        }
