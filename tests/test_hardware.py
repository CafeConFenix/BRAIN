import os
import unittest
from unittest import mock

from brain.core import hardware
from brain.core.config import _url_ollama
from brain.core.hardware import Hardware, alternatives, recommend_model
from tests.helpers import CaseBrain


def machine(ram=16, vram=0, disk=200):
    return Hardware(ram_gb=ram, gpu_name="GPU" if vram else "", vram_gb=vram, free_disk_gb=disk)


class TestRecommendation(unittest.TestCase):
    def label(self, **kw):
        return recommend_model(machine(**kw))["label"]

    def test_gpu_potente_elige_the_large(self):
        self.assertEqual(self.label(ram=64, vram=24), "qwen3.8:27b")

    def test_gpu_media(self):
        self.assertEqual(self.label(ram=32, vram=12), "gemma4:12b")
        self.assertEqual(self.label(ram=16, vram=8), "gemma4:e4b")

    def test_without_gpu_depende_of_the_ram(self):
        self.assertEqual(self.label(ram=64), "gemma4:26b")
        self.assertEqual(self.label(ram=16), "gemma4:e4b")
        self.assertEqual(self.label(ram=8), "gemma4:e2b")
        self.assertEqual(self.label(ram=4), "qwen3:4b")

    def test_gpu_small_uses_the_ram(self):
        self.assertEqual(self.label(ram=16, vram=4), "gemma4:e4b")

    def test_no_elige_lo_that_no_cabe_in_disco(self):
        r = recommend_model(machine(ram=64, vram=24, disk=15))

        self.assertNotEqual(r["label"], "qwen3.8:27b")
        self.assertIn("disk", r["explanation"])

    def test_alternatives_son_more_pequenas(self):
        self.assertEqual(alternatives("qwen3:4b"), [])
        self.assertIn("qwen3:4b", alternatives("gemma4:e4b"))
        self.assertEqual(alternatives("no-existe"), [])

    def test_the_detection_real_no_falla(self):
        hw = hardware.detect_hardware()

        self.assertGreaterEqual(hw.ram_gb, 0)
        self.assertTrue(recommend_model(hw)["label"])


class TestAddressOllama(unittest.TestCase):
    def url(self, **env):
        with mock.patch.dict(os.environ, env, clear=False):
            for key in ("BRAIN_OLLAMA_URL", "OLLAMA_HOST"):
                if key not in env:
                    os.environ.pop(key, None)

            return _url_ollama()

    def test_by_default(self):
        self.assertEqual(self.url(), "http://127.0.0.1:11434")

    def test_respects_ollama_host(self):
        self.assertEqual(self.url(OLLAMA_HOST="127.0.0.1:11500"), "http://127.0.0.1:11500")
        self.assertEqual(self.url(OLLAMA_HOST="0.0.0.0"), "http://127.0.0.1:11434")
        self.assertEqual(self.url(OLLAMA_HOST="https://otro:9999"), "https://otro:9999")

    def test_brain_ollama_url_send(self):
        self.assertEqual(self.url(BRAIN_OLLAMA_URL="http://x:1", OLLAMA_HOST="y"), "http://x:1")


class TestModelSavedYdescarga(CaseBrain):
    models = ("qwen3:4b", "gemma4:e4b")

    def test_uses_the_model_saved(self):
        hardware.save_model("gemma4:e4b")

        self.assertEqual(self.brain.ai.ollama.resolve_model(), "gemma4:e4b")

    def test_ignora_the_saved_si_already_no_esta_installed(self):
        hardware.save_model("qwen3.8:27b")

        self.assertEqual(self.brain.ai.ollama.resolve_model(), "gemma4:e4b")

    def test_download_by_the_api_of_same_server(self):
        ollama = self.brain.ai.ollama
        progress = []

        self.assertTrue(ollama.download_model("gemma4:12b", progress=lambda *a: progress.append(a)))
        self.assertIn("gemma4:12b", ollama.models())
        self.assertEqual(progress[0], ("pulling", 50, 100))

    def test_download_failed_lanza_error(self):
        from brain.ai.ollama import OllamaError

        self.ollama.pull_ok = False

        with self.assertRaises(OllamaError):
            self.brain.ai.ollama.download_model("no-existe:1b", progress=lambda *a: None)

    def test_upgrade_ia_download_y_guarda(self):
        from brain.cli import upgrade_model

        with mock.patch("brain.cli.detect_hardware", return_value=machine(ram=64, vram=12)):
            self.assertEqual(upgrade_model(self.brain, auto=True), 0)

        self.assertEqual(hardware.read_saved_model(), "gemma4:12b")
        self.assertIn("gemma4:12b", self.ollama.downloaded)

    def test_upgrade_ia_test_uno_more_small_si_falla(self):
        from brain.cli import upgrade_model

        original = self.brain.ai.ollama.download_model
        attempts = []

        def download(name, progress=None):
            attempts.append(name)
            return False if name == "gemma4:12b" else original(name, progress=lambda *a: None)

        self.brain.ai.ollama.download_model = download

        with mock.patch("brain.cli.detect_hardware", return_value=machine(ram=64, vram=12)):
            self.assertEqual(upgrade_model(self.brain, auto=True), 0)

        self.assertEqual(attempts[:2], ["gemma4:12b", "gemma4:e4b"])
