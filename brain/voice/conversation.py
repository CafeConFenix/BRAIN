from brain.i18n import t

# A long message (40 pasted products, for example) is saved trimmed in
# the history: it is already done, and repeating it on every question
# only burns the AI's working memory.
MAX_HISTORY_CHARS = 1200


def crop(text, limit=MAX_HISTORY_CHARS):
    if len(text) <= limit:
        return text

    return text[: limit - 120].rstrip() + t(
        "\n[... trimmed: the original message had {0} characters ...]", len(text)
    )


class Conversation:
    """
    Manages a conversation with BRAIN.

    Keeps the message history and saves it to disk
    (data/conversations/history.json), so BRAIN remembers
    the conversation even after closing and reopening.
    """

    CATEGORY = "conversations"
    FILE = "history"  # the main ("general") conversation's file

    def __init__(self, brain, max_messages=20, persistent=True, id="general", instructions=None):
        self.brain = brain
        self.max_messages = max_messages
        self.persistent = persistent
        self.id = id
        self.instructions = instructions
        self.history = []

        if id != "general":
            self.FILE = f"c_{id}"

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self):
        if not self.persistent:
            return

        data = self.brain.data.read(self.CATEGORY, self.FILE)

        if not isinstance(data, dict):
            return

        for message in data.get("messages", []):
            if (
                isinstance(message, dict)
                and message.get("role") in {"user", "assistant"}
                and isinstance(message.get("content"), str)
            ):
                self.history.append(
                    {
                        "role": message["role"],
                        "content": message["content"],
                    }
                )

        self._limit_history()

    def _save(self):
        if not self.persistent:
            return

        try:
            self.brain.data.save(
                self.CATEGORY,
                self.FILE,
                {"messages": self.history},
            )
        except OSError:
            # Not being able to save the history must not stop the conversation.
            pass

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def clear(self):
        """Clears the history of the current conversation."""
        self.history.clear()
        self._save()

    def messages(self):
        """Returns a copy of the history."""
        return list(self.history)

    def ask(self, message):
        """
        Sends a message to BRAIN and saves the conversation.

        If the AI fails, the message is not saved to the history and the
        error is propagated so the caller can show it.
        """

        response = self._pasted_list(message)

        if response is None:
            # The topic of this conversation (for example "recipes only") is added
            # to the AI's prompt only while answering here.
            self.brain.ai.extra_context = self.instructions

            try:
                response = self.brain.ai.ask(
                    message,
                    history=list(self.history),
                )
            finally:
                self.brain.ai.extra_context = None

        self.history.append({"role": "user", "content": crop(message)})
        self.history.append({"role": "assistant", "content": crop(response)})

        self._limit_history()
        self._save()

        return response

    def record_exchange(self, message, response):
        """Saves something that happened without the AI to the history (for example, a reading taken from a photo)."""

        self.history.append({"role": "user", "content": crop(message)})
        self.history.append({"role": "assistant", "content": crop(response)})

        self._limit_history()
        self._save()

    def _pasted_list(self, message):
        """
        If the message is a long list of products with amounts, it is saved
        directly (without going through the AI, which gets long lists wrong).
        It goes to the pantry by default; it only goes to the shopping list
        if the user says so. Returns the response, or None if it was not a list.
        """

        from brain.utils.lists import apply_list, interpret_list, looks_like_pasted_list

        if not looks_like_pasted_list(message):
            return None

        inventory = self.brain.modules.get("inventory")
        shopping = self.brain.modules.get("shopping")

        if inventory is None or shopping is None:
            return None

        parsed = interpret_list(message)

        result = apply_list(parsed, inventory, shopping)

        self.brain.ai.tools_used = [
            {
                "name": "add_to_shopping" if result["destination"] == "shopping" else "add_many_to_inventory",
                "arguments": {"products": result["total"]},
                "result": result,
            }
        ]

        text = result["text"]

        if result["destination"] == "shopping":
            text += t(" If it was for the pantry, tell me and I'll change it.")
        else:
            text += t(" You can see them in the panel on the right. If you wanted the shopping list, tell me and I'll change it.")

        return text

    def _limit_history(self):
        """Limits the size of the history."""

        if len(self.history) > self.max_messages:
            excess = len(self.history) - self.max_messages

            del self.history[:excess]

        # The history must always start with a message from the user.
        while self.history and self.history[0]["role"] != "user":
            del self.history[0]


class ConversationManager:
    """
    Several conversations in parallel, each with its own history (and, if
    wanted, a topic: "this conversation is recipes only").

    The "general" conversation is the usual one (data/conversations/history.json)
    and cannot be deleted. The others are saved as c_<id>.json and listed in
    data/conversations/index.json.
    """

    INDEX = "index"
    NEW_TITLE = "New conversation"
    MAX_CONVERSATIONS = 30

    @property
    def _new_title(self):
        return t(self.NEW_TITLE)

    def __init__(self, brain, persistent=True):
        self.brain = brain
        self.persistent = persistent
        self._opened = {}

    # ------------------------------------------------------------------
    # Index
    # ------------------------------------------------------------------

    def _read_index(self):
        data = self.brain.data.read(Conversation.CATEGORY, self.INDEX) if self.persistent else None
        items = []

        if isinstance(data, dict):
            for c in data.get("conversations", []):
                if isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] != "general":
                    items.append(
                        {
                            "id": c["id"],
                            "title": str(c.get("title") or self._new_title)[:60],
                            "instructions": c.get("instructions") or None,
                            "created": c.get("created", ""),
                            "updated": c.get("updated", ""),
                        }
                    )

        if not self.persistent:
            items = list(getattr(self, "_memory_index", []))

        return items

    def _save_index(self, items):
        if not self.persistent:
            self._memory_index = items
            return

        try:
            self.brain.data.save(Conversation.CATEGORY, self.INDEX, {"conversations": items})
        except OSError:
            pass

    @staticmethod
    def _now():
        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def get(self, id=None):
        """The requested conversation (the main one by default). Raises KeyError if it does not exist."""

        id = id or "general"

        if id in self._opened:
            return self._opened[id]

        instructions = None

        if id != "general":
            data = next((c for c in self._read_index() if c["id"] == id), None)

            if data is None:
                raise KeyError(t("Conversation '{0}' does not exist.", id))

            instructions = data["instructions"]

        conversation = Conversation(self.brain, persistent=self.persistent, id=id, instructions=instructions)
        self._opened[id] = conversation

        return conversation

    def items(self):
        """All conversations, the main one first and then the most recent first."""

        result = [
            {
                "id": "general",
                "title": t("Main conversation"),
                "instructions": None,
                "messages": len(self.get("general").history),
                "updated": "",
            }
        ]

        other = sorted(self._read_index(), key=lambda c: c["updated"] or c["created"], reverse=True)

        for c in other:
            result.append(
                {
                    "id": c["id"],
                    "title": c["title"],
                    "instructions": c["instructions"],
                    "messages": len(self.get(c["id"]).history),
                    "updated": c["updated"],
                }
            )

        return result

    def create(self, title=None, instructions=None):
        import uuid

        items = self._read_index()

        if len(items) >= self.MAX_CONVERSATIONS:
            raise ValueError(t("There are already {0} conversations. Delete one to create another.", self.MAX_CONVERSATIONS))

        title = (title or "").strip() or self._new_title
        instructions = (instructions or "").strip() or None

        if instructions and len(instructions) > 500:
            raise ValueError(t("The conversation topic is too long (maximum 500 characters)."))

        now = self._now()
        new = {
            "id": uuid.uuid4().hex[:8],
            "title": title[:60],
            "instructions": instructions,
            "created": now,
            "updated": now,
        }

        items.append(new)
        self._save_index(items)

        return new

    def rename(self, id, title):
        items = self._read_index()
        title = (title or "").strip()

        if not title:
            raise ValueError(t("The title cannot be empty."))

        for c in items:
            if c["id"] == id:
                c["title"] = title[:60]
                self._save_index(items)

                return c

        raise KeyError(t("Conversation '{0}' does not exist.", id))

    def delete(self, id):
        if id == "general":
            raise ValueError(t("The main conversation cannot be deleted (it can be cleared)."))

        items = self._read_index()
        remaining = [c for c in items if c["id"] != id]

        if len(remaining) == len(items):
            raise KeyError(t("Conversation '{0}' does not exist.", id))

        self._save_index(remaining)
        self._opened.pop(id, None)

        if self.persistent:
            self.brain.data.remove(Conversation.CATEGORY, f"c_{id}")

    def ask(self, id, message):
        """Asks within a specific conversation and updates its date and title."""

        conversation = self.get(id)
        response = conversation.ask(message)

        if id and id != "general":
            items = self._read_index()

            for c in items:
                if c["id"] == id:
                    c["updated"] = self._now()

                    if c["title"] == self._new_title:
                        c["title"] = " ".join(message.split())[:40]

            self._save_index(items)

        return response
