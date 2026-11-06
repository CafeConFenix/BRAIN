"""
Detects the computer's hardware and picks the best AI model for it.

Uses only the Python standard library. Works on Windows, Linux and macOS.

The rule is simple: the model has to fit in the graphics card's memory
(VRAM) if there is an NVIDIA one; otherwise the computer's RAM is used,
which is quite a bit slower, so a smaller model is picked.
"""

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from brain.core.config import Config
from brain.i18n import t
from brain.utils.processes import execute

GB = 1024**3

# Recommended models, from best to lowest quality.
#   label         : exact name for `ollama pull`
#   download_state: approximate download size in GB
#   memory        : minimum recommended memory (VRAM with an NVIDIA card, RAM without one)
#
# All of them support tools (needed to control the house).
LEVELS = (
    {"label": "qwen3.8:27b", "download_state": 18, "gpu_memory": 22, "cpu_memory": None},
    {"label": "gemma4:26b", "download_state": 17, "gpu_memory": None, "cpu_memory": 32},
    {"label": "gemma4:12b", "download_state": 8, "gpu_memory": 12, "cpu_memory": None},
    {"label": "gemma4:e4b", "download_state": 6.6, "gpu_memory": 8, "cpu_memory": 12},
    {"label": "gemma4:e2b", "download_state": 4.6, "gpu_memory": None, "cpu_memory": 8},
    {"label": "qwen3:4b", "download_state": 2.5, "gpu_memory": 0, "cpu_memory": 0},
)

# Free disk space left as a margin after the download.
DISK_MARGIN_GB = 3


@dataclass
class Hardware:
    """Summary of what the computer has."""

    ram_gb: float = 0.0
    gpu_name: str = ""
    vram_gb: float = 0.0
    free_disk_gb: float = 0.0
    system: str = ""
    notes: list = field(default_factory=list)

    @property
    def has_gpu(self):
        return self.vram_gb > 0

    def summary(self):
        gpu = f"{self.gpu_name} ({self.vram_gb:.0f} GB {t('of VRAM')})" if self.has_gpu else t("none compatible")

        return t(
            "RAM: {0} GB · NVIDIA graphics card: {1} · Free disk: {2} GB",
            f"{self.ram_gb:.0f}",
            gpu,
            f"{self.free_disk_gb:.0f}",
        )


# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------


def _ram_windows():
    class State(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("load", ctypes.c_ulong),
            ("physical_total", ctypes.c_ulonglong),
            ("physical_free", ctypes.c_ulonglong),
            ("page_total", ctypes.c_ulonglong),
            ("page_free", ctypes.c_ulonglong),
            ("virtual_total", ctypes.c_ulonglong),
            ("virtual_free", ctypes.c_ulonglong),
            ("extended_free", ctypes.c_ulonglong),
        ]

    state = State()
    state.length = ctypes.sizeof(State)

    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
        return state.physical_total / GB

    return 0.0


def _ram_linux():
    with open("/proc/meminfo", encoding="utf-8") as file:
        for line in file:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024 / GB

    return 0.0


def _ram_mac():
    output = execute(["sysctl", "-n", "hw.memsize"], capture_output=True, timeout=5)

    return int(output.stdout.decode("utf-8", errors="replace").strip()) / GB


def detect_ram():
    """Total RAM in GB (0 if it can't be determined)."""

    try:
        system = platform.system()

        if system == "Windows":
            return _ram_windows()

        if system == "Darwin":
            return _ram_mac()

        return _ram_linux()
    except Exception:
        return 0.0


def _find_nvidia_smi():
    path = shutil.which("nvidia-smi")

    if path:
        return path

    # On Windows it is usually here even when it's not on the PATH.
    for base in (os.environ.get("SystemRoot", r"C:\Windows"), os.environ.get("ProgramFiles", "")):
        for sub in ("System32", r"NVIDIA Corporation\NVSMI"):
            candidate = Path(base) / sub / "nvidia-smi.exe"

            if base and candidate.exists():
                return str(candidate)

    return None


def detect_gpu_nvidia():
    """
    Returns (name, vram_gb) of the NVIDIA card with the most memory,
    or ("", 0.0) if there is none.
    """

    path = _find_nvidia_smi()

    if not path:
        return "", 0.0

    try:
        output = execute(
            [path, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return "", 0.0

    if output.returncode != 0:
        return "", 0.0

    best = ("", 0.0)

    for line in (output.stdout or b"").decode("utf-8", errors="replace").splitlines():
        parts = [p.strip() for p in line.rsplit(",", 1)]

        if len(parts) != 2:
            continue

        try:
            vram = float(parts[1]) / 1024  # nvidia-smi gives MiB
        except ValueError:
            continue

        if vram > best[1]:
            best = (parts[0], vram)

    return best


def detect_free_disk(folder=None):
    """Free space in GB on the disk where the models are saved."""

    candidates = []

    if os.environ.get("OLLAMA_MODELS"):
        candidates.append(Path(os.environ["OLLAMA_MODELS"]))

    candidates.append(Path.home())
    candidates.append(folder or Config.PROJECT)

    for candidate in candidates:
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent

        try:
            return shutil.disk_usage(candidate).free / GB
        except OSError:
            continue

    return 0.0


def detect_hardware():
    """Measures the computer and returns a Hardware object."""

    gpu_name, vram = detect_gpu_nvidia()

    hw = Hardware(
        ram_gb=detect_ram(),
        gpu_name=gpu_name,
        vram_gb=vram,
        free_disk_gb=detect_free_disk(),
        system=platform.system(),
    )

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        # On Macs with an Apple chip, memory is shared with the GPU.
        hw.gpu_name = "Apple Silicon"
        hw.vram_gb = hw.ram_gb * 0.7

    if hw.ram_gb == 0:
        hw.notes.append(t("I could not measure the RAM; I chose a cautious model."))

    return hw


# ----------------------------------------------------------------------
# Model choice
# ----------------------------------------------------------------------


def recommend_model(hw=None):
    """
    Picks the best model that fits on the computer.

    Returns a dictionary with the label, the download size and an
    explanation, in the user's language, of why it was chosen.
    """

    hw = hw or detect_hardware()

    # A card with less than 8 GB of VRAM is not enough for the good models:
    # the computer's RAM is used instead (Ollama splits the work between both).
    if hw.vram_gb >= 8:
        key, memory = "gpu_memory", hw.vram_gb
        source = t("your graphics card ({0} GB of VRAM)", f"{hw.vram_gb:.0f}")
    else:
        key, memory = "cpu_memory", hw.ram_gb
        source = t("your RAM ({0} GB, no NVIDIA card)", f"{hw.ram_gb:.0f}")

    chosen = None
    disk_reason = False

    for level in LEVELS:
        minimum = level[key]

        if minimum is None or memory < minimum:
            continue

        # The model also has to fit on disk.
        if hw.free_disk_gb and level["download_state"] + DISK_MARGIN_GB > hw.free_disk_gb:
            disk_reason = True
            continue

        chosen = level
        break

    if chosen is None:
        chosen = LEVELS[-1]

    explanation = t("Chosen based on {0}.", source)

    if disk_reason:
        explanation += " " + t("There are better models, but they don't fit in the free disk space.")

    return {
        "label": chosen["label"],
        "download_gb": chosen["download_state"],
        "explanation": explanation,
        "hardware": hw,
    }


def alternatives(label):
    """Models smaller than the given one, in case the download fails."""

    labels = [n["label"] for n in LEVELS]

    if label not in labels:
        return []

    return labels[labels.index(label) + 1 :]


# ----------------------------------------------------------------------
# Chosen model (remembered between sessions)
# ----------------------------------------------------------------------


def _model_file():
    return Config.DATA / "ai" / "model.txt"


def read_saved_model():
    """The model BRAIN chose last time (or '' if there isn't one)."""

    try:
        return _model_file().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def save_model(label):
    """Remembers which model BRAIN should use."""

    file = _model_file()
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(label + "\n", encoding="utf-8")
