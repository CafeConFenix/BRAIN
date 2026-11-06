import re

from brain.i18n import t, vocab
from brain.tools.decorators import TOOL_REGISTRY, JSON_TYPES


def _number_from_text(value):
    """
    Pulls the first number out of a text such as "1 unit", "2 un.", "1.5 kg" or
    "two". Small models often send the quantity together with its unit.
    """

    text = value.strip().lower()

    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)

    if match:
        return float(match.group(0).replace(",", "."))

    number_words = vocab("number_words")

    for word in re.findall(r"[a-záéíóú]+", text):
        if word in number_words:
            return float(number_words[word])

    raise ValueError(value)


def _convert(name, value, kind):
    """
    Converts the value received from the AI to the type the tool expects.

    Models usually send numbers as text ("188.5") and, depending on the
    language, sometimes with a decimal comma ("188,5").
    """

    if value is None:
        return None

    try:
        if kind == "float":
            if isinstance(value, str):
                return _number_from_text(value)

            return float(value)

        if kind == "int":
            number = _number_from_text(value) if isinstance(value, str) else float(value)

            if number != int(number):
                raise ValueError

            return int(number)

        if kind == "bool":
            if isinstance(value, str):
                return value.strip().lower() in vocab("true_words")

            return bool(value)

        if kind == "str":
            return str(value)

    except (ValueError, TypeError, OverflowError):
        raise ValueError(t("The argument '{0}' must be of type {1}, but {2!r} was received.", name, kind, value)) from None

    return value


class ToolRegistry:
    """
    BRAIN's central tool registry.

    Always reads from the global registry, so tools added
    after the registry is created show up too.
    """

    def items(self):
        """Returns all the registered tools."""
        return list(TOOL_REGISTRY)

    def get(self, name):
        """Gets a tool by name."""

        for tool in TOOL_REGISTRY:
            if tool["name"] == name:
                return tool

        return None

    def schemas(self, categories=None):
        """
        Describes the tools in Ollama's "tool calling" format
        (JSON Schema), so the model can call them.

        With `categories` only tools in those categories are described.
        """

        schemas = []

        for tool in TOOL_REGISTRY:
            if categories and tool["category"] not in categories:
                continue

            properties = {}

            for param in tool["parameters"]:
                prop = {"type": JSON_TYPES.get(param["kind"], "string")}

                if param["description"]:
                    prop["description"] = param["description"]

                properties[param["name"]] = prop

            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": [p["name"] for p in tool["parameters"] if p["required"]],
                        },
                    },
                }
            )

        return schemas

    def execute(self, name, arguments=None, /, **extra):
        """
        Executes a registered tool.

        Validates the arguments and converts them to the right type before
        calling the function.
        """

        kwargs = {**(arguments or {}), **extra}

        tool = self.get(name)

        if tool is None:
            raise ValueError(t("Tool '{0}' not found.", name))

        parameters = {p["name"]: p for p in tool.get("parameters", [])}

        if not parameters:
            # A tool with no arguments: whatever the model sends is ignored.
            return tool["function"]()

        # Small models sometimes make up arguments ("unit", "note"...).
        # They are ignored instead of failing: what matters is that the action happens.
        kwargs = {n: v for n, v in kwargs.items() if n in parameters}

        missing = [n for n, p in parameters.items() if p["required"] and kwargs.get(n) in (None, "")]

        if missing:
            raise ValueError(t("Missing required arguments for '{0}': {1}.", name, missing))

        # Empty optional arguments ("" or None) are dropped so their
        # default value is used.
        converted = {
            n: _convert(n, value, parameters[n]["kind"]) for n, value in kwargs.items() if value not in (None, "")
        }

        return tool["function"](**converted)
