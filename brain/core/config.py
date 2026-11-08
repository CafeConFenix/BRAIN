import os
from pathlib import Path

from brain.core import migrate


LEGACY_ENV = {
    "BRAIN_DATA": "BRAIN_DATOS",
    "BRAIN_MODEL": "BRAIN_MODELO",
    "BRAIN_THINK": "BRAIN_PENSAR",
    "BRAIN_CONTEXT": "BRAIN_CONTEXTO",
    "BRAIN_PORT": "BRAIN_PUERTO",
    "BRAIN_POLL_SECONDS": "BRAIN_SONDEO_SEGUNDOS",
    "BRAIN_SCHEDULER": "BRAIN_PLANIFICADOR",
    "BRAIN_VOICE_MODEL": "BRAIN_VOZ_MODELO",
}


def env(name, default=None):
    """Read an environment variable; the old Spanish name still works (deprecated)."""

    value = os.environ.get(name)

    if value is None and name in LEGACY_ENV:
        value = os.environ.get(LEGACY_ENV[name])

    return default if value is None else value


def _env_bool(name, default=False):
    """Read an environment variable as true/false."""

    value = env(name)

    if value is None:
        return default

    return value.strip().lower().replace(chr(0xED), "i") in {"1", "true", "si", "yes", "on"}


def _env_int(name, default):
    """Read an environment variable as an integer."""

    try:
        return int(env(name, default))
    except (TypeError, ValueError):
        return default


def _url_ollama():
    """
    Ollama's address.

    Respects BRAIN_OLLAMA_URL and, if it doesn't exist, the standard
    OLLAMA_HOST variable (so BRAIN talks to the same Ollama as the
    console's `ollama` command).
    """

    explicit = os.environ.get("BRAIN_OLLAMA_URL", "").strip()

    if explicit:
        return explicit

    host = os.environ.get("OLLAMA_HOST", "").strip()

    if not host:
        return "http://127.0.0.1:11434"

    schema = "http"

    if "://" in host:
        schema, host = host.split("://", 1)

    host = host.rstrip("/")

    name, _, port = host.partition(":")

    if name in ("", "0.0.0.0", "::", "[::]"):
        name = "127.0.0.1"

    return f"{schema}://{name}:{port or '11434'}"


class Config:
    """
    BRAIN's global configuration.

    Optional environment variables:

    - BRAIN_DATA:       folder where data is saved.
    - BRAIN_OLLAMA_URL:  Ollama's address (default 127.0.0.1:11434).
    - BRAIN_MODEL:      model to use (default, the best one installed).
    - BRAIN_THINK:      1 to turn on Qwen3's "think mode" (slower).
    - BRAIN_CONTEXT:    the AI's memory size in tokens (default 16384).
    - BRAIN_PORT:      web interface port (default 8765).
    - BRAIN_HOST:      address the web server listens on (default 127.0.0.1,
                        local-only; a Docker container sets this to 0.0.0.0
                        so the port mapping can reach it).
    - BRAIN_POLL_SECONDS: how often, in seconds, it checks Home Assistant in the background (default 120).
    - BRAIN_SCHEDULER: 0 to turn off the background tasks.
    """

    # Folder of the "brain" package
    ROOT = Path(__file__).resolve().parent.parent

    # Project folder (where main.py lives)
    PROJECT = ROOT.parent

    # All the data lives in <project>/data, next to the personality
    # and the logs. (There used to be a second, duplicated brain/data folder.)
    if env("BRAIN_DATA"):
        DATA = Path(env("BRAIN_DATA"))
    else:
        DATA = PROJECT / "data"
        migrate.move_old_folder(PROJECT, DATA)

    LOGS = DATA / "logs"

    PERSONALITY = PROJECT / "data" / "knowledge" / "personality.md"

    # The personality BRAIN ships with. If the one above (the user's own)
    # exists, that one wins.
    BASE_PERSONALITY = ROOT / "core" / "personality_base.md"

    # 127.0.0.1 instead of "localhost": on Windows "localhost" usually
    # resolves to IPv6 (::1) first, and Ollama listens on IPv4.
    OLLAMA_URL = _url_ollama()

    # Empty = choose automatically among the installed models.
    MODEL = env("BRAIN_MODEL", "").strip()

    THINK = _env_bool("BRAIN_THINK", False)

    # The AI's working memory (tokens). Ollama defaults to 4096. BRAIN's own
    # tool descriptions alone take up about 5,000 tokens, so at 8192 the
    # model used to lose its instructions and answer with nothing.
    CONTEXT = _env_int("BRAIN_CONTEXT", 16384)

    WEB_PORT = _env_int("BRAIN_PORT", 8765)

    # Local-only by default: only this same machine can reach it directly
    # (remote access still goes through the password-gated Tailscale check).
    WEB_HOST = env("BRAIN_HOST", "127.0.0.1").strip() or "127.0.0.1"

    POLL_SECONDS = max(10, _env_int("BRAIN_POLL_SECONDS", 120))

    SCHEDULER = _env_bool("BRAIN_SCHEDULER", True)

    # Model downloaded by the installer / the first-run assistant.
    DEFAULT_MODEL = "qwen3:4b"

    VERSION = "2.1.0"

    NAME = "BRAIN"
