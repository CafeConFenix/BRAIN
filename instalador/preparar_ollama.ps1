# Installs Ollama (BRAIN's AI) silently. Run by the graphical installer. Written without accents on purpose.
# If there is no internet or it fails, no problem: BRAIN explains it when opened and it can be installed later.

$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = "SilentlyContinue"

$destination = Join-Path $env:TEMP "OllamaSetup.exe"

try {
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $destination -UseBasicParsing
    if (Test-Path $destination) {
        Start-Process -FilePath $destination -ArgumentList "/SILENT", "/NORESTART" -Wait
        Remove-Item $destination -Force
    }
} catch {
    exit 0
}
exit 0
