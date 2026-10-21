"""
Icono de BRAIN junto al reloj de Windows.

Se hace con un pequeño script de PowerShell (NotifyIcon). Cuando el usuario
elige una opción del menú, el script se lo pide a BRAIN por su propia
dirección local (/api/escritorio/<accion>): así no depende de tuberías entre
procesos y las acciones son las mismas que usa la ventana. Si BRAIN deja de
existir, el icono desaparece solo.
"""

import base64
import os
import subprocess
from pathlib import Path
from typing import Optional

from brain.core.config import Config
from brain.utils.procesos import sin_ventana

SCRIPT = r"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$base = "http://127.0.0.1:" + $env:BRAIN_PUERTO + "/api/escritorio/"
$padre = [int]$env:BRAIN_PID
$parar = $env:BRAIN_PARAR

function Enviar($accion) {
    try {
        Invoke-RestMethod -Method Post -Uri ($base + $accion) -ContentType "application/json" -Body "{}" -TimeoutSec 5 | Out-Null
    } catch { }
}

function Terminar {
    # Quitar el icono de verdad: si el proceso muriese sin esto, Windows dejaria
    # el icono "fantasma" junto al reloj hasta pasar el raton por encima.
    try { $icono.Visible = $false } catch { }
    try { $icono.Dispose() } catch { }
    [System.Windows.Forms.Application]::Exit()
}

$icono = New-Object System.Windows.Forms.NotifyIcon
$icono.Icon = New-Object System.Drawing.Icon($env:BRAIN_ICONO)
$icono.Text = "BRAIN"

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$abrir = $menu.Items.Add("Abrir BRAIN")
$abrir.Font = New-Object System.Drawing.Font($abrir.Font, [System.Drawing.FontStyle]::Bold)
$abrir.Add_Click({ Enviar "mostrar" })
$null = $menu.Items.Add("-")
$silencio = $menu.Items.Add("Silenciar avisos")
$silencio.Add_Click({ Enviar "silencio" })
$fondo = $menu.Items.Add("Seguir en segundo plano al cerrar la ventana")
$fondo.Add_Click({ Enviar "segundo_plano" })
$arranque = $menu.Items.Add("Arrancar con Windows")
$arranque.Add_Click({ Enviar "autoarranque" })
$null = $menu.Items.Add("-")
$salir = $menu.Items.Add("Salir de BRAIN")
$salir.Add_Click({
    Enviar "salir"
    Terminar
})

# Al desplegar el menu se leen los ajustes actuales para marcar las casillas.
$menu.Add_Opening({
    try {
        $e = Invoke-RestMethod -Method Get -Uri ($base + "estado") -TimeoutSec 3
        $silencio.Checked = [bool]$e.silencio
        $fondo.Checked = [bool]$e.segundo_plano
        $arranque.Checked = [bool]$e.autoarranque
    } catch { }
})

$icono.ContextMenuStrip = $menu
$icono.Add_MouseClick({
    param($origen, $datos)
    if ($datos.Button -eq [System.Windows.Forms.MouseButtons]::Left) { Enviar "mostrar" }
})
$icono.Visible = $true

# Si BRAIN pide cerrar el icono, o BRAIN desaparece (se cierra o falla), el icono se quita solo.
$reloj = New-Object System.Windows.Forms.Timer
$reloj.Interval = 1000
$reloj.Add_Tick({
    if ($parar -and (Test-Path -LiteralPath $parar)) { Terminar; return }
    if (-not (Get-Process -Id $padre -ErrorAction SilentlyContinue)) { Terminar }
})
$reloj.Start()

[System.Windows.Forms.Application]::Run()
try { $icono.Dispose() } catch { }
"""


class Bandeja:
    def __init__(self, icono: Path, puerto: int):
        self.icono = Path(icono)
        self.puerto = puerto
        self.proceso: Optional[subprocess.Popen] = None
        self.archivo_parar = Path(Config.DATOS) / "bandeja.parar"

    @staticmethod
    def _comando() -> list:
        """El script va codificado (UTF-16 + base64): así no hay problemas de comillas ni de acentos."""

        codificado = base64.b64encode(SCRIPT.encode("utf-16-le")).decode("ascii")

        return ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-EncodedCommand", codificado]

    def iniciar(self) -> bool:
        if os.name != "nt" or not self.icono.exists():
            return False

        try:
            self.archivo_parar.parent.mkdir(parents=True, exist_ok=True)
            self.archivo_parar.unlink()
        except OSError:
            pass

        try:
            self.proceso = subprocess.Popen(
                self._comando(),
                env={
                    **os.environ,
                    "BRAIN_ICONO": str(self.icono),
                    "BRAIN_PUERTO": str(self.puerto),
                    "BRAIN_PID": str(os.getpid()),
                    "BRAIN_PARAR": str(self.archivo_parar),
                },
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **sin_ventana(),
            )
        except OSError:
            self.proceso = None
            return False

        return True

    def activa(self) -> bool:
        return self.proceso is not None and self.proceso.poll() is None

    def detener(self) -> None:
        """
        Quita el icono con elegancia: se le pide que se oculte y se cierre solo
        (si se matase a la fuerza, Windows dejaria el icono fantasma junto al reloj).
        """

        if self.proceso is None:
            return

        try:
            self.archivo_parar.parent.mkdir(parents=True, exist_ok=True)
            self.archivo_parar.write_text("parar", encoding="utf-8")
            self.proceso.wait(timeout=5)
        except Exception:
            try:
                self.proceso.kill()
            except Exception:
                pass
        finally:
            try:
                self.archivo_parar.unlink()
            except OSError:
                pass
