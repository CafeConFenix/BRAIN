"""
Detección del hardware del equipo y elección del mejor modelo de IA.

Solo usa la biblioteca estándar de Python. Funciona en Windows, Linux y macOS.

La regla es sencilla: el modelo tiene que caber en la memoria de la tarjeta
gráfica (VRAM) si hay una NVIDIA; si no, se usa la RAM del ordenador, que es
bastante más lenta, así que se elige un modelo más pequeño.
"""

import ctypes
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from brain.core.config import Config

GB = 1024**3

# Modelos recomendados, de mayor a menor calidad.
#   etiqueta  : nombre exacto para `ollama pull`
#   descarga  : tamaño aproximado de la descarga en GB
#   memoria   : memoria mínima recomendada (VRAM con tarjeta NVIDIA, RAM sin ella)
#
# Todos admiten herramientas (necesarias para controlar la casa) y hablan español.
NIVELES = (
    {"etiqueta": "qwen3.8:27b", "descarga": 18, "memoria_gpu": 22, "memoria_cpu": None},
    {"etiqueta": "gemma4:26b", "descarga": 17, "memoria_gpu": None, "memoria_cpu": 32},
    {"etiqueta": "gemma4:12b", "descarga": 8, "memoria_gpu": 12, "memoria_cpu": None},
    {"etiqueta": "gemma4:e4b", "descarga": 6.6, "memoria_gpu": 8, "memoria_cpu": 12},
    {"etiqueta": "gemma4:e2b", "descarga": 4.6, "memoria_gpu": None, "memoria_cpu": 8},
    {"etiqueta": "qwen3:4b", "descarga": 2.5, "memoria_gpu": 0, "memoria_cpu": 0},
)

# Espacio libre que se deja de margen en el disco tras la descarga.
MARGEN_DISCO_GB = 3


@dataclass
class Hardware:
    """Resumen de lo que tiene el equipo."""

    ram_gb: float = 0.0
    gpu_nombre: str = ""
    vram_gb: float = 0.0
    disco_libre_gb: float = 0.0
    sistema: str = ""
    notas: list = field(default_factory=list)

    @property
    def tiene_gpu(self):
        return self.vram_gb > 0

    def resumen(self):
        gpu = f"{self.gpu_nombre} ({self.vram_gb:.0f} GB de VRAM)" if self.tiene_gpu else "ninguna compatible"

        return (
            f"RAM: {self.ram_gb:.0f} GB · Tarjeta gráfica NVIDIA: {gpu} · "
            f"Disco libre: {self.disco_libre_gb:.0f} GB"
        )


# ----------------------------------------------------------------------
# Detección
# ----------------------------------------------------------------------


def _ram_windows():
    class Estado(ctypes.Structure):
        _fields_ = [
            ("longitud", ctypes.c_ulong),
            ("carga", ctypes.c_ulong),
            ("total_fisica", ctypes.c_ulonglong),
            ("libre_fisica", ctypes.c_ulonglong),
            ("total_pagina", ctypes.c_ulonglong),
            ("libre_pagina", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("libre_virtual", ctypes.c_ulonglong),
            ("libre_extendida", ctypes.c_ulonglong),
        ]

    estado = Estado()
    estado.longitud = ctypes.sizeof(Estado)

    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
        return estado.total_fisica / GB

    return 0.0


def _ram_linux():
    with open("/proc/meminfo", encoding="utf-8") as archivo:
        for linea in archivo:
            if linea.startswith("MemTotal:"):
                return int(linea.split()[1]) * 1024 / GB

    return 0.0


def _ram_mac():
    salida = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, timeout=5)

    return int(salida.stdout.decode("utf-8", errors="replace").strip()) / GB


def detectar_ram():
    """Memoria RAM total en GB (0 si no se puede saber)."""

    try:
        sistema = platform.system()

        if sistema == "Windows":
            return _ram_windows()

        if sistema == "Darwin":
            return _ram_mac()

        return _ram_linux()
    except Exception:
        return 0.0


def _buscar_nvidia_smi():
    ruta = shutil.which("nvidia-smi")

    if ruta:
        return ruta

    # En Windows suele estar aquí aunque no esté en el PATH.
    for base in (os.environ.get("SystemRoot", r"C:\Windows"), os.environ.get("ProgramFiles", "")):
        for sub in ("System32", r"NVIDIA Corporation\NVSMI"):
            candidato = Path(base) / sub / "nvidia-smi.exe"

            if base and candidato.exists():
                return str(candidato)

    return None


def detectar_gpu_nvidia():
    """
    Devuelve (nombre, vram_gb) de la tarjeta NVIDIA con más memoria,
    o ("", 0.0) si no hay ninguna.
    """

    ruta = _buscar_nvidia_smi()

    if not ruta:
        return "", 0.0

    try:
        salida = subprocess.run(
            [ruta, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return "", 0.0

    if salida.returncode != 0:
        return "", 0.0

    mejor = ("", 0.0)

    for linea in (salida.stdout or b"").decode("utf-8", errors="replace").splitlines():
        partes = [p.strip() for p in linea.rsplit(",", 1)]

        if len(partes) != 2:
            continue

        try:
            vram = float(partes[1]) / 1024  # nvidia-smi da MiB
        except ValueError:
            continue

        if vram > mejor[1]:
            mejor = (partes[0], vram)

    return mejor


def detectar_disco_libre(carpeta=None):
    """Espacio libre en GB en el disco donde se guardan los modelos."""

    candidatas = []

    if os.environ.get("OLLAMA_MODELS"):
        candidatas.append(Path(os.environ["OLLAMA_MODELS"]))

    candidatas.append(Path.home())
    candidatas.append(carpeta or Config.PROYECTO)

    for candidata in candidatas:
        while not candidata.exists() and candidata != candidata.parent:
            candidata = candidata.parent

        try:
            return shutil.disk_usage(candidata).free / GB
        except OSError:
            continue

    return 0.0


def detectar_hardware():
    """Mide el equipo y devuelve un objeto Hardware."""

    gpu_nombre, vram = detectar_gpu_nvidia()

    hw = Hardware(
        ram_gb=detectar_ram(),
        gpu_nombre=gpu_nombre,
        vram_gb=vram,
        disco_libre_gb=detectar_disco_libre(),
        sistema=platform.system(),
    )

    if platform.system() == "Darwin" and platform.machine() == "arm64":
        # En los Mac con chip Apple la memoria es compartida con la GPU.
        hw.gpu_nombre = "Apple Silicon"
        hw.vram_gb = hw.ram_gb * 0.7

    if hw.ram_gb == 0:
        hw.notas.append("No he podido medir la memoria RAM; he elegido un modelo prudente.")

    return hw


# ----------------------------------------------------------------------
# Elección del modelo
# ----------------------------------------------------------------------


def recomendar_modelo(hw=None):
    """
    Elige el mejor modelo que cabe en el equipo.

    Devuelve un diccionario con la etiqueta, el tamaño de descarga y una
    explicación en español de por qué se ha elegido.
    """

    hw = hw or detectar_hardware()

    # Una tarjeta con menos de 8 GB de VRAM no sirve para los modelos buenos:
    # se usa la RAM del ordenador (Ollama reparte el trabajo entre ambas).
    if hw.vram_gb >= 8:
        clave, memoria = "memoria_gpu", hw.vram_gb
        origen = f"tu tarjeta gráfica ({hw.vram_gb:.0f} GB de VRAM)"
    else:
        clave, memoria = "memoria_cpu", hw.ram_gb
        origen = f"tu memoria RAM ({hw.ram_gb:.0f} GB, sin tarjeta NVIDIA)"

    elegido = None
    motivo_disco = False

    for nivel in NIVELES:
        minimo = nivel[clave]

        if minimo is None or memoria < minimo:
            continue

        # El modelo tiene que caber también en el disco.
        if hw.disco_libre_gb and nivel["descarga"] + MARGEN_DISCO_GB > hw.disco_libre_gb:
            motivo_disco = True
            continue

        elegido = nivel
        break

    if elegido is None:
        elegido = NIVELES[-1]

    explicacion = f"Elegido según {origen}."

    if motivo_disco:
        explicacion += " Hay modelos mejores, pero no caben en el espacio libre del disco."

    return {
        "etiqueta": elegido["etiqueta"],
        "descarga_gb": elegido["descarga"],
        "explicacion": explicacion,
        "hardware": hw,
    }


def alternativas(etiqueta):
    """Modelos más pequeños que el indicado, por si falla la descarga."""

    etiquetas = [n["etiqueta"] for n in NIVELES]

    if etiqueta not in etiquetas:
        return []

    return etiquetas[etiquetas.index(etiqueta) + 1 :]


# ----------------------------------------------------------------------
# Modelo elegido (se recuerda entre sesiones)
# ----------------------------------------------------------------------


def _archivo_modelo():
    return Config.DATOS / "ia" / "modelo.txt"


def leer_modelo_guardado():
    """Modelo que BRAIN eligió la última vez (o '' si no hay)."""

    try:
        return _archivo_modelo().read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def guardar_modelo(etiqueta):
    """Recuerda qué modelo debe usar BRAIN."""

    archivo = _archivo_modelo()
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(etiqueta + "\n", encoding="utf-8")
