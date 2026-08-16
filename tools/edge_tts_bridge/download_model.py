# -*- coding: utf-8 -*-
"""download_model.py —— 下载伊卡洛斯 VITS 声线模型权重（model.pth）。

模型来源：HuggingFace `Ikaros521/moe-tts`（saved_model/19/，config.json 已随仓库提供）。
⚠️ 该模型是 **Gated（受限）模型**：下载前需要：
  1) 注册 HuggingFace 账号，并在浏览器打开
     https://huggingface.co/Ikaros521/moe-tts 点击「Agree and access repository」同意条款；
  2) 生成访问令牌（Settings → Access Tokens，需 read 权限）；
  3) 下载时提供令牌（二选一）：
     - 环境变量：set HF_TOKEN=hf_xxxx
     - 参数：      python download_model.py --token hf_xxxx
模型权重涉及声线版权，不入库；仅供个人使用，禁止再分发与商用。

用法：
  python download_model.py [--mirror] [--token hf_xxx] [--output 目录]
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "vits" / "saved_model" / "19"
MODEL_NAME = "model.pth"
EXPECTED_MB = 150  # 模型约 151MB，用于下载后大小 sanity check

HF_BASE = "https://huggingface.co/Ikaros521/moe-tts/resolve/main/saved_model/19/model.pth"
MIRROR_BASE = "https://hf-mirror.com/Ikaros521/moe-tts/resolve/main/saved_model/19/model.pth"
MODEL_PAGE = "https://huggingface.co/Ikaros521/moe-tts"


def _download(url: str, target: Path, token: str) -> None:
    headers = {"User-Agent": "ikaros-dsh-pet/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    print(f"[download] {url}")
    print(f"[download] 保存到 {target}")
    req = urllib.request.Request(url, headers=headers)
    tmp = target.with_suffix(".part")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 1048576:.1f} / {total / 1048576:.1f} MB", end="", flush=True)
    except urllib.error.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        if exc.code == 401:
            raise RuntimeError(
                "401 Unauthorized：该模型是受限（Gated）模型。请先在浏览器打开 "
                f"{MODEL_PAGE} 同意条款，然后生成 Access Token 并用 --token / HF_TOKEN 提供。"
            ) from exc
        raise
    print()
    tmp.replace(target)


def main() -> int:
    parser = argparse.ArgumentParser(description="下载伊卡洛斯 VITS 模型权重 model.pth（Gated 模型）")
    parser.add_argument("--mirror", action="store_true", help="使用 hf-mirror.com 镜像")
    parser.add_argument("--token", default="", help="HuggingFace Access Token（或设 HF_TOKEN）")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出目录")
    args = parser.parse_args()

    token = args.token.strip() or os.environ.get("HF_TOKEN", "").strip()

    target = args.output / MODEL_NAME
    if target.exists() and target.stat().st_size > EXPECTED_MB * 1024 * 1024:
        print(f"[download] 已存在：{target}（{target.stat().st_size / 1048576:.1f} MB），跳过")
        return 0
    try:
        args.output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[download] 无法创建输出目录 {args.output}：{exc}")
        return 1

    if not token:
        print(
            "[download] 提示：这是 Gated 模型。若 401，请按脚本头部说明同意条款并生成 Access Token，"
            "再用 --token 或 HF_TOKEN 提供。"
        )
    url = MIRROR_BASE if args.mirror else HF_BASE
    try:
        _download(url, target, token)
    except Exception as exc:  # noqa: BLE001
        print(f"[download] 失败：{exc}")
        if not args.mirror:
            print("[download] 可尝试镜像：python download_model.py --mirror --token hf_xxx")
        return 1

    size_mb = target.stat().st_size / 1048576
    if size_mb < EXPECTED_MB * 0.8:
        print(f"[download] 警告：文件偏小（{size_mb:.1f} MB），可能下载不完整")
        return 1
    print(f"[download] 完成：{target}（{size_mb:.1f} MB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
