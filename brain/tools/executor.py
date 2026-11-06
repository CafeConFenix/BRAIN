from brain.tools.registry import ToolRegistry


class ToolExecutor:
    """
    Executes registered tools.
    """

    def __init__(self):
        self.registry = ToolRegistry()

    def execute(self, name, /, arguments=None, **kwargs):
        """
        Executes a tool.

        Arguments can be passed as a dict or as named
        parameters:

            execute("save_weight", {"weight": 80})
            execute("save_weight", weight=80)
        """

        if arguments:
            if not isinstance(arguments, dict):
                raise TypeError("Arguments must be a dict.")

            kwargs = {**arguments, **kwargs}

        # `name` is positional-only: so a tool can have a
        # parameter called "name" (add_inventory) without clashing with it.
        return self.registry.execute(name, kwargs)

    def items(self):
        """Returns the available tools."""

        return self.registry.items()

    def get(self, name):
        """Gets a tool."""

        return self.registry.get(name)

    def schemas(self, categories=None):
        """Returns the tools in JSON Schema format for Ollama."""

        return self.registry.schemas(categories)
