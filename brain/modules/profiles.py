from brain.base.module import ModuleBase
from brain.i18n import t
from brain.modules.inventory import normalize


class Profiles(ModuleBase):
    """The people in the household. Habits and chores can belong to one person or to everyone."""

    name = "profiles"

    def items(self) -> list:
        return [p for p in self.get_section("people") if isinstance(p, dict) and p.get("name")]

    def names(self) -> list:
        return [p["name"] for p in self.items()]

    def add(self, name) -> dict:
        name = str(name or "").strip()[:30]

        if not name:
            raise ValueError(t("Give the name of the person."))

        people = self.items()

        for p in people:
            if normalize(p["name"]) == normalize(name):
                return p

        if len(people) >= 12:
            raise ValueError(t("There are already 12 people; delete one first."))

        new = {"name": name}
        people.append(new)
        self.save_section("people", people)

        return new

    def search(self, name) -> dict:
        key = normalize(name)

        for p in self.items():
            if normalize(p["name"]) == key:
                return p

        raise ValueError(t("I don't know '{0}' among the people in the household.", name))

    def delete(self, name) -> dict:
        person = self.search(name)
        self.save_section("people", [p for p in self.items() if p["name"] != person["name"]])

        return person
