"""
Import of product lists pasted as text.

Used by the chat (when the user pastes a long list), the web "Import list"
dialog and the AI tools, so a list of 40 products is always saved the same way,
whether or not the AI model copies it correctly.
"""

from brain.i18n import t, vocab
from brain.modules.inventory import LOCATIONS, normalize, parse_lines

# Places a list can be imported to ("shopping" is the shopping list).
DESTINATIONS = ("shopping",) + LOCATIONS

MIN_LIST_LINES = 4


def _has(words, text):
    return any(w in text for w in words)


def _destination_from_text(text):
    """Guess where the list goes from what the user says."""

    plain = normalize(text)

    if _has(vocab("fridge_words"), plain):
        return "fridge"

    if _has(vocab("freezer_words"), plain):
        return "freezer"

    if _has(vocab("shopping_words"), plain) and not _has(vocab("pantry_words"), plain):
        return "shopping"

    return "pantry"


def interpret_list(text, destination=None):
    """
    Understand a text with several products.

    Returns {"destination", "products": [(name, quantity)], "title"} or None if
    the text does not look like a list of products.

    With no ``destination`` it is guessed from the text and, with no clue, it is
    the pantry (never the shopping list by surprise).
    """

    lines = parse_lines(text)

    if not lines:
        return None

    title = ""

    # A first line with no quantity before others that have one is a title or an
    # introduction ("Add this to the pantry").
    if len(lines) > 2 and not lines[0][2]:
        rest = lines[1:]

        if sum(1 for _, _, explicit in rest if explicit) >= 0.8 * len(rest):
            title = lines[0][0]
            lines = rest

    if destination is None:
        destination = _destination_from_text(f"{title}\n{text[:300]}")

    if destination not in DESTINATIONS:
        destination = "pantry"

    return {
        "destination": destination,
        "title": title,
        "products": [(name, quantity) for name, quantity, _ in lines],
        "with_quantity": sum(1 for _, _, explicit in lines if explicit),
    }


def looks_like_pasted_list(text):
    """True if the message is a long list of products with quantities (not a question or a normal order)."""

    lines = [line for line in str(text).splitlines() if line.strip()]

    if len(lines) < MIN_LIST_LINES:
        return False

    parsed = interpret_list(text)

    if not parsed:
        return False

    products = len(parsed["products"])

    return products >= MIN_LIST_LINES - 1 and parsed["with_quantity"] >= 0.6 * products


def apply_list(parsed, inventory, shopping):
    """Save the interpreted list. Returns a summary."""

    destination = parsed["destination"]
    products = parsed["products"]

    if destination == "shopping":
        shopping.add_many(products)
        text = t("Done: I added {0} products to the shopping list.", len(products))
    else:
        inventory.add_many(products, destination)
        names = {"pantry": t("the pantry"), "fridge": t("the fridge"), "freezer": t("the freezer")}
        text = t("Done: I added {0} products to {1}.", len(products), names.get(destination, destination))

    return {
        "destination": destination,
        "total": len(products),
        "units": sum(c for _, c in products),
        "text": text,
    }
