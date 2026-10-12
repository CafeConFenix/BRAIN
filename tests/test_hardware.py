import os
import unittest
from unittest import mock

from brain.core import hardware
from brain.core.config import _url_ollama
from brain.core.hardware import Hardware, alternativas, recomendar_modelo
from tests.helpers import CasoBrain


def equipo(ram=16, vram=0, disco=200):
    return Hardware(ram_gb=ram, gpu_nombre="GPU" if vram else "", vram_gb=vram, disco_libre_gb=disco)


class TestRecomendacion(unittest.TestCase):
    def etiqueta(self, **kw):
        return recomendar_modelo(equipo(**kw))["etiqueta"]

    def test_gpu_potente_elige_el_grande(self):
        self.assertEqual(self.etiqueta(ram=64, vram=24), "qwen3.8:27b")

    def test_gpu_media(self):
        self.assertEqual(self.etiqueta(ram=32, vram=12), "gemma4:12b")
        self.assertEqual(self.etiqueta(ram=16, vram=8), "gemma4:e4b")

    def test_sin_gpu_depende_de_la_ram(self):
        self.assertEqual(self.etiqueta(ram=64), "gemma4:26b")
        self.assertEqual(self.etiqueta(ram=16), "gemma4:e4b")
        self.assertEqual(self.etiqueta(ram=8), "gemma4:e2b")
        self.assertEqual(self.etiqueta(ram=4), "qwen3:4b")

    def test_gpu_pequena_usa_la_ram(self):
        self.assertEqual(self.etiqueta(ram=16, vram=4), "gemma4:e4b")

    def test_no_elige_lo_que_no_cabe_en_disco(self):
        r = recomendar_modelo(equipo(ram=64, vram=24, disco=15))

        self.assertNotEqual(r["etiqueta"], "qwen3.8:27b")
        self.assertIn("disco", r["explicacion"])

    def test_alternativas_son_mas_pequenas(self):
        self.assertEqual(alternativas("qwen3:4b"), [])
        self.assertIn("qwen3:4b", alternativas("gemma4:e4b"))
        self.assertEqual(alternativas("no-existe"), [])

    def test_la_deteccion_real_no_falla(self):
        hw = hardware.detectar_hardware()

        self.assertGreaterEqual(hw.ram_gb, 0)
        self.assertTrue(recomendar_modelo(hw)["etiqueta"])


class TestDireccionOllama(unittest.TestCase):
    def url(self, **entorno):
        with mock.patch.dict(os.environ, entorno, clear=False):
            for clave in ("BRAIN_OLLAMA_URL", "OLLAMA_HOST"):
                if clave not in entorno:
                    os.environ.pop(clave, None)

            return _url_ollama()

    def test_por_defecto(self):
        self.assertEqual(self.url(), "http://127.0.0.1:11434")

    def test_respeta_ollama_host(self):
        self.assertEqual(self.url(OLLAMA_HOST="127.0.0.1:11500"), "http://127.0.0.1:11500")
        self.assertEqual(self.url(OLLAMA_HOST="0.0.0.0"), "http://127.0.0.1:11434")
        self.assertEqual(self.url(OLLAMA_HOST="https://otro:9999"), "https://otro:9999")

    def test_brain_ollama_url_manda(self):
        self.assertEqual(self.url(BRAIN_OLLAMA_URL="http://x:1", OLLAMA_HOST="y"), "http://x:1")


class TestModeloGuardadoYDescarga(CasoBrain):
    modelos = ("qwen3:4b", "gemma4:e4b")

    def test_usa_el_modelo_guardado(self):
        hardware.guardar_modelo("gemma4:e4b")

        self.assertEqual(self.brain.ai.ollama.resolver_modelo(), "gemma4:e4b")

    def test_ignora_el_guardado_si_ya_no_esta_instalado(self):
        hardware.guardar_modelo("qwen3.8:27b")

        self.assertEqual(self.brain.ai.ollama.resolver_modelo(), "gemma4:e4b")

    def test_descarga_por_la_api_del_mismo_servidor(self):
        ollama = self.brain.ai.ollama
        avances = []

        self.assertTrue(ollama.descargar_modelo("gemma4:12b", progreso=lambda *a: avances.append(a)))
        self.assertIn("gemma4:12b", ollama.modelos())
        self.assertEqual(avances[0], ("pulling", 50, 100))

    def test_descarga_fallida_lanza_error(self):
        from brain.ai.ollama import OllamaError

        self.ollama.pull_ok = False

        with self.assertRaises(OllamaError):
            self.brain.ai.ollama.descargar_modelo("no-existe:1b", progreso=lambda *a: None)

    def test_mejorar_ia_descarga_y_guarda(self):
        from brain.cli import mejorar_ia

        with mock.patch("brain.cli.detectar_hardware", return_value=equipo(ram=64, vram=12)):
            self.assertEqual(mejorar_ia(self.brain, auto=True), 0)

        self.assertEqual(hardware.leer_modelo_guardado(), "gemma4:12b")
        self.assertIn("gemma4:12b", self.ollama.descargados)

    def test_mejorar_ia_prueba_uno_mas_pequeno_si_falla(self):
        from brain.cli import mejorar_ia

        original = self.brain.ai.ollama.descargar_modelo
        intentos = []

        def descargar(nombre, progreso=None):
            intentos.append(nombre)
            return False if nombre == "gemma4:12b" else original(nombre, progreso=lambda *a: None)

        self.brain.ai.ollama.descargar_modelo = descargar

        with mock.patch("brain.cli.detectar_hardware", return_value=equipo(ram=64, vram=12)):
            self.assertEqual(mejorar_ia(self.brain, auto=True), 0)

        self.assertEqual(intentos[:2], ["gemma4:12b", "gemma4:e4b"])
