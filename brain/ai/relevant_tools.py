"""
Chooses which tools are shown to the AI for each question.

The descriptions of every BRAIN tool take up more than 10,000 tokens, almost
all of the model's working memory: sending them all makes the AI lose its
instructions and reply empty. That's why each question only gets the tools of
the topics it is about (the current message and the last part of the
conversation). Tools that are not sent still exist.
"""

import re
import unicodedata
from typing import Iterable, List, Optional, Set

from brain.i18n import vocab

# If no topic is recognized this set is sent (the most common case).
BASIC = ("inventory", "shopping", "calendar", "smart_home", "health")

# Always available (it is small and useful in any chat).
ALWAYS = ("memory",)

CONTEXT_MESSAGES = 3


def _normalize(text: str) -> str:
    strip_accents = "".join(c for c in unicodedata.normalize("NFD", str(text)) if unicodedata.category(c) != "Mn")

    return " " + re.sub(r"\s+", " ", strip_accents.lower()) + " "


def _topics_of(text: str) -> Set[str]:
    clean = _normalize(text)

    return {topic for topic, keys in vocab("topic_words").items() if any(key in clean for key in keys)}


def relevant_categories(message: str, history: Optional[Iterable[dict]] = None) -> Set[str]:
    """Tool categories that should be shown for this question."""

    topics = _topics_of(message)

    for previous in list(history or [])[-CONTEXT_MESSAGES:]:
        topics |= _topics_of(previous.get("content", ""))

    if not topics:
        topics = set(BASIC)

    return topics | set(ALWAYS)


def filter_by(tools: List[dict], categories: Optional[Set[str]]) -> List[dict]:
    if not categories:
        return list(tools)

    return [h for h in tools if h["category"] in categories]
