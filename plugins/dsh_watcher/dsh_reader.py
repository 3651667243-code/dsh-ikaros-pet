# -*- coding: utf-8 -*-
"""dsh_reader.py —— 增量读取 DeepSeek Harness 会话事件日志。

日志位置：~/.dsh/sessions/<workspace-encoded>/<session-id>/session.jsonl.zstd
格式：zstd 压缩的 JSONL（每行一个会话事件，字段含 type / seq / payload / time）。

设计：
- 轮询扫描 sessions 目录，按最后修改时间选择"最新活跃"的会话文件；
- 文件内容变化时用 zstandard 解压并解析，按事件 seq 去重，
  只把新增事件交给回调（事件摘要 + 原始事件）。
- 全程只读，不修改 DSH 的任何数据。

依赖：zstandard（install.bat 会安装到 Sakura 运行时）。
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("dsh_watcher")

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover
    zstd = None  # type: ignore[assignment]


DEFAULT_DSH_HOME = Path.home() / ".dsh"
SESSIONS_DIR_NAME = "sessions"
LOG_FILE_NAME = "session.jsonl.zstd"

EventCallback = Callable[[dict[str, Any]], None]


def find_latest_session_log(dsh_home: Path, workspace_keyword: str = "") -> Path | None:
    """在 sessions 目录下找最新写入的会话日志文件。

    workspace_keyword 非空时，优先匹配目录名包含该关键字的会话。
    """
    sessions_dir = dsh_home / SESSIONS_DIR_NAME
    if not sessions_dir.is_dir():
        return None

    candidates: list[Path] = []
    for path in sessions_dir.rglob(LOG_FILE_NAME):
        try:
            if path.stat().st_size > 0:
                candidates.append(path)
        except OSError:
            continue

    if workspace_keyword:
        keyword = workspace_keyword.replace("\\", "/").lower()
        keyword_dir = f"-{keyword}-".replace("/", "~002f").lower()
        matching = [
            p
            for p in candidates
            if keyword_dir in p.as_posix().lower() or keyword.lower() in p.as_posix().lower()
        ]
        if matching:
            candidates = matching

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _decompress_log(path: Path, offset: int = 0) -> tuple[str, int]:
    """解压 zstd 会话日志为文本；返回 (文本, 已读取的文件字节数)。

    DSH 会把会话事件分批压缩成**多个独立 zstd frame 追加写入**同一个文件，
    因此必须逐 frame 连续解压。offset > 0 时只解压从该字节起的新增 frame
    （增量读取；文件被重写/变小时不适用，调用方需自行全量重读）。
    """
    if zstd is None:
        raise RuntimeError("缺少 zstandard 依赖，请先安装：pip install zstandard")
    with open(path, "rb") as fh:
        if offset > 0:
            fh.seek(offset)
        raw = fh.read()
    if not raw:
        return "", offset
    dctx = zstd.ZstdDecompressor()
    dobj = dctx.decompressobj()
    parts: list[bytes] = []
    rest = raw
    consumed = 0
    while rest:
        try:
            chunk = dobj.decompress(rest)
        except zstd.ZstdError:
            break
        parts.append(chunk)
        consumed += len(rest) - len(dobj.unused_data)
        rest = dobj.unused_data
        if not rest:
            break
        dobj = dctx.decompressobj()
    parts.append(dobj.flush())
    return b"".join(parts).decode("utf-8", errors="replace"), offset + consumed


def _parse_events(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            import json

            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get("type"):
            events.append(event)
    return events


class DSHLogReader:
    """后台轮询线程：监控最新会话日志，把新增事件交给回调。"""

    def __init__(
        self,
        callback: EventCallback,
        *,
        dsh_home: Path | None = None,
        workspace_keyword: str = "",
        poll_interval_seconds: float = 5.0,
        max_initial_events: int = 20,
    ) -> None:
        self.callback = callback
        self.dsh_home = Path(dsh_home) if dsh_home else DEFAULT_DSH_HOME
        self.workspace_keyword = workspace_keyword
        self.poll_interval = max(1.0, float(poll_interval_seconds))
        self.max_initial_events = max(1, int(max_initial_events))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_path: Path | None = None
        self._last_seen_seq = -1
        self._seen_seqs: set[int] = set()
        self._read_offset = 0
        self._started_at = time.time()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="dsh-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        log.info("DSH 日志监听已启动：%s", self.dsh_home)
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("DSH 日志轮询失败：%s", exc)
            self._stop.wait(self.poll_interval)

    def _poll_once(self) -> None:
        path = find_latest_session_log(self.dsh_home, self.workspace_keyword)
        if path is None:
            return
        try:
            size = path.stat().st_size
            mtime = path.stat().st_mtime
        except OSError:
            return
        if path != self._current_path:
            # 切换会话：全量重读
            self._current_path = path
            self._read_offset = 0
        elif size < self._read_offset:
            # 文件被重写（压缩/compact）：全量重读
            self._read_offset = 0
        elif mtime == getattr(self, "_last_mtime", None) and size == getattr(
            self, "_last_size", None
        ):
            return
        self._last_mtime = mtime
        self._last_size = size
        try:
            text, consumed = _decompress_log(path, offset=self._read_offset)
            self._read_offset = max(self._read_offset, consumed)
        except Exception as exc:  # noqa: BLE001
            log.warning("解压会话日志失败 %s：%s", path, exc)
            return
        events = _parse_events(text)
        fresh = 0
        booting = time.time() - self._started_at < 3
        if booting:
            events = events[-self.max_initial_events :]
        for event in events:
            seq = int(event.get("seq") or -1)
            if seq in self._seen_seqs:
                continue
            if len(self._seen_seqs) > 2000:
                self._seen_seqs = set(sorted(self._seen_seqs)[-1000:])
            self._seen_seqs.add(seq)
            try:
                self.callback(event)
            except Exception as exc:  # noqa: BLE001
                log.warning("事件回调异常：%s", exc)
            fresh += 1
        log.debug("会话 %s 新增事件 %d 条", path.name, fresh)
