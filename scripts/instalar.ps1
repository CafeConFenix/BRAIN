# Instalador de BRAIN para Windows.
# Se ejecuta con doble clic en INSTALAR.bat (no hace falta abrirlo a mano).
#
# Hace, en orden:
#   1. Comprueba Python (si falta, lo instala).
#   2. Comprueba Ollama (si falta, lo instala).
#   3. Arranca Ollama y descarga un modelo de IA si no hay ninguno.
#   4. Prueba que BRAIN arranca y crea un acceso directo en el escritorio.
#
# Nota: este archivo esta escrito sin tildes a proposito, para que
# Windows PowerShell lo lea bien en cualquier equipo.

param(
    [string]$Modelo = ""
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$proyecto = Split-Path -Parent $PSScriptRoot

function Titulo($texto) {
    Write-Host ""
    Write-Host "=== $texto ===" -ForegroundColor Cyan
}

function Bien($texto) {
    Write-Host "[OK] $texto" -ForegroundColor Green
}

function Aviso($texto) {
    Write-Host "[!] $texto" -ForegroundColor Yellow
}

function Fallo($texto) {
    Write-Host "[ERROR] $texto" -ForegroundColor Red
}

function Actualizar-Path {
    # Tras instalar un programa, la ventana actual no ve su PATH nuevo.
    $maquina = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $usuario = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$maquina;$usuario"
}

function Hay-Winget {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------

function Probar-Python {
    param([string]$Exe, [string[]]$Prefijo = @())

    try {
        & $Exe @Prefijo -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Encontrar-Python {
    $opciones = @(
        @{ Exe = "py"; Prefijo = @("-3") },
        @{ Exe = "python"; Prefijo = @() }
    )

    foreach ($o in $opciones) {
        if (Get-Command $o.Exe -ErrorAction SilentlyContinue) {
            if (Probar-Python $o.Exe $o.Prefijo) {
                return $o
            }
        }
    }

    foreach ($v in @("314", "313", "312", "311", "310", "39")) {
        $rutas = @(
            "$env:LOCALAPPDATA\Programs\Python\Python$v\python.exe",
            "$env:ProgramFiles\Python$v\python.exe"
        )

        foreach ($ruta in $rutas) {
            if ((Test-Path $ruta) -and (Probar-Python $ruta @())) {
                return @{ Exe = $ruta; Prefijo = @() }
            }
        }
    }

    return $null
}

function Instalar-Python {
    if (Hay-Winget) {
        Write-Host "Instalando Python con winget (puede tardar un par de minutos)..."
        winget install -e --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        Actualizar-Path
    }

    if (Encontrar-Python) {
        return
    }

    Write-Host "Descargando Python desde python.org..."
    $instalador = Join-Path $env:TEMP "python-3.12.8-amd64.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe" -OutFile $instalador -UseBasicParsing
    Write-Host "Instalando Python..."
    Start-Process -FilePath $instalador -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1" -Wait
    Actualizar-Path
}

# ---------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------

function Encontrar-Ollama {
    $comando = Get-Command ollama -ErrorAction SilentlyContinue

    if ($comando) {
        return $comando.Source
    }

    $rutas = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe"
    )

    foreach ($ruta in $rutas) {
        if (Test-Path $ruta) {
            return $ruta
        }
    }

    return $null
}

function Instalar-Ollama {
    if (Hay-Winget) {
        Write-Host "Instalando Ollama con winget (puede tardar unos minutos)..."
        winget install -e --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
        Actualizar-Path
    }

    if (Encontrar-Ollama) {
        return
    }

    Write-Host "Descargando Ollama desde ollama.com..."
    $instalador = Join-Path $env:TEMP "OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $instalador -UseBasicParsing
    Write-Host "Instalando Ollama..."
    Start-Process -FilePath $instalador -ArgumentList "/SILENT" -Wait
    Actualizar-Path
}

function Url-Ollama {
    # Misma direccion que usa BRAIN: OLLAMA_HOST si existe, o la de por defecto.
    $h = $env:OLLAMA_HOST

    if (-not $h) {
        return "http://127.0.0.1:11434"
    }

    if ($h -notmatch "^https?://") {
        $h = "http://$h"
    }

    $h = $h -replace "//0\.0\.0\.0", "//127.0.0.1"

    if ($h -notmatch ":\d+$") {
        $h = "${h}:11434"
    }

    return $h
}

function Modelos-Instalados {
    try {
        $respuesta = Invoke-RestMethod -Uri ((Url-Ollama) + "/api/tags") -TimeoutSec 5
        $lista = @($respuesta.models | ForEach-Object { $_.name } | Where-Object { $_ -notmatch "embed" })
        # La coma evita que PowerShell convierta una lista vacia en $null.
        return ,$lista
    } catch {
        return $null
    }
}

function Arrancar-Ollama($ollama) {
    if ($null -ne (Modelos-Instalados)) {
        return $true
    }

    Write-Host "Arrancando Ollama..."
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1

        if ($null -ne (Modelos-Instalados)) {
            return $true
        }
    }

    return $false
}

# ---------------------------------------------------------------------
# Proceso principal
# ---------------------------------------------------------------------

Write-Host ""
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host "    Instalador de BRAIN" -ForegroundColor Cyan
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Esto puede tardar varios minutos la primera vez (descarga unos 2,5 GB)."
Write-Host "No cierres esta ventana hasta que termine."

try {
    Titulo "1/4  Python"

    $python = Encontrar-Python

    if (-not $python) {
        Instalar-Python
        $python = Encontrar-Python
    }

    if (-not $python) {
        Fallo "No he podido instalar Python. Instalalo a mano desde https://www.python.org/downloads/ (marca la casilla 'Add python.exe to PATH') y vuelve a ejecutar INSTALAR.bat."
        exit 1
    }

    Bien "Python listo."

    Titulo "2/4  Ollama (la inteligencia artificial local)"

    $ollama = Encontrar-Ollama

    if (-not $ollama) {
        Instalar-Ollama
        $ollama = Encontrar-Ollama
    }

    if (-not $ollama) {
        Fallo "No he podido instalar Ollama. Descargalo desde https://ollama.com/download, instalalo y vuelve a ejecutar INSTALAR.bat."
        exit 1
    }

    Bien "Ollama instalado en $ollama"

    Titulo "3/4  Modelo de IA"

    if (-not (Arrancar-Ollama $ollama)) {
        Fallo "Ollama no arranca. Reinicia el ordenador y vuelve a ejecutar INSTALAR.bat."
        exit 1
    }

    $env:PYTHONUTF8 = "1"
    $prefijo = $python.Prefijo
    Push-Location $proyecto

    $instalados = Modelos-Instalados
    $codigoModelo = 0

    if ($Modelo -ne "") {
        Write-Host "Descargando el modelo $Modelo..."
        & $ollama pull $Modelo
        $codigoModelo = $LASTEXITCODE
    } elseif ($instalados.Count -gt 0) {
        Bien ("Ya tienes modelos instalados: " + ($instalados -join ", "))
        Write-Host "Si quieres que BRAIN elija un modelo mejor para tu PC, usa MEJORAR_IA.bat."
    } else {
        # BRAIN mide la RAM y la tarjeta grafica, elige el mejor modelo que
        # le cabe a este PC, lo descarga por el mismo Ollama que luego usara
        # y comprueba por si mismo que Ollama lo lista.
        & $python.Exe @prefijo main.py --mejorar-ia --auto
        $codigoModelo = $LASTEXITCODE
    }

    Pop-Location

    if ($codigoModelo -ne 0) {
        Fallo "No se ha podido preparar el modelo de IA. Comprueba tu conexion a internet y vuelve a ejecutar INSTALAR.bat. Si sigue igual, ejecuta DIAGNOSTICO.bat."
        exit 1
    }

    $instalados = Modelos-Instalados

    if ($instalados.Count -gt 0) {
        Bien ("Modelos listos: " + ($instalados -join ", "))
    } else {
        # BRAIN ya ha comprobado el modelo; esta lectura es solo informativa.
        Aviso "El modelo se ha descargado. Si BRAIN dice que no tiene modelo, pulsa el boton Descargar IA dentro de BRAIN."
    }

    Titulo "4/4  Comprobando BRAIN"

    Push-Location $proyecto
    & $python.Exe @prefijo main.py --diagnostico
    $codigo = $LASTEXITCODE
    Pop-Location

    if ($codigo -ne 0) {
        Fallo "BRAIN no ha arrancado bien. Haz una foto o copia el mensaje de arriba para pedir ayuda."
        exit 1
    }

    try {
        $escritorio = [Environment]::GetFolderPath("Desktop")
        $shell = New-Object -ComObject WScript.Shell
        $acceso = $shell.CreateShortcut((Join-Path $escritorio "BRAIN.lnk"))
        $acceso.TargetPath = Join-Path $proyecto "INICIAR.bat"
        $acceso.WorkingDirectory = $proyecto
        $acceso.IconLocation = "shell32.dll,13"
        $acceso.Description = "Abrir BRAIN"
        $acceso.Save()
        Bien "He creado el acceso directo BRAIN en tu escritorio."
    } catch {
        Aviso "No he podido crear el acceso directo. Puedes abrir BRAIN con INICIAR.bat."
    }

    Write-Host ""
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host "  BRAIN esta instalado. Para usarlo, haz doble clic en" -ForegroundColor Green
    Write-Host "  el icono BRAIN del escritorio (o en INICIAR.bat)." -ForegroundColor Green
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host ""

    $abrir = Read-Host "Quieres abrir BRAIN ahora? (s/n)"

    if ($abrir -match "^[sSyY]") {
        Start-Process -FilePath (Join-Path $proyecto "INICIAR.bat") -WorkingDirectory $proyecto
    }

    exit 0
} catch {
    Fallo $_.Exception.Message
    exit 1
}
