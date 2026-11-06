from brain.i18n import t
from brain.modules.documents import DocumentError, Documents
from brain.tools.decorators import tool

documents = Documents()


@tool(
    description=(
        "Search the user's saved notes, manuals and documents (.txt, .md and .json files) and return "
        "the most relevant fragments. Use it when the answer might be in their notes or manuals "
        "('how do I program the washing machine?', 'what did I note about the boiler?'). Answer only with what you "
        "find and say which document it comes from."
    ),
    category="documents",
    arguments={
        "query": "Keywords of what to look for",
        "limit": "How many fragments to return. Default 5.",
    },
)
def search_documents(query: str, limit: int = 5):
    """Search the saved documents."""

    try:
        results = documents.search(query, limit)
    except DocumentError as error:
        return {"error": str(error)}

    if not results:
        available = documents.items()

        if not available:
            return {"message": t("There are no documents. Save .txt, .md or .json files in {0}.", documents.folder)}

        return {"message": t("I found nothing about '{0}'.", query), "documents": [d["name"] for d in available]}

    return {"results": results}


@tool(
    description=(
        "Read a whole saved document (by pages), or list the available documents if no name is given. "
        "Use it after search_documents when more context is needed."
    ),
    category="documents",
    arguments={
        "name": "Document name, for example 'washer_manual.md'. Omit to see the list.",
        "since": "Character to start from (to read the next page). Default 0.",
    },
)
def read_document(name: str = None, since: int = 0):
    """Read a document, or list the available ones."""

    if not name:
        items = documents.items()

        if not items:
            return {"message": t("There are no documents. Save .txt, .md or .json files in {0}.", documents.folder)}

        return {"documents": items}

    try:
        return documents.read(name, since)
    except DocumentError as error:
        return {"error": str(error)}
