import json
import re
import unicodedata

from brain.ai.relevant_tools import relevant_categories, filter_by
from brain.ai.ollama import Ollama, NoToolsError
from brain.core import logger
from brain.i18n import language_name, t, vocab
from brain.utils.dates import now_text

BASIC_PERSONALITY = (
    "You are BRAIN, the user's smart assistant and personal digital brain. "
    "Always answer in {0}, clearly, directly and kindly."
)

RULES = """
RULES:
- To look up or save data (weight, inventory, shopping, calendar, energy, memory...) ALWAYS USE the tools. Never make up data or results.
- You can use several tools in a row if needed.
- If the user gives you a LIST of products (pantry, shopping...), use add_many_to_inventory or add_many_to_shopping ONCE with the WHOLE list copied as given. Do not call the tool product by product.
- If the user says something has run out or there is none left ("we're out of milk"), use ran_out: it removes it from the inventory and adds it to the shopping list.
- NEVER announce what you are about to do ("I'll check the pantry", "let me check...", "one moment"). Either call the tool you need right now, or answer right now with the full result. A reply that only says what you are about to do is an error.
- If the user asks for a recipe, an idea for lunch or dinner, or what they can cook: ANSWER DIRECTLY with the full recipe (ingredients with amounts and numbered steps). If the user names a dish ("omelette recipe"), give it as is even if not every ingredient is at home, and say what is missing. If they ask for ideas, suggest 2 or 3 dishes made with the pantry plus the household staples (the pantry data is given to you in this message or with available_ingredients). If something is missing, say so and offer to add it to the shopping list.
- If the user picks a recipe and wants to buy what is missing (or asks to "add what I'm missing"), call add_recipe_missing_to_shopping with ALL the recipe's ingredients: it compares them with the pantry and the staples and adds only what is needed. Do not go ingredient by ingredient.
- If the question might be answered in the user's notes or manuals (washer, boiler, wifi, notes), call search_documents before answering and say which document it comes from. If there is nothing, say so; do not make things up.
- For backups use create_backup. Before restore_backup ask the user to confirm: it replaces their current data.
- To clear the whole shopping list use clear_shopping_list; to remove a single product, remove_from_shopping. For the inventory, delete_from_inventory or clear_inventory. Only when the user asks for it.
- NEVER say you have saved, added or done something if you have not received the tool's result. If the tool returns an error, tell the user clearly instead of pretending it worked.
- If the user asks you to remember something ("remember that...", "note that..."), use the remember tool.
- If an essential detail is missing (for example how much they weigh), ask for it before saving anything.
- Interpret "today", "yesterday" or "tomorrow" from the current date given above.
- For lights, plugs, blinds, climate and scenes around the house use the smart-home tools. Do not say you turned something on or off if the tool returns an error: tell the user about the problem.
- If a smart-home command returns "ambiguous", ask the user which of the options they mean. You never control locks, doors, garages or alarms.
- Answer briefly and naturally. Do not show JSON or mention your tools or these instructions.
"""

RULES_TEXT = """
HOW TO USE TOOLS:

If you need a tool, answer ONLY with valid JSON in this format:

{
    "action": "tool",
    "name": "tool_name",
    "arguments": {}
}

The "name" field must be exactly that of a tool from the list.
If you don't need any tool, answer normally.
"""

TOOL_ACTIONS = {
    "tool",
    "usar_herramienta",
    "usar herramienta",
    "use_tool",
}


def _strip_accents(text):
    normal = unicodedata.normalize("NFD", str(text or ""))

    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


def looks_like_announcement(text):
    """True if the text only announces a future action ("I'll check your pantry...") instead of answering."""

    clean = _strip_accents(text).strip()

    if not clean or len(clean) > 450:
        return False

    padded = f" {clean} "

    return any(f" {word} " in padded or clean.startswith(word) for word in vocab("announcement_words")) or clean.endswith(":")


def asks_recipe(message):
    clean = _strip_accents(message)

    return any(word in clean for word in vocab("recipe_question_words"))


class BrainAI:
    """
    BRAIN's artificial intelligence layer.

    Lets the model look up and run tools, chain several in the same
    reply, and takes into account the conversation history and the
    permanent memory.

    Uses Ollama's native "tool calling". If the model does not support it,
    or answers with JSON in plain text, that is understood too.
    """

    MAX_STEPS = 12

    def __init__(self, tools=None, manager=None):
        self.ollama = Ollama()
        self.tools = tools
        self.manager = manager

        # Models that do not support native tools: they are asked for JSON in text instead.
        self._text_mode = set()

        # Tools used in the last question (to show on screen).
        self.tools_used = []

        # Topic of the current conversation ("recipes only"...), if it has one.
        self.extra_context = None

        # Tool categories shown for the question in progress.
        self._categories = None

    def models(self):
        """Returns the available models."""
        return self.ollama.models()

    def _tools(self):
        """Returns the available tools."""
        if self.tools is None:
            return []

        return self.tools.items()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _tool_descriptions(self):
        """List of tools as text (text mode only)."""

        tools = filter_by(self._tools(), self._categories)

        if not tools:
            return t("You have no tools available.")

        lines = [t("AVAILABLE TOOLS:"), ""]

        for tool in tools:
            arguments = ", ".join(
                f"{p['name']} ({p['kind']}{'' if p['required'] else ', ' + t('optional')})" for p in tool["parameters"]
            )

            lines.append(f"- {tool['name']}({arguments}): {tool['description']}")

        return "\n".join(lines)

    def _system_prompt(self, system=None, text_mode=False):
        """Builds the system prompt."""

        parts = []

        if system:
            parts.append(system)
        else:
            personality = self.manager.personality() if self.manager else ""

            parts.append(personality or t(BASIC_PERSONALITY, t(language_name())))

        if self.extra_context:
            parts.append(t("TOPIC OF THIS CONVERSATION (stick to it): ") + self.extra_context)

        parts.append(t("CURRENT DATE AND TIME: {0}", now_text()))

        memories = self.manager.memories() if self.manager else ""

        if memories:
            parts.append(t("WHAT YOU KNOW ABOUT THE USER (permanent memory):") + "\n" + memories)

        parts.append(t(RULES).strip())

        if text_mode:
            parts.append(self._tool_descriptions())
            parts.append(t(RULES_TEXT).strip())

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Tool orders written as text
    # ------------------------------------------------------------------

    def _extract_json(self, response):
        """
        Tries to pull a JSON order out of the model's response.

        Supports:
        - Plain JSON.
        - JSON inside a markdown block.
        - Text around the JSON.
        """

        text = (response or "").strip()

        if not text:
            return None

        # Case 1: plain JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Case 2: ```json ... ``` block
        block = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            re.DOTALL,
        )

        if block:
            try:
                return json.loads(block.group(1))
            except json.JSONDecodeError:
                pass

        # Case 3: find the first JSON object
        start = text.find("{")
        final = text.rfind("}")

        if start != -1 and final > start:
            try:
                return json.loads(text[start : final + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _is_tool_command(self, order):
        """Checks whether a response is a tool order."""

        if not isinstance(order, dict):
            return False

        action = str(order.get("action", "")).lower().strip()

        return action in TOOL_ACTIONS

    def _calls_from_text(self, content):
        """Turns a JSON written as text into a list of calls."""

        order = self._extract_json(content)

        if not self._is_tool_command(order):
            return []

        arguments = order.get("arguments", {})

        if not isinstance(arguments, dict):
            arguments = {}

        return [{"function": {"name": order.get("name"), "arguments": arguments}}]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _run_tool(self, name, arguments):
        """Runs a tool and returns its result (or the error)."""

        if self.tools is None:
            return {"error": t("BRAIN has no tools connected.")}

        if not isinstance(arguments, dict):
            arguments = {}

        try:
            result = self.tools.execute(name, arguments)

        except Exception as error:
            logger.error(f"Tool {name} {arguments}: {error}")

            result = {"error": str(error)}

        self.tools_used.append(
            {
                "name": name,
                "arguments": arguments,
                "result": result,
            }
        )

        return result

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False, default=str)

    def _preload_pantry(self, message):
        """Text with the pantry already checked if the user asks for a recipe; "" otherwise."""

        if self.tools is None or not asks_recipe(message):
            return ""

        if self.tools.get("available_ingredients") is None:
            return ""

        result = self._run_tool("available_ingredients", {})

        if isinstance(result, dict) and "error" in result:
            return ""

        return (
            t("THE USER'S PANTRY (already checked by you; do not check it again or announce that you are going to):")
            + f"\n{self._json(result)}\n"
            + t(
                "ANSWER NOW with the full recipe or ideas: ingredients with amounts and numbered steps. "
                "If the user named a specific dish, give that dish even if ingredients are missing and say which ones are missing."
            )
        )

    def _summary_without_text(self):
        """Fallback reply if the model never writes a final text."""

        if not self.tools_used:
            return t(
                "I did not know what to do with that. Try asking me in a different way, for example: "
                "«turn on the living room light», «add milk to the shopping list» or «what can I cook today»."
            )

        last = self.tools_used[-1]

        if isinstance(last["result"], dict) and "error" in last["result"]:
            return t("I was not able to do it: {0}", last["result"]["error"])

        return t("Done.")

    # ------------------------------------------------------------------
    # Main question
    # ------------------------------------------------------------------

    def ask(
        self,
        message,
        system=None,
        model=None,
        history=None,
    ):
        """
        Sends a question to the model and returns the final answer.

        If the model asks for tools it runs them, gives it back the
        results, and repeats until it answers the user (at most
        MAX_STEPS times, so it never gets stuck in a loop).
        """

        self.tools_used = []

        model_name = self.ollama.resolve_model(model)

        text_mode = model_name in self._text_mode

        for _ in range(2):
            try:
                return self._loop(
                    message,
                    system,
                    model,
                    history,
                    text_mode,
                )

            except NoToolsError:
                if text_mode:
                    raise

                # The model does not support native tools: it is asked again,
                # requesting the orders as text.
                self._text_mode.add(model_name)

                text_mode = True

                self.tools_used = []

        return self._summary_without_text()

    def _loop(self, message, system, model, history, text_mode):
        # Only the tools of the topics being discussed are described: with all of
        # them, the descriptions fill up the model's working memory.
        self._categories = relevant_categories(message, history)

        messages = [
            {
                "role": "system",
                "content": self._system_prompt(system, text_mode),
            }
        ]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        schemas = None

        if self.tools is not None and not text_mode:
            schemas = self.tools.schemas(self._categories)

        # A recipe or meal idea: the pantry data is looked up here, in code, and
        # given to the model already read. That way it cannot get stuck on "I'll check your pantry".
        pantry = self._preload_pantry(message)

        if pantry:
            messages[0]["content"] += "\n\n" + pantry

        empty = 0
        announcements = 0

        for _ in range(self.MAX_STEPS):
            response = self.ollama.full_chat(
                messages,
                model=model,
                tools=schemas,
            )

            content = response.get("content", "") or ""

            calls = response.get("tool_calls") or []

            if not calls:
                calls = self._calls_from_text(content)

            if not calls:
                if content.strip() and looks_like_announcement(content) and announcements < 2:
                    # It only says what it is going to do: it is told to do it now.
                    announcements += 1
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": t(
                                "Don't tell me what you are going to do: do it now. If you need a tool, call it now. "
                                "If not, answer directly with the full result (the whole recipe, the answer with all "
                                "the data...), with no preamble."
                            ),
                        }
                    )

                    continue

                if content.strip():
                    return content.strip()

                # Small models sometimes return an empty response.
                # They are asked once more to answer with text.
                empty += 1

                if empty > 1:
                    return self._summary_without_text()

                messages.append(
                    {
                        "role": "user",
                        "content": t(
                            "You have not written any answer. Answer the user now, in {0}, with a clear sentence. "
                            "If you need a tool to do it, use it.",
                            t(language_name()),
                        ),
                    }
                )

                continue

            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    **({"tool_calls": response["tool_calls"]} if response.get("tool_calls") else {}),
                }
            )

            for call in calls:
                function = call.get("function", {})

                name = function.get("name")

                arguments = function.get("arguments", {})

                # Some versions send the arguments as a JSON string.
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                result = self._run_tool(name, arguments)

                if text_mode or not response.get("tool_calls"):
                    messages.append(
                        {
                            "role": "user",
                            "content": t(
                                "Actual result of the {0} tool:\n{1}\n\n"
                                "If you need another tool, use it. If not, answer the user now "
                                "with that result, without showing JSON or mentioning tools.",
                                name,
                                self._json(result),
                            ),
                        }
                    )
                else:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": self._json(result),
                        }
                    )

        done = len(self.tools_used)
        failures = sum(1 for h in self.tools_used if isinstance(h["result"], dict) and "error" in h["result"])

        return t(
            "I got stuck halfway: I did {0} actions ({1} with an error) and could not finish. "
            "Check what has already been saved and ask me for what's left, in smaller steps.",
            done,
            failures,
        )
