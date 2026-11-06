from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.inventory import normalize
from brain.utils.dates import today


class Shopping(ModuleBase):
    name = "shopping"

    def add(self, product, quantity=1):
        """Add a product to the shopping list (adds up if it was already there)."""

        quantity = float(quantity)

        if quantity <= 0:
            raise ValueError(t("The quantity must be greater than zero."))

        if quantity == int(quantity):
            quantity = int(quantity)

        items = self.get_section("shopping_list")

        for item in items:
            if normalize(item.get("product", "")) == normalize(product):
                item["quantity"] = item.get("quantity", 0) + quantity
                self.save_section("shopping_list", items)

                return item

        item = {"product": str(product).strip(), "quantity": quantity}

        items.append(item)

        self.save_section("shopping_list", items)

        return item

    def add_many(self, products):
        """Add several products at once (list of (name, quantity))."""

        items = self.get_section("shopping_list")

        index = {normalize(i.get("product", "")): i for i in items}

        added = []

        for name, quantity in products:
            key = normalize(name)

            if key in index:
                index[key]["quantity"] = index[key].get("quantity", 0) + quantity
            else:
                item = {"product": str(name).strip(), "quantity": quantity}
                items.append(item)
                index[key] = item

            added.append({"product": index[key]["product"], "total_quantity": index[key]["quantity"]})

        self.save_section("shopping_list", items)

        return added

    def items(self):
        return self.get_section("shopping_list")

    def bought(self, product):
        """Take a product off the list and record it in the history."""

        items = self.get_section("shopping_list")

        for item in items:
            if normalize(item.get("product", "")) == normalize(product):
                items.remove(item)

                self.save_section("shopping_list", items)

                self.add_record("history", {**item, "date": today()})

                return item

        raise ValueError(t("'{0}' is not on the shopping list.", product))

    def remove(self, product):
        """Remove a product from the shopping list without recording it as bought."""

        key = normalize(product)

        items = self.get_section("shopping_list")

        removed = [i for i in items if normalize(i.get("product", "")) == key]

        if not removed and len(key) >= 3:
            removed = [i for i in items if key in normalize(i.get("product", ""))]

        if not removed:
            raise ValueError(t("'{0}' is not on the shopping list.", product))

        self.save_section("shopping_list", [i for i in items if i not in removed])

        return removed

    def empty(self):
        """Delete the whole shopping list. Returns how many products there were."""

        total = len(self.get_section("shopping_list"))

        self.save_section("shopping_list", [])

        return total

    def history(self, limit=20):
        return self.get_section("history")[-int(limit) :]
