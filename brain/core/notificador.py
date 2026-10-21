"""
Entrega de avisos fuera de la interfaz web: notificación de Windows y sonido.

Solo biblioteca estándar. En Windows usa PowerShell (notificación "toast") y
winsound (sonidos .wav); los .mp3/.ogg se reproducen con el reproductor de
Windows vía PowerShell. Cualquier fallo se ignora: un aviso que no puede
mostrarse nunca debe romper nada.
"""

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

ES_WINDOWS = os.name == "nt"

# Identificador de aplicación de PowerShell: Windows solo muestra "toasts" de
# aplicaciones registradas y esta siempre lo está.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

SCRIPT_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$t = [System.Security.SecurityElement]::Escape($env:BRAIN_TITULO)
$m = [System.Security.SecurityElement]::Escape($env:BRAIN_MENSAJE)
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$m</text></binding></visual><audio silent='true'/></toast>")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:BRAIN_APPID).Show($toast)
"""

SCRIPT_SONIDO = r"""
Add-Type -AssemblyName presentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([uri]$env:BRAIN_SONIDO)
$p.Play()
Start-Sleep -Seconds 12
"""


def _powershell(script: str, entorno: dict) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        env={**os.environ, **entorno},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
    )


def reproducir_sonido(ruta: Optional[Path]) -> None:
    """Reproduce un sonido (o el pitido del sistema si no hay archivo)."""

    if not ES_WINDOWS:
        return

    try:
        import winsound

        if ruta and Path(ruta).exists():
            if Path(ruta).suffix.lower() == ".wav":
                winsound.PlaySound(str(ruta), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                _powershell(SCRIPT_SONIDO, {"BRAIN_SONIDO": str(ruta)})
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


def mostrar_notificacion(titulo: str, mensaje: str) -> None:
    try:
        if ES_WINDOWS:
            _powershell(SCRIPT_TOAST, {"BRAIN_TITULO": titulo, "BRAIN_MENSAJE": mensaje, "BRAIN_APPID": APP_ID})
        elif sys.platform.startswith("linux") and shutil.which("notify-send"):
            subprocess.Popen(["notify-send", titulo, mensaje], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notificar(titulo: str, mensaje: str = "", sonido: Optional[Path] = None, con_sonido: bool = True) -> None:
    """Muestra la notificación y toca el sonido sin bloquear a quien llama."""

    def tarea():
        mostrar_notificacion(titulo, mensaje)

        if con_sonido:
            reproducir_sonido(sonido)

    threading.Thread(target=tarea, name="brain-notificacion", daemon=True).start()
