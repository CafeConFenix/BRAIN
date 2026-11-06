"""Pruebas en español de voz y gestor de conversaciones."""

from brain import i18n
from brain.voice.conversation import ConversationManager
from brain.voice.recognition import VoiceError, wav_to_audio
from tests.helpers import CaseBrain


class TestEsVoice(CaseBrain):
    def setUp(self):
        super().setUp()
        i18n.set_language("es", persist=False)

    def tearDown(self):
        i18n.reset()
        super().tearDown()

    def test_bad_wav_error_in_spanish(self):
        with self.assertRaises(VoiceError) as err:
            wav_to_audio(b"esto no es un wav")

        self.assertIn("No he entendido el audio", str(err.exception))

    def test_new_conversation_title_in_spanish(self):
        manager = ConversationManager(self.brain, persistent=False)
        new = manager.create()

        self.assertEqual(new["title"], "Nueva conversación")

    def test_delete_main_conversation_error_in_spanish(self):
        manager = ConversationManager(self.brain, persistent=False)

        with self.assertRaises(ValueError) as err:
            manager.delete("general")

        self.assertIn("no se puede borrar", str(err.exception))


if __name__ == "__main__":
    import unittest

    unittest.main()
