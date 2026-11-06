"""
Web routes for what happens "at home": budget, expiries, habits,
household chores with turns, people, weekly menu, Leaving/Good night
buttons, electricity cost, global search, manuals and a second backup
destination.

`handle` returns (code, response), or None if the route does not belong here.
"""

from urllib.parse import parse_qs, urlparse

from brain.i18n import t
from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.system import BackupError
from brain.utils.search import search_all

LOCAL_ONLY = ("/api/backup/destination", "/api/backup/fetch", "/api/routine/turn_off")

GET_ROUTES = (
    "/api/budget",
    "/api/expiries",
    "/api/habits",
    "/api/chores",
    "/api/menu",
    "/api/routine",
    "/api/search",
    "/api/documents",
    "/api/energy/cost",
    "/api/backup/state",
)

POST_ROUTES = (
    "/api/budget/save",
    "/api/inventory/expiry",
    "/api/habits/create",
    "/api/habits/log",
    "/api/habits/delete",
    "/api/chores/create",
    "/api/chores/done",
    "/api/chores/skip",
    "/api/chores/delete",
    "/api/people/add",
    "/api/people/delete",
    "/api/menu/save",
    "/api/menu/shopping",
    "/api/menu/clear",
    "/api/routine/turn_off",
    "/api/documents/delete",
    "/api/energy/tariff",
    "/api/backup/destination",
    "/api/backup/fetch",
)


def _query(route_path, key, default=None):
    return parse_qs(urlparse(route_path).query).get(key, [default])[0]


def _backups_state(brain) -> dict:
    system = brain.modules.get("system")

    return {
        "destination": system.extra_destination(),
        "suggested": system.suggested_destinations(),
        "backups": system.list_backups(),
        "destination_backups": system.backups_at_destination(),
    }


def _chores(brain) -> dict:
    chores = brain.modules.get("chores")
    profiles = brain.modules.get("profiles")

    return {"tasks": chores.items(), "people": profiles.names()}


def handle(brain, method, route_path, data, local):
    path = urlparse(route_path).path

    if path not in (GET_ROUTES if method == "GET" else POST_ROUTES):
        return None

    if path in LOCAL_ONLY and not local:
        return 403, {"error": t("This can only be done from the home computer.")}

    m = brain.modules.get

    try:
        if method == "GET":
            if path == "/api/budget":
                return 200, m("expenses").budget_state(_query(route_path, "month"))

            if path == "/api/expiries":
                return 200, {"products": m("inventory").expiring(int(_query(route_path, "days", "5") or 5))}

            if path == "/api/habits":
                return 200, {**m("habits").state(person=_query(route_path, "person", "")), "people": m("profiles").names()}

            if path == "/api/chores":
                return 200, _chores(brain)

            if path == "/api/menu":
                return 200, {**m("menu").show(), "missing": [{"name": n, "quantity": c} for n, c in m("menu").missing()]}

            if path == "/api/routine":
                return 200, m("routines").review(_query(route_path, "kind", "leaving"))

            if path == "/api/search":
                return 200, search_all(brain.modules, _query(route_path, "q", ""))

            if path == "/api/documents":
                return 200, {"documents": m("documents").items()}

            if path == "/api/energy/cost":
                energy = m("energy")

                return 200, {"month": energy.month_cost(_query(route_path, "month")), "comparison": energy.compare_months(), "tariff": energy.tariff(), "cheap_hours": energy.cheap_hours()}

            if path == "/api/backup/state":
                return 200, _backups_state(brain)

        # ------------------------------------------------------------ POST
        if path == "/api/budget/save":
            m("expenses").configure_budget(data.get("total"), data.get("category", ""), data.get("limit"))

            return 200, m("expenses").budget_state()

        if path == "/api/inventory/expiry":
            return 200, {"updated": m("inventory").set_expiry(data.get("name", ""), data.get("date", ""))}

        if path == "/api/habits/create":
            return 200, {"habit": m("habits").create(data.get("name"), data.get("goal", 1), data.get("unit", ""), data.get("hour", ""), data.get("person", ""))}

        if path == "/api/habits/log":
            return 200, {"state": m("habits").log(data.get("name"), data.get("quantity", 1))}

        if path == "/api/habits/delete":
            return 200, {"deleted": m("habits").delete(data.get("name"))}

        if path == "/api/chores/create":
            return 200, {"task": m("chores").create(data.get("name"), data.get("people", ""), data.get("every_days", 7), data.get("starts") or None)}

        if path == "/api/chores/done":
            return 200, {"task": m("chores").done(data.get("name"), data.get("who", ""))}

        if path == "/api/chores/skip":
            return 200, {"task": m("chores").skip_turn(data.get("name"))}

        if path == "/api/chores/delete":
            return 200, {"deleted": m("chores").delete(data.get("name"))}

        if path == "/api/people/add":
            m("profiles").add(data.get("name"))

            return 200, _chores(brain)

        if path == "/api/people/delete":
            m("profiles").delete(data.get("name"))

            return 200, _chores(brain)

        if path == "/api/menu/save":
            return 200, m("menu").save(data.get("text", ""))

        if path == "/api/menu/shopping":
            return 200, m("menu").add_missing_to_shopping()

        if path == "/api/menu/clear":
            return 200, {"deleted": m("menu").empty()}

        if path == "/api/routine/turn_off":
            return 200, m("routines").turn_off(data.get("entities") or [])

        if path == "/api/documents/delete":
            return 200, {"deleted": m("documents").delete(data.get("name", ""))}

        if path == "/api/energy/tariff":
            energy = m("energy")

            if data.get("buy") not in (None, "") or data.get("sell") not in (None, ""):
                energy.configure_tariff(data.get("buy"), data.get("sell"))

            if data.get("offpeak_from") or data.get("offpeak_until") or data.get("offpeak_price") not in (None, ""):
                energy.set_cheap_hours(data.get("offpeak_from"), data.get("offpeak_until"), data.get("offpeak_price"))

            return 200, {"tariff": energy.tariff()}

        if path == "/api/backup/destination":
            m("system").configure_destination(data.get("path", ""))

            return 200, _backups_state(brain)

        if path == "/api/backup/fetch":
            m("system").fetch_backup_from_destination(data.get("name", ""))

            return 200, _backups_state(brain)

    except HomeAssistantError as error:
        return 502, {"error": str(error)}

    except BackupError as error:
        return 400, {"error": str(error)}

    except ValueError as error:
        return 400, {"error": str(error)}

    except Exception as error:
        # DocumentError and similar errors inherit from ValueError; this is the unexpected case.
        from brain.core import logger

        logger.error(f"Web {path}: {error!r}")

        return 500, {"error": t("Unexpected error: {0}", error)}

    return None
