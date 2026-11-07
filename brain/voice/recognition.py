"""
Local speech recognition for BRAIN (the web interface's microphone).

Chrome and Edge ship their own speech recognition, but Brave disables it
(it depends on Google's servers). For the microphone to work in any
browser, the web page records the audio and BRAIN transcribes it here, on
the computer itself, with Whisper (the `faster-whisper` package). The audio
never leaves the machine.

The package and the model (about 150-500 MB) are installed only once, when
the user clicks "Install voice" on the web page.
"""

import importlib
import importlib.util
import io
import sys
import threading
import wave

from brain.core import logger
from brain.core.config import Config, env
from brain.i18n import language, t
from brain.utils.processes import execute

MAX_SECONDS = 60

# Whisper "hallucinates" typical phrases when it hears silence or noise: these are discarded.
GHOST_PHRASES = (
    "subtítulos",
    "subtitulos",
    "amara.org",
    "gracias por ver",
    "suscríbete",
    "suscribete",
    "música",
    "subtitles",
    "thanks for watching",
    "subscribe",
    "music",
)


class VoiceError(RuntimeError):
    """Speech-recognition error (the message is meant for the user)."""


def recommended_model():
    """Whisper model size based on the computer's memory."""

    import os

    if env("BRAIN_VOICE_MODEL"):
        return env("BRAIN_VOICE_MODEL").strip()

    from brain.core.hardware import detect_ram

    return "small" if detect_ram() >= 8 else "base"


def _package_installed():
    return importlib.util.find_spec("faster_whisper") is not None


def resample(audio, origin, destination=16000):
    """
    Changes the sample rate of an audio (float32 array).

    When lowering the rate (48 kHz -> 16 kHz), everything that would end up
    above half the final rate is filtered out first (a sinc low-pass filter
    with a Blackman window). Without that filter, the high frequencies "fold"
    back down and mix with the voice (aliasing), which is what happens with
    plain linear interpolation.
    """

    import numpy

    if origin == destination or not len(audio):
        return audio

    audio = numpy.asarray(audio, dtype=numpy.float32)

    if origin > destination:
        reason = origin / destination
        cut = 0.42 / reason  # cycles per sample; leaves margin under half of `destination`
        half = int(48 * reason)
        n = numpy.arange(-half, half + 1)
        filter_by = 2 * cut * numpy.sinc(2 * cut * n) * numpy.blackman(2 * half + 1)
        filter_by /= filter_by.sum()
        audio = numpy.convolve(audio, filter_by, mode="same").astype(numpy.float32)

    output = int(len(audio) * destination / origin)
    positions = numpy.arange(output) * (origin / destination)

    return numpy.interp(positions, numpy.arange(len(audio)), audio).astype(numpy.float32)


def wav_to_audio(content):
    """
    Converts a WAV (16-bit, mono or stereo) into a float32 array at 16 kHz.

    Raises VoiceError if the audio is not valid or is too long.
    """


    try:
        with wave.open(io.BytesIO(content), "rb") as file:
            channels = file.getnchannels()
            width = file.getsampwidth()
            frequency = file.getframerate()
            frames = file.getnframes()

            if width != 2:
                raise VoiceError(t("The audio must be 16-bit."))

            if frequency <= 0 or frames / frequency > MAX_SECONDS:
                raise VoiceError(t("The audio is too long (maximum {0} seconds).", MAX_SECONDS))

            data = file.readframes(frames)
    except (wave.Error, EOFError) as error:
        raise VoiceError(t("I did not understand the audio received ({0}).", error)) from error
    # numpy is only needed from here on, once we know the WAV itself is valid.
    try:
        import numpy
    except ImportError as error:
        raise VoiceError(t("Voice support is not installed (numpy is missing).")) from error

    audio = numpy.frombuffer(data, dtype=numpy.int16).astype(numpy.float32) / 32768.0

    if channels > 1:
        audio = audio[: len(audio) // channels * channels].reshape(-1, channels).mean(axis=1)

    if frequency != 16000 and len(audio):
        audio = resample(audio, frequency, 16000)

    return audio


class Recognizer:
    """Transcribes audio to text, in the interface's language, with Whisper, offline (once installed)."""

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()
        self._installation_step = {"active": False, "step": "", "error": ""}

    # ------------------------------------------------------------------
    # Status and installation
    # ------------------------------------------------------------------

    def available(self):
        return self._model is not None or (_package_installed() and self._model_downloaded())

    def _model_downloaded(self):
        return (Config.DATA / "voice" / "ready.txt").exists()

    def state(self):
        return {
            "available": self.available(),
            "installing": self._installation_step["active"],
            "step": self._installation_step["step"],
            "error": self._installation_step["error"],
            "model": recommended_model(),
        }

    def install(self):
        """Installs the package and downloads the model in the background. True if it starts (or is already running)."""

        with self._lock:
            if self._installation_step["active"]:
                return True

            if self.available():
                return False

            self._installation_step.update({"active": True, "step": t("Starting..."), "error": ""})

        threading.Thread(target=self._install, daemon=True).start()

        return True

    def _install(self):
        try:
            if not _package_installed():
                self._installation_step["step"] = t("Installing speech recognition (1-2 minutes)...")

                result = execute(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "faster-whisper"],
                    capture_output=True,
                )

                if result.returncode != 0:
                    tail = (result.stderr or result.stdout or b"").decode("utf-8", errors="replace")[-400:]
                    raise VoiceError(t("I could not install faster-whisper. Check your connection. Detail: {0}", tail))

                importlib.invalidate_caches()

            name = recommended_model()

            self._installation_step["step"] = t(
                "Downloading the voice model '{0}' (only the first time, it may take a while)...", name
            )

            self._load_model(name)

            folder = Config.DATA / "voice"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "ready.txt").write_text(name + "\n", encoding="utf-8")

            self._installation_step["step"] = t("Done")

            logger.system(f"Speech recognition installed (model {name})")

        except Exception as error:
            logger.error(f"Voice installation: {error!r}")

            self._installation_step["error"] = str(error)
        finally:
            self._installation_step["active"] = False

    def _load_model(self, name=None):
        """Loads (and downloads if needed) the Whisper model."""

        import os

        # On Windows without "developer mode" the download warns that it cannot
        # use symlinks (and copies the files instead); the warning is harmless.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise VoiceError(t("The faster-whisper package is missing. Click \"Install voice\".")) from error

        folder = Config.DATA / "voice"
        folder.mkdir(parents=True, exist_ok=True)

        self._model = WhisperModel(
            name or recommended_model(), device="cpu", compute_type="int8", download_root=str(folder)
        )

        return self._model

    # ------------------------------------------------------------------
    # Transcription
    # ------------------------------------------------------------------

    def transcribe(self, wav_content):
        """Returns the text spoken in a WAV audio ('' if nothing is heard)."""

        if not self.available():
            raise VoiceError(t("Speech recognition is not installed. Click \"Install voice\"."))

        audio = wav_to_audio(wav_content)

        # Less than 0.3 s or near silence: there is nothing to transcribe.
        if len(audio) < 4800 or float(abs(audio).max()) < 0.01:
            return ""

        with self._lock:
            if self._model is None:
                self._load_model()

            segments, _ = self._model.transcribe(
                audio, language=language(), beam_size=1, vad_filter=True, condition_on_previous_text=False
            )

            text = " ".join(s.text.strip() for s in segments).strip()

        if any(f in text.lower() for f in GHOST_PHRASES) and len(text) < 60:
            return ""

        return text
