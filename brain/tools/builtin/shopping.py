from brain.modules.inventory import parse_list
from brain.modules.shopping import Shopping
from brain.tools.decorators import tool

shopping = Shopping()


@tool(
    description="Add a product to the shopping list.",
    category="shopping",
    arguments={
        "product": "Product name",
        "quantity": "Units. Default 1.",
    },
)
def add_to_shopping(product: str, quantity: float = 1):
    """Add to the shopping list."""

    return {"saved": shopping.add(product, quantity)}


@tool(
    description=(
        "Add SEVERAL products to the shopping list at once. Always use it when the user "
        "mentions two or more products (\"add milk, bread and eggs\")."
    ),
    category="shopping",
    arguments={
        "products": "The products, one per line or separated by commas/semicolons. They may carry a quantity: '2 x milk', 'bread, 3'.",
    },
)
def add_many_to_shopping(products: str):
    """Add several products to the shopping list."""

    # A comma separates products when there are no line breaks, semicolons or quantities.
    text = str(products)

    if "\n" not in text and ";" not in text and "," in text:
        text = text.replace(",", "\n")

    pairs = parse_list(text)

    if not pairs:
        return {"error": "I did not understand any product in the text."}

    return {"added": shopping.add_many(pairs), "total_products": len(pairs)}


@tool(
    description="Show the pending shopping list.",
    category="shopping",
)
def show_shopping_list():
    """Show the shopping list."""

    items = shopping.items()

    if not items:
        return {"message": "The shopping list is empty."}

    return {"shopping_list": items}


@tool(
    description="Mark a product as bought and take it off the shopping list.",
    category="shopping",
    arguments={"product": "Name of the product bought"},
)
def mark_bought(product: str):
    """Mark a product as bought."""

    return {"bought": shopping.bought(product)}


@tool(
    description="Take a product off the shopping list (no longer needed) without recording it as bought.",
    category="shopping",
    arguments={"product": "Name of the product to take off the list"},
)
def remove_from_shopping(product: str):
    """Take a product off the shopping list."""

    return {"removed": [i["product"] for i in shopping.remove(product)]}


@tool(
    description=(
        "DELETE THE WHOLE shopping list. Use it only if the user explicitly asks to empty or delete it entirely "
        "(\"delete the shopping list\", \"remove everything from the list\")."
    ),
    category="shopping",
)
def clear_shopping_list():
    """Empty the shopping list."""

    return {"deleted": shopping.empty()}
