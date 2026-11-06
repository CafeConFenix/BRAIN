from brain.i18n import t
from brain.modules.profiles import Profiles
from brain.tools.decorators import tool

profiles = Profiles()


@tool(
    description="Add a person to the household to split habits, chores and reminders (for example 'Ana').",
    category="chores",
    arguments={"name": "Name of the person"},
)
def add_person(name: str):
    """Add a person."""

    return {"people": profiles.add(name)}


@tool(description="List the people in the household.", category="chores")
def list_people():
    """People in the household."""

    items = profiles.items()

    return {"people": items} if items else {"message": t("There are no people yet. I can add them to split chores and habits.")}


@tool(description="Remove a person from the household list.", category="chores", arguments={"name": "Name of the person"})
def remove_person(name: str):
    """Remove a person."""

    return {"people": profiles.delete(name)}
