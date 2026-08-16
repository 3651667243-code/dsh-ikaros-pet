# -*- coding: utf-8 -*-
"""dsh_watcher 回归测试：zstd 多帧扫描/解码、损坏回退、工作区过滤、脱敏、非法 seq。

运行：<Sakura>/runtime/python.exe -m pytest tests/ -q
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest
import zstandard as zstd

# 仓库根（tests/ 的上一级）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins.dsh_watcher.dsh_reader import (  # noqa: E402
    ZSTD_MAGIC,
    DSHLogReader,
    _parse_events,
    context_percent,
    decode_frames,
    find_latest_session_log,
    scan_zstd_frames,
)
from plugins.dsh_watcher.event_summarizer import (  # noqa: E402
    _redact,
    summarize_event,
)


def _zstd_frames(*texts: str) -> bytes:
    """每段文本压缩成一个独立 zstd 帧。"""
    cctx = zstd.ZstdCompressor()
    return b"".join(cctx.compress(t.encode("utf-8")) for t in texts)


def _event_line(etype: str, seq: int, **data_extra) -> str:
    return json.dumps(
        {"type": etype, "seq": seq, "time": "2026-01-01T00:00:00+08:00", "data": data_extra},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# 帧边界扫描
# ---------------------------------------------------------------------------


class TestScanFrames:
    def test_single_frame(self) -> None:
        buf = _zstd_frames("hello")
        frames, torn = scan_zstd_frames(buf)
        assert len(frames) == 1
        assert frames[0] == (0, len(buf))
        assert torn is None

    def test_multi_frame(self) -> None:
        buf = _zstd_frames("a", "b", "c")
        frames, torn = scan_zstd_frames(buf)
        assert len(frames) == 3
        assert torn is None
        assert frames[-1][1] == len(buf)

    def test_torn_tail_frame(self) -> None:
        buf = _zstd_frames("完整帧")
        torn = buf + b"\x28\xb5\x2f\xfd"  # 追加半个帧头
        frames, torn_start = scan_zstd_frames(torn)
        assert len(frames) == 1
        assert torn_start is not None
        # 完整帧结束位置 = 原 buf 长度
        assert frames[0][1] == len(buf)

    def test_garbage_after_frame(self) -> None:
        buf = _zstd_frames("ok") + b"\x00\x01\x02"
        frames, torn_start = scan_zstd_frames(buf)
        assert len(frames) == 1
        assert torn_start == len(_zstd_frames("ok"))

    def test_empty(self) -> None:
        frames, torn = scan_zstd_frames(b"")
        assert frames == []
        assert torn is None


# ---------------------------------------------------------------------------
# 解码与解析
# ---------------------------------------------------------------------------


class TestDecode:
    def test_multi_frame_roundtrip(self) -> None:
        buf = _zstd_frames(_event_line("user/message", 1), _event_line("tool/call", 2))
        text = decode_frames(buf)
        assert "user/message" in text and "tool/call" in text

    def test_parse_events_filters_by_type(self) -> None:
        lines = [
            _event_line("user/message", 1, content=[{"type": "text", "text": "你好"}]),
            _event_line("chunk/delta", 2, content="不关注"),
            '{"type": "user/message", "seq": 3, "data": {"content": [{"type": "text", "text": "x"}]}}',
        ]
        events = _parse_events("\n".join(lines))
        assert [e["seq"] for e in events] == [1, 3]

    def test_parse_events_skips_broken_json(self) -> None:
        events = _parse_events('{"type": "user/message", "seq": 1, broken')
        assert events == []

    def test_parse_events_includes_request_context(self) -> None:
        # request/context 是上下文占用统计的事件类型，必须通过白名单过滤
        lines = [
            _event_line(
                "request/context",
                1,
                provider="deepseek-official",
                model="deepseek-v4-flash",
                contextWindow=1000000,
            ),
            _event_line("assistant/message", 2, turn=1, step=1),
        ]
        events = _parse_events("\n".join(lines))
        assert [e["seq"] for e in events] == [1, 2]


# ---------------------------------------------------------------------------
# 上下文占用百分比（与 DSH Web UI 口径一致）
# ---------------------------------------------------------------------------


class TestContextPercent:
    def test_basic(self) -> None:
        assert context_percent(126000, 1000000) == 13
        assert context_percent(0, 1000000) == 0

    def test_clamped_to_100(self) -> None:
        assert context_percent(2_000_000, 1_000_000) == 100

    def test_invalid_inputs(self) -> None:
        assert context_percent(None, 1000000) is None
        assert context_percent(-1, 1000000) is None
        assert context_percent(100, 0) is None
        assert context_percent("abc", 1000) is None
        assert context_percent(100, "1000") == 10  # 数字字符串可解析


# ---------------------------------------------------------------------------
# 工作区过滤（隐私：严格匹配）
# ---------------------------------------------------------------------------


class TestFindLatest:
    def test_no_matching_keyword_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "sessions" / "session-workspace-a").mkdir(parents=True)
        (tmp_path / "sessions" / "session-workspace-a" / "session.jsonl.zstd").write_bytes(
            _zstd_frames(_event_line("user/message", 1))
        )
        # 关键字无匹配 → 必须返回 None（绝不回退读取其他工作区）
        assert find_latest_session_log(tmp_path, "ikaros") is None

    def test_keyword_match(self, tmp_path: Path) -> None:
        (tmp_path / "sessions" / "session-ikaros-proj").mkdir(parents=True)
        target = tmp_path / "sessions" / "session-ikaros-proj" / "session.jsonl.zstd"
        target.write_bytes(_zstd_frames(_event_line("user/message", 1)))
        result = find_latest_session_log(tmp_path, "ikaros")
        assert result == target

    def test_ignores_non_session_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "sessions" / "not-a-session").mkdir(parents=True)
        (tmp_path / "sessions" / "not-a-session" / "session.jsonl.zstd").write_bytes(b"x")
        assert find_latest_session_log(tmp_path, "") is None


# ---------------------------------------------------------------------------
# 摘要脱敏与健壮性
# ---------------------------------------------------------------------------


class TestSummarize:
    def test_redact_key_patterns(self) -> None:
        assert "sk-abc12345" not in _redact("key sk-abc12345xyz")
        assert "github_pat_" not in _redact("github_pat_11ABCdefghijklmnopQRSTuvwxyz1234567890")
        assert "me@example.com" not in _redact("联系 me@example.com 谢谢")
        assert _redact("普通文本 123") == "普通文本 123"

    def test_illegal_seq_does_not_crash(self) -> None:
        ev = {"type": "goal/change", "seq": "abc", "data": {"operation": "complete", "goal": {"objective": "测试"}}}
        r = summarize_event(ev)
        assert r is not None and r.category == "goal_done"

    def test_missing_seq_ok(self) -> None:
        ev = {"type": "turn/start", "data": {}}
        r = summarize_event(ev)
        assert r is not None

    def test_tool_names_cleaned_after_result(self) -> None:
        names: dict[str, str] = {}
        call = {"type": "tool/call", "seq": 1, "data": {"callId": "c1", "name": "web_search", "arguments": "{}"}}
        result = {"type": "tool/result", "seq": 2, "data": {"message": {"source": {"callId": "c1"}}, "content": [{"type": "text", "text": "ok"}]}}
        summarize_event(call, names)
        assert names == {"c1": "web_search"}
        summarize_event(result, names)
        assert names == {}

    def test_user_message_redacted(self) -> None:
        ev = {"type": "user/message", "seq": 1, "data": {"content": [{"type": "text", "text": "我的 key 是 sk-abcdefgh123456 别外传"}]}}
        r = summarize_event(ev)
        assert "sk-abcdefgh123456" not in (r.summary if r else "")


# ---------------------------------------------------------------------------
# 损坏帧：decode 抛错（reader 会走全量回退路径）
# ---------------------------------------------------------------------------


class TestCorruption:
    def test_decode_frames_raises_on_corrupt(self) -> None:
        good = _zstd_frames("abc")
        corrupt = good[: len(good) // 2] + b"\xff" * 8
        with pytest.raises(zstd.ZstdError):
            decode_frames(corrupt)


# ---------------------------------------------------------------------------
# 上下文占用 bootstrap：重启落在轮中时，首轮全量扫描带出窗口/压力值
# ---------------------------------------------------------------------------


class TestBootstrap:
    def test_bootstrap_from_full_scan(self, tmp_path: Path) -> None:
        (tmp_path / "sessions" / "session-ikaros-proj").mkdir(parents=True)
        target = tmp_path / "sessions" / "session-ikaros-proj" / "session.jsonl.zstd"
        # 事件流：request/context 在文件头部（重放尾 40 条拿不到），assistant/message 在尾部
        lines = [
            _event_line(
                "request/context", 1,
                provider="deepseek-official", model="deepseek-v4-flash", contextWindow=1000000,
            ),
            _event_line("assistant/message", 2, turn=1, step=1, usage={
                "inputTokens": 120000, "cacheReadTokens": 30000, "cacheWriteTokens": 0,
            }),
        ]
        target.write_bytes(_zstd_frames("\n".join(lines)))

        received: list[str] = []
        reader = DSHLogReader(received.append, dsh_home=tmp_path, workspace_keyword="ikaros",
                              poll_interval_seconds=1.0, max_initial_events=40)
        reader.start()
        try:
            deadline = time.monotonic() + 10
            while not reader.bootstrapped and time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            reader.stop()
        assert reader.bootstrapped
        assert reader.bootstrap_window == 1000000
        assert reader.bootstrap_pressure == 150000
        assert context_percent(reader.bootstrap_pressure, reader.bootstrap_window) == 15

    def test_bootstrap_missing_fields(self, tmp_path: Path) -> None:
        (tmp_path / "sessions" / "session-ikaros-proj").mkdir(parents=True)
        target = tmp_path / "sessions" / "session-ikaros-proj" / "session.jsonl.zstd"
        target.write_bytes(_zstd_frames(_event_line("user/message", 1, content="hi")))
        reader = DSHLogReader(lambda ev: None, dsh_home=tmp_path, workspace_keyword="ikaros",
                              poll_interval_seconds=1.0)
        reader.start()
        try:
            deadline = time.monotonic() + 10
            while not reader.bootstrapped and time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            reader.stop()
        assert reader.bootstrapped
        assert reader.bootstrap_window is None
        assert reader.bootstrap_pressure is None
