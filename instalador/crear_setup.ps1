# Creates the graphical installer "instalbrain (version).exe" with Inno Setup. Written without accents on purpose.
#
# Internet is only needed on the PC where it is built: it downloads portable Python (it goes inside the
# installer, so whoever installs it does not need to download Python) and, if missing, Inno Setup.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$project = Split-Path -Parent $PSScriptRoot
$work = Join-Path $env:TEMP "brain_setup_build"

# --- version -----------------------------------------------------------
$config = Get-Content (Join-Path $project "brain\core\config.py") -Raw
if ($config -notmatch 'VERSION\s*=\s*"([^"]+)"') { throw "Could not find the version in brain\core\config.py." }
$version = $Matches[1]
Write-Host "BRAIN version: $version"

# --- Inno Setup --------------------------------------------------------
function Find-Inno {
    $paths = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $paths) { if ($p -and (Test-Path $p)) { return $p } }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$iscc = Find-Inno
if (-not $iscc) {
    Write-Host "Inno Setup (the free program that builds installers) is not present. Installing it..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements | Out-Null
        $iscc = Find-Inno
    }
    if (-not $iscc) {
        $inno = Join-Path $env:TEMP "innosetup.exe"
        Invoke-WebRequest -Uri "https://jrsoftware.org/download.php/is.exe" -OutFile $inno -UseBasicParsing
        Start-Process -FilePath $inno -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER" -Wait
        $iscc = Find-Inno
    }
    if (-not $iscc) { throw "Could not install Inno Setup. Install it from https://jrsoftware.org/isdl.php and run CREAR_SETUP.bat again." }
}
Write-Host "Inno Setup: $iscc"

# --- portable Python ---------------------------------------------------
if (Test-Path $work) { Remove-Item -Recurse -Force $work }
New-Item -ItemType Directory -Force -Path $work | Out-Null
$python = Join-Path $work "python"

$architecture = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "amd64" }
$zip = Join-Path $work "python-embed.zip"
Write-Host "Downloading portable Python ($architecture)..."
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-$architecture.zip" -OutFile $zip -UseBasicParsing
Expand-Archive -Path $zip -DestinationPath $python -Force
Remove-Item $zip -Force

# The ._pth file limits where it looks for modules: BRAIN's folder (the one above) is added to it.
$pth = Get-ChildItem -Path $python -Filter "python3*._pth" | Select-Object -First 1
if (-not $pth) { throw "The downloaded portable Python does not have the expected ._pth file." }
$lines = @(Get-Content $pth.FullName | Where-Object { $_ -notmatch "^\s*#?\s*import site" })
$lines += ".."
$lines += "import site"
Set-Content -Path $pth.FullName -Value $lines -Encoding ASCII

# --- build ------------------------------------------------------------
Get-ChildItem -Path $project -Filter "instalbrain*.exe" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "Building the installer (takes a couple of minutes)..."
& $iscc "/Qp" "/DVersion=$version" "/DSource=$project" "/DPythonDir=$python" "/DOutput=$project" (Join-Path $project "instalador\brain.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup reported an error (code $LASTEXITCODE). Read the message above." }

Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue

$output = Join-Path $project "instalbrain ($version).exe"
if (-not (Test-Path $output)) { throw "$output was not created." }
Write-Host ""
Write-Host "Done: $output" -ForegroundColor Green
