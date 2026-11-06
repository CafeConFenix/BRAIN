@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build the BRAIN installer

echo Building BRAIN's graphical installer (internet is only needed on this PC).
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalador\crear_setup.ps1"
echo.
if exist "%~dp0instalbrain (*).exe" (
    echo Done. The installer is in this same folder, named instalbrain, followed by the version.
    echo You can copy it to any Windows PC and double-click it: it ships with Python included.
) else (
    echo Could not create the installer. Read the message above.
)
pause
