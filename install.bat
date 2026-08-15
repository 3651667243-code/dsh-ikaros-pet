@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
REM ============================================================
REM  ikaros-dsh-pet 安装脚本
REM  把角色包 / 插件 / TTS 桥合并进已有的 Sakura Desktop Pet 安装
REM ============================================================

echo.
echo [ikaros-dsh-pet] 开始安装到 Sakura Desktop Pet ...
echo.

set "BASE_DIR=%~dp0"

if not exist "%BASE_DIR%characters\ikaros\character.json" (
    echo [错误] 未找到角色包 characters\ikaros\character.json
    exit /b 1
)

REM ---- 1. 定位 Sakura 安装目录 ----
set "SAKURA_DIR=%1"
if "%SAKURA_DIR%"=="" set "SAKURA_DIR=%BASE_DIR%..\Sakura"
if not exist "%SAKURA_DIR%\main.py" (
    echo.
    echo [提示] 没有在默认位置找到 Sakura：
    echo        %SAKURA_DIR%
    echo.
    echo 请把本仓库放在 Sakura 目录旁边（推荐），或者：
    echo    install.bat ^<Sakura安装目录^>
    echo.
    set /p SAKURA_DIR="请输入 Sakura 安装目录: "
)
if not exist "%SAKURA_DIR%\main.py" (
    echo [错误] 未找到 %SAKURA_DIR%\main.py，安装中止。
    exit /b 1
)
echo [1/4] Sakura 目录: %SAKURA_DIR%

REM ---- 2. 复制角色包 ----
if not exist "%SAKURA_DIR%\characters" mkdir "%SAKURA_DIR%\characters"
xcopy /E /I /Y "%BASE_DIR%characters\ikaros" "%SAKURA_DIR%\characters\ikaros" >nul
echo [2/4] 角色包 ikaros 已安装。

REM ---- 3. 复制插件 ----
if not exist "%SAKURA_DIR%\plugins" mkdir "%SAKURA_DIR%\plugins"
xcopy /E /I /Y "%BASE_DIR%plugins\dsh_watcher" "%SAKURA_DIR%\plugins\dsh_watcher" >nul
echo [3/4] 插件 dsh_watcher 已安装。

REM ---- 4. 复制 TTS 桥 ----
if not exist "%SAKURA_DIR%\tools\edge_tts_bridge" mkdir "%SAKURA_DIR%\tools\edge_tts_bridge"
xcopy /E /I /Y "%BASE_DIR%tools\edge_tts_bridge" "%SAKURA_DIR%\tools\edge_tts_bridge" >nul
echo [4/4] TTS 桥已安装。

REM ---- 5. 安装 Python 依赖到 Sakura 运行时 ----
set "PYTHON_EXE=%SAKURA_DIR%\runtime\python.exe"
if not exist "%PYTHON_EXE%" (
    echo.
    echo [提示] 未找到 %PYTHON_EXE%
    echo        请确认 Sakura 已解压完整 Release 包（含 runtime 目录）。
    echo        依赖安装请手动执行：
    echo        "%SAKURA_DIR%\runtime\python.exe" -m pip install zstandard edge-tts
) else (
    echo [5/4] 安装依赖 (zstandard, edge-tts) ...
    "%PYTHON_EXE%" -m pip install zstandard edge-tts
)

echo.
echo ============================================================
echo  安装完成！
echo
echo  1. 启动 TTS 桥：     start_tts_bridge.bat
echo  2. 启动 Sakura：     start.bat
echo  3. 首次启动请按引导配置：
echo     - 选择角色「伊卡洛斯」
echo     - API：智谱 GLM-4-Flash（免费）
echo         Base URL: https://open.bigmodel.cn/api/paas/v4
echo         Model:    glm-4-flash
echo     - TTS：provider 选 gpt-sovits（外置），
echo         api_url: http://127.0.0.1:9880/tts
echo ============================================================
echo.
pause
