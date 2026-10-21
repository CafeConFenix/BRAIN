import io
import unittest
import wave

try:
    import numpy
except ImportError:  # pragma: no cover
    numpy = None

from brain.voice.reconocimiento import remuestrear, wav_a_audio


def _nivel(señal):
    return float(numpy.sqrt(numpy.mean(señal[1000:-1000] ** 2)) / 0.3536)


@unittest.skipIf(numpy is None, "numpy no está instalado")
class TestRemuestreo(unittest.TestCase):
    def tono(self, frecuencia, origen=48000, segundos=2):
        t = numpy.arange(origen * segundos) / origen

        return (0.5 * numpy.sin(2 * numpy.pi * frecuencia * t)).astype(numpy.float32)

    def test_la_voz_se_conserva(self):
        for f in (300, 1000, 3000):
            self.assertGreater(_nivel(remuestrear(self.tono(f), 48000)), 0.98, f)

    def test_las_frecuencias_altas_no_se_pliegan(self):
        # Con interpolación lineal un tono de 15 kHz reaparecía a ~1 kHz con el 70 % de su fuerza.
        for f in (11000, 15000, 20000):
            self.assertLess(_nivel(remuestrear(self.tono(f), 48000)), 0.02, f)

    def test_44100_hz(self):
        self.assertGreater(_nivel(remuestrear(self.tono(1000, 44100), 44100)), 0.98)
        self.assertLess(_nivel(remuestrear(self.tono(14000, 44100), 44100)), 0.02)

    def test_longitud(self):
        self.assertEqual(len(remuestrear(self.tono(500), 48000)), 32000)

    def test_misma_frecuencia_y_vacio(self):
        x = self.tono(500, 16000)
        self.assertIs(remuestrear(x, 16000), x)
        self.assertEqual(len(remuestrear(numpy.zeros(0, dtype=numpy.float32), 48000)), 0)

    def test_subir_frecuencia(self):
        self.assertEqual(len(remuestrear(self.tono(500, 8000), 8000)), 32000)

    def test_wav_a_audio_usa_el_filtro(self):
        pcm = (self.tono(15000) * 32767).astype("<i2").tobytes()
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(pcm)

        self.assertLess(_nivel(wav_a_audio(buffer.getvalue())), 0.02)


if __name__ == "__main__":
    unittest.main()
