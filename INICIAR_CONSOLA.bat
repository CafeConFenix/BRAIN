@echo off
chcp 65001 >nul
cd /d "%~dp0"
title BRAIN (consola)
set "PYTHONUTF8=1"

call :buscar_python
if not defined PY (
    echo No encuentro Python en este equipo.
    echo Ejecuta primero INSTALAR.bat.
    echo.
    pause
    exit /b 1
)

%PY% main.py --consola %*
set "CODIGO=%errorlevel%"

if not "%CODIGO%"=="0" (
    echo.
    echo BRAIN se ha cerrado con un error. Lee el mensaje de arriba.
)
pause
exit /b %CODIGO%


:buscar_python
set "PY="
call :probar "py -3"
call :probar "python"
for %%V in (314 313 312 311 310 39) do (
    call :probar_ruta "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    call :probar_ruta "%ProgramFiles%\Python%%V\python.exe"
)
exit /b 0

:probar
if defined PY exit /b 0
%~1 -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%~1"
exit /b 0

:probar_ruta
if defined PY exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if not errorlevel 1 set "PY="%~1""
exit /b 0
