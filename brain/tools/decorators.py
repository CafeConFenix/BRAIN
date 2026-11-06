import inspect

TOOL_REGISTRY = []

# Python type -> JSON Schema type (for Ollama's "tool calling").
JSON_TYPES = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


def _parameters(func, descriptions):
    """
    Gets a function's parameters to describe them to the AI.

    Returns a list of dicts with name, type, description and whether
    it is required.
    """

    parameters = []

    for name, param in inspect.signature(func).parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        annotation = param.annotation

        if isinstance(annotation, type):
            kind = annotation.__name__
        else:
            kind = "str"

        if kind not in JSON_TYPES:
            kind = "str"

        parameters.append(
            {
                "name": name,
                "kind": kind,
                "description": descriptions.get(name, ""),
                "required": param.default is inspect.Parameter.empty,
            }
        )

    return parameters


def tool(name=None, description="", category="general", arguments=None):
    """
    Decorator to automatically register a tool.

    Each tool is registered with:
    - name
    - description
    - category
    - parameters (taken from the function's signature)
    - the original function

    `arguments` is an optional dict {parameter: explanation} that
    helps the AI fill in each argument correctly.
    """

    def decorator(func):
        final_name = name or func.__name__

        # If the module is reloaded, the tool is replaced.
        TOOL_REGISTRY[:] = [h for h in TOOL_REGISTRY if h["name"] != final_name]

        TOOL_REGISTRY.append(
            {
                "name": final_name,
                "description": description,
                "category": category,
                "parameters": _parameters(func, arguments or {}),
                "function": func,
            }
        )

        return func

    return decorator
