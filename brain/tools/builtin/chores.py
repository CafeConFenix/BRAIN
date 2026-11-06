from brain.modules.chores import Chores
from brain.modules.profiles import Profiles
from brain.tools.decorators import tool

chores = Chores()
profiles = Profiles()


@tool(
    description="Create a recurring household chore with turns between people (trash, washing up, walking the dog...). If it already exists, update it.",
    category="chores",
    arguments={
        "name": "Name of the chore, for example 'take out the trash'",
        "people": "Who takes turns, separated by commas: 'Ana, Luis, Marta'. Empty if anyone can do it.",
        "every_days": "Every how many days it repeats (1 = daily, 7 = weekly). Default 7.",
        "starts": "First date YYYY-MM-DD. Omit if it is today.",
    },
)
def create_chore(name: str, people: str = "", every_days: int = 7, starts: str = None):
    """Create a household chore with turns."""

    return {"task": chores.create(name, people, every_days, starts)}


@tool(
    description="List the household chores with whose turn it is and when. Use it for 'whose turn is it to take out the trash?' or 'what chores are there today?'.",
    category="chores",
    arguments={"today_only": "true to see only those due today", "person": "Filter by person (optional)"},
)
def list_chores(today_only: bool = False, person: str = ""):
    """List the household chores."""

    items = chores.todays(person) if today_only else chores.items()

    return {"tasks": items} if items else {"message": "There are no household chores for today." if today_only else "There are no household chores yet."}


@tool(
    description="Record that a household chore is done; the turn passes to the next person. Use it for 'I already took out the trash'.",
    category="chores",
    arguments={"name": "Name of the chore", "who": "Who did it (omit if it was whoever's turn it was)", "date": "YYYY-MM-DD. Omit if it is today."},
)
def chore_done(name: str, who: str = "", date: str = None):
    """Mark a household chore as done."""

    return {"done": chores.done(name, who, date)}


@tool(
    description="Pass the turn of a household chore to the next person without doing it (for example, if they cannot).",
    category="chores",
    arguments={"name": "Name of the chore"},
)
def skip_chore_turn(name: str):
    """Pass the turn."""

    return {"task": chores.skip_turn(name)}


@tool(
    description="Delete a household chore.",
    category="chores",
    arguments={"name": "Name of the chore"},
)
def delete_chore(name: str):
    """Delete a household chore."""

    return {"deleted": chores.delete(name)}


@tool(
    description="Add a person to the household (to share chores and habits). Without arguments, list the people.",
    category="chores",
    arguments={"name": "Name of the person. Omit to list them."},
)
def household_people(name: str = ""):
    """Manage the people of the household."""

    if name:
        profiles.add(name)

    return {"people": profiles.names()}
