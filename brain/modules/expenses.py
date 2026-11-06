import re
from datetime import date as Date

from brain.base.module import ModuleBase
from brain.i18n import t, vocab
from brain.modules.inventory import normalize
from brain.utils.dates import month_number, validate_date

CATEGORIES = ("groceries", "home", "bills", "transport", "leisure", "health", "clothing", "restaurants", "other")


def _amount(value) -> float:
    """Accepts 12, 12.5, '12.50', '12,50 €', '1,234.56'."""

    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = re.sub(r"[^\d,.\-]", "", str(value or ""))

        if not text:
            raise ValueError(t("The amount of the expense is missing."))

        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        elif text.count(".") > 1:
            text = text.replace(".", "")

        try:
            number = float(text)
        except ValueError:
            raise ValueError(t("I do not understand the amount '{0}'.", value)) from None

    if not 0 < number <= 1_000_000:
        raise ValueError(t("The amount must be greater than zero (and reasonable).")) 

    return round(number, 2)


def guess_category(description) -> str:
    text = f" {normalize(description)} "

    for category, words in vocab("expense_hints").items():
        if any(word in text for word in words):
            return category

    return "other"


def _category(value, description) -> str:
    if not value:
        return guess_category(description)

    key = normalize(value)
    key = vocab("expense_categories").get(key, key)

    for category in CATEGORIES:
        if key == category or key.rstrip("s") == category.rstrip("s"):
            return category

    guessed = guess_category(value)

    return guessed if guessed != "other" else key[:30]


def interpret_month(value=None) -> str:
    """'2026-10', 'october', 'this month', 'last month' -> 'YYYY-MM'."""

    today = Date.today()

    if value in (None, ""):
        return f"{today.year:04d}-{today.month:02d}"

    text = normalize(value)

    if re.fullmatch(r"\d{4}-\d{1,2}", text):
        year, month = text.split("-")

        if 1 <= int(month) <= 12:
            return f"{int(year):04d}-{int(month):02d}"

    if any(w in text for w in ("pasado", "anterior", "last", "previous")):
        year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)

        return f"{year:04d}-{month:02d}"

    for word in re.findall(r"[a-z]+", text):
        number = month_number(word)

        if number:
            return f"{today.year:04d}-{number:02d}"

    return f"{today.year:04d}-{today.month:02d}"


class Expenses(ModuleBase):
    """Simple household expense tracking: record, see the month summary and delete."""

    name = "expenses"

    def add(self, amount, description="", category="", date=None) -> dict:
        records = self.get_section("expenses")
        description = str(description or "").strip()[:80]

        expense = {
            "id": max([g.get("id", 0) for g in records] + [0]) + 1,
            "date": validate_date(date),
            "amount": _amount(amount),
            "category": _category(category, description),
            "description": description,
        }

        records.append(expense)
        self.save_section("expenses", records)
        self._warn_budget(expense["date"][:7])

        return expense

    # ------------------------------------------------------------------
    # Monthly budget
    # ------------------------------------------------------------------

    def budget(self) -> dict:
        """{'total': 800.0, 'categories': {'leisure': 50.0}} (empty if there is no budget)."""

        config = self.get_section("budget")

        return dict(config[0]) if config and isinstance(config[0], dict) else {}

    def configure_budget(self, total=None, category="", limit=None) -> dict:
        """Set the total monthly budget and/or the limit of a category. 0 removes it."""

        config = self.budget()
        categories = dict(config.get("categories") or {})

        if total not in (None, ""):
            try:
                value = float(str(total).replace(",", ".")) if not isinstance(total, (int, float)) else float(total)
            except ValueError:
                raise ValueError(t("I do not understand the budget '{0}'. Write an amount in euros, for example 900.", total)) from None

            if value < 0:
                raise ValueError(t("The budget cannot be negative."))

            if value == 0:
                config.pop("total", None)
            else:
                config["total"] = round(value, 2)

        if category:
            name = _category(category, category)

            if limit in (None, ""):
                raise ValueError(t("Give the limit of that category in euros."))

            value = _amount(limit) if str(limit).strip() not in ("0", "0.0") else 0

            if value == 0:
                categories.pop(name, None)
            else:
                categories[name] = value

        config["categories"] = categories
        self.save_section("budget", [config])

        return config

    @staticmethod
    def _level(spent, limit) -> str:
        if not limit:
            return "no_limit"

        if spent >= limit:
            return "exceeded"

        return "notice" if spent >= limit * 0.8 else "ok"

    def budget_state(self, month=None) -> dict:
        """How much has been spent against the budget of the month (total and per category)."""

        month = interpret_month(month)
        config = self.budget()
        summary = self.summary(month)
        limit_total = config.get("total")
        categories = []

        spent_by = {c["category"]: c["total"] for c in summary["by_category"]}

        for name, limit in sorted((config.get("categories") or {}).items()):
            spent = spent_by.get(name, 0.0)
            categories.append({"category": name, "limit": limit, "spent": spent, "percent": round(spent * 100 / limit), "level": self._level(spent, limit)})

        return {
            "month": month,
            "configured": bool(limit_total or categories),
            "limit": limit_total,
            "spent": summary["total"],
            "remaining": round(limit_total - summary["total"], 2) if limit_total else None,
            "percent": round(summary["total"] * 100 / limit_total) if limit_total else None,
            "level": self._level(summary["total"], limit_total),
            "categories": categories,
        }

    def _warn_budget(self, month) -> None:
        """Notify (only once per month and level) on reaching 80 % and 100 %."""

        try:
            state = self.budget_state(month)

            if not state["configured"]:
                return

            facts = set(self.get_section("notified"))
            pending = []
            situations = [("total", t("the budget of the month"), state["limit"], state["spent"], state["level"])]
            situations += [(c["category"], t("the {0} budget", c["category"]), c["limit"], c["spent"], c["level"]) for c in state["categories"]]

            for key, text, limit, spent, level in situations:
                if level not in ("notice", "exceeded"):
                    continue

                brand = f"{month}:{key}:{level}"

                if brand in facts:
                    continue

                facts.add(brand)
                pending.append((level, text, limit, spent))

            if not pending:
                return

            self.save_section("notified", sorted(facts)[-200:])

            from brain.modules.notices import Notices

            notices = Notices()

            for level, text, limit, spent in pending:
                if level == "exceeded":
                    notices.notify(t("Budget exceeded"), t("You have spent {0} € and {1} was {2} €.", f"{spent:.2f}", text, f"{limit:.2f}"), kind="alert")
                else:
                    notices.notify(t("Budget at 80 %"), t("You are at {0} € of {1} € in {2}.", f"{spent:.2f}", f"{limit:.2f}", text), kind="info", level="important")
        except Exception:
            pass  # a failure to notify must never prevent recording the expense

    def this_month(self, month=None) -> list:
        month = interpret_month(month)

        return sorted((g for g in self.get_section("expenses") if str(g.get("date", "")).startswith(month)), key=lambda g: (g["date"], g["id"]))

    def summary(self, month=None) -> dict:
        month = interpret_month(month)
        expenses = self.this_month(month)
        by_category = {}

        for g in expenses:
            c = by_category.setdefault(g["category"], {"category": g["category"], "total": 0.0, "n": 0})
            c["total"] = round(c["total"] + g["amount"], 2)
            c["n"] += 1

        return {
            "month": month,
            "total": round(sum(g["amount"] for g in expenses), 2),
            "n": len(expenses),
            "by_category": sorted(by_category.values(), key=lambda c: -c["total"]),
            "last": list(reversed(expenses))[:10],
        }

    def delete(self, expense_id) -> dict:
        records = self.get_section("expenses")

        if not records:
            raise ValueError(t("There are no recorded expenses."))

        if normalize(str(expense_id)) in ("last", "ultimo", ""):
            goal = max(records, key=lambda g: g.get("id", 0))
        else:
            try:
                number = int(expense_id)
            except (TypeError, ValueError):
                raise ValueError(t("Give the number of the expense (or 'last').")) from None

            goal = next((g for g in records if g.get("id") == number), None)

            if goal is None:
                raise ValueError(t("There is no expense number {0}.", number))

        records.remove(goal)
        self.save_section("expenses", records)

        return goal
