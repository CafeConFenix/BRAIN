from brain.modules.memory import Memory
from brain.tools.decorators import tool

memory = Memory()

KINDS = "people, preferences, context or projects"


@tool(
    description=(
        "Save something in BRAIN's permanent memory to always remember it "
        "(a fact about the user, a person, a preference, a project)."
    ),
    category="memory",
    arguments={
        "text": "What to remember, written as a complete sentence",
        "kind": KINDS + ". Default context.",
    },
)
def remember(text: str, kind: str = "context"):
    """Save a memory."""

    return {"saved": memory.remember(text, kind)}


@tool(
    description="Look up what BRAIN has saved in its permanent memory.",
    category="memory",
    arguments={"kind": KINDS + ". Omit to see everything."},
)
def query_memory(kind: str = None):
    """Look up the memory."""

    memories = memory.query(kind)

    if not memories or not any(memories.values()):
        return {"message": "There is nothing saved in the memory."}

    return memories


@tool(
    description="Delete from the memory the records that contain some text.",
    category="memory",
    arguments={"text": "Word or phrase that appears in the memory to delete"},
)
def forget(text: str):
    """Delete memories."""

    return memory.forget(text)
