from brain.core.config import Config
from brain.core.data_manager import DataManager
from brain.i18n import language


class KnowledgeManager:
    """
    Single point of access to BRAIN's knowledge.

    The AI and other system components use this class to look up
    information without reaching the DataManager directly.
    """

    def __init__(self):
        self.data = DataManager()

    def get(self, module: str, section: str):
        """
        Returns the content of a module's section.
        """

        data = self.data.read_module(module)

        if data is None:
            return None

        return data.get(section, [])

    def personality(self):
        """
        Returns the text of personality.md (the user's own, or the factory one if there isn't one).

        Read with utf-8-sig to accept files saved with Windows Notepad.
        """

        base = Config.BASE_PERSONALITY

        if language() == "es":
            spanish = base.with_suffix(".es.md")

            if spanish.exists():
                base = spanish

        for path in (Config.PERSONALITY, base):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    return f.read().strip()

            except OSError:
                continue

        return ""

    def memories(self):
        """Returns, as text, everything the user has asked to remember."""

        from brain.modules.memory import Memory

        return Memory().summary_for_ai()
