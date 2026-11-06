"""
Delivers notices outside the web interface: Windows notification and sound.

Standard library only. On Windows it uses PowerShell (a "toast" notification)
and winsound (.wav sounds); .mp3/.ogg files are played with Windows' player
via PowerShell. Any failure is ignored: a notice that cannot be shown must
never break anything.
"""

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

IS_WINDOWS = os.name == "nt"

# PowerShell application ID: Windows only shows "toasts" from registered
# applications, and this one always is.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

SCRIPT_TOAST = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$t = [System.Security.SecurityElement]::Escape($env:BRAIN_TITLE)
$m = [System.Security.SecurityElement]::Escape($env:BRAIN_MESSAGE)
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$m</text></binding></visual><audio silent='true'/></toast>")
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:BRAIN_APPID).Show($toast)
"""

SOUND_SCRIPT = r"""
Add-Type -AssemblyName presentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Open([uri]$env:BRAIN_SOUND)
$p.Play()
Start-Sleep -Seconds 12
"""


def _powershell(script: str, env: dict) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    subprocess.Popen(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        env={**os.environ, **env},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
    )


def play_sound(path: Optional[Path]) -> None:
    """Plays a sound (or the system beep if there is no file)."""

    if not IS_WINDOWS:
        return

    try:
        import winsound

        if path and Path(path).exists():
            if Path(path).suffix.lower() == ".wav":
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                _powershell(SOUND_SCRIPT, {"BRAIN_SOUND": str(path)})
        else:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


def show_notification(title: str, message: str) -> None:
    try:
        if IS_WINDOWS:
            _powershell(SCRIPT_TOAST, {"BRAIN_TITLE": title, "BRAIN_MESSAGE": message, "BRAIN_APPID": APP_ID})
        elif sys.platform.startswith("linux") and shutil.which("notify-send"):
            subprocess.Popen(["notify-send", title, message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def notify(title: str, message: str = "", sound: Optional[Path] = None, with_sound: bool = True) -> None:
    """Shows the notification and plays the sound without blocking the caller."""

    def task():
        show_notification(title, message)

        if with_sound:
            play_sound(sound)

    threading.Thread(target=task, name="brain-notification", daemon=True).start()
