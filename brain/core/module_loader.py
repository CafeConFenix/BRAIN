import importlib
import inspect
from pathlib import Path


class ModuleLoader:
    """
    Automatically discovers, loads and exposes BRAIN's modules.

    Each file in brain/modules/ must contain a class whose name
    matches the module name in PascalCase.

    Example:

        health.py -> class Health
        inventory.py -> class Inventory
        energy.py -> class Energy
    """

    def __init__(self):
        self.path = Path(__file__).resolve().parent.parent / "modules"

        self.modules = {}
        self.instances = {}

        self._load()

    def _class_name(self, name):
        """
        Converts a module name to a class name.

        health -> Health
        inventory -> Inventory
        memory -> Memory
        """

        return "".join(part.capitalize() for part in name.split("_"))

    def _load(self):
        """
        Discovers and imports every available module.
        """

        if not self.path.exists():
            return

        for file in sorted(self.path.glob("*.py")):

            if file.name.startswith("_"):
                continue

            name = file.stem
            class_name = self._class_name(name)

            try:
                module = importlib.import_module(f"brain.modules.{name}")

                klass = getattr(
                    module,
                    class_name,
                    None,
                )

                if klass is None:
                    print(
                        f"[BRAIN] Module "
                        f"{name} has no class "
                        f"{class_name}"
                    )
                    continue

                if not inspect.isclass(klass):
                    continue

                instance = klass()

                self.modules[name] = module
                self.instances[name] = instance

            except Exception as error:
                print(f"[BRAIN] Error loading module " f"{name}: {error}")

    def items(self):
        """
        Returns the names of the loaded modules.
        """

        return sorted(self.instances.keys())

    def get(self, name):
        """
        Returns a module's instance.
        """

        return self.instances.get(name)
