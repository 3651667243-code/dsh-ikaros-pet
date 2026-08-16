@echo off
chcp 65001 >nul
REM ============================================================
REM  启动 VITS 语音桥（WSL 内运行，伊卡洛斯声线）
REM  前置：WSL Ubuntu 已部署 venv + 模型（见 docs/SETUP.md「WSL 部署」）
REM  发行版名：默认使用 WSL 默认发行版；多发行版时设置环境变量：
REM    set WSL_DISTRO=Ubuntu-22.04  再运行本脚本
REM ============================================================

set "BASE_DIR=%~dp0"
if "%WSL_DISTRO%"=="" (
    set "WSL_EXE=wsl.exe"
) else (
    set "WSL_EXE=wsl.exe -d %WSL_DISTRO%"
)

echo [ikaros-dsh-pet] 启动 VITS 语音桥 (WSL, 127.0.0.1:9880) ...
start "IkarosVITSBridge" /min %WSL_EXE% -e bash "%BASE_DIR%tools\edge_tts_bridge\wsl_run_vits.sh"
timeout /t 5 /nobreak >nul
echo.
echo 桥已启动。模型加载约需 30-60 秒；在 Sakura 设置中将 TTS 指向：
echo   http://127.0.0.1:9880/tts
echo 若桥启用了访问令牌（VITS_AUTH），TTS 地址需带 ?token=^<令牌^>。
pause
