from brain.modules.calendar import Calendar
from brain.tools.decorators import tool

calendar = Calendar()


@tool(
    description="Note an event or appointment in the calendar.",
    category="calendar",
    arguments={
        "title": "What the event is, for example 'Dentist'",
        "date": "Date YYYY-MM-DD. Omit if it is today.",
        "hour": "Time HH:MM in 24-hour format (for example 18:30). Optional.",
    },
)
def add_event(title: str, date: str = None, hour: str = None):
    """Add an event to the calendar."""

    return {"saved": calendar.add_event(title, date, hour)}


@tool(
    description="Note a pending task (optionally with a deadline).",
    category="calendar",
    arguments={
        "title": "What has to be done",
        "date": "Deadline YYYY-MM-DD. Optional.",
    },
)
def add_task(title: str, date: str = None):
    """Add a task."""

    return {"saved": calendar.add_task(title, date)}


@tool(
    description="Mark a pending task as done.",
    category="calendar",
    arguments={"title": "Name (or part of the name) of the task"},
)
def complete_task(title: str):
    """Complete a task."""

    return {"completed": calendar.complete_task(title)}


@tool(
    description="Show the agenda: events of the coming days and pending tasks.",
    category="calendar",
    arguments={"days": "How many days ahead to look. Default 7."},
)
def show_agenda(days: int = 7):
    """Show the agenda."""

    return calendar.agenda(days)
