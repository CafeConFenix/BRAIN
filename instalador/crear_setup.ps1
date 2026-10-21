# Crea el instalador grafico "instalbrain (version).exe" con Inno Setup. Escrito sin tildes a proposito.
#
# Hace falta internet solo en el PC donde se crea: descarga Python portable (va dentro del
# instalador, asi que quien lo instale no necesita descargar Python) y, si falta, Inno Setup.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$proyecto = Split-Path -Parent $PSScriptRoot
$trabajo = Join-Path $env:TEMP "brain_setup_build"

# --- version -----------------------------------------------------------
$config = Get-Content (Join-Path $proyecto "brain\core\config.py") -Raw
if ($config -notmatch 'VERSION\s*=\s*"([^"]+)"') { throw "No encuentro la version en brain\core\config.py." }
$version = $Matches[1]
Write-Host "Version de BRAIN: $version"

# --- Inno Setup --------------------------------------------------------
function Buscar-Inno {
    $rutas = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($r in $rutas) { if ($r -and (Test-Path $r)) { return $r } }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$iscc = Buscar-Inno
if (-not $iscc) {
    Write-Host "Inno Setup (el programa que crea instaladores, gratis) no esta. Lo instalo..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements | Out-Null
        $iscc = Buscar-Inno
    }
    if (-not $iscc) {
        $inno = Join-Path $env:TEMP "innosetup.exe"
        Invoke-WebRequest -Uri "https://jrsoftware.org/download.php/is.exe" -OutFile $inno -UseBasicParsing
        Start-Process -FilePath $inno -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER" -Wait
        $iscc = Buscar-Inno
    }
    if (-not $iscc) { throw "No he podido instalar Inno Setup. Instalalo desde https://jrsoftware.org/isdl.php y vuelve a ejecutar CREAR_SETUP.bat." }
}
Write-Host "Inno Setup: $iscc"

# --- Python portable ---------------------------------------------------
if (Test-Path $trabajo) { Remove-Item -Recurse -Force $trabajo }
New-Item -ItemType Directory -Force -Path $trabajo | Out-Null
$python = Join-Path $trabajo "python"

$arquitectura = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
$zip = Join-Path $trabajo "python-embed.zip"
Write-Host "Descargando Python portable ($arquitectura)..."
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-$arquitectura.zip" -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $python -Force
Remove-Item $zip -Force

# El archivo ._pth limita donde busca modulos: se le anade la carpeta de BRAIN (la de arriba).
$pth = Get-ChildItem -Path $python -Filter "python3*._pth" | Select-Object -First 1
if (-not $pth) { throw "El Python portable descargado no tiene el archivo ._pth esperado." }
$lineas = @(Get-Content $pth.FullName | Where-Object { $_ -notmatch "^\s*#?\s*import site" })
$lineas += ".."
$lineas += "import site"
Set-Content -Path $pth.FullName -Value $lineas -Encoding ASCII

# --- compilar ------------------------------------------------------------
Get-ChildItem -Path $proyecto -Filter "instalbrain*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "Creando el instalador (tarda un par de minutos)..."
& $iscc "/Qp" "/DVersion=$version" "/DFuente=$proyecto" "/DPythonDir=$python" "/DSalida=$proyecto" (Join-Path $proyecto "instalador\brain.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup ha dado un error (codigo $LASTEXITCODE). Lee el mensaje de arriba." }

Remove-Item -Recurse -Force $trabajo -ErrorAction SilentlyContinue

$salida = Join-Path $proyecto "instalbrain ($version).exe"
if (-not (Test-Path $salida)) { throw "No se ha creado $salida." }
Write-Host ""
Write-Host "Listo: $salida" -ForegroundColor Green
