@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Instalador de BRAIN

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar.ps1"
set "CODIGO=%errorlevel%"

echo.
if not "%CODIGO%"=="0" (
    echo La instalacion no ha terminado bien. Lee el mensaje de arriba.
    echo Si no sabes que hacer, copia ese mensaje y pidele ayuda a Claude.
)
pause
exit /b %CODIGO%
