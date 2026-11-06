import json
import time
from calendar import monthrange
from datetime import datetime, timedelta

from brain.base.module import ModuleBase
from brain.core.config import Config
from brain.core.database import Database
from brain.i18n import noop, t, vocab
from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, read_config
from brain.modules.inventory import normalize
from brain.utils.dates import valid_hour, validate_date


class Energy(ModuleBase):
    name = "energy"

    def __init__(self):
        super().__init__()
        self.db = Database()

    def record_production(self, kwh, date=None):
        """Save the solar production of a day (updates it if it already existed)."""

        kwh = float(kwh)

        if not 0 <= kwh <= 10000:
            raise ValueError(t("The production of {0} kWh does not look right.", kwh))

        date = validate_date(date)

        self.db.save_production(date, kwh)

        return {"production": kwh, "date": date}

    def production(self, limit=7):
        """Latest solar production records, with their total and average."""

        records = self.db.production(limit)

        total = round(sum(r.get("production", 0) for r in records), 2)

        average = round(total / len(records), 2) if records else 0

        return {
            "records": records,
            "total_kwh": total,
            "average_kwh": average,
        }

    def set_cheap_hours(self, since=None, until=None, price=None):
        """Cheap period (off-peak): for example 00:00 to 08:00 at 0.08 EUR/kWh. With empty since/until it is removed."""

        data = self.data.read_module(self.name)
        tariff = dict(data.get("tariff") or {})

        if since in (None, "") and until in (None, ""):
            for key in ("offpeak_from", "offpeak_until", "offpeak_price"):
                tariff.pop(key, None)
        else:
            tariff["offpeak_from"] = valid_hour(since, allow_24=True)
            tariff["offpeak_until"] = valid_hour(until, allow_24=True)
            number = float(str(price).replace(",", ".")) if price not in (None, "") else None

            if number is None or not 0 < number <= 5:
                raise ValueError(t("Give the price per kWh during those hours (for example 0.08)."))

            tariff["offpeak_price"] = round(number, 4)

        data["tariff"] = tariff
        self.data.save_module(self.name, data)

        return tariff

    @staticmethod
    def _in_offpeak(tariff, hour_min) -> bool:
        if not tariff.get("offpeak_from"):
            return False

        def minutes(t):
            h, m = t.split(":")
            return int(h) * 60 + int(m)

        d, h = minutes(tariff["offpeak_from"]), minutes(tariff["offpeak_until"])

        return d <= hour_min < h if d < h else (hour_min >= d or hour_min < h)

    def month_cost(self, month=None) -> dict:
        """
        Estimate in euros of what a month of electricity costs, from the inverter readings:
        energy bought from the grid (at normal or off-peak price), sold, and what the panels save.
        """

        from brain.modules.expenses import interpret_month

        month = interpret_month(month)
        tariff = self.tariff()

        if not tariff.get("buy"):
            return {"error": t("First tell me how much you pay per kWh (for example 0.15 EUR) with set_electricity_tariff.")}

        year, number = int(month[:4]), int(month[5:])
        rows = self.db.energy_readings(since=f"{month}-01", limit=200000)
        rows = [f for f in rows if str(f["date"]).startswith(month)]
        bought = sold = self_consumption = cost = income = 0.0
        normal_cost_all = 0.0
        previous = None

        for row in rows:
            moment = datetime.fromisoformat(row["date"])

            if previous is not None:
                hours = min((moment - previous[0]).total_seconds(), 1800) / 3600
                grid, production, consumption = previous[1], previous[2] or 0, previous[3]
                price = tariff["offpeak_price"] if self._in_offpeak(tariff, previous[0].hour * 60 + previous[0].minute) else tariff["buy"]

                if grid is not None:
                    if grid > 0:
                        kwh = grid * hours / 1000
                        bought += kwh
                        cost += kwh * price
                    elif grid < 0:
                        kwh = -grid * hours / 1000
                        sold += kwh
                        income += kwh * tariff.get("sell", 0)

                if consumption is not None:
                    home_expense = consumption * hours / 1000
                    normal_cost_all += home_expense * tariff["buy"]
                    self_consumption += max(0.0, home_expense - (max(grid, 0) * hours / 1000 if grid is not None else 0))

            previous = (moment, row["grid_w"], row["production_w"], row["consumption_w"])

        panel_savings = round(self_consumption * tariff["buy"], 2)

        return {
            "month": month,
            "days_with_data": len({str(f["date"])[:10] for f in rows}),
            "days_in_month": monthrange(year, number)[1],
            "kwh_bought": round(bought, 2),
            "kwh_sold": round(sold, 2),
            "kwh_self_consumed": round(self_consumption, 2),
            "cost_eur": round(cost, 2),
            "surplus_income_eur": round(income, 2),
            "panel_savings_eur": panel_savings,
            "net_eur": round(cost - income, 2),
            "note": "Estimate based on the saved readings; it does not replace your bill.",
        }

    def compare_months(self) -> dict:
        current, previous = self.month_cost("this month"), self.month_cost("last month")

        if "error" in current:
            return current

        difference = round(current["net_eur"] - previous["net_eur"], 2)

        return {"this_month": current, "last_month": previous, "difference_eur": difference, "best": difference <= 0 if previous["days_with_data"] else None}

    def cheap_hours(self) -> dict:
        tariff = self.tariff()

        if not tariff.get("offpeak_from"):
            return {"message": "No cheap period is set. Tell me from what hour to what hour electricity is cheaper and the price per kWh."}

        return {"since": tariff["offpeak_from"], "until": tariff["offpeak_until"], "offpeak_price": tariff["offpeak_price"], "normal_price": tariff.get("buy"), "now_is_cheap": self._in_offpeak(tariff, datetime.now().hour * 60 + datetime.now().minute)}

    def configure_tariff(self, buy=None, sell=None):
        """Electricity price in euros per kWh: what you pay (buy) and what you are paid for surplus (sell)."""

        data = self.data.read_module(self.name)
        tariff = dict(data.get("tariff") or {})

        for key, value in (("buy", buy), ("sell", sell)):
            if value in (None, ""):
                continue

            number = float(str(value).replace(",", "."))

            if not 0 < number <= 5:
                raise ValueError(t("The {0} price must be greater than 0 and in euros per kWh (for example 0.15).", key))

            tariff[key] = round(number, 4)

        if not tariff:
            raise ValueError(t("Give at least the price you pay for electricity (euros per kWh)."))

        data["tariff"] = tariff
        self.data.save_module(self.name, data)

        return tariff

    def tariff(self):
        value = self.data.read_module(self.name).get("tariff")

        return dict(value) if isinstance(value, dict) else {}

    def solar_savings(self, days=30):
        """
        Approximate value of what the panels produced in the last days.

        This is an estimate: if all the energy had been used at home it would be worth
        `buy` per kWh; if it had all been sold, `sell` per kWh.
        """

        tariff = self.tariff()

        if not tariff.get("buy"):
            return {"error": t("First tell me how much you pay per kWh (for example 0.15 EUR) with set_electricity_tariff.")}

        summary = self.production(max(1, int(days)))

        if not summary["records"]:
            return {"message": "There is no solar production recorded to calculate the savings."}

        kwh = summary["total_kwh"]
        result = {
            "days_with_data": len(summary["records"]),
            "kwh_produced": kwh,
            "max_value_eur": round(kwh * tariff["buy"], 2),
            "note": "Estimate: the maximum assumes everything is used at home; the minimum, that everything is sold to the grid.",
        }

        if tariff.get("sell"):
            result["min_value_eur"] = round(kwh * tariff["sell"], 2)

        return result

    def record_reading(self, reading):
        """
        Save in SQLite a reading from RealtimeEnergy.read() to keep
        a history. Returns True if there was data to save.
        """

        if not isinstance(reading, dict) or not reading.get("configured") or reading.get("error"):
            return False

        fields = ("production_w", "consumption_w", "grid_w", "battery_pct")

        if all(reading.get(c) is None for c in fields):
            return False

        self.db.save_energy_reading(
            datetime.now().isoformat(timespec="seconds"),
            reading.get("production_w"),
            reading.get("consumption_w"),
            reading.get("grid_w"),
            reading.get("battery_pct"),
        )

        return True

    def analyze(self, days=14):
        """
        Analyse the reading history: at what hours there is spare solar production
        (the best for the washing machine, dishwasher, water heater...), when the home
        uses most and how the daily production is going.
        """

        days = max(1, int(days))
        since = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")

        hours = self.db.energy_by_hour(since)
        samples = sum(h["n"] for h in hours)

        result = {"analyzed_days": days, "samples": samples}

        if samples < 20:
            result["message"] = (
                "There is not enough inverter data yet to advise you. BRAIN saves it every few minutes "
                "while it is open and Home Assistant is connected; ask again in a couple of days."
            )

            return self._with_daily_production(result)

        table = []

        for h in hours:
            production = h["production"] or 0
            consumption = h["consumption"] if h["consumption"] is not None else None
            surplus = production - consumption if consumption is not None else production

            table.append(
                {
                    "hour": h["hour"],
                    "production_w": round(production),
                    "consumption_w": None if consumption is None else round(consumption),
                    "surplus_w": round(surplus),
                }
            )

        result["by_hour"] = table

        with_sun = [t for t in table if t["production_w"] > 100]

        if with_sun:
            best = sorted(with_sun, key=lambda t: t["surplus_w"], reverse=True)[:4]
            best.sort(key=lambda t: t["hour"])
            result["best_hours"] = [t["hour"] for t in best]
            result["average_surplus_w"] = round(sum(t["surplus_w"] for t in best) / len(best))

        consumptions = [t for t in table if t["consumption_w"] is not None]

        if consumptions:
            peak = max(consumptions, key=lambda t: t["consumption_w"])
            result["peak_hour"] = peak["hour"]
            result["peak_consumption_w"] = peak["consumption_w"]

        result["tip"] = self._write_tip(result)

        return self._with_daily_production(result)

    @staticmethod
    def _write_tip(r):
        parts = []

        best = r.get("best_hours")

        if best and r.get("average_surplus_w", 0) > 200:
            parts.append(
                f"The hours with the most spare sun are {', '.join(f'{h}:00' for h in best)} "
                f"(about {round(r['average_surplus_w'] / 1000, 1)} kW of surplus on average): schedule the washing machine, "
                "the dishwasher or the water heater then."
            )
        elif best:
            parts.append("Your home uses almost everything the panels produce; there is no big surplus to take advantage of.")
        else:
            parts.append("I see no relevant solar production in the analysed period.")

        if r.get("peak_hour") is not None:
            parts.append(f"Your highest consumption is around {r['peak_hour']}:00 ({r['peak_consumption_w']} W on average).")

        return " ".join(parts)

    def _with_daily_production(self, result):
        records = self.db.production(14)

        if records:
            last = records[-7:]
            result["daily_production"] = {
                "average_7_days_kwh": round(sum(r["production"] for r in last) / len(last), 1),
                "best_day": max(records, key=lambda r: r["production"]),
            }

        return result

    def now_moment(self, reading):
        """Immediate advice from the live reading (is it a good moment to run an appliance?)."""

        if not isinstance(reading, dict) or not reading.get("configured") or reading.get("error"):
            return None

        production, consumption = reading.get("production_w"), reading.get("consumption_w")

        if production is None or consumption is None:
            return None

        surplus = production - consumption

        if surplus >= 800:
            return f"There is about {round(surplus)} W of spare sun right now: a good moment to run the washing machine or the dishwasher."

        if production < 100:
            return "There is no sun right now: better wait for the hours of highest production for the big appliances."

        return "The panels barely cover current consumption; if you can, wait until there is more spare sun."


# ----------------------------------------------------------------------
# Real-time energy (solar inverter and meter, through Home Assistant)
# ----------------------------------------------------------------------

ROLES = ("production", "consumption", "grid", "battery_pct")

ROLE_NAMES = {
    "production": noop("solar production (what the panels generate now)"),
    "consumption": noop("home consumption"),
    "grid": noop("exchange with the electricity grid"),
    "battery_pct": noop("battery charge (%)"),
}

def _hints(role):
    return vocab(f"energy_keywords_{role}"), vocab(f"energy_support_{role}")


def _discard():
    return vocab("energy_discard")

POWER_UNITS = {"w": 1.0, "kw": 1000.0, "mw": 1_000_000.0}

DETECTION_CACHE_SECONDS = 60


def _inverter_file():
    return Config.DATA / "energy" / "inverter.json"


def read_energy_sensors():
    """Sensors chosen by the user ({} if none)."""

    try:
        data = json.loads(_inverter_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    return data if isinstance(data, dict) else {}


def save_energy_sensors(sensors):
    file = _inverter_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(sensors, indent=4, ensure_ascii=False), encoding="utf-8")


def _to_watts(state):
    """Value of a power sensor in watts (None if it is not a number)."""

    try:
        value = float(state.get("state"))
    except (TypeError, ValueError):
        return None

    unit = str((state.get("attributes") or {}).get("unit_of_measurement", "W")).strip().lower()

    return value * POWER_UNITS.get(unit, 1.0)


def _is_power(state):
    attributes = state.get("attributes") or {}
    unit = str(attributes.get("unit_of_measurement", "")).strip().lower()

    if unit not in POWER_UNITS:
        return False

    return state.get("entity_id", "").startswith("sensor.")


def _score(role, text):
    """How well a sensor (by its name) fits a role. 0 = not at all."""

    keywords, reinforcement = _hints(role)

    if any(d in text for d in _discard()):
        return 0

    points = sum(2 for p in keywords if p in text)

    if not points:
        return 0

    return points + sum(1 for p in reinforcement if p in text)


def detect_sensors(states):
    """
    Look in Home Assistant for the sensors that seem to belong to the inverter, the
    home or the meter.

    Returns {role: [candidates]} with the best first. Each candidate is
    {entity, name, value_w}.
    """

    result = {role: [] for role in ROLES}

    for state in states:
        entity = state.get("entity_id", "")
        attributes = state.get("attributes") or {}
        name = attributes.get("friendly_name") or entity
        text = normalize(f"{name} {entity}").replace("_", " ")

        if state.get("state") in ("unavailable", "unknown", None):
            continue

        if _is_power(state):
            watts = _to_watts(state)

            if watts is None:
                continue

            for role in ("production", "consumption", "grid"):
                points = _score(role, text)

                if points:
                    result[role].append({"entity": entity, "name": name, "value_w": round(watts), "_p": points})

        elif attributes.get("device_class") == "battery" or (
            entity.startswith("sensor.") and str(attributes.get("unit_of_measurement", "")) == "%" and "batter" in text
        ):
            if any(p in text for p in vocab("battery_words")) and not any(p in text for p in vocab("phone_words")):
                result["battery_pct"].append({"entity": entity, "name": name, "value_w": None, "_p": 1})

    for role in ROLES:
        result[role].sort(key=lambda c: -c["_p"])

        for candidate in result[role]:
            candidate.pop("_p", None)

        result[role] = result[role][:6]

    return result


class RealtimeEnergy:
    """Live reading of production, consumption and grid from Home Assistant."""

    def __init__(self):
        self._client = None
        self._detection = None
        self._detection_until = 0.0

    def _ha(self):
        url, token = read_config()

        if self._client is None or (self._client.url, self._client.token) != (url, token):
            self._client = HomeAssistant(url, token, timeout=8)
            self._detection = None

        return self._client

    def _sensors(self, ha):
        """Sensors to use: the saved ones or, if there are none, the ones detected automatically."""

        saved = read_energy_sensors()

        if any(saved.get(role) for role in ROLES):
            return saved, False

        now = time.time()

        if self._detection is None or now > self._detection_until:
            candidates = detect_sensors(ha.states())
            self._detection = {role: (c[0]["entity"] if c else "") for role, c in candidates.items()}
            self._detection_until = now + DETECTION_CACHE_SECONDS

        return self._detection, True

    def read(self):
        """
        Current energy state of the home.

        Always returns a dictionary; if something fails it has "error" or
        "configured": False with an explanation.
        """

        ha = self._ha()

        if not ha.configured:
            return {
                "configured": False,
                "message": t("Connect Home Assistant first (CONFIGURE_SMART_HOME.bat) to see the inverter live."),
            }

        try:
            sensors, automatic = self._sensors(ha)

            values = {}

            for role in ROLES:
                entity = sensors.get(role)

                if not entity:
                    continue

                state = ha.state(entity)

                if role == "battery_pct":
                    try:
                        values[role] = round(float(state.get("state")))
                    except (TypeError, ValueError):
                        pass
                else:
                    watts = _to_watts(state)

                    if watts is not None:
                        values[role] = watts

        except HomeAssistantError as error:
            return {"configured": True, "error": str(error)}

        if not values:
            return {
                "configured": False,
                "message": t(
                    "I could not find the inverter in Home Assistant. Run CONFIGURE_ENERGY.bat to choose "
                    "the sensors (the inverter has to show up in Home Assistant first)."
                ),
            }

        production = values.get("production")
        grid = values.get("grid")

        if grid is not None and sensors.get("grid_inverted"):
            grid = -grid

        consumption = values.get("consumption")
        computed = False

        # Without a consumption sensor: home = what the panels produce + what is bought from the grid.
        if consumption is None and production is not None and grid is not None:
            consumption = max(0.0, production + grid)
            computed = True

        if grid is None:
            grid_state = None
        elif grid > 50:
            grid_state = "buying"
        elif grid < -50:
            grid_state = "selling"
        else:
            grid_state = "balanced"

        result = {
            "configured": True,
            "automatic": automatic,
            "production_w": None if production is None else round(production),
            "consumption_w": None if consumption is None else round(consumption),
            "computed_consumption": computed,
            "grid_w": None if grid is None else round(grid),
            "grid_state": grid_state,
            "battery_pct": values.get("battery_pct"),
            "hour": datetime.now().strftime("%H:%M:%S"),
        }

        if production is not None and consumption:
            result["solar_covered_pct"] = min(100, round(production * 100 / consumption)) if consumption > 0 else 0

        return result


def _format_power(watts):
    if watts is None:
        return t("no data")

    if abs(watts) >= 1000:
        return f"{watts / 1000:.2f} kW"

    return f"{watts:.0f} W"


def describe(reading):
    """Plain-language summary of a reading (for the AI and the console)."""

    if not reading.get("configured") or "error" in reading:
        return reading.get("error") or reading.get("message", t("There is no inverter data."))

    parts = []

    if reading.get("production_w") is not None:
        parts.append(t("The panels produce {0}", _format_power(reading["production_w"])))

    if reading.get("consumption_w") is not None:
        parts.append(t("the home uses {0}", _format_power(reading["consumption_w"])))

    grid = reading.get("grid_w")

    if grid is not None:
        if reading["grid_state"] == "buying":
            parts.append(t("{0} is bought from the grid", _format_power(grid)))
        elif reading["grid_state"] == "selling":
            parts.append(t("{0} is fed into the grid", _format_power(-grid)))
        else:
            parts.append(t("there is no exchange with the grid"))

    if reading.get("battery_pct") is not None:
        parts.append(t("battery at {0} %", reading["battery_pct"]))

    text = ", ".join(parts)

    return text[:1].upper() + text[1:] + "."
