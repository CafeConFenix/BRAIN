from brain.base.module import ModuleBase
from brain.i18n import t, vocab
from brain.modules.inventory import normalize
from brain.utils.dates import today

TYPES = ("people", "preferences", "context", "projects")


class Memory(ModuleBase):
    """What BRAIN remembers about the user, by kind (people, preferences, context, projects)."""

    name = "memory"

    def _kind(self, kind):
        key = normalize(kind or "")

        return vocab("memory_synonyms").get(key, key)

    def normalize_type(self, kind, strict=False):
        """Official kind of memory. Anything unknown is saved as "context"."""

        key = self._kind(kind or "context")

        if key in TYPES:
            return key

        if strict:
            raise ValueError(t("The kind of memory '{0}' does not exist. Options: {1}.", kind, ", ".join(TYPES)))

        return "context"

    def remember(self, text, kind="context"):
        """Save something so that BRAIN always remembers it."""

        kind = self.normalize_type(kind)

        text = str(text).strip()

        if not text:
            raise ValueError(t("There is nothing to remember."))

        existing = self.get_section(kind)

        for record in existing:
            if normalize(record.get("text", "")) == normalize(text):
                return {**record, "kind": kind, "already_existed": True}

        record = {"text": text, "date": today()}

        self.add_record(kind, record)

        return {**record, "kind": kind}

    def query(self, kind=None):
        key = self._kind(kind)

        # "all", "memories"... or a kind that does not exist: everything is shown.
        if key in TYPES:
            return {key: self.get_section(key)}

        return {name: self.get_section(name) for name in TYPES if self.get_section(name)}

    def forget(self, text):
        """Delete the memories that contain the given text."""

        key = normalize(text)

        deleted = []

        for kind in TYPES:
            records = self.get_section(kind)

            remaining = [r for r in records if key not in normalize(r.get("text", ""))]

            if len(remaining) != len(records):
                deleted.extend(r for r in records if r not in remaining)
                self.save_section(kind, remaining)

        if not deleted:
            raise ValueError(t("I cannot find any memory with '{0}'.", text))

        return {"forgotten": deleted}

    def summary_for_ai(self):
        """Short text with everything remembered, to include in the prompt."""

        lines = []

        for kind, records in self.query().items():
            for record in records:
                lines.append(f"- ({kind}) {record.get('text', '')}")

        return "\n".join(lines)
