from brain.core.module_loader import ModuleLoader
from brain.tools.decorators import tool
from brain.utils.search import search_all

_modules = None


@tool(
    description=(
        "Search a word in EVERYTHING at once: pantry, shopping list, agenda, expenses, manuals, household chores and memories. "
        "Use it for 'where did I put...?' or 'find the washing machine warranty'."
    ),
    category="search",
    arguments={"text": "What to look for, for example 'washing machine' or 'wifi'"},
)
def search_everything(text: str):
    """Global search."""

    global _modules

    if _modules is None:
        _modules = ModuleLoader()

    return search_all(_modules, text)
