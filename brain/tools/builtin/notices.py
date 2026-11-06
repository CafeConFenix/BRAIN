from brain.i18n import t
from brain.modules.notices import Notices
from brain.tools.decorators import tool

notices = Notices()


def _error(error):
    return {"error": str(error)}


@tool(
    description=(
        "Schedule a reminder that will sound as a notification at its time. Use it for 'remind me in 20 minutes "
        "to take the chicken out' or 'remind me tomorrow at 9:00 to call the doctor'. Give in_minutes OR date_time."
    ),
    category="notices",
    arguments={
        "message": "What to remember",
        "in_minutes": "Minutes from now. Omit if you give date_time.",
        "date_time": "YYYY-MM-DD HH:MM, or just HH:MM (today, or tomorrow if it already passed). Omit if you give in_minutes.",
        "person": "Who the reminder is for, if not the user talking (optional).",
    },
)
def create_reminder(message: str, in_minutes: float = None, date_time: str = None, person: str = ""):
    """Schedule a reminder."""

    if person:
        message = t("For {0}: {1}", person.strip()[:30], message)

    try:
        return {"scheduled": notices.create_reminder(message, in_minutes, date_time)}
    except ValueError as error:
        return _error(error)


@tool(description="Show the pending reminders.", category="notices")
def list_reminders():
    """List the pending reminders."""

    pending = notices.reminders()

    if not pending:
        return {"message": t("There are no pending reminders.")}

    return {"reminders": pending}


@tool(
    description="Cancel a pending reminder by its number (the id that list_reminders gives).",
    category="notices",
    arguments={"id": "Reminder number"},
)
def cancel_reminder(id: int):
    """Cancel a reminder."""

    if not notices.delete_reminder(id):
        return {"error": t("There is no pending reminder with the number {0}.", id)}

    return {"canceled": id}


@tool(
    description="Show the received notices (alerts, reminders, summaries). Only the unread ones by default.",
    category="notices",
    arguments={"all_items": "true to also see the ones already read"},
)
def list_notices(all_items: bool = False):
    """List the notices."""

    items = notices.items(unread_only=not all_items, limit=20)

    if not items:
        return {"message": t("There are no new notices.")}

    return {"notices": [{k: a[k] for k in ("date", "kind", "title", "message", "level")} for a in items]}


@tool(description="Mark all notices as read.", category="notices")
def mark_notices_read():
    """Mark the notices as read."""

    return {"marked": notices.mark_read()}


@tool(
    description=(
        "Show the sounds available for notices and which one each kind has. The user adds their own sounds "
        "(.wav, .mp3, .ogg) by copying them into the folder given."
    ),
    category="notices",
)
def list_sounds():
    """List the notice sounds."""

    return notices.list_sounds()


@tool(
    description=(
        "Assigns a sound to a notice kind (alert, reminder, summary, automation, energy, info). "
        "With file 'none' it goes back to the default sound."
    ),
    category="notices",
    arguments={
        "kind": "alert, reminder, summary, automation, energy or info",
        "file": "Sound file name, for example 'bell.wav'",
    },
)
def assign_sound(kind: str, file: str):
    """Assign a sound to a notice kind."""

    try:
        return {"assigned": notices.assign_sound(kind, file)}
    except ValueError as error:
        return _error(error)


@tool(
    description=(
        "Adjusts notices: mute them completely, turn Windows notifications on or off, or the "
        "'do not disturb' window (only critical alerts sound). Use 'none' to remove the window."
    ),
    category="notices",
    arguments={
        "mute": "true to silence all notices, false to turn them back on",
        "windows_notifications": "true/false for Windows' own notifications and sounds",
        "dnd_from": "Start time HH:MM, for example 23:00, or 'none'",
        "dnd_until": "End time HH:MM, for example 07:00",
    },
)
def configure_notices(
    mute: bool = None,
    windows_notifications: bool = None,
    dnd_from: str = None,
    dnd_until: str = None,
):
    """Configure the notices."""

    try:
        return {"config": notices.configure(mute, windows_notifications, dnd_from, dnd_until)}
    except ValueError as error:
        return _error(error)


@tool(
    description="Send a test notice so the user can check the notification and sound.",
    category="notices",
    arguments={"kind": "Kind of notice to test (default info)"},
)
def send_test_notice(kind: str = "info"):
    """Send a test notice."""

    try:
        return {"sent": notices.notify(t("Test notice"), t("If you see and hear this, notices are working."), kind=kind)}
    except ValueError as error:
        return _error(error)
