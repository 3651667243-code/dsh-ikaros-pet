@echo off
chcp 65001 >nul
REM ============================================================
REM  启动 edge-tts 语音桥（Sakura 的 GPT-SoVITS 兼容外置 TTS）
REM  用法：start_tts_bridge.bat [--proxy http://127.0.0.1:7890]
REM  网络受限时加上面的 --proxy 参数
REM ============================================================

set "BASE_DIR=%~dp0"

REM 优先用 Sakura 运行时，其次系统 python
set "PYTHON_EXE=%BASE_DIR%..\Sakura\runtime\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

echo [ikaros-dsh-pet] 启动 edge-tts 语音桥 (127.0.0.1:9880) ...
"%PYTHON_EXE%" "%BASE_DIR%server.py" %*
pause
