from brain.i18n import t
from brain.modules.system import BackupError, System
from brain.tools.decorators import tool

system = System()


@tool(
    description=(
        "Create a backup (ZIP) of all of BRAIN's data: pantry, shopping, weight, "
        "memory, agenda, energy, documents... Only the last 5 are kept."
    ),
    category="system",
)
def create_backup():
    """Create a backup of data/."""

    return {"backup": system.create_backup()}


@tool(
    description="List the available backups, most recent first.",
    category="system",
)
def show_backups():
    """List the backups."""

    backups = system.list_backups()

    if not backups:
        return {"message": t("There are no backups yet.")}

    return {"backups": backups}


@tool(
    description=(
        "Restores BRAIN's data from a backup, after checking it is not damaged. "
        "Replaces the current data (first saves a backup of the previous state in case it needs to be undone). "
        "Ask the user for confirmation before using it."
    ),
    category="system",
    arguments={
        "name": "Name of the backup (backup_YYYYMMDD_HHMMSS.zip). Omit, or 'last', for the most recent one.",
    },
)
def restore_backup(name: str = None):
    """Restore a backup."""

    try:
        return {"restored": system.restore_backup_file(name)}
    except BackupError as error:
        return {"error": str(error)}


@tool(
    description="Choose a second folder (USB, OneDrive, another disk) where BRAIN also saves every backup. An empty path removes it.",
    category="system",
    arguments={"path": "Destination folder, for example 'D:\\\\BRAIN-backups' or the OneDrive folder. Empty to remove it."},
)
def set_backup_destination(path: str = ""):
    """Second destination for the backups."""

    try:
        return system.configure_destination(path)
    except BackupError as error:
        return {"error": str(error)}
