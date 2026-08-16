# -*- coding: utf-8 -*-
"""vits_server.py —— 伊卡洛斯 VITS 语音桥（GPT-SoVITS 兼容协议）。

后端：HuggingFace Ikaros521/moe-tts 的 ikaros VITS 模型（早见沙织声线训练），
模型文件位于本目录 vits/saved_model/19/（model.pth + config.json）。

协议对齐（与 edge_tts_bridge 相同）：
  GET  /                   -> 200 文本（Sakura 就绪探测）
  GET  /set_gpt_weights    -> 200（无权重概念，返回空成功）
  GET  /set_sovits_weights -> 200
  POST /tts                -> wav 字节（22050Hz 16bit 单声道）
        请求体 JSON：{"text": "...", "text_lang": "ja", ...}（其余字段忽略）

用法：
  python vits_server.py [--port 9880] [--device auto|cpu|cuda]
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import urllib.parse
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import torch

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "vits" / "saved_model" / "19"
MODEL_PATH = MODEL_DIR / "model.pth"
CONFIG_PATH = MODEL_DIR / "config.json"


def _prepare_vits_path() -> None:
    """把 vits/ 目录加入 sys.path，使 models/text/commons 等模块可顶层导入。"""
    vits_dir = str(BASE_DIR / "vits")
    if vits_dir not in sys.path:
        sys.path.insert(0, vits_dir)


class IkarosVITS:
    """伊卡洛斯 VITS 合成器（懒加载 + 串行推理）。"""

    def __init__(
        self,
        device: str = "auto",
        noise_scale: float = 0.5,
        noise_scale_w: float = 0.7,
    ) -> None:
        self.device = device
        self.noise_scale = noise_scale
        self.noise_scale_w = noise_scale_w
        self._lock = threading.Lock()
        self._model = None
        self._hps_ns = None
        self._text_to_sequence = None
        self._speaker_id = 0  # config.speakers["ikaros"]
        self._ready = False
        self._load_error: str | None = None

    def ensure_ready(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            if self._load_error is not None:
                return  # 加载已失败：不再反复重试（health 返回 503 说明原因）
            try:
                self._load()
            except Exception as exc:  # noqa: BLE001
                self._load_error = str(exc)
                import traceback

                traceback.print_exc()
                print(f"[vits] 模型加载失败：{exc}")
                print("[vits] 请确认模型文件存在：", MODEL_PATH)
                print("[vits] 若使用 cuda 失败，可用 --device cpu 重试")

    @property
    def ready(self) -> bool:
        return self._ready

    def _load(self) -> None:
        print("[vits] 加载伊卡洛斯模型...")
        _prepare_vits_path()
        import importlib

        import commons  # noqa: F401  确保依赖模块先加载
        import models
        import utils
        from text import text_to_sequence

        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        from types import SimpleNamespace

        hps = SimpleNamespace(
            data=SimpleNamespace(
                text_cleaners=config["data"]["text_cleaners"],
                max_wav_value=float(config["data"]["max_wav_value"]),
                sampling_rate=int(config["data"]["sampling_rate"]),
                add_blank=bool(config["data"]["add_blank"]),
            ),
            model=config["model"],
            symbols=config["symbols"],
        )
        self._hps_ns = hps

        device = self._resolve_device()
        n_speakers = int(config["data"].get("n_speakers", 0)) or len(config.get("speakers", {}))
        # vits-fast 模型：PosteriorEncoder 用 linear spectrogram（filter_length//2+1 维），
        # segment_size = train.segment_size // hop_length（见 moe-tts app.py 的构造方式）
        spec_channels = config["data"]["filter_length"] // 2 + 1
        segment_size = config["train"]["segment_size"] // config["data"]["hop_length"]
        model = models.SynthesizerTrn(
            len(config["symbols"]),
            spec_channels,
            segment_size,
            n_speakers=n_speakers,
            **config["model"],
        )
        utils.load_checkpoint(str(MODEL_PATH), model, None)
        model.eval()
        model.to(device)
        self._model = model
        self._device = device
        self._text_to_sequence = text_to_sequence
        self._ready = True
        print(f"[vits] 模型加载完成，设备={device}")

    def _resolve_device(self) -> torch.device:
        if self.device == "cpu":
            return torch.device("cpu")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    def synthesize(self, text: str, text_lang: str) -> bytes:
        self.ensure_ready()
        with self._lock:
            hps = self._hps_ns
            # 按文本内容自动检测语言（比依赖 text_lang 更可靠）：
            # 含日文假名 → 日语；否则 → 中文。避免"日文音素器读中文"。
            import re

            if re.search(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]", text):
                marked = f"[JA]{text}[JA]"
            else:
                marked = f"[ZH]{text}[ZH]"
            sequence = self._text_to_sequence(marked, hps.symbols, hps.data.text_cleaners)
            if not sequence:
                raise ValueError("文本转音素序列为空")
            # add_blank 配置：音素间插入 0 分隔符（moe-tts get_text 的 intersperse）
            if hps.data.add_blank:
                sequence = [item for pair in zip([0] * len(sequence), sequence) for item in pair] + [0]
            x_tst = torch.LongTensor(sequence).unsqueeze(0).to(self._device)
            x_tst_lengths = torch.LongTensor([len(sequence)]).to(self._device)
            sid = torch.LongTensor([self._speaker_id]).to(self._device)
            with torch.no_grad():
                audio = self._model.infer(
                    x_tst,
                    x_tst_lengths,
                    sid=sid,
                    noise_scale=self.noise_scale,
                    noise_scale_w=self.noise_scale_w,
                    length_scale=1.0,
                )[0][0]
            audio_np = audio.float().cpu().numpy()
            # 裁剪到 int16 范围，防止超出 [-32768, 32767] 时环绕失真
            pcm = np.clip(audio_np * hps.data.max_wav_value, -32768, 32767).astype(np.int16)
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(hps.data.sampling_rate)
                wav_file.writeframes(pcm.tobytes())
            return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="伊卡洛斯 VITS 语音桥（GPT-SoVITS 兼容）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9880)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--noise-scale", type=float, default=0.5, help="合成噪声（越低越干净，0.3-0.6 常用）")
    parser.add_argument("--noise-scale-w", type=float, default=0.7, help="时长预测噪声")
    args = parser.parse_args()

    vits = IkarosVITS(device=args.device, noise_scale=args.noise_scale, noise_scale_w=args.noise_scale_w)
    # 启动时后台预加载模型
    loader = threading.Thread(target=vits.ensure_ready, name="vits-loader", daemon=True)
    loader.start()

    handler = type(
        "VitsHandler",
        (_Handler,),
        {"vits": vits},
    )
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        print(
            f"[vits] 启动失败：端口 {args.port} 被占用（{exc}）。\n"
            f"[vits] 可能有实例已在运行：netstat -ano | findstr :{args.port}\n"
            f"[vits] 或换端口重试：--port 9881"
        )
        return 1
    server.timeout = 0.5  # serve_forever 轮询间隔，配合 socket 超时
    print(f"[vits] 伊卡洛斯语音桥就绪：http://{args.host}:{args.port}/tts (设备={args.device})")
    print("[vits] 在 Sakura 设置中将 TTS 指向该地址即可使用。Ctrl+C 退出。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


class _Handler(BaseHTTPRequestHandler):
    server_version = "IkarosVITSBridge/1.0"
    vits: IkarosVITS  # class attribute

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, data: object) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_text(self, status: int, text: str) -> None:
        self._send_bytes(status, text.encode("utf-8"), "text/plain; charset=utf-8")

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"[vits-bridge] {fmt % args}\n")

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/health"):
            vits = getattr(self, "vits", None)
            ready = vits is not None and vits.ready
            error = getattr(vits, "_load_error", "") if vits is not None else ""
            if ready:
                self._send_text(200, "ok")
            else:
                self._send_json(503, {"success": False, "message": f"模型未就绪：{error}"})
        elif path in ("/set_gpt_weights", "/set_sovits_weights"):
            self._send_json(200, {"success": True, "code": 0})
        else:
            self._send_text(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path != "/tts":
            self._send_text(404, "not found")
            return
        try:
            raw_length = self.headers.get("Content-Length")
            length = int(raw_length) if raw_length else 0
            if length < 0 or length > 2 * 1024 * 1024:
                self._send_json(413, {"success": False, "message": "request body too large"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                self._send_json(400, {"success": False, "message": "payload must be a JSON object"})
                return
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json(400, {"success": False, "message": f"bad request: {exc}"})
            return
        text = str(payload.get("text") or "").strip()
        if not text:
            self._send_json(400, {"success": False, "message": "empty text"})
            return
        text_lang = str(payload.get("text_lang") or "ja")
        print(f"[vits] TTS 文本: {text[:40]!r}... (text_lang={text_lang})", flush=True)
        try:
            audio = self.vits.synthesize(text, text_lang)
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            self._send_json(500, {"success": False, "message": "TTS 合成失败"})
            return
        if not audio:
            self._send_json(500, {"success": False, "message": "empty audio"})
            return
        self._send_bytes(200, audio, "audio/wav")


if __name__ == "__main__":
    raise SystemExit(main())
