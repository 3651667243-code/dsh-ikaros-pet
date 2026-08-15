#!/bin/bash
# WSL 里前台运行伊卡洛斯 VITS 语音桥（阻塞保持发行版活跃）
# 脚本自动定位自身目录，无需硬编码；venv 路径可用 VITS_VENV 环境变量覆盖
export HOME=/root
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VITS_VENV="${VITS_VENV:-/root/ikaros-vits-venv}"
exec "$VITS_VENV/bin/python" vits_server.py --port 9880 --host 0.0.0.0 --noise-scale 0.3 --noise-scale-w 0.5
