"""
Reconocimiento de voz local para BRAIN (el micrófono de la interfaz web).

Chrome y Edge traen su propio reconocimiento de voz, pero Brave lo desactiva
(depende de servidores de Google). Para que el micrófono funcione en
cualquier navegador, la web graba el audio y BRAIN lo transcribe aquí, en el
propio ordenador, con Whisper (paquete `faster-whisper`). El audio nunca sale
del equipo.

El paquete y el modelo (unos 150-500 MB) se instalan una sola vez, cuando el
usuario pulsa «Instalar voz» en la web.
"""

import importlib
import importlib.util
import io
import subprocess
import sys
import threading
import wave

from brain.core import logger
from brain.core.config import Config

MAX_SEGUNDOS = 60

# Whisper "alucina" frases típicas cuando oye silencio o ruido: se descartan.
FRASES_FANTASMA = (
    "subtítulos",
    "subtitulos",
    "amara.org",
    "gracias por ver",
    "suscríbete",
    "suscribete",
    "música",
)


class VozError(RuntimeError):
    """Error del reconocimiento de voz (el mensaje está pensado para el usuario)."""


def modelo_recomendado():
    """Tamaño del modelo Whisper según la memoria del equipo."""

    import os

    if os.environ.get("BRAIN_VOZ_MODELO"):
        return os.environ["BRAIN_VOZ_MODELO"].strip()

    from brain.core.hardware import detectar_ram

    return "small" if detectar_ram() >= 8 else "base"


def _paquete_instalado():
    return importlib.util.find_spec("faster_whisper") is not None


def wav_a_audio(contenido):
    """
    Convierte un WAV (16 bits, mono o estéreo) en un array float32 a 16 kHz.

    Lanza VozError si el audio no es válido o es demasiado largo.
    """

    import numpy

    try:
        with wave.open(io.BytesIO(contenido), "rb") as archivo:
            canales = archivo.getnchannels()
            ancho = archivo.getsampwidth()
            frecuencia = archivo.getframerate()
            tramas = archivo.getnframes()

            if ancho != 2:
                raise VozError("El audio debe ser de 16 bits.")

            if frecuencia <= 0 or tramas / frecuencia > MAX_SEGUNDOS:
                raise VozError(f"El audio es demasiado largo (máximo {MAX_SEGUNDOS} segundos).")

            datos = archivo.readframes(tramas)
    except (wave.Error, EOFError) as error:
        raise VozError(f"No he entendido el audio recibido ({error}).") from error

    audio = numpy.frombuffer(datos, dtype=numpy.int16).astype(numpy.float32) / 32768.0

    if canales > 1:
        audio = audio[: len(audio) // canales * canales].reshape(-1, canales).mean(axis=1)

    if frecuencia != 16000 and len(audio):
        destino = int(len(audio) * 16000 / frecuencia)
        audio = numpy.interp(numpy.linspace(0, len(audio) - 1, destino), numpy.arange(len(audio)), audio).astype(
            numpy.float32
        )

    return audio


class Reconocedor:
    """Transcribe audio a texto en español con Whisper, sin conexión a internet (tras instalarlo)."""

    def __init__(self):
        self._modelo = None
        self._cerrojo = threading.Lock()
        self._instalacion = {"activa": False, "paso": "", "error": ""}

    # ------------------------------------------------------------------
    # Estado e instalación
    # ------------------------------------------------------------------

    def disponible(self):
        return self._modelo is not None or (_paquete_instalado() and self._modelo_descargado())

    def _modelo_descargado(self):
        return (Config.DATOS / "voz" / "listo.txt").exists()

    def estado(self):
        return {
            "disponible": self.disponible(),
            "instalando": self._instalacion["activa"],
            "paso": self._instalacion["paso"],
            "error": self._instalacion["error"],
            "modelo": modelo_recomendado(),
        }

    def instalar(self):
        """Instala el paquete y descarga el modelo en segundo plano. True si empieza (o ya está en marcha)."""

        with self._cerrojo:
            if self._instalacion["activa"]:
                return True

            if self.disponible():
                return False

            self._instalacion.update({"activa": True, "paso": "Empezando...", "error": ""})

        threading.Thread(target=self._instalar, daemon=True).start()

        return True

    def _instalar(self):
        try:
            if not _paquete_instalado():
                self._instalacion["paso"] = "Instalando el reconocimiento de voz (1-2 minutos)..."

                resultado = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "faster-whisper"],
                    capture_output=True,
                )

                if resultado.returncode != 0:
                    cola = (resultado.stderr or resultado.stdout or b"").decode("utf-8", errors="replace")[-400:]
                    raise VozError(f"No he podido instalar faster-whisper. Comprueba tu conexión. Detalle: {cola}")

                importlib.invalidate_caches()

            nombre = modelo_recomendado()

            self._instalacion["paso"] = f"Descargando el modelo de voz «{nombre}» (solo la primera vez, puede tardar)..."

            self._cargar_modelo(nombre)

            carpeta = Config.DATOS / "voz"
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / "listo.txt").write_text(nombre + "\n", encoding="utf-8")

            self._instalacion["paso"] = "Listo"

            logger.sistema(f"Reconocimiento de voz instalado (modelo {nombre})")

        except Exception as error:
            logger.error(f"Instalación de voz: {error!r}")

            self._instalacion["error"] = str(error)
        finally:
            self._instalacion["activa"] = False

    def _cargar_modelo(self, nombre=None):
        """Carga (y descarga si hace falta) el modelo Whisper."""

        import os

        # En Windows sin "modo desarrollador" la descarga avisa de que no puede
        # usar enlaces simbólicos (y copia los archivos); el aviso solo asusta.
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

        try:
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise VozError("Falta el paquete faster-whisper. Pulsa «Instalar voz».") from error

        carpeta = Config.DATOS / "voz"
        carpeta.mkdir(parents=True, exist_ok=True)

        self._modelo = WhisperModel(
            nombre or modelo_recomendado(), device="cpu", compute_type="int8", download_root=str(carpeta)
        )

        return self._modelo

    # ------------------------------------------------------------------
    # Transcripción
    # ------------------------------------------------------------------

    def transcribir(self, contenido_wav):
        """Devuelve el texto dicho en un audio WAV ('' si no se oye nada)."""

        if not self.disponible():
            raise VozError("El reconocimiento de voz no está instalado. Pulsa «Instalar voz».")

        audio = wav_a_audio(contenido_wav)

        # Menos de 0,3 s o casi silencio: no hay nada que transcribir.
        if len(audio) < 4800 or float(abs(audio).max()) < 0.01:
            return ""

        with self._cerrojo:
            if self._modelo is None:
                self._cargar_modelo()

            segmentos, _ = self._modelo.transcribe(
                audio, language="es", beam_size=1, vad_filter=True, condition_on_previous_text=False
            )

            texto = " ".join(s.text.strip() for s in segmentos).strip()

        if any(f in texto.lower() for f in FRASES_FANTASMA) and len(texto) < 60:
            return ""

        return texto
