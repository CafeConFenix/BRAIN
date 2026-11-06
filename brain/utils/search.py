"""Global search: one box to find things anywhere in the house."""

from brain.i18n import t
from brain.modules.inventory import normalize


def _matches(key, *texts) -> bool:
    return any(key in normalize(text) for text in texts if text)


def search_all(modules, text, limit=8) -> dict:
    """``modules`` is the module registry (brain.modules). Returns the results grouped by kind."""

    key = normalize(text)

    if len(key) < 2:
        raise ValueError(t("Type at least two letters to search."))

    groups = []

    def add(kind, title, items):
        if items:
            groups.append({"kind": kind, "title": title, "results": items[:limit]})

    inventory = modules.get("inventory")

    if inventory:
        add(
            "pantry",
            t("At home"),
            [
                {"text": f"{p['name']} ({p['quantity']})", "detail": p["location"] + (", " + t("expires {0}", p["expires"]) if p.get("expires") else "")}
                for p in inventory.everything()
                if _matches(key, p["name"], p["location"])
            ],
        )

    shopping = modules.get("shopping")

    if shopping:
        add(
            "shopping",
            t("Shopping list"),
            [{"text": i.get("product", ""), "detail": f"x{i.get('quantity', 1)}"} for i in shopping.items() if _matches(key, i.get("product"))],
        )

    calendar = modules.get("calendar")

    if calendar:
        events = [
            {"text": e.get("title", ""), "detail": f"{e.get('date', '')} {e.get('hour') or ''}".strip()}
            for e in calendar.get_section("events")
            if _matches(key, e.get("title"), e.get("date"))
        ]
        tasks = [
            {"text": task.get("title", ""), "detail": t("task, done") if task.get("done") else t("task")}
            for task in calendar.get_section("tasks")
            if _matches(key, task.get("title"))
        ]
        add("agenda", t("Agenda"), events + tasks)

    expenses = modules.get("expenses")

    if expenses:
        add(
            "expenses",
            t("Expenses"),
            [
                {"text": f"{g['description'] or g['category']} — {g['amount']:.2f} €", "detail": g["date"]}
                for g in reversed(expenses.get_section("expenses"))
                if _matches(key, g.get("description"), g.get("category"))
            ],
        )

    memory = modules.get("memory")

    if memory:
        from brain.modules.memory import TYPES

        memories = [{**r, "kind": kind} for kind in TYPES for r in memory.get_section(kind) if isinstance(r, dict)]
        add("memory", t("Things I remember"), [{"text": r.get("text", ""), "detail": r["kind"]} for r in memories if _matches(key, r.get("text"))])

    appliances = modules.get("appliances")

    if appliances:
        add(
            "devices",
            t("Appliances"),
            [
                {"text": str(a.get("name", "")), "detail": " ".join(str(a.get(k) or "") for k in ("brand", "model")).strip()}
                for a in appliances.devices()
                if isinstance(a, dict) and _matches(key, a.get("name"), a.get("brand"), a.get("model"))
            ],
        )

    chores = modules.get("chores")

    if chores:
        add(
            "chores",
            t("Household chores"),
            [
                {"text": c["name"], "detail": t("{0}'s turn", c["turn_of"]) if c["turn_of"] else ""}
                for c in chores.items()
                if _matches(key, c["name"], c["turn_of"])
            ],
        )

    documents = modules.get("documents")

    if documents:
        try:
            found = documents.search(text, limit=limit)
        except Exception:
            found = []

        add(
            "documents",
            t("In your manuals and notes"),
            [{"text": (r.get("text") or "")[:160].replace("\n", " "), "detail": r.get("document") or ""} for r in found],
        )

    return {"query": text, "total": sum(len(g["results"]) for g in groups), "groups": groups}
