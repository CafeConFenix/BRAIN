import re
import unicodedata
from datetime import date as Date, timedelta

from brain.base.module import ModuleBase
from brain.i18n import language, t, vocab
from brain.utils.dates import validate_date

LOCATIONS = ("fridge", "freezer", "pantry", "tools", "supplies")

# Where food is kept (what a recipe can use).
FOOD_PLACES = ("fridge", "freezer", "pantry")


def _strip_accents(text):
    normal = unicodedata.normalize("NFD", str(text))

    return "".join(c for c in normal if unicodedata.category(c) != "Mn")


def normalize(text):
    """Lowercase and without accents, to compare names."""

    return _strip_accents(text).strip().lower()


def _alternatives(name):
    return "|".join(vocab(name))


UNITS = rf"(?:{_alternatives('units')})"

# "- ", "• ", "* ", "1. ", "2) " at the start of a list line.
BULLET = re.compile(r"^\s*(?:[-•*·–]|\d+[.)])\s+")

SEPARATOR = r"[,;:\s\-–]+"

QUANTITY_FINAL = re.compile(rf"{SEPARATOR}(\d+(?:[.,]\d+)?)\s*{UNITS}\s*$", re.IGNORECASE)
QUANTITY_X_FINAL = re.compile(r"\s+[xX×]\s*(\d+(?:[.,]\d+)?)\s*$")
QUANTITY_IN_PARENS = re.compile(r"\s*\(\s*(\d+(?:[.,]\d+)?)\s*\)\s*$")
QUANTITY_ONLY_COMMA = re.compile(r"[,:]\s*(\d+(?:[.,]\d+)?)\s*$")
QUANTITY_INITIAL = re.compile(rf"^\s*(\d+(?:[.,]\d+)?)\s*(?:[xX×]|{UNITS}\s+(?:{_alternatives('of_words')})|{UNITS})\s+(.+)$", re.IGNORECASE)

APPROX = re.compile(rf"[\s,;:(]*\b(?:{_alternatives('approx_words')})\.?\)?\s*$", re.IGNORECASE)


def _positive(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return True


def _number(text):
    number = float(text.replace(",", "."))

    return int(number) if number == int(number) else number


def parse_lines(text):
    """
    Turn a text with several products into [(name, quantity, explicit)].

    ``explicit`` is True if the line said how many units there were (and 1 was
    not assumed). One product per line (or separated by ";"):

      "Whole milk, 2 units" · "Milk: 2 units" · "Chicken 600 g approx.: 2 packs"
      "2 x milk" · "Milk x2" · "Bread, 3" · "Eggs (12)" · "Salt"

    Lines ending in ":" are titles and are ignored. A repeated product adds up.
    """

    if isinstance(text, (list, tuple)):
        text = "\n".join(str(t) for t in text)

    lines = re.split(r"[\n;]+", str(text))

    accumulated = {}
    order = []

    for line in lines:
        line = BULLET.sub("", line).strip()

        if not line or line.endswith(":"):
            continue

        line = line.rstrip(".").strip()

        quantity = 1
        explicit = False
        name = line

        for pattern in (QUANTITY_FINAL, QUANTITY_X_FINAL, QUANTITY_IN_PARENS, QUANTITY_ONLY_COMMA):
            match = pattern.search(name)

            if match:
                quantity = _number(match.group(1))
                explicit = True
                name = name[: match.start()]
                break
        else:
            initial = QUANTITY_INITIAL.match(name)

            if initial:
                quantity = _number(initial.group(1))
                explicit = True
                name = initial.group(2)

        name = APPROX.sub("", name).strip(" ,;:-–")

        if not name or quantity <= 0:
            continue

        key = normalize(name)

        if key in accumulated:
            accumulated[key][1] += quantity
            accumulated[key][2] = accumulated[key][2] or explicit
        else:
            accumulated[key] = [name, quantity, explicit]
            order.append(key)

    return [tuple(accumulated[c]) for c in order]


def parse_list(text):
    """Like parse_lines but returns only [(name, quantity), ...]."""

    return [(name, quantity) for name, quantity, _ in parse_lines(text)]


# "200 g of flour", "2 tablespoons of oil", "1 clove of garlic"...
INITIAL_MEASUREMENT = re.compile(
    rf"^\s*\d+(?:[.,]\d+)?\s*(?:{_alternatives('measure_units')})\b\s*(?:(?:{_alternatives('of_words')})\s+)?",
    re.IGNORECASE,
)

QUANTITY_LOOSE = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s+(?![xX×]\s)(\D.*)$")

STOPWORDS = set(vocab("stopwords"))


def _words(text):
    """Key words of a product name (no accents, plurals or articles)."""

    words = set()

    for word in re.findall(r"[a-z0-9ñ]+", normalize(text)):
        if word in STOPWORDS:
            continue

        # Rough stem: tomatoes/tomato -> tomato, limones/limon -> limon.
        if len(word) > 3 and word.endswith("s"):
            word = word[:-1]

        if len(word) > 4 and word.endswith("e"):
            word = word[:-1]

        words.add(word)

    return words


def same_product(a, b):
    """
    True if two names are the same product: the words of the shorter one are
    all in the longer one ("oil" and "olive oil" yes; "salt" and "salmon" no).
    """

    pa, pb = _words(a), _words(b)

    if not pa or not pb:
        return False

    short, longer = (pa, pb) if len(pa) <= len(pb) else (pb, pa)

    return short <= longer


def clean_ingredient(name, quantity=1):
    """
    Remove leading measures and numbers: '200 g of flour' -> 'flour',
    '2 eggs' -> 'eggs'. Returns (name, quantity).
    """

    text = str(name).strip()

    if INITIAL_MEASUREMENT.match(text):
        text = INITIAL_MEASUREMENT.sub("", text).strip(" ,;:-")
    else:
        loose = QUANTITY_LOOSE.match(text)

        if loose:
            quantity = _number(loose.group(1))
            text = loose.group(2).strip()

    return (text or str(name).strip()), quantity


def default_staples():
    """What every kitchen is assumed to have, in the interface language."""

    return list(vocab("staples", language() if language() in ("en", "es") else "en"))


def all_default_staples():
    """The default staples in every language (to recognise an ingredient in any of them)."""

    return list(vocab("staples"))


class Inventory(ModuleBase):
    name = "inventory"

    # ------------------------------------------------------------------
    # Recipes: what is missing
    # ------------------------------------------------------------------

    def compare_recipe(self, ingredients):
        """
        Compare the ingredients of a recipe (text or list) with the fridge,
        the freezer, the pantry and the household staples.

        Returns:
          available: [{ingredient, en}]  (en = location, or "staples")
          depleted:  [{ingredient, en}]  (in the inventory but with quantity 0)
          missing:   [(name, quantity)]  (nothing of it at home: what to buy)
        """

        requested = [clean_ingredient(n, c) for n, c in parse_list(ingredients)]

        food = []

        for place in FOOD_PLACES:
            for product in self.get_section(place):
                food.append((place, str(product.get("name", "")), product.get("quantity", 1)))

        staples = self.staples() + all_default_staples()

        available, depleted, missing = [], [], []

        for name, quantity in requested:
            matches = [(place, n, q) for place, n, q in food if same_product(name, n)]

            with_stock = [c for c in matches if _positive(c[2])]

            if with_stock:
                available.append({"ingredient": name, "en": with_stock[0][0]})
            elif any(same_product(name, b) for b in staples):
                available.append({"ingredient": name, "en": "staples"})
            else:
                if matches:
                    depleted.append({"ingredient": name, "en": matches[0][0]})

                missing.append((name, quantity))

        return {"available": available, "depleted": depleted, "missing": missing}

    # ------------------------------------------------------------------
    # Household staples (for recipes)
    # ------------------------------------------------------------------

    def staples(self):
        """The household staples: the user's own or, if untouched, the defaults."""

        saved = self.data.read_module(self.name).get("staples")

        if isinstance(saved, list):
            return [str(b) for b in saved]

        return default_staples()

    def add_staple(self, name):
        name = str(name).strip()

        if not name:
            raise ValueError(t("The name of the staple is missing."))

        staples = self.staples()

        if normalize(name) not in {normalize(b) for b in staples}:
            staples.append(name)
            self.save_section("staples", staples)

        return staples

    def remove_staple(self, name):
        key = normalize(name)

        staples = self.staples()

        remaining = [b for b in staples if normalize(b) != key]

        if len(remaining) == len(staples):
            raise ValueError(t("'{0}' is not among the household staples.", name))

        self.save_section("staples", remaining)

        return remaining

    def ingredients_to_cook(self):
        """Everything available to cook with: food in the inventory + household staples."""

        food = []

        for place in FOOD_PLACES:
            for product in sorted(self.get_section(place), key=lambda p: normalize(p.get("name", ""))):
                food.append(f"{product.get('name', '')} (x{product.get('quantity', 1)}, {place})")

        return {"inventory": food, "staples": self.staples()}

    def normalize_location(self, location, strict=False):
        """
        The official location. If it is not recognised and ``strict`` is False
        the pantry is used instead of failing (AI models invent names such as
        "kitchen" or "lower cupboard").
        """

        key = normalize(location or "pantry")
        synonyms = vocab("location_synonyms")

        key = synonyms.get(key, key)

        if key in LOCATIONS:
            return key

        for word in key.replace("-", " ").split():
            word = synonyms.get(word, word)

            if word in LOCATIONS:
                return word

        if strict:
            raise ValueError(t("The location '{0}' does not exist. Options: {1}.", location, ", ".join(LOCATIONS)))

        return "pantry"

    def add_many(self, products, location="pantry"):
        """
        Add many products at once (list of (name, quantity)).

        Reads and saves the file once and returns what was added.
        """

        location = self.normalize_location(location)

        existing = self.get_section(location)

        index = {normalize(p.get("name", "")): p for p in existing}

        added = []

        for name, quantity in products:
            key = normalize(name)

            if key in index:
                index[key]["quantity"] = index[key].get("quantity", 0) + quantity
            else:
                new = {"name": str(name).strip(), "quantity": quantity}
                existing.append(new)
                index[key] = new

            added.append({"name": index[key]["name"], "total_quantity": index[key]["quantity"]})

        self.save_section(location, existing)

        return {"location": location, "added": added}

    def everything(self):
        """Every product as a flat list [{location, name, quantity}]."""

        flat = []

        for place in LOCATIONS:
            for product in sorted(self.get_section(place), key=lambda p: normalize(p.get("name", ""))):
                row = {"location": place, "name": product.get("name", ""), "quantity": product.get("quantity", 1)}

                if product.get("expires"):
                    row["expires"] = product["expires"]

                flat.append(row)

        return flat

    def add(self, name, quantity=1, location="pantry", expires=None):
        """
        Add units of a product. If it already exists in that location the
        quantity is added up. ``expires`` (YYYY-MM-DD, optional) sets the expiry date.
        """

        expires = validate_date(expires) if expires not in (None, "") else None

        location = self.normalize_location(location)

        quantity = float(quantity)

        if quantity <= 0:
            raise ValueError(t("The quantity must be greater than zero."))

        if quantity == int(quantity):
            quantity = int(quantity)

        products = self.get_section(location)

        for product in products:
            if normalize(product.get("name", "")) == normalize(name):
                product["quantity"] = product.get("quantity", 0) + quantity

                if expires:
                    product["expires"] = expires

                self.save_section(location, products)

                return {**product, "location": location}

        new = {"name": str(name).strip(), "quantity": quantity}

        if expires:
            new["expires"] = expires

        products.append(new)

        self.save_section(location, products)

        return {**new, "location": location}

    def _matches(self, key, product):
        """Exact name, or "milk" finds "Whole milk Brand"."""

        existing = normalize(product.get("name", ""))

        return existing == key or (len(key) >= 3 and key in existing)

    def remove(self, name, quantity=1, location=None):
        """
        Subtract units of a product (in one location or in all). At zero it is removed.
        """

        quantity = float(quantity)

        locations = [self.normalize_location(location)] if location else list(LOCATIONS)

        # If it is not in the given place, look in the rest too.
        if location:
            locations += [u for u in LOCATIONS if u not in locations]

        key = normalize(name)

        for place in locations:
            products = self.get_section(place)

            for product in products:
                if not self._matches(key, product):
                    continue

                remaining = product.get("quantity", 0) - quantity

                if remaining <= 0:
                    products.remove(product)
                    remaining = 0
                else:
                    product["quantity"] = int(remaining) if remaining == int(remaining) else remaining

                self.save_section(place, products)

                return {
                    "name": product.get("name"),
                    "location": place,
                    "remaining_quantity": remaining,
                }

        raise ValueError(t("I can't find '{0}' in the inventory.", name))

    def delete(self, name, location=None):
        """Remove a product completely (whatever the units). Returns the deleted products."""

        key = normalize(name)

        places = [self.normalize_location(location)] if location else list(LOCATIONS)

        deleted = []

        for place in places:
            products = self.get_section(place)

            remaining = []

            for product in products:
                if self._matches(key, product):
                    deleted.append({**product, "location": place})
                else:
                    remaining.append(product)

            if len(remaining) != len(products):
                self.save_section(place, remaining)

        if not deleted:
            raise ValueError(t("I can't find '{0}' in the inventory.", name))

        return deleted

    def empty(self, location=None):
        """Delete every product of a location (or of all). Returns how many."""

        places = [self.normalize_location(location)] if location else list(LOCATIONS)

        total = 0

        for place in places:
            total += len(self.get_section(place))
            self.save_section(place, [])

        return total

    def items(self, location=None):
        """The inventory of one location or of all."""

        if location:
            place = self.normalize_location(location)

            return {place: self.get_section(place)}

        return {place: self.get_section(place) for place in LOCATIONS if self.get_section(place)}

    def search(self, text):
        """Products whose name contains the text."""

        key = normalize(text)

        found = []

        for place in LOCATIONS:
            for product in self.get_section(place):
                if key in normalize(product.get("name", "")):
                    found.append({**product, "location": place})

        return found

    # ------------------------------------------------------------------
    # Expiry dates
    # ------------------------------------------------------------------

    def set_expiry(self, name, date):
        """Set (or remove, with an empty date) the expiry date of a stored product."""

        no_date = ("", "none", "remove") + tuple(vocab("none_words"))
        date = validate_date(date) if date not in (None, *no_date) else None
        key = normalize(name)
        changed = []

        for place in LOCATIONS:
            products = self.get_section(place)
            touched = False

            for product in products:
                if self._matches(key, product):
                    if date:
                        product["expires"] = date
                    else:
                        product.pop("expires", None)

                    changed.append({"name": product["name"], "location": place, "expires": date})
                    touched = True

            if touched:
                self.save_section(place, products)

        if not changed:
            raise ValueError(t("I don't have '{0}' at home.", name))

        return changed

    def expiring(self, days=5):
        """Expired products and those expiring in the next ``days`` days, most urgent first."""

        today = Date.today()
        limit = today + timedelta(days=int(days))
        items = []

        for place in LOCATIONS:
            for product in self.get_section(place):
                try:
                    day = Date.fromisoformat(str(product.get("expires", "")))
                except ValueError:
                    continue

                if day <= limit:
                    remaining = (day - today).days
                    items.append(
                        {
                            "name": product.get("name", ""),
                            "location": place,
                            "expires": day.isoformat(),
                            "days": remaining,
                            "state": "expired" if remaining < 0 else "today" if remaining == 0 else "soon",
                        }
                    )

        return sorted(items, key=lambda p: (p["days"], normalize(p["name"])))

    def warn_expiries(self, days=3):
        """Daily notice (at most one a day) with what expires soon. Returns the notice or None."""

        items = self.expiring(days)

        if not items:
            return None

        data = self.data.read_module(self.name)
        today = Date.today().isoformat()

        if data.get("_expiries_notified") == today:
            return None

        data["_expiries_notified"] = today
        self.data.save_module(self.name, data)

        def phrase(p):
            if p["days"] < 0:
                when = t("expired")
            elif p["days"] == 0:
                when = t("expires today")
            else:
                when = t("in {0} d", p["days"])

            return f"{p['name']} ({when})"

        from brain.modules.notices import Notices

        return Notices().notify(
            t("Things expiring soon"),
            ", ".join(phrase(p) for p in items[:8]) + ". " + t("Ask me for a recipe to use them up."),
            kind="alert",
            level="important",
        )
