# -*- coding: utf-8 -*-
"""edge-tts 语音桥 —— 让 Sakura Desktop Pet 通过标准 GPT-SoVITS 外置接口
使用微软 Edge 神经语音（免费）进行合成。

协议对齐（app/voice/tts_synthesis.py / tts_service.py）：
  GET  /                        -> 200 文本（Sakura 就绪探测）
  GET  /set_gpt_weights         -> 200（edge-tts 无权重概念，返回空成功）
  GET  /set_sovits_weights      -> 200
  POST /tts                     -> 音频字节（wav），请求体为 JSON：
        {"text": "...", "text_lang": "ja", "ref_audio_path": "...", ...}
        除 text / text_lang 外的字段（参考音频等）全部忽略。

用法：
  pip install edge-tts
  python server.py                 # 默认 127.0.0.1:9880
  python server.py --port 9881 --ja-voice ja-JP-NanamiNeural --zh-voice zh-CN-XiaoyiNeural
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import edge_tts
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "缺少 edge-tts 依赖，请先执行：pip install edge-tts\n"
    )
    raise

DEFAULT_JA_VOICE = "ja-JP-NanamiNeural"   # 日文女声（偏安静、适合三无系角色）
DEFAULT_ZH_VOICE = "zh-CN-XiaoyiNeural"   # 中文女声
DEFAULT_PORT = 9880                        # 与 GPT-SoVITS 常用端口一致


def _text_lang_to_voice(text_lang: str, ja_voice: str, zh_voice: str) -> str:
    lang = (text_lang or "").strip().lower()
    if lang.startswith("zh"):
        return zh_voice
    return ja_voice


async def _synthesize(text: str, voice: str, rate: str, volume: str, proxy: str | None) -> bytes:
    """调用 edge-tts 合成，返回 wav 字节（edge-tts 输出为 MP3，转为 WAV）。"""
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume, proxy=proxy)
    chunks: list[bytes] = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    audio = b"".join(chunks)
    if audio[:4] == b"RIFF":
        # 已经是 WAV（理论上 edge-tts 输出 MP3，这里做兼容）
        return audio
    return _mp3_to_wav(audio)


def _mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """用 miniaudio 把 MP3 解码为 16bit PCM 的 WAV（Sakura 校验 RIFF 头）。"""
    try:
        import io
        import wave

        import miniaudio

        decoded = miniaudio.decode(
            mp3_bytes,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=1,
            sample_rate=24000,
        )
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(decoded.sample_rate)
            wav_file.writeframes(decoded.samples)
        return buffer.getvalue()
    except Exception:  # noqa: BLE001 - 转换失败时原样返回，让 Sakura 自行判定
        return mp3_bytes


class Bridge:
    """线程安全的合成器；Sakura 串行调用，这里加锁防止 edge-tts 并发问题。"""

    def __init__(self, ja_voice: str, zh_voice: str, rate: str, volume: str, proxy: str | None) -> None:
        self.ja_voice = ja_voice
        self.zh_voice = zh_voice
        self.rate = rate
        self.volume = volume
        self.proxy = proxy
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

    def start(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=self._loop.run_forever, name="edge-tts-loop", daemon=True
        )
        self._loop_thread.start()

    def synthesize(self, text: str, text_lang: str) -> bytes:
        assert self._loop is not None
        voice = _text_lang_to_voice(text_lang, self.ja_voice, self.zh_voice)
        with self._lock:
            return asyncio.run_coroutine_threadsafe(
                _synthesize(text, voice, self.rate, self.volume, self.proxy),
                self._loop,
            ).result(timeout=120)


class _Handler(BaseHTTPRequestHandler):
    server_version = "IkarosEdgeTTSBridge/1.0"
    bridge: Bridge  # class attribute, 由工厂注入

    # ---- helpers ----

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

    def log_message(self, fmt: str, *args: object) -> None:  # 精简日志
        sys.stderr.write(f"[edge-tts-bridge] {fmt % args}\n")

    # ---- routes ----

    def do_GET(self) -> None:  # noqa: N802 (http.server 约定)
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/health"):
            self._send_text(200, "ok")
        elif path in ("/set_gpt_weights", "/set_sovits_weights"):
            # edge-tts 没有模型权重概念：返回空成功，Sakura 会跳过后续
            self._send_json(200, {"success": True, "code": 0})
        else:
            self._send_text(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path != "/tts":
            self._send_text(404, "not found")
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json(400, {"success": False, "message": f"bad request: {exc}"})
            return

        text = str(payload.get("text") or "").strip()
        if not text:
            self._send_json(400, {"success": False, "message": "empty text"})
            return
        text_lang = str(payload.get("text_lang") or "ja")
        try:
            audio = self.bridge.synthesize(text, text_lang)
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            self._send_json(500, {"success": False, "message": str(exc)})
            return
        if not audio:
            self._send_json(500, {"success": False, "message": "empty audio"})
            return
        self._send_bytes(200, audio, "audio/wav")


def main() -> int:
    parser = argparse.ArgumentParser(description="edge-tts 语音桥（Sakura GPT-SoVITS 兼容外置服务）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--ja-voice", default=DEFAULT_JA_VOICE)
    parser.add_argument("--zh-voice", default=DEFAULT_ZH_VOICE)
    parser.add_argument("--rate", default="+0%", help="语速，如 +10% / -10%")
    parser.add_argument("--volume", default="+0%", help="音量，如 +10% / -10%")
    parser.add_argument(
        "--proxy",
        default=None,
        help="HTTP(S) 代理地址（如 http://127.0.0.1:7890）。网络受限时需要。",
    )
    args = parser.parse_args()

    bridge = Bridge(args.ja_voice, args.zh_voice, args.rate, args.volume, args.proxy)
    bridge.start()

    handler = type("IkarosHandler", (_Handler,), {"bridge": bridge})
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/tts"
    print(f"[edge-tts-bridge] 就绪：{url}  (ja={args.ja_voice}, zh={args.zh_voice})")
    print("[edge-tts-bridge] 在 Sakura 设置中将 TTS 指向该地址即可使用。Ctrl+C 退出。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if bridge._loop is not None:
            bridge._loop.call_soon_threadsafe(bridge._loop.stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
