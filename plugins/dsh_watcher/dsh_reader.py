# -*- coding: utf-8 -*-
"""dsh_reader.py —— 增量读取 DeepSeek Harness 会话事件日志。

日志位置：~/.dsh/sessions/<workspace-encoded>/<session-id>/session.jsonl.zstd
格式：zstd 压缩的 JSONL，DSH 每 ~200ms 把一批事件压缩成一个**独立 zstd 帧**追加写入。

设计（v2，依据实证审计优化）：
- **帧边界结构扫描**（不解压）：定位完整帧区间与 torn 尾帧，offset 永远推进到
  最后一个完整帧边界，杜绝"frame 中间偏移解压失败丢事件"。
- **增量解码**：正常路径只解新帧（毫秒级）；stream_reader(read_across_frames=True)
  让全量回退也只需 ~35ms（旧实现逐帧 decompressobj 需 20s+）。
- **每文件独立状态**：同一工作区多会话并发写入时不再按 mtime 跳变导致反复全量重读。
- **按文件回放限制**：首次/重置只投递尾部 N 条，并抑制主动发言（plugin 侧）。
- 只读，不修改 DSH 的任何数据。

依赖：zstandard（install.bat 会安装到 Sakura 运行时）。
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import zstandard as zstd

log = logging.getLogger("dsh_watcher")

DEFAULT_DSH_HOME = Path.home() / ".dsh"
SESSIONS_DIR_NAME = "sessions"
LOG_FILE_NAME = "session.jsonl.zstd"
ZSTD_MAGIC = 0xFD2FB528

EventCallback = Callable[[dict[str, Any]], None]

# summarize_event 关注的事件类型白名单（其他类型跳过 json.loads）
_INTERESTING_TYPES = frozenset(
    {
        "user/message",
        "assistant/message",
        "turn/start",
        "turn/end",
        "step/start",
        "step/end",
        "tool/call",
        "tool/result",
        "tool-workflow/run-start",
        "tool-workflow/run-end",
        "tool-workflow/agent-start",
        "tool-workflow/agent-end",
        "goal/change",
        "todo/write",
        "approval/asked",
        "approval/decided",
        "subagent/descriptor",
        "session/title",
    }
)


def find_latest_session_log(dsh_home: Path, workspace_keyword: str = "") -> Path | None:
    """在 sessions 目录下找最新写入的**主会话**日志文件。

    只考虑目录名以 ``session-`` 开头的主会话；子代理/工作流会话（UUID 目录名）
    包含父会话 seed 事件且写入频繁，会导致读错文件。
    workspace_keyword 非空时，优先匹配目录名包含该关键字的会话。
    """
    sessions_dir = dsh_home / SESSIONS_DIR_NAME
    if not sessions_dir.is_dir():
        return None

    candidates: list[Path] = []
    for path in sessions_dir.rglob(LOG_FILE_NAME):
        try:
            if path.stat().st_size <= 0:
                continue
            session_dir = path.parent.name
            if not session_dir.startswith("session-"):
                continue
            candidates.append(path)
        except OSError:
            continue

    if workspace_keyword:
        keyword = workspace_keyword.replace("\\", "/").lower()
        matching = [
            p for p in candidates if keyword.lower() in p.as_posix().lower()
        ]
        if matching:
            candidates = matching

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def scan_zstd_frames(buf: bytes) -> tuple[list[tuple[int, int]], int | None]:
    """结构扫描 zstd 多帧，返回 (完整帧 [(start, end), ...], torn_start 或 None)。

    只解析帧头/块头，不解压；DSH 每帧带校验和（ZSTD_c_checksumFlag=1）。
    """
    frames: list[tuple[int, int]] = []
    offset = 0
    n = len(buf)
    while offset < n:
        start = offset
        if n - offset < 4 or int.from_bytes(buf[offset : offset + 4], "little") != ZSTD_MAGIC:
            return frames, start
        offset += 4
        if offset >= n:
            return frames, start
        d = buf[offset]
        offset += 1
        if d & 0x18:
            return frames, start  # reserved bits
        single = bool(d & 0x20)
        checksum = bool(d & 0x04)
        dict_flag = d & 0x03
        dict_bytes = 4 if dict_flag == 3 else dict_flag
        fcs_flag = d >> 6
        fcs_bytes = 1 if (fcs_flag == 0 and single) else (0 if fcs_flag == 0 else 1 << fcs_flag)
        header_rest = (0 if single else 1) + dict_bytes + fcs_bytes
        if n - offset < header_rest:
            return frames, start
        offset += header_rest
        while True:
            if n - offset < 3:
                return frames, start
            bh = int.from_bytes(buf[offset : offset + 3], "little")
            offset += 3
            last = bh & 1
            btype = (bh >> 1) & 3
            bsize = bh >> 3
            if btype == 3:
                return frames, start  # reserved block type
            payload = 1 if btype == 1 else bsize
            if n - offset < payload:
                return frames, start
            offset += payload
            if last:
                break
        if checksum:
            if n - offset < 4:
                return frames, start
            offset += 4
        frames.append((start, offset))
    return frames, None


def decode_frames(buf: bytes) -> str:
    """一次调用解完多帧（stream_reader 跨帧，实测比逐帧 decompressobj 快 ~240×）。"""
    with zstd.ZstdDecompressor().stream_reader(buf, read_across_frames=True) as reader:
        return reader.read().decode("utf-8", errors="replace")


def _parse_events(text: str) -> list[dict[str, Any]]:
    """解析 JSONL；先用类型白名单过滤，避免对海量 chunk 行做 json.loads。"""
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 12:
            continue
        # 快速取 type 字段（跳过非关注类型）
        colon = line.find('"type"')
        if colon < 0:
            continue
        rest = line[colon + 7 :]
        q = rest.find('"')
        if q < 0:
            continue
        end_q = rest.find('"', q + 1)
        if end_q < 0:
            continue
        etype = rest[q + 1 : end_q]
        if etype not in _INTERESTING_TYPES:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(event, dict) and event.get("type"):
            events.append(event)
    return events


@dataclass
class _FileState:
    """单个会话文件的增量读取状态。"""

    offset: int = 0
    identity: tuple[int, int] = (0, 0)
    size: int = -1
    mtime_ns: int = -1
    last_seq: int = -1
    seen: set[int] = field(default_factory=set)
    first_seen: bool = True
    poisoned_until: float = 0.0


class DSHLogReader:
    """后台轮询线程：监控最新主会话日志，把新增事件交给回调。"""

    def __init__(
        self,
        callback: EventCallback,
        *,
        dsh_home: Path | None = None,
        workspace_keyword: str = "",
        poll_interval_seconds: float = 5.0,
        max_initial_events: int = 20,
        max_seen: int = 5000,
    ) -> None:
        self.callback = callback
        self.dsh_home = Path(dsh_home) if dsh_home else DEFAULT_DSH_HOME
        self.workspace_keyword = workspace_keyword
        self.poll_interval = max(1.0, float(poll_interval_seconds))
        self.max_initial_events = max(1, int(max_initial_events))
        self.max_seen = max(500, int(max_seen))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._states: dict[Path, _FileState] = {}
        self._started_at = time.time()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return  # 防重入：避免插件重载时线程泄漏
        self._thread = threading.Thread(
            target=self._run, name="dsh-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

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
            st = path.stat()
        except OSError:
            return
        state = self._states.get(path)
        if state is None:
            state = self._states[path] = _FileState()

        identity = (st.st_ino, st.st_dev)
        fresh_identity = state.first_seen or identity != state.identity or st.st_size < state.offset
        if fresh_identity:
            state = self._states[path] = _FileState(identity=identity)
        elif st.st_mtime_ns == state.mtime_ns and st.st_size == state.size:
            return  # 无变化，空转
        state.identity = identity
        state.size = st.st_size
        state.mtime_ns = st.st_mtime_ns

        if time.time() < state.poisoned_until:
            return  # 损坏退避

        try:
            with open(path, "rb") as fh:
                fh.seek(state.offset)
                tail = fh.read()
        except OSError as exc:
            log.warning("读取会话日志失败 %s：%s", path, exc)
            return

        if len(tail) < 4 or int.from_bytes(tail[:4], "little") != ZSTD_MAGIC:
            # offset 不再是帧边界（文件被替换/重写）→ 全量重扫
            state.first_seen = True
            state.offset = 0
            state.last_seq = -1
            try:
                with open(path, "rb") as fh:
                    whole = fh.read()
            except OSError:
                return
            tail = whole

        frames, torn_start = scan_zstd_frames(tail)
        complete_end = torn_start if torn_start is not None else len(tail)
        try:
            text = decode_frames(tail[:complete_end])
        except zstd.ZstdError:
            # 解码失败（校验和/损坏）→ 全量重读一次
            log.warning("会话日志解码失败，全量重读 %s", path)
            try:
                with open(path, "rb") as fh:
                    whole = fh.read()
                frames0, torn0 = scan_zstd_frames(whole)
                text = decode_frames(whole[: (torn0 or len(whole))])
                state.first_seen = True
                state.offset = 0
                state.last_seq = -1
                state.seen.clear()
            except (zstd.ZstdError, OSError):
                state.poisoned_until = time.time() + 60
                log.warning("会话日志损坏，退避 60s：%s", path)
                return

        events = _parse_events(text)
        booting = state.first_seen
        if booting:
            events = events[-self.max_initial_events :]
        fresh = 0
        for event in events:
            seq = int(event.get("seq") or -1)
            if seq >= 0:
                if seq <= state.last_seq:
                    continue
                if seq in state.seen:
                    continue
            if len(state.seen) > self.max_seen:
                state.seen = set(sorted(state.seen)[-int(self.max_seen * 0.8) :])
            if seq >= 0:
                state.seen.add(seq)
                if seq > state.last_seq:
                    state.last_seq = seq
            try:
                self.callback(event)
            except Exception as exc:  # noqa: BLE001
                log.warning("事件回调异常：%s", exc)
            fresh += 1
        state.first_seen = False
        state.offset += complete_end
        if fresh:
            log.debug("会话 %s 新增事件 %d 条", path.name, fresh)
