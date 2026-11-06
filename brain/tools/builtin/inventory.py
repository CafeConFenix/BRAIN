from brain.modules.inventory import Inventory, parse_list, same_product
from brain.modules.shopping import Shopping
from brain.tools.decorators import tool

inventory = Inventory()
shopping = Shopping()

LOCATION_HELP = "fridge, freezer, pantry, tools or supplies."


@tool(
    description="Add a product to the home inventory (or add units if it already exists).",
    category="inventory",
    arguments={
        "name": "Product name, for example 'milk'",
        "quantity": "Number of units. Default 1.",
        "location": LOCATION_HELP + " Default pantry.",
        "expires": "Expiry date YYYY-MM-DD (optional).",
    },
)
def add_inventory(name: str, quantity: float = 1, location: str = "pantry", expires: str = None):
    """Add a product to the inventory."""

    return {"saved": inventory.add(name, quantity, location, expires)}


@tool(
    description=(
        "Add SEVERAL products to the inventory at once. ALWAYS use it when the user gives you a list "
        "or mentions two or more products; never call add_inventory many times in a row."
    ),
    category="inventory",
    arguments={
        "products": (
            "All the products, one per line, as the user said them. They may carry a quantity: "
            "'Whole milk, 2 units', '2 x milk', 'Bread x3'. Without a quantity 1 is assumed."
        ),
        "location": LOCATION_HELP + " Default pantry.",
    },
)
def add_many_to_inventory(products: str, location: str = "pantry"):
    """Add many products to the inventory."""

    pairs = parse_list(products)

    if not pairs:
        return {"error": "I did not understand any product in the text."}

    result = inventory.add_many(pairs, location)

    return {
        "location": result["location"],
        "total_products": len(result["added"]),
        "added": [f"{a['name']} (x{a['total_quantity']})" for a in result["added"]],
    }


@tool(
    description=(
        "The user says something HAS RUN OUT or is gone (\"we ran out of milk\", \"there is no oil left\"). "
        "Removes it from the inventory and adds it to the shopping list automatically."
    ),
    category="inventory",
    arguments={
        "product": "Name of the product that ran out",
        "quantity_to_buy": "Units to buy. Default 1.",
    },
)
def ran_out(product: str, quantity_to_buy: float = 1):
    """Remove a depleted product from the inventory and add it to the shopping list."""

    removed = None

    try:
        existing = inventory.search(product)

        if existing:
            removed = inventory.remove(existing[0]["name"], existing[0].get("quantity", 1) or 1, existing[0]["location"])
    except ValueError:
        pass

    # Use the name it already had in the inventory, if it was there.
    name = removed["name"] if removed else str(product).strip()

    in_shopping = shopping.add(name, quantity_to_buy)

    return {
        "added_to_shopping": in_shopping,
        "removed_from_inventory": bool(removed),
    }


@tool(
    description="Take units of a product out of the inventory (used up). At zero it is added to the shopping list.",
    category="inventory",
    arguments={
        "name": "Product name",
        "quantity": "Units to remove. Default 1.",
        "location": "A specific location. Omit to look in all of them.",
    },
)
def remove_from_inventory(name: str, quantity: float = 1, location: str = None):
    """Take a product out of the inventory."""

    result = inventory.remove(name, quantity, location)

    # Nothing left: add it to the shopping list to restock it.
    if result.get("remaining_quantity") == 0:
        shopping.add(result["name"], 1)
        result["added_to_shopping"] = True

    return result


@tool(
    description="Show what is in the inventory, in every location or in a specific one.",
    category="inventory",
    arguments={"location": LOCATION_HELP + " Omit to see everything."},
)
def show_inventory(location: str = None):
    """List the inventory."""

    content = inventory.items(location)

    if not content or not any(content.values()):
        if location:
            # The AI sometimes asks for a place other than the one used when saving.
            other = inventory.items()

            if any(other.values()):
                return {
                    "message": f"There is nothing in '{location}', but there is in other locations.",
                    "inventory": other,
                }

        return {"message": "The inventory is empty."}

    return {place: [f"{p['name']} (x{p.get('quantity', 1)})" for p in products] for place, products in content.items()}


@tool(
    description="Look for a product in the inventory and say where it is and how many there are.",
    category="inventory",
    arguments={"text": "Part of the product name"},
)
def search_inventory(text: str):
    """Search the inventory."""

    found = inventory.search(text)

    if not found:
        return {"message": f"There is nothing similar to '{text}' in the inventory."}

    return {"found": found}


@tool(
    description="Remove a product from the inventory completely (all its units), for example because it was added by mistake.",
    category="inventory",
    arguments={
        "name": "Product name",
        "location": "A specific location. Omit to look in all of them.",
    },
)
def delete_from_inventory(name: str, location: str = None):
    """Delete a product from the inventory."""

    return {"deleted": [f"{p['name']} ({p['location']})" for p in inventory.delete(name, location)]}


@tool(
    description=(
        "DELETE EVERYTHING in the inventory or in one location. Use it only if the user explicitly asks "
        "(\"empty the pantry\", \"delete the whole inventory\")."
    ),
    category="inventory",
    arguments={"location": LOCATION_HELP + " Omit to empty everything."},
)
def clear_inventory(location: str = None):
    """Empty the inventory."""

    return {"deleted": inventory.empty(location)}


@tool(
    description=(
        "Give the list of ingredients that can be cooked with at home: what is in the pantry, the fridge and the "
        "freezer PLUS the staples of any kitchen (oil, salt, water, flour, sugar, spices...). "
        "ALWAYS CALL IT BEFORE suggesting a recipe or saying what can be cooked or had for dinner."
    ),
    category="recipes",
)
def available_ingredients():
    """Ingredients to cook with."""

    ingredients = inventory.ingredients_to_cook()

    return {
        **ingredients,
        "how_to_use": (
            "Suggest recipes using ONLY these ingredients. Staples are assumed (they do not need to be bought). "
            "If a recipe needs something that is not there, say so and offer to add it to the shopping list. "
            "If the inventory is empty, say so and suggest something made only with the staples."
        ),
    }


@tool(
    description="Show the household staples BRAIN assumes for recipes (oil, salt, spices...).",
    category="recipes",
)
def list_staples():
    """List the staples."""

    return {"staples": inventory.staples()}


@tool(
    description="Add an ingredient to the household staples (something that is always there: white wine, stock, milk...).",
    category="recipes",
    arguments={"name": "Staple ingredient, for example 'chicken stock'"},
)
def add_staple(name: str):
    """Add a staple."""

    return {"staples": inventory.add_staple(name)}


@tool(
    description="Remove an ingredient from the household staples (something that is no longer always in the kitchen).",
    category="recipes",
    arguments={"name": "Ingredient to remove from the staples"},
)
def remove_staple(name: str):
    """Remove a staple."""

    return {"staples": inventory.remove_staple(name)}


@tool(
    description=(
        "When the user wants to cook a recipe: compare its ingredients with the fridge, the freezer, "
        "the pantry and the household staples, and add to the shopping list, in one go, only those "
        "that are missing or depleted. Those already at home or already on the list are not duplicated. "
        "Returns what was added and what was already available."
    ),
    category="recipes",
    arguments={
        "ingredients": "All the ingredients of the recipe, one per line or separated by commas. They may carry a quantity: '2 eggs', '200 g flour'.",
        "recipe": "Recipe name, only for the summary. Optional.",
    },
)
def add_recipe_missing_to_shopping(ingredients: str, recipe: str = None):
    """Add the ingredients of a recipe that are not at home to the shopping list."""

    text = ingredients

    if isinstance(text, str) and "\n" not in text and ";" not in text and "," in text:
        text = text.replace(",", "\n")

    if not parse_list(text):
        return {"error": "I did not understand any ingredient in the text."}

    comparison = inventory.compare_recipe(text)

    in_list = [i.get("product", "") for i in shopping.items()]

    def logged(name):
        return any(same_product(name, p) for p in in_list)

    new = [(n, c) for n, c in comparison["missing"] if not logged(n)]
    already_logged = [n for n, _ in comparison["missing"] if logged(n)]

    if new:
        shopping.add_many(new)  # a single write: either all are saved or none

    available = [f"{d['ingredient']} ({d['en']})" for d in comparison["available"]]
    added = [n for n, _ in new]

    parts = []

    if added:
        parts.append(f"Added to the shopping list: {', '.join(added)}.")

    if already_logged:
        parts.append(f"Already on the list: {', '.join(already_logged)}.")

    if available:
        parts.append(f"You already have: {', '.join(available)}.")

    if not added and not already_logged:
        parts = ["Nothing is missing: you have all the ingredients."]

    return {
        "recipe": recipe,
        "added_to_shopping": [{"product": n, "quantity": c} for n, c in new],
        "were_already_in_list": already_logged,
        "already_available": comparison["available"],
        "depleted": comparison["depleted"],
        "summary": " ".join(parts),
    }


@tool(
    description="Set or change the expiry date of a product already at home. Use it for 'the milk expires on the 25th'.",
    category="inventory",
    arguments={"product": "Product name", "date": "Date YYYY-MM-DD. Empty to remove it."},
)
def set_expiry(product: str, date: str = ""):
    """Set the expiry of a product."""

    return {"updated": inventory.set_expiry(product, date)}


@tool(
    description="List what is expired or expires soon at home. Use it for 'what expires this week?' or before suggesting recipes to use up food.",
    category="inventory",
    arguments={"days": "Look at the next N days (default 5)."},
)
def show_expiries(days: int = 5):
    """Products expiring soon."""

    items = inventory.expiring(days)

    if not items:
        return {"message": f"Nothing is expired or expires within {days} days (among the products with a date)."}

    return {"products": items}
