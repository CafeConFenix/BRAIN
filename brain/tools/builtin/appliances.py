from brain.modules.appliances import Appliances
from brain.tools.decorators import tool

appliances = Appliances()


@tool(
    description=(
        "Save a home appliance with its brand, model, purchase date and warranty. Use it when the user says "
        "they have or have bought an appliance ('I have a Bosch WAN28258ES washing machine bought in March, with a "
        "3 year warranty'). If the appliance already existed, it completes the new data without erasing the old."
    ),
    category="appliances",
    arguments={
        "name": "What it is: washing machine, fridge, oven, dishwasher, air conditioner...",
        "brand": "Brand, for example Bosch",
        "model": "Exact model, for example WAN28258ES",
        "location": "Where it is: kitchen, utility room...",
        "purchase_date": "Purchase date (YYYY-MM-DD)",
        "warranty_months": "Months of warranty from the purchase",
        "notes": "Any useful detail (color, installer, serial number...)",
    },
)
def add_appliance(
    name: str,
    brand: str = None,
    model: str = None,
    location: str = None,
    purchase_date: str = None,
    warranty_months: int = None,
    notes: str = None,
):
    """Save or update an appliance."""

    try:
        return {"saved": appliances.save(name, brand, model, location, purchase_date, warranty_months, notes)}
    except ValueError as error:
        return {"error": str(error)}


@tool(description="Show the registered appliances, with their model and the state of the warranty.", category="appliances")
def list_appliances():
    """List the appliances."""

    items = appliances.items()

    if not items:
        return {"message": "There are no appliances registered yet."}

    return {"appliances": items}


@tool(
    description="Delete an appliance from the register.",
    category="appliances",
    arguments={"name": "Name of the appliance"},
)
def remove_appliance(name: str):
    """Remove an appliance."""

    try:
        return {"removed": appliances.remove(name)["name"]}
    except ValueError as error:
        return {"error": str(error)}


@tool(
    description=(
        "When the user reports a fault or asks a question about one of their appliances ('the washing machine does not "
        "spin', 'the oven shows error E3'), use it: it returns the brand and model and the passages of the saved "
        "manuals. With that, explain what is wrong and how to fix it: if there is a manual, rely on it and say so; if "
        "not, use what you know about that specific model and warn that it does not come from the manual. If it "
        "involves gas, electricity or any risk, recommend a technician. If the appliance is not registered, ask for the "
        "brand and model and save them."
    ),
    category="appliances",
    arguments={
        "name": "Which appliance it is (washing machine, oven...)",
        "problem": "The fault or the error code, in the user's words",
    },
)
def query_appliance(name: str, problem: str = None):
    """Card and manuals of an appliance to diagnose a fault."""

    try:
        return appliances.query(name, problem)
    except ValueError as error:
        return {"error": str(error)}
