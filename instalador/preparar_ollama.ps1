# Instala Ollama (la IA de BRAIN) sin ventanas. Lo ejecuta el instalador grafico. Escrito sin tildes a proposito.
# Si no hay internet o falla, no pasa nada: BRAIN lo explica al abrirse y se puede instalar despues.

$ErrorActionPreference = "SilentlyContinue"
$ProgressPreference = "SilentlyContinue"

$destino = Join-Path $env:TEMP "OllamaSetup.exe"

try {
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $destino -UseBasicParsing
    if (Test-Path $destino) {
        Start-Process -FilePath $destino -ArgumentList "/SILENT", "/NORESTART" -Wait
        Remove-Item $destino -Force
    }
} catch {
    exit 0
}
exit 0
