@echo off
chcp 65001 >nul
REM ============================================================
REM  启动 VITS 语音桥（WSL 内运行，伊卡洛斯声线）
REM  前置：WSL Ubuntu 已配置（见 docs/SETUP.md 的 WSL 部署章节）
REM ============================================================

set "BASE_DIR=%~dp0"

echo [ikaros-dsh-pet] 启动 VITS 语音桥 (WSL, 127.0.0.1:9880) ...
start "IkarosVITSBridge" /min wsl.exe -d Ubuntu-D -e bash "%BASE_DIR%tools\edge_tts_bridge\wsl_run_vits.sh"
timeout /t 5 /nobreak >nul
echo.
echo 桥已启动。在 Sakura 设置中将 TTS 指向 http://127.0.0.1:9880/tts
pause
