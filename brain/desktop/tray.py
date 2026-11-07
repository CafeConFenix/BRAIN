"""
BRAIN's icon next to the Windows clock.

It is built with a small PowerShell script (NotifyIcon). When the user
picks an option from the menu, the script asks BRAIN itself through its own
local address (/api/desktop/<action>): that way it does not depend on pipes
between processes and the actions are the same ones the window uses. If
BRAIN stops existing, the icon disappears on its own.
"""

import base64
import os
import subprocess
from pathlib import Path
from typing import Optional

from brain.core.config import Config
from brain.i18n import t
from brain.utils.processes import no_window

SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$base = "http://127.0.0.1:" + $env:BRAIN_PORT + "/api/desktop/"
$parent = [int]$env:BRAIN_PID
$stop_file = $env:BRAIN_STOP

function Send($action) {
    try {
        Invoke-RestMethod -Method Post -Uri ($base + $action) -ContentType "application/json" -Body "{}" -TimeoutSec 5 | Out-Null
    } catch { }
}

function Finish {
    # Really remove the icon: without this, if the process died, Windows would
    # leave a "ghost" icon next to the clock until the mouse passed over it.
    try { $icon.Visible = $false } catch { }
    try { $icon.Dispose() } catch { }
    [System.Windows.Forms.Application]::Exit()
}

$icon = New-Object System.Windows.Forms.NotifyIcon
$icon.Icon = New-Object System.Drawing.Icon($env:BRAIN_ICON)
$icon.Text = "BRAIN"

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$open = $menu.Items.Add($env:BRAIN_LABEL_OPEN)
$open.Font = New-Object System.Drawing.Font($open.Font, [System.Drawing.FontStyle]::Bold)
$open.Add_Click({ Send "show" })
$null = $menu.Items.Add("-")
$mute = $menu.Items.Add($env:BRAIN_LABEL_MUTE)
$mute.Add_Click({ Send "mute" })
$background = $menu.Items.Add($env:BRAIN_LABEL_BACKGROUND)
$background.Add_Click({ Send "background" })
$autostart = $menu.Items.Add($env:BRAIN_LABEL_AUTOSTART)
$autostart.Add_Click({ Send "autostart" })
$null = $menu.Items.Add("-")
$quit = $menu.Items.Add($env:BRAIN_LABEL_QUIT)
$quit.Add_Click({
    Send "quit"
    Finish
})

# When the menu opens, the current settings are read to tick the checkboxes.
$menu.Add_Opening({
    try {
        $e = Invoke-RestMethod -Method Get -Uri ($base + "state") -TimeoutSec 3
        $mute.Checked = [bool]$e.mute
        $background.Checked = [bool]$e.background
        $autostart.Checked = [bool]$e.autostart
    } catch { }
})

$icon.ContextMenuStrip = $menu
$icon.Add_MouseClick({
    param($source, $data)
    if ($data.Button -eq [System.Windows.Forms.MouseButtons]::Left) { Send "show" }
})
$icon.Visible = $true

# If BRAIN asks to close the icon, or BRAIN disappears (closes or crashes), the icon removes itself.
$clock = New-Object System.Windows.Forms.Timer
$clock.Interval = 1000
$clock.Add_Tick({
    if ($stop_file -and (Test-Path -LiteralPath $stop_file)) { Finish; return }
    if (-not (Get-Process -Id $parent -ErrorAction SilentlyContinue)) { Finish }
})
$clock.Start()

[System.Windows.Forms.Application]::Run()
try { $icon.Dispose() } catch { }
"""


class Tray:
    def __init__(self, icon: Path, port: int):
        # Don't rebuild an already-built Path: pathlib can't construct the
        # other OS's flavour (e.g. PosixPath on a real Windows machine), and
        # tests simulate "not on Windows" by faking os.name around this call.
        self.icon = icon if isinstance(icon, Path) else Path(icon)
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.stop_file = Path(Config.DATA) / "tray.stop"

    @staticmethod
    def _command() -> list:
        """The script is encoded (UTF-16 + base64): that avoids any quoting or accent issues."""

        encoded = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")

        return ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]

    def start(self) -> bool:
        if os.name != "nt" or not self.icon.exists():
            return False

        try:
            self.stop_file.parent.mkdir(parents=True, exist_ok=True)
            self.stop_file.unlink()
        except OSError:
            pass

        try:
            self.process = subprocess.Popen(
                self._command(),
                env={
                    **os.environ,
                    "BRAIN_ICON": str(self.icon),
                    "BRAIN_PORT": str(self.port),
                    "BRAIN_PID": str(os.getpid()),
                    "BRAIN_STOP": str(self.stop_file),
                    "BRAIN_LABEL_OPEN": t("Open BRAIN"),
                    "BRAIN_LABEL_MUTE": t("Mute notices"),
                    "BRAIN_LABEL_BACKGROUND": t("Keep running in the background when the window closes"),
                    "BRAIN_LABEL_AUTOSTART": t("Start with Windows"),
                    "BRAIN_LABEL_QUIT": t("Quit BRAIN"),
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **no_window(),
            )
        except OSError:
            self.process = None
            return False

        return True

    def active(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        """
        Removes the icon gracefully: it is asked to hide and close itself
        (killing it by force would leave a ghost icon next to the clock).
        """

        if self.process is None:
            return

        try:
            self.stop_file.parent.mkdir(parents=True, exist_ok=True)
            self.stop_file.write_text("stop", encoding="utf-8")
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        finally:
            try:
                self.stop_file.unlink()
            except OSError:
                pass
