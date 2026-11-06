from brain.modules.habits import Habits
from brain.tools.decorators import tool

habits = Habits()


@tool(
    description="Create a daily habit with a goal (drinking water, taking a pill, walking...). If it already exists, change its goal.",
    category="habits",
    arguments={
        "name": "Name of the habit, for example 'drink water'",
        "goal": "Times or amount per day to meet it (default 1), for example 8",
        "unit": "Optional unit, for example 'glasses' or 'minutes'",
        "hour": "Time HH:MM at which BRAIN reminds you if it is not met yet (optional)",
        "person": "Person the habit belongs to (optional)",
    },
)
def create_habit(name: str, goal: int = 1, unit: str = "", hour: str = "", person: str = ""):
    """Create a habit."""

    return {"habit": habits.create(name, goal, unit, hour, person)}


@tool(
    description="Record that a habit was done today (or on another date). Use it for 'I drank a glass of water' or 'I took my pill'. Returns the progress of the day and the streak.",
    category="habits",
    arguments={
        "name": "Name of the habit",
        "quantity": "How much was done (default 1; negative to correct)",
        "date": "YYYY-MM-DD. Omit if it is today.",
    },
)
def log_habit(name: str, quantity: int = 1, date: str = None):
    """Record a habit."""

    return habits.log(name, quantity, date)


@tool(
    description="Show the habits of the day: progress, whether they are met and the streak of consecutive days. Use it for 'how am I doing with my habits?'.",
    category="habits",
    arguments={"date": "YYYY-MM-DD. Omit for today."},
)
def list_habits(date: str = None):
    """Progress of the habits."""

    result = habits.state(date)

    if not result["total"]:
        return {"message": "There are no habits yet. You can create one, for example 'drink water' with a goal of 8."}

    return result


@tool(
    description="Delete a habit and all its history.",
    category="habits",
    arguments={"name": "Name of the habit"},
)
def delete_habit(name: str):
    """Delete a habit."""

    return {"deleted": habits.delete(name)}
