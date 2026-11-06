import unittest

from tests.helpers import CaseBrain, call, text


class TestConversation(CaseBrain):
    def test_the_history_travels_to_the_ai(self):
        self.ollama.responses = [text("You weigh 88 kg."), text("On August 5th you weighed 90.")]

        self.brain.conversation.ask("How much do I weigh?")
        self.brain.conversation.ask("And on August 5th?")

        messages = self.ollama.requests[1]["messages"]

        roles = [m["role"] for m in messages]

        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        self.assertEqual(messages[1]["content"], "How much do I weigh?")
        self.assertEqual(messages[2]["content"], "You weigh 88 kg.")

    def test_the_history_is_remembered_on_reopening(self):
        self.ollama.responses = [text("Hi Luis.")]

        self.brain.conversation.ask("Hi")

        from brain.core import Brain

        other = Brain(quiet=True)

        self.assertEqual(
            other.conversation.messages(),
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hi Luis."},
            ],
        )

    def test_clear_also_deletes_from_disk(self):
        self.ollama.responses = [text("Hi.")]

        self.brain.conversation.ask("Hi")
        self.brain.conversation.clear()

        from brain.core import Brain

        self.assertEqual(Brain(quiet=True).conversation.messages(), [])

    def test_history_limit(self):
        self.ollama.responses = [text(f"r{i}") for i in range(30)]

        for i in range(30):
            self.brain.conversation.ask(f"p{i}")

        messages = self.brain.conversation.messages()

        self.assertLessEqual(len(messages), 20)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[-1]["content"], "r29")

    def test_if_the_ai_fails_the_message_is_not_saved(self):
        from brain.ai.ollama import OllamaError

        self.ollama.models.clear()

        with self.assertRaises(OllamaError):
            self.brain.conversation.ask("Hi")

        self.assertEqual(self.brain.conversation.messages(), [])

    def test_damaged_history_does_not_break_startup(self):
        self.brain.data.save("conversations", "history", {"messages": [{"role": "weird"}, 5, None]})

        from brain.core import Brain

        self.assertEqual(Brain(quiet=True).conversation.messages(), [])

    def test_full_flow_weight_and_historical_query(self):
        health = self.brain.modules.get("health")

        health.save_weight(189.2, "2026-08-05")
        health.save_weight(188.5, "2026-08-10")

        self.ollama.responses = [
            call("weight_on_date", date="2026-08-05"),
            text("On August 5th you weighed 189.2 kg."),
        ]

        response = self.brain.conversation.ask("How much did I weigh on August 5th?")

        self.assertIn("189.2", response)

        tool_result = self.ollama.requests[1]["messages"][-1]["content"]

        self.assertIn("189.2", tool_result)


if __name__ == "__main__":
    unittest.main()
