import unittest

from tests.helpers import CaseBrain, call, text


def user_messages(req):
    return [m["content"] for m in req["messages"] if m["role"] == "user"]


class TestIA(CaseBrain):
    def test_simple_response(self):
        self.ollama.responses = [text("I am BRAIN.")]

        self.assertEqual(self.brain.ai.ask("Who are you?"), "I am BRAIN.")

    def test_picks_the_installed_model(self):
        self.assertEqual(self.brain.ai.ollama.resolve_model(), "qwen3:4b")

    def test_sends_tools_and_context(self):
        self.ollama.responses = [text("ok")]

        self.brain.ai.ask("hi")

        req = self.ollama.requests[0]

        self.assertGreater(len(req["tools"]), 5)
        self.assertEqual(req["options"]["num_ctx"], 16384)
        self.assertFalse(req["stream"])

    def test_the_prompt_includes_date_personality_and_memory(self):
        self.brain.modules.get("memory").remember("My name is Luis", "people")

        self.ollama.responses = [text("ok")]

        self.brain.ai.ask("hi")

        system = self.ollama.requests[0]["messages"][0]["content"]

        self.assertIn("CURRENT DATE AND TIME", system)
        self.assertIn("My name is Luis", system)
        self.assertIn("BRAIN", system)

    def test_uses_a_tool_and_answers_with_the_result(self):
        self.ollama.responses = [
            call("save_weight", weight="88.4", date="2026-08-10"),
            text("Noted: 88.4 kg."),
        ]

        response = self.brain.ai.ask("Today I weigh 88.4")

        self.assertEqual(response, "Noted: 88.4 kg.")
        self.assertEqual(self.brain.modules.get("health").current_weight()["weight"], 88.4)
        self.assertEqual([h["name"] for h in self.brain.ai.tools_used], ["save_weight"])

        # The second request carries the tool's result.
        roles = [m["role"] for m in self.ollama.requests[1]["messages"]]

        self.assertEqual(roles[-2:], ["assistant", "tool"])

    def test_chains_several_tools(self):
        self.ollama.responses = [
            call("add_to_shopping", product="milk", quantity=2),
            call("add_to_shopping", product="bread"),
            call("show_shopping_list"),
            text("You have milk and bread on the list."),
        ]

        response = self.brain.ai.ask("Add milk and bread and tell me what's there")

        self.assertIn("milk", response)
        self.assertEqual(len(self.brain.modules.get("shopping").items()), 2)
        self.assertEqual(len(self.brain.ai.tools_used), 3)

    def test_tool_error_is_returned_to_the_model(self):
        self.ollama.responses = [
            call("save_weight", weight="a lot"),
            text("That weight is not valid, how much do you weigh?"),
        ]

        response = self.brain.ai.ask("Today I weigh a lot")

        self.assertIn("not valid", response)

        tool_message = self.ollama.requests[1]["messages"][-1]

        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("error", tool_message["content"])
        self.assertIsNone(self.brain.modules.get("health").current_weight())

    def test_made_up_tool(self):
        self.ollama.responses = [call("hack_the_nasa"), text("I can't do that.")]

        self.assertEqual(self.brain.ai.ask("hack it"), "I can't do that.")

    def test_the_model_answers_with_json_in_text(self):
        self.ollama.responses = [
            text('```json\n{"action": "tool", "name": "save_weight", '
                 '"arguments": {"weight": 87, "date": "2026-08-11"}}\n```'),
            text("Saved: 87 kg."),
        ]

        response = self.brain.ai.ask("Today I weigh 87")

        self.assertEqual(response, "Saved: 87 kg.")
        self.assertEqual(self.brain.modules.get("health").current_weight()["weight"], 87.0)

    def test_model_without_native_tools_switches_to_text_mode(self):
        self.ollama.responses = [
            ("error", 400, "registry.ollama.ai/library/gemma:2b does not support tools"),
            text('{"action": "tool", "name": "get_weight", "arguments": {}}'),
            text("You have no weight recorded yet."),
        ]

        response = self.brain.ai.ask("How much do I weigh?")

        self.assertEqual(response, "You have no weight recorded yet.")

        # The repeated request no longer carries "tools" and the list goes in the prompt.
        repeated = self.ollama.requests[1]

        self.assertNotIn("tools", repeated)
        self.assertIn("AVAILABLE TOOLS", repeated["messages"][0]["content"])

        # The next question remembers that this model does not support tools.
        self.ollama.responses = [text("ok")]

        self.brain.ai.ask("other")

        self.assertNotIn("tools", self.ollama.requests[-1])

    def test_does_not_get_stuck_in_a_loop(self):
        self.ollama.responses = [call("get_weight")] * 20

        response = self.brain.ai.ask("loop")

        self.assertIn("stuck halfway", response)
        self.assertLessEqual(len(self.ollama.requests), self.brain.ai.MAX_STEPS)

    def test_removes_qwens_internal_reasoning(self):
        self.ollama.responses = [text("<think>thinking...</think>Hello Luis.")]

        self.assertEqual(self.brain.ai.ask("hi"), "Hello Luis.")

    def test_without_installed_models(self):
        from brain.ai.ollama import OllamaError

        self.ollama.models.clear()

        with self.assertRaises(OllamaError):
            self.brain.ai.ask("hi")

    def test_requests_a_model_that_does_not_exist(self):
        from brain.ai.ollama import OllamaError

        with self.assertRaises(OllamaError) as context:
            self.brain.ai.ask("hi", model="made-up:1b")

        self.assertIn("ollama pull made-up:1b", str(context.exception))

    def test_ollama_off_gives_a_clear_error(self):
        from brain.ai.ollama import Ollama, OllamaError

        client = Ollama(url="http://127.0.0.1:9")

        self.assertFalse(client.active_server())

        with self.assertRaises(OllamaError) as context:
            client.models()

        self.assertIn("Ollama", str(context.exception))


class TestDoesNotGetStuckOnAnnouncements(CaseBrain):
    """The model must answer or act, not say "I'll check your pantry" and stop."""

    def test_looks_like_announcement(self):
        from brain.ai.brain_ai import looks_like_announcement

        for announcement_text in (
            "I'm going to check your pantry to suggest a recipe.",
            "Let me check what you have at home.",
            "First I need to check what's in the fridge:",
            "One moment, I'll check the inventory.",
        ):
            self.assertTrue(looks_like_announcement(announcement_text), announcement_text)

        for response_text in (
            "Potato omelette: 4 eggs, 3 potatoes and oil. 1. Peel the potatoes...",
            "Done, I turned on the living room light.",
            "",
        ):
            self.assertFalse(looks_like_announcement(response_text), response_text)

        self.assertFalse(looks_like_announcement("Recipe: " + "long step " * 80))

    def test_recipe_carries_the_pantry_already_checked(self):
        self.brain.tools.execute("add_inventory", {"name": "eggs", "quantity": 6, "location": "fridge"})
        self.ollama.responses = [text("Omelette: 3 eggs and oil. 1. Beat the eggs...")]

        response = self.brain.ai.ask("give me a recipe for dinner")

        system = self.ollama.requests[0]["messages"][0]["content"]
        self.assertIn("THE USER'S PANTRY", system)
        self.assertIn("eggs", system)
        self.assertTrue(response.startswith("Omelette"))
        self.assertEqual(len(self.ollama.requests), 1)  # a single call to the model
        self.assertEqual(self.brain.ai.tools_used[0]["name"], "available_ingredients")

    def test_empty_pantry_also_gives_a_recipe(self):
        self.ollama.responses = [text("Plain rice: 1 cup of rice, 2 of water, salt. 1. Boil the water...")]

        response = self.brain.ai.ask("what can I cook today?")

        self.assertIn("rice", response)
        self.assertIn("THE USER'S PANTRY", self.ollama.requests[0]["messages"][0]["content"])

    def test_if_it_only_announces_it_is_told_to_answer(self):
        self.ollama.responses = [
            text("I'm going to check your pantry to see what we can make."),
            text("Pasta with tomato: 200 g of pasta and tomato sauce. 1. Cook the pasta..."),
        ]

        response = self.brain.ai.ask("hi, give me a pasta recipe")

        self.assertTrue(response.startswith("Pasta with tomato"))
        requirement = self.ollama.requests[1]["messages"][-1]
        self.assertEqual(requirement["role"], "user")
        self.assertIn("do it now", requirement["content"])

    def test_does_not_repeat_without_end(self):
        self.ollama.responses = [text("I'm going to check your pantry.")] * 3

        response = self.brain.ai.ask("what's the weather like at home")

        self.assertEqual(response, "I'm going to check your pantry.")  # after 2 warnings whatever it says is accepted
        self.assertEqual(len(self.ollama.requests), 3)

    def test_other_requests_do_not_check_the_pantry(self):
        self.ollama.responses = [text("Weight saved.")]
        self.brain.ai.ask("today I weigh 80")

        self.assertNotIn("THE USER'S PANTRY", self.ollama.requests[0]["messages"][0]["content"])


if __name__ == "__main__":
    unittest.main()
