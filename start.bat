@echo off
chcp 65001 >nul
REM ============================================================
REM  启动 ikaros-dsh-pet（Sakura 桌宠）
REM  1. 先确保 TTS 桥已启动（另开窗口运行 start_tts_bridge.bat）
REM  2. 再启动 Sakura
REM ============================================================

set "BASE_DIR=%~dp0"

REM 如果本仓库与 Sakura 相邻，直接进 Sakura 启动
if exist "%BASE_DIR%..\Sakura\main.py" (
    cd /d "%BASE_DIR%..\Sakura"
) else (
    cd /d "%BASE_DIR%"
)

if not exist "main.py" (
    echo [错误] 未找到 Sakura 的 main.py
    echo        请确认本仓库放在 Sakura 目录旁边，或先执行 install.bat
    pause
    exit /b 1
)

set "PYTHON_EXE=runtime\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo [ikaros-dsh-pet] 启动 Sakura Desktop Pet ...
"%PYTHON_EXE%" main.py
pause
