import re
from datetime import date, timedelta

from brain.base.module import ModuleBase
from brain.i18n import t, vocab
from brain.modules.inventory import normalize
from brain.utils.dates import weekday_index, weekday_names


def _day(text):
    key = normalize(text)
    index = weekday_index(key)

    if index is not None:
        return index

    # Any abbreviation of at least three letters ("mon", "lun", "thur").
    for alias, number in vocab("weekday_aliases").items():
        if len(key) >= 3 and alias.startswith(key[:3]):
            return number

    raise ValueError(t("I don't understand the day '{0}'.", text))


def parse_menu(text) -> list:
    """
    One line per dish: 'monday lunch: Macaroni with tomato | pasta, tomato, cheese'.
    Lunch or dinner is optional (lunch by default) and the ingredients come after '|' or ' - '.
    """

    dishes = []
    dinner_words = [normalize(w)[:3] for w in vocab("dinner_words")]

    for line in str(text or "").splitlines():
        line = line.strip(" -*•\t")

        if ":" not in line:
            continue

        header, rest = line.split(":", 1)
        words = header.split()

        if not words:
            continue

        try:
            day = _day(words[0])
        except ValueError:
            continue

        moment = "dinner" if any(normalize(word)[:3] in dinner_words for word in words[1:]) else "lunch"
        parts = re.split(r"\s*\|\s*|\s+[-–—]\s+", rest, maxsplit=1)
        name = parts[0].strip()

        if not name:
            continue

        ingredients = [i.strip() for i in re.split(r"[,;]", parts[1]) if i.strip()] if len(parts) > 1 else []
        dishes.append({"day": day, "moment": moment, "dish": name[:80], "ingredients": ingredients})

    return dishes


class Menu(ModuleBase):
    """The weekly menu: dishes by day (lunch and dinner) and shopping for what is missing."""

    name = "menu"

    def save(self, text) -> dict:
        dishes = parse_menu(text)

        if not dishes:
            raise ValueError(t("I found no dishes. Use one line per dish, for example: 'monday lunch: Lentils | lentils, chorizo, carrot'."))

        today = date.today()
        monday = today - timedelta(days=today.weekday())
        self.save_section("dishes", dishes)
        data = self.data.read_module(self.name)
        data["week"] = monday.isoformat()
        self.data.save_module(self.name, data)

        return self.show()

    def show(self) -> dict:
        dishes = self.get_section("dishes")
        days = []

        for i, name in enumerate(weekday_names()):
            row = {"day": name}

            for dish in dishes:
                if dish["day"] == i:
                    row[dish["moment"]] = dish["dish"]

            if len(row) > 1:
                days.append(row)

        return {"days": days, "total_dishes": len(dishes), "week": self.data.read_module(self.name).get("week")}

    def missing(self) -> list:
        """Ingredients of the menu that are not at home (no repeats)."""

        from brain.modules.inventory import Inventory

        inventory = Inventory()
        seen, missing = set(), []

        for dish in self.get_section("dishes"):
            if not dish["ingredients"]:
                continue

            for name, quantity in inventory.compare_recipe("\n".join(dish["ingredients"]))["missing"]:
                key = normalize(name)

                if key not in seen:
                    seen.add(key)
                    missing.append((name, quantity))

        return missing

    def add_missing_to_shopping(self) -> dict:
        from brain.modules.shopping import Shopping

        if not self.get_section("dishes"):
            raise ValueError(t("There is no weekly menu yet. Ask me to prepare one."))

        missing = self.missing()
        shopping = Shopping()
        in_list = {normalize(i.get("product", "")) for i in shopping.items()}
        new = [(n, c) for n, c in missing if normalize(n) not in in_list]

        if new:
            shopping.add_many(new)

        return {"added": [n for n, _ in new], "already_in_list": [n for n, _ in missing if normalize(n) in in_list]}

    def empty(self) -> int:
        total = len(self.get_section("dishes"))
        self.save_section("dishes", [])

        return total
