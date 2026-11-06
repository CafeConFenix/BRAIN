@echo off
chcp 65001 >nul
cd /d "%~dp0"
title BRAIN installer

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\instalar.ps1"
set "CODE=%errorlevel%"

echo.
if not "%CODE%"=="0" (
    echo The install did not finish correctly. Read the message above.
    echo If you don't know what to do, copy that message and ask Claude for help.
)
pause
exit /b %CODE%
