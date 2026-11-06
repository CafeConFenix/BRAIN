from brain.modules.energy import Energy, RealtimeEnergy, describe
from brain.tools.decorators import tool

energy = Energy()
realtime = RealtimeEnergy()


@tool(
    description="Save the production of the solar panels for one day, in kWh.",
    category="energy",
    arguments={
        "kwh": "Energy produced in kWh, for example 32.5",
        "date": "Date YYYY-MM-DD. Omit if it is today.",
    },
)
def save_solar_production(kwh: float, date: str = None):
    """Save the solar production."""

    return {"saved": energy.record_production(kwh, date)}


@tool(
    description="Look up the solar production of the last days, with the total and the average in kWh.",
    category="energy",
    arguments={"days": "How many recent records to look at. Default 7."},
)
def show_solar_production(days: int = 7):
    """Look up the solar production."""

    result = energy.production(days)

    if not result["records"]:
        return {"message": "There is no solar production recorded."}

    return result


@tool(
    description=(
        "Read the solar inverter and the meter LIVE: how much electricity the panels produce right now, "
        "how much the home uses right now and whether electricity is being bought from or sold to the grid. "
        "Use it for questions like 'how much am I consuming?' or 'how much are the panels producing now?'."
    ),
    category="energy",
)
def show_energy_now():
    """Production, consumption and grid in real time."""

    reading = realtime.read()

    return {**reading, "summary": describe(reading)}


@tool(
    description=(
        "Advise how to make the most of solar energy: at what hours there is spare production (the best for the "
        "washing machine, dishwasher or water heater), when the home uses most and whether now is a good moment "
        "to run an appliance. It uses the inverter history BRAIN keeps. Use it for 'when do I run the washing "
        "machine?' or 'how do I save electricity?'."
    ),
    category="energy",
    arguments={"days": "Days of history to analyse. Default 14."},
)
def show_energy_tip(days: int = 14):
    """Advice on using solar energy."""

    analysis = energy.analyze(days)

    now = energy.now_moment(realtime.read())

    if now:
        analysis["now"] = now

    return analysis


@tool(
    description="Save the price of electricity (euros per kWh) to work out what the solar panels are worth. 'I pay 0.15 and I am paid 0.06 for the surplus'.",
    category="energy",
    arguments={
        "buy": "Euros per kWh you pay for electricity, for example 0.15",
        "sell": "Euros per kWh you are paid for the surplus. Optional.",
    },
)
def set_electricity_tariff(buy: float = None, sell: float = None):
    """Save the electricity tariff."""

    return {"tariff": energy.configure_tariff(buy, sell)}


@tool(
    description="Work out roughly how much money the solar panels have been worth in the last days. Use it for 'how much have I saved with the panels?'.",
    category="energy",
    arguments={"days": "How many recent daily records to use. Default 30."},
)
def show_solar_savings(days: int = 30):
    """Estimated savings with the panels."""

    return energy.solar_savings(days)


@tool(
    description="What a month of electricity costs (estimated from the inverter readings): euros paid to the grid, income from surplus and what the panels save. Use it for 'how much have I spent on electricity?'.",
    category="energy",
    arguments={"month": "YYYY-MM, 'this month' or 'last month'. Default this month."},
)
def show_electricity_cost(month: str = None):
    """Electricity cost of the month."""

    return energy.month_cost(month)


@tool(
    description="Compare what electricity costs this month with last month.",
    category="energy",
)
def compare_electricity_cost():
    """Compare the electricity cost."""

    return energy.compare_months()


@tool(
    description="Save the cheap period of the tariff (off-peak), for example 00:00 to 08:00 at 0.08 EUR/kWh. BRAIN uses it to work out the cost and to say when to run appliances.",
    category="energy",
    arguments={"since": "Start time HH:MM", "until": "End time HH:MM", "price": "Euros per kWh in that period, for example 0.08"},
)
def set_cheap_hours(since: str = None, until: str = None, price: str = None):
    """Save the cheap hours."""

    return {"tariff": energy.set_cheap_hours(since, until, price)}


@tool(
    description="Say what the cheap period of electricity is and whether it is cheap right now. Use it for 'is it a good moment to run the washing machine?'.",
    category="energy",
)
def show_cheap_hours():
    """Cheap hours of electricity."""

    return energy.cheap_hours()
