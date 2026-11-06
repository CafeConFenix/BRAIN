from brain.modules.menu import Menu
from brain.tools.decorators import tool

_menu = Menu()


@tool(
    description=(
        "Save the weekly menu you have planned (lunches and dinners) and add to the shopping list ONLY what is missing at home. "
        "Before calling it, look at the pantry (show_inventory / show_expiries) and think up the dishes yourself; do not ask the user what they want unless they ask you to."
    ),
    category="menu",
    arguments={
        "dishes": (
            "One line per dish in this format: 'monday lunch: Lentils | lentils, chorizo, carrot'. "
            "Days monday to sunday, lunch or dinner (lunch by default), ingredients after the bar."
        ),
        "buy_missing": "true to add what is missing to the shopping list (default true)",
    },
)
def save_weekly_menu(dishes: str, buy_missing: bool = True):
    """Save the menu of the week."""

    result = _menu.save(dishes)

    if buy_missing:
        result["shopping"] = _menu.add_missing_to_shopping()

    return result


@tool(
    description="Show the saved weekly menu. Use it for 'what is for dinner today?' or 'what is on the menu?'.",
    category="menu",
)
def show_weekly_menu():
    """The weekly menu."""

    result = _menu.show()

    return result if result["total_dishes"] else {"message": "There is no weekly menu. I can prepare one with what you have at home."}


@tool(
    description="Add to the shopping list the ingredients of the weekly menu that are missing at home.",
    category="menu",
)
def buy_menu_items():
    """Add to the shopping list what the menu is missing."""

    return _menu.add_missing_to_shopping()
