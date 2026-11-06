import io
import unittest
import wave

try:
    import numpy
except ImportError:  # pragma: no cover
    numpy = None

from brain.voice.recognition import resample, wav_to_audio


def _level(signal):
    return float(numpy.sqrt(numpy.mean(signal[1000:-1000] ** 2)) / 0.3536)


@unittest.skipIf(numpy is None, "numpy no está instalado")
class TestResampling(unittest.TestCase):
    def tone(self, frequency, origin=48000, seconds=2):
        t = numpy.arange(origin * seconds) / origin

        return (0.5 * numpy.sin(2 * numpy.pi * frequency * t)).astype(numpy.float32)

    def test_the_voice_self_conserva(self):
        for f in (300, 1000, 3000):
            self.assertGreater(_level(resample(self.tone(f), 48000)), 0.98, f)

    def test_las_frecuencias_high_no_self_pliegan(self):
        # Con interpolación lineal un tono de 15 kHz reaparecía a ~1 kHz con el 70 % de su fuerza.
        for f in (11000, 15000, 20000):
            self.assertLess(_level(resample(self.tone(f), 48000)), 0.02, f)

    def test_44100_hz(self):
        self.assertGreater(_level(resample(self.tone(1000, 44100), 44100)), 0.98)
        self.assertLess(_level(resample(self.tone(14000, 44100), 44100)), 0.02)

    def test_length(self):
        self.assertEqual(len(resample(self.tone(500), 48000)), 32000)

    def test_same_frequency_y_empty(self):
        x = self.tone(500, 16000)
        self.assertIs(resample(x, 16000), x)
        self.assertEqual(len(resample(numpy.zeros(0, dtype=numpy.float32), 48000)), 0)

    def test_upload_frequency(self):
        self.assertEqual(len(resample(self.tone(500, 8000), 8000)), 32000)

    def test_wav_to_audio_uses_the_filter(self):
        pcm = (self.tone(15000) * 32767).astype("<i2").tobytes()
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(48000)
            w.writeframes(pcm)

        self.assertLess(_level(wav_to_audio(buffer.getvalue())), 0.02)


if __name__ == "__main__":
    unittest.main()
