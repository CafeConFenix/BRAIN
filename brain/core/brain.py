from brain.ai import BrainAI
from brain.core.config import Config
from brain.core.data_manager import DataManager
from brain.core.gestor_conocimiento import GestorConocimiento
from brain.core.module_loader import ModuleLoader
from brain.tools.executor import ToolExecutor
from brain.voice import Conversation
from brain.voice.conversation import GestorConversaciones


class Brain:
    """
    Núcleo principal de BRAIN.

    Coordina datos, módulos, herramientas, IA y conversación.
    """

    def __init__(self, silencioso=False, historial_persistente=True):

        self.data = DataManager()

        self.gestor = GestorConocimiento()

        self.modules = ModuleLoader()

        self.tools = ToolExecutor()

        self.ai = BrainAI(
            tools=self.tools,
            gestor=self.gestor,
        )

        # Varias conversaciones en paralelo; "conversacion" es la principal.
        self.conversaciones = GestorConversaciones(
            self,
            persistente=historial_persistente,
        )

        self.conversacion = self.conversaciones.obtener("general")

        if not silencioso:
            print("=" * 50)
            print(f"BRAIN {Config.VERSION} iniciado correctamente")
            print("=" * 50)
