@echo off
chcp 65001 >nul
cd /d "%~dp0"
title BRAIN (console)
set "PYTHONUTF8=1"

call :find_python
if not defined PY (
    echo Could not find Python on this computer.
    echo Run INSTALAR.bat first.
    echo.
    pause
    exit /b 1
)

%PY% main.py --console %*
set "CODE=%errorlevel%"

if not "%CODE%"=="0" (
    echo.
    echo BRAIN closed with an error. Read the message above.
)
pause
exit /b %CODE%


:find_python
set "PY="
rem First BRAIN's portable Python (python folder), in case the installer had to use it.
call :try_path "%~dp0python\python.exe"
call :try "py -3"
call :try "python"
for %%V in (314 313 312 311 310 39) do (
    call :try_path "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
    call :try_path "%ProgramFiles%\Python%%V\python.exe"
)
exit /b 0

:try
if defined PY exit /b 0
%~1 -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if not errorlevel 1 set "PY=%~1"
exit /b 0

:try_path
if defined PY exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 1)" >nul 2>nul
if not errorlevel 1 set "PY="%~1""
exit /b 0
