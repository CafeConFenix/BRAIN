from brain.ai import BrainAI
from brain.core.config import Config
from brain.core.data_manager import DataManager
from brain.core.knowledge_manager import KnowledgeManager
from brain.core.module_loader import ModuleLoader
from brain.i18n import t
from brain.tools.executor import ToolExecutor
from brain.voice.conversation import ConversationManager


class Brain:
    """
    BRAIN's main core.

    Coordinates data, modules, tools, AI and conversation.
    """

    def __init__(self, quiet=False, persistent_history=True):

        self.data = DataManager()

        self.manager = KnowledgeManager()

        self.modules = ModuleLoader()

        self.tools = ToolExecutor()

        self.ai = BrainAI(
            tools=self.tools,
            manager=self.manager,
        )

        # Several conversations in parallel; "conversation" is the main one.
        self.conversations = ConversationManager(
            self,
            persistent=persistent_history,
        )

        self.conversation = self.conversations.get("general")

        if not quiet:
            print("=" * 50)
            print(t("BRAIN {0} started correctly", Config.VERSION))
            print("=" * 50)
