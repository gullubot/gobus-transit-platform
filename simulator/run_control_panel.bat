@echo off
setlocal enabledelayedexpansion
title GoBus Transit Platform — Mission Control

echo ======================================================================
echo  GOBUS TRANSIT PLATFORM — MISSION CONTROL DASHBOARD LAUNCHER
echo ======================================================================
echo.

cd /d "%~dp0"

:: 1. Locate Python Interpreter
set PYTHON_EXE=
if exist "..\backend\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\backend\.venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    for /f "tokens=*" %%i in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%i"
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Could not locate a valid Python interpreter.
    echo Please ensure Python 3.10+ is installed and available in PATH.
    echo.
    pause
    exit /b 1
)

echo [OK] Using Python: %PYTHON_EXE%

:: 2. Launch Mission Control Server in background & open browser
echo [OK] Starting Mission Control on http://127.0.0.1:8080 ...
echo [OK] Press Ctrl+C in this terminal window to stop the server.
echo.

:: Automatically open default browser after brief startup pause
start "" "http://127.0.0.1:8080"

:: 3. Run the Mission Control server
"%PYTHON_EXE%" -m simulator.main ui --port 8080

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Mission Control server exited with error code %ERRORLEVEL%.
    pause
)

endlocal
