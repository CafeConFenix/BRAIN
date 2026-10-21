@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Crear el instalador de BRAIN

echo Voy a crear el instalador grafico de BRAIN (hace falta internet solo en este PC).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalador\crear_setup.ps1"
echo.
if exist "%~dp0instalbrain (*).exe" (
    echo Listo. El instalador esta en esta misma carpeta, con el nombre instalbrain, seguido de la version.
    echo Puedes copiarlo a cualquier PC con Windows y hacer doble clic: lleva Python incluido.
) else (
    echo No se ha podido crear el instalador. Lee el mensaje de arriba.
)
pause
