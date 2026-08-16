@echo off
setlocal enabledelayedexpansion
REM ============================================================
REM  ikaros-dsh-pet installer
REM  Copies character / plugin / TTS bridge into a Sakura install
REM  Usage: install.bat [SakuraDir]
REM ============================================================

echo.
echo [ikaros-dsh-pet] Installing into Sakura Desktop Pet ...
echo.

set "BASE_DIR=%~dp0"

if not exist "%BASE_DIR%characters\ikaros\character.json" (
    echo [ERROR] character package not found: characters\ikaros\character.json
    exit /b 1
)

REM ---- 1. locate Sakura ----
set "SAKURA_DIR=%1"
if "%SAKURA_DIR%"=="" set "SAKURA_DIR=%BASE_DIR%..\Sakura"
if not exist "%SAKURA_DIR%\main.py" (
    echo.
    echo [HINT] Sakura not found at: %SAKURA_DIR%
    echo        Put this repo next to the Sakura folder, or:
    echo        install.bat ^<SakuraDir^>
    echo.
    set /p SAKURA_DIR="Enter Sakura directory: "
)
if not exist "%SAKURA_DIR%\main.py" (
    echo [ERROR] %SAKURA_DIR%\main.py not found. Aborted.
    exit /b 1
)
echo [1/4] Sakura: %SAKURA_DIR%

REM ---- 2. character package ----
if not exist "%SAKURA_DIR%\characters" mkdir "%SAKURA_DIR%\characters"
xcopy /E /I /Y "%BASE_DIR%characters\ikaros" "%SAKURA_DIR%\characters\ikaros" >nul
if errorlevel 1 (
    echo [ERROR] failed to copy character package. Aborted.
    exit /b 1
)
echo [2/4] character ikaros installed.

REM ---- 3. plugin ----
if not exist "%SAKURA_DIR%\plugins" mkdir "%SAKURA_DIR%\plugins"
xcopy /E /I /Y "%BASE_DIR%plugins\dsh_watcher" "%SAKURA_DIR%\plugins\dsh_watcher" >nul
if errorlevel 1 (
    echo [ERROR] failed to copy plugin. Aborted.
    exit /b 1
)
echo [3/4] plugin dsh_watcher installed.

REM ---- 4. TTS bridge ----
if not exist "%SAKURA_DIR%\tools\edge_tts_bridge" mkdir "%SAKURA_DIR%\tools\edge_tts_bridge"
xcopy /E /I /Y "%BASE_DIR%tools\edge_tts_bridge" "%SAKURA_DIR%\tools\edge_tts_bridge" >nul
if errorlevel 1 (
    echo [ERROR] failed to copy TTS bridge. Aborted.
    exit /b 1
)
echo [4/4] TTS bridge installed.

REM ---- 5. Python deps into Sakura runtime ----
set "PYTHON_EXE=%SAKURA_DIR%\runtime\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [HINT] %PYTHON_EXE% not found - install deps manually: %PYTHON_EXE% -m pip install -r tools\edge_tts_bridge\requirements.txt
) else (
    echo [5/4] Installing deps (edge-tts, zstandard, miniaudio) ...
    "%PYTHON_EXE%" -m pip install -r "%BASE_DIR%tools\edge_tts_bridge\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] dependency install failed. Check network and retry.
        exit /b 1
    )
)

echo.
echo ============================================================
echo  Install complete!
echo
echo  1. Apply local patches (required):
echo     Sakura\runtime\python.exe tools\apply_patches.py ^<SakuraDir^>
echo  2. Start TTS bridge:  start_tts_bridge.bat  (see docs/SETUP.md)
echo  3. Start Sakura:      start.bat
echo  4. First-run config: pick character Ikaros, fill LLM keys,
echo     TTS api_url: http://127.0.0.1:9880/tts
echo     (visual model slot: glm-4v-flash; see docs/SETUP.md section 5)
echo ============================================================
echo.
pause
