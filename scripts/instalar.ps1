# BRAIN installer for Windows.
# Runs by double-clicking INSTALL.bat (no need to open it by hand).
#
# Does, in order:
#   1. Checks Python (installs it if missing).
#   2. Checks Ollama (installs it if missing).
#   3. Starts Ollama and downloads an AI model if there isn't one yet.
#   4. Tests that BRAIN starts, creates the shortcuts (desktop and Start
#      menu) with its icon, and sets it to start with Windows.
#
# Note: this file is written without accents on purpose, so that
# Windows PowerShell reads it correctly on any machine.

param(
    [string]$Model = "",
    [switch]$NoPrompt
)

$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"

$project = Split-Path -Parent $PSScriptRoot

function Heading($text) {
    Write-Host ""
    Write-Host "=== $text ===" -ForegroundColor Cyan
}

function Good($text) {
    Write-Host "[OK] $text" -ForegroundColor Green
}

function Warn($text) {
    Write-Host "[!] $text" -ForegroundColor Yellow
}

function Fail($text) {
    Write-Host "[ERROR] $text" -ForegroundColor Red
}

function Update-Path {
    # After installing a program, the current window does not see its new PATH.
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Has-Winget {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------

function Test-PythonExe {
    param([string]$Exe, [string[]]$Prefix = @())

    try {
        & $Exe @Prefix -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-Python {
    $options = @(
        @{ Exe = "py"; Prefix = @("-3") },
        @{ Exe = "python"; Prefix = @() }
    )

    foreach ($o in $options) {
        if (Get-Command $o.Exe -ErrorAction SilentlyContinue) {
            if (Test-PythonExe $o.Exe $o.Prefix) {
                return $o
            }
        }
    }

    $paths = @()

    # BRAIN's own Python (portable version, no installer): the project's "python" folder.
    $own = Join-Path $project "python\python.exe"
    if (Test-Path $own) { $paths += $own }

    foreach ($pattern in @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:ProgramFiles\Python3*\python.exe",
        "${env:ProgramFiles(x86)}\Python3*\python.exe",
        "C:\Python3*\python.exe"
    )) {
        $paths += @(Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $_.FullName })
    }

    # Python registered in Windows (even if not on the PATH).
    foreach ($key in @("HKCU:\Software\Python\PythonCore", "HKLM:\Software\Python\PythonCore", "HKLM:\Software\WOW6432Node\Python\PythonCore")) {
        foreach ($version in @(Get-ChildItem -Path $key -ErrorAction SilentlyContinue)) {
            try {
                $base = (Get-ItemProperty -Path (Join-Path $version.PSPath "InstallPath") -ErrorAction Stop).'(default)'
                if ($base) { $paths += (Join-Path $base "python.exe") }
            } catch { }
        }
    }

    foreach ($path in $paths) {
        if ((Test-Path $path) -and (Test-PythonExe $path @())) {
            return @{ Exe = $path; Prefix = @() }
        }
    }

    return $null
}

function Install-PortablePython {
    # The "embedded" Python from python.org: a zip that gets unpacked into BRAIN's folder.
    # It does not use the Windows Installer (so it does not suffer from error 1603) and
    # BRAIN only needs the standard library.
    $architecture = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
    $zip = Join-Path $env:TEMP "python-embed.zip"
    $destination = Join-Path $project "python"

    try {
        Write-Host "Downloading portable Python..."
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-$architecture.zip" -OutFile $zip -UseBasicParsing

        if (Test-Path $destination) { Remove-Item $destination -Recurse -Force -ErrorAction SilentlyContinue }
        Expand-Archive -Path $zip -DestinationPath $destination -Force

        # The ._pth file limits where it looks for modules: BRAIN's folder is added to it.
        $pth = Get-ChildItem -Path $destination -Filter "python3*._pth" | Select-Object -First 1
        if ($pth) {
            $lines = @(Get-Content $pth.FullName | Where-Object { $_ -notmatch "^\s*#?\s*import site" })
            $lines += ".."
            $lines += "import site"
            Set-Content -Path $pth.FullName -Value $lines -Encoding ASCII
        }

        Remove-Item $zip -ErrorAction SilentlyContinue
        Good "Portable Python ready at $destination"
    } catch {
        Fail "Could not prepare portable Python: $($_.Exception.Message)"
    }
}

function Install-Python {
    # Only the essentials are installed (no tests, documentation, Tcl/Tk or dev
    # headers). Python's test suite is thousands of files and is usually what
    # causes failures (error 1603) with antivirus software and some Windows setups;
    # BRAIN does not need it.
    $process = $null
    $log = Join-Path $env:TEMP "python-install.log"

    try {
        Write-Host "Downloading Python from python.org..."
        $installer = Join-Path $env:TEMP "python-3.12.8-amd64.exe"
        Remove-Item $log -ErrorAction SilentlyContinue
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe" -OutFile $installer -UseBasicParsing
        Write-Host "Installing Python (reduced version)..."
        $process = Start-Process -FilePath $installer -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=0", "Include_test=0", "Include_doc=0", "Include_tcltk=0", "Include_dev=0", "Include_pip=1", "/log", "`"$log`"" -Wait -PassThru
        Update-Path
    } catch {
        Warn "Could not use the python.org installer: $($_.Exception.Message)"
    }

    if (Find-Python) {
        return
    }

    if (Has-Winget) {
        Write-Host "Trying winget..."
        winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
        Update-Path
    }

    if (Find-Python) {
        return
    }

    Write-Host ""
    $code = if ($process) { $process.ExitCode } else { "no installer" }
    Warn "The Windows installer could not install Python (code $code)."
    Write-Host "No problem: using a portable copy of Python, which needs no installer."
    Install-PortablePython
    return
}

# ---------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------

function Find-Ollama {
    $command = Get-Command ollama -ErrorAction SilentlyContinue

    if ($command) {
        return $command.Source
    }

    $paths = @(
        "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
        "$env:ProgramFiles\Ollama\ollama.exe"
    )

    foreach ($path in $paths) {
        if (Test-Path $path) {
            return $path
        }
    }

    return $null
}

function Install-Ollama {
    if (Has-Winget) {
        Write-Host "Installing Ollama with winget (can take a few minutes)..."
        winget install -e --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
        Update-Path
    }

    if (Find-Ollama) {
        return
    }

    Write-Host "Downloading Ollama from ollama.com..."
    $installer = Join-Path $env:TEMP "OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $installer -UseBasicParsing
    Write-Host "Installing Ollama..."
    Start-Process -FilePath $installer -ArgumentList "/SILENT" -Wait
    Update-Path
}

function Get-OllamaUrl {
    # Same address BRAIN uses: OLLAMA_HOST if set, otherwise the default one.
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

function Get-InstalledModels {
    try {
        $response = Invoke-RestMethod -Uri ((Get-OllamaUrl) + "/api/tags") -TimeoutSec 5
        $list = @($response.models | ForEach-Object { $_.name } | Where-Object { $_ -notmatch "embed" })
        # The comma stops PowerShell turning an empty list into $null.
        return ,$list
    } catch {
        return $null
    }
}

function Start-Ollama($ollama) {
    if ($null -ne (Get-InstalledModels)) {
        return $true
    }

    Write-Host "Starting Ollama..."
    Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden

    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1

        if ($null -ne (Get-InstalledModels)) {
            return $true
        }
    }

    return $false
}

# ---------------------------------------------------------------------
# Main process
# ---------------------------------------------------------------------

Write-Host ""
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host "    BRAIN Installer" -ForegroundColor Cyan
Write-Host "  ==============================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This can take several minutes the first time (downloads about 2.5 GB)."
Write-Host "Do not close this window until it finishes."

try {
    Heading "1/4  Python"

    $python = Find-Python

    if (-not $python) {
        Install-Python
        $python = Find-Python
    }

    if (-not $python) {
        Fail "Could not install Python. Install it by hand from https://www.python.org/downloads/ (check the 'Add python.exe to PATH' box) and run INSTALAR.bat again."
        exit 1
    }

    Good "Python ready."

    Heading "2/4  Ollama (the local artificial intelligence)"

    $ollama = Find-Ollama

    if (-not $ollama) {
        Install-Ollama
        $ollama = Find-Ollama
    }

    if (-not $ollama) {
        Fail "Could not install Ollama. Download it from https://ollama.com/download, install it and run INSTALAR.bat again."
        exit 1
    }

    Good "Ollama installed at $ollama"

    Heading "3/4  AI model"

    if (-not (Start-Ollama $ollama)) {
        Fail "Ollama does not start. Restart the computer and run INSTALAR.bat again."
        exit 1
    }

    $env:PYTHONUTF8 = "1"
    $prefix = $python.Prefix
    Push-Location $project

    $installed = Get-InstalledModels
    $modelCode = 0

    if ($Model -ne "") {
        Write-Host "Downloading model $Model..."
        & $ollama pull $Model
        $modelCode = $LASTEXITCODE
    } elseif ($installed.Count -gt 0) {
        Good ("You already have models installed: " + ($installed -join ", "))
        Write-Host "If you want BRAIN to pick a better model for your PC, use MEJORAR_IA.bat."
    } else {
        # BRAIN measures the RAM and graphics card, picks the best model that
        # fits this PC, downloads it through the same Ollama it will later use,
        # and checks for itself that Ollama lists it.
        & $python.Exe @prefix main.py --upgrade-model --auto
        $modelCode = $LASTEXITCODE
    }

    Pop-Location

    if ($modelCode -ne 0) {
        Fail "Could not prepare the AI model. Check your internet connection and run INSTALAR.bat again. If it still fails, run DIAGNOSTICO.bat."
        exit 1
    }

    $installed = Get-InstalledModels

    if ($installed.Count -gt 0) {
        Good ("Models ready: " + ($installed -join ", "))
    } else {
        # BRAIN has already checked the model; this read is just informational.
        Warn "The model has been downloaded. If BRAIN says it has no model, press the Download AI button inside BRAIN."
    }

    Heading "4/4  Checking BRAIN"

    Push-Location $project
    & $python.Exe @prefix main.py --diagnose
    $code = $LASTEXITCODE
    Pop-Location

    if ($code -ne 0) {
        Fail "BRAIN did not start correctly. Take a screenshot or copy the message above to ask for help."
        exit 1
    }

    $launcher = $null
    try {
        # pythonw.exe opens BRAIN without a black console window.
        $exe = (& $python.Exe @prefix -c "import sys; print(sys.executable)").Trim()
        $pythonw = Join-Path (Split-Path $exe) "pythonw.exe"
        if (-not (Test-Path $pythonw)) { $pythonw = $exe }
        $launcher = $pythonw

        $icon = Join-Path $project "brain\desktop\brain.ico"
        $shell = New-Object -ComObject WScript.Shell
        $menu = Join-Path ([Environment]::GetFolderPath("Programs")) "BRAIN.lnk"
        $desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "BRAIN.lnk"

        foreach ($path in @($desktop, $menu)) {
            $shortcut = $shell.CreateShortcut($path)
            $shortcut.TargetPath = $pythonw
            $shortcut.Arguments = '"' + (Join-Path $project "main.py") + '" --desktop'
            $shortcut.WorkingDirectory = $project
            $shortcut.IconLocation = $icon
            $shortcut.Description = "Open BRAIN"
            $shortcut.Save()
        }

        # Automatic start with Windows (just the icon next to the clock, so notifications still sound).
        $command = '"' + $pythonw + '" "' + (Join-Path $project "main.py") + '" --desktop --background'
        New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "BRAIN" -Value $command -PropertyType String -Force | Out-Null

        Good "I've created the BRAIN icon on the desktop and in the Start menu, and BRAIN will start with Windows."
    } catch {
        Warn "Could not create the shortcuts. You can open BRAIN with INICIAR.bat."
    }

    Write-Host ""
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host "  BRAIN is installed. To use it, double-click the" -ForegroundColor Green
    Write-Host "  BRAIN icon on the desktop." -ForegroundColor Green
    Write-Host "=====================================================" -ForegroundColor Green
    Write-Host ""

    if ($NoPrompt) {
        $open = "y"
    } else {
        $open = Read-Host "Do you want to open BRAIN now? (y/n)"
    }

    if ($open -match "^[sSyY]") {
        if ($launcher) {
            Start-Process -FilePath $launcher -ArgumentList ('"' + (Join-Path $project "main.py") + '" --desktop') -WorkingDirectory $project
        } else {
            Start-Process -FilePath (Join-Path $project "INICIAR.bat") -WorkingDirectory $project
        }
    }

    exit 0
} catch {
    Fail $_.Exception.Message
    exit 1
}
