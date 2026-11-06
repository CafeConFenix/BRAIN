from brain.i18n import t
from brain.modules.expenses import Expenses
from brain.tools.decorators import tool

expenses = Expenses()


@tool(
    description="Record an expense (what was paid at the supermarket, a bill, petrol...). Use it for 'I spent 23 euros at the supermarket'.",
    category="expenses",
    arguments={
        "amount": "Amount in euros, for example 23.50",
        "description": "What it was spent on, for example 'Walmart' or 'electricity bill'",
        "category": "groceries, home, bills, transport, leisure, health, clothing, restaurants or other. Omit it and it is deduced from the description.",
        "date": "YYYY-MM-DD. Omit if it is today.",
    },
)
def add_expense(amount: str, description: str = "", category: str = "", date: str = None):
    """Record an expense."""

    return {"logged": expenses.add(amount, description, category, date)}


@tool(
    description="Summary of the expenses of a month: total, split by category and the latest expenses. Use it for 'how much have I spent this month?'.",
    category="expenses",
    arguments={"month": "YYYY-MM, or 'october', 'this month' or 'last month'. Default this month."},
)
def show_expenses(month: str = None):
    """Expense summary."""

    result = expenses.summary(month)

    if not result["n"]:
        return {"message": t("There are no expenses recorded in {0}.", result["month"]), "month": result["month"]}

    return result


@tool(
    description="Delete an expense recorded by mistake.",
    category="expenses",
    arguments={"id": "Number of the expense (it appears in show_expenses) or 'last' for the latest one."},
)
def delete_expense(id: str = "last"):
    """Delete an expense."""

    return {"deleted": expenses.delete(id)}


@tool(
    description="Set the monthly expense budget (total and/or the limit of a category). BRAIN notifies at 80 % and 100 %. 0 removes it.",
    category="expenses",
    arguments={
        "total": "Total budget of the month in euros, for example 900. Omit if only a category is limited.",
        "category": "Category to limit (leisure, groceries...). Omit for the total.",
        "limit": "Limit in euros of that category.",
    },
)
def set_budget(total: str = None, category: str = "", limit: str = None):
    """Set the budget."""

    return {"budget": expenses.configure_budget(total, category, limit)}


@tool(
    description="How the budget of the month is going: how much was spent, how much is left and the percentage. Use it for 'how am I doing on budget?'.",
    category="expenses",
    arguments={"month": "YYYY-MM, or 'this month' / 'last month'. Default this month."},
)
def show_budget(month: str = None):
    """Budget state."""

    state = expenses.budget_state(month)

    if not state["configured"]:
        return {"message": t("There is no budget yet. Tell me the most you want to spend per month."), **state}

    return state
