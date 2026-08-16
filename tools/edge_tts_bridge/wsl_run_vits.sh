#!/bin/bash
# WSL 里前台运行伊卡洛斯 VITS 语音桥（阻塞保持发行版活跃）
# 自动定位脚本目录，不依赖固定发行版名/用户目录：
#   VITS_VENV    venv 路径（默认 $HOME/ikaros-vits-venv，其次 /root/ikaros-vits-venv）
#   VITS_PORT    监听端口（默认 9880）
#   VITS_HOST    监听地址（默认 0.0.0.0，WSL2 localhost 转发需要）
#   VITS_AUTH    可选访问令牌（配合 vits_server.py --auth-token）
# 用法示例：
#   VITS_AUTH=mysecret wsl_run_vits.sh
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "$VITS_VENV" ] && [ -x "$VITS_VENV/bin/python" ]; then
  PY="$VITS_VENV/bin/python"
elif [ -x "$HOME/ikaros-vits-venv/bin/python" ]; then
  PY="$HOME/ikaros-vits-venv/bin/python"
elif [ -x "/root/ikaros-vits-venv/bin/python" ]; then
  PY="/root/ikaros-vits-venv/bin/python"
else
  echo "[vits] 未找到 venv python（可设 VITS_VENV 指定，或按 docs/SETUP.md 创建）" >&2
  exit 1
fi

ARGS=(--port "${VITS_PORT:-9880}" --host "${VITS_HOST:-0.0.0.0}" --noise-scale 0.3 --noise-scale-w 0.5)
if [ -n "$VITS_AUTH" ]; then
  ARGS+=(--auth-token "$VITS_AUTH")
fi

exec "$PY" vits_server.py "${ARGS[@]}"
