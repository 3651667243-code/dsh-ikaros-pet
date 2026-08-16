@echo off
chcp 65001 >nul
REM ============================================================
REM  Start ikaros-dsh-pet (Sakura desktop pet)
REM  1. Start the TTS bridge first (start_tts_bridge.bat)
REM  2. Then start Sakura
REM ============================================================

set "BASE_DIR=%~dp0"

REM If this repo sits next to Sakura, launch Sakura directly
if exist "%BASE_DIR%..\Sakura\main.py" (
    cd /d "%BASE_DIR%..\Sakura"
) else (
    cd /d "%BASE_DIR%"
)

if not exist "main.py" (
    echo [ERROR] Sakura main.py not found.
    echo         Put this repo next to the Sakura folder, or run install.bat first.
    pause
    exit /b 1
)

set "PYTHON_EXE=runtime\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo [ikaros-dsh-pet] Starting Sakura Desktop Pet ...
"%PYTHON_EXE%" main.py
pause
