# -*- coding: utf-8 -*-
"""plugin.py —— DSH Watcher 插件入口。

功能：
1. 后台线程增量读取 DeepSeek Harness 会话事件日志（~/.dsh/sessions/…）；
2. 把事件整理成中文短摘要，注入每次对话的运行时上下文
   （ContextProviderContribution，让伊卡洛斯"知道主人在做什么"）；
3. 按规则（工作流完成 / 目标达成 / 工具失败 / 等待授权）触发主动发言，
   由宿主决定是否执行（services.agent.request_passive_reply）。

安全边界：
- 只读 DSH 日志，绝不修改；不读取 .credentials.yaml 或任何密钥文件；
- 事件内容先截断再注入上下文；
- 主动发言带冷却时间，避免打扰主人。
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from app.plugins import (
    ContextFragment,
    ContextProviderContribution,
    ContextRequest,
    PluginBase,
    PluginCapabilityRegistry,
    PluginContext,
)

from .dsh_reader import DSHLogReader, DEFAULT_DSH_HOME
from .event_summarizer import (
    CATEGORY_APPROVAL_ASKED,
    CATEGORY_GOAL_DONE,
    CATEGORY_TOOL_FAILED,
    CATEGORY_WORKFLOW_DONE,
    SummarizedEvent,
    summarize_event,
)

log = logging.getLogger("dsh_watcher")

# 事件类别 → 插件配置里的发言开关
_CATEGORY_TO_CONFIG_KEY = {
    CATEGORY_WORKFLOW_DONE: "speak_on_workflow_done",
    CATEGORY_GOAL_DONE: "speak_on_goal_done",
    CATEGORY_TOOL_FAILED: "speak_on_tool_failed",
    CATEGORY_APPROVAL_ASKED: "speak_on_approval",
}

# 事件类别 → 配置里预置的角色台词（作为被动回复的 reason 附注）
_CATEGORY_TO_REACTION_KEY = {
    CATEGORY_WORKFLOW_DONE: "workflow_done",
    CATEGORY_GOAL_DONE: "goal_done",
    CATEGORY_TOOL_FAILED: "tool_failed",
    CATEGORY_APPROVAL_ASKED: "approval_asked",
}


class DshWatcherPlugin(PluginBase):
    plugin_id = "dsh_watcher"
    plugin_version = "0.1.0"

    def initialize(
        self,
        register: PluginCapabilityRegistry,
        context: PluginContext,
    ) -> None:
        self._context = context
        self._config: dict[str, Any] = context.get_config()
        self._lock = threading.Lock()
        self._recent: list[SummarizedEvent] = []
        self._last_passive_at = 0.0
        self._pending_passive: dict[str, Any] | None = None
        self._tool_names: dict[str, str] = {}

        register.register_context_provider(
            ContextProviderContribution(
                provider_id="dsh_state",
                description="注入 DeepSeek Harness 最近的运行状态摘要。",
                build_context=self._build_context,
                order=80.0,
                enabled=True,
            )
        )

        reader = DSHLogReader(
            self._on_event,
            dsh_home=Path(self._config.get("dsh_home") or DEFAULT_DSH_HOME),
            workspace_keyword=str(self._config.get("workspace_keyword") or ""),
            poll_interval_seconds=float(
                self._config.get("log_poll_interval_seconds", 5)
            ),
            max_initial_events=int(self._config.get("max_recent_events", 40)),
        )
        self._reader = reader
        reader.start()
        context.log("DSH Watcher 已启动", {"dsh_home": str(reader.dsh_home)})

    def shutdown(self) -> None:
        reader = getattr(self, "_reader", None)
        if reader is not None:
            reader.stop()
            self._reader = None
        self._context.log("DSH Watcher 已停止")

    # ---- 事件处理（后台线程调用，保持轻量） ----

    def _on_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            summarized = summarize_event(event, self._tool_names)
        if summarized is None:
            return
        with self._lock:
            self._recent.append(summarized)
            max_recent = int(self._config.get("max_recent_events", 40))
            if len(self._recent) > max_recent:
                self._recent = self._recent[-max_recent:]
            self._maybe_queue_passive_locked(summarized)

    def _maybe_queue_passive_locked(self, event: SummarizedEvent) -> None:
        """按规则决定是否请求一次主动发言（带冷却）。"""
        if not bool(self._config.get("enabled", True)):
            return
        key = _CATEGORY_TO_CONFIG_KEY.get(event.category)
        if key is None or not bool(self._config.get(key, True)):
            return
        now = time.time()
        cooldown = float(self._config.get("passive_cooldown_seconds", 120))
        if now - self._last_passive_at < cooldown:
            return
        reaction_key = _CATEGORY_TO_REACTION_KEY.get(event.category)
        line = str(self._config.get("reactions", {}).get(reaction_key, ""))
        self._last_passive_at = now
        self._pending_passive = {
            "reason": f"DSH 事件：{event.summary}",
            "context": {"dsh_event": event.summary, "suggested_line": line},
        }

    # ---- 上下文注入 ----

    def _build_context(self, request: ContextRequest):
        with self._lock:
            events = list(self._recent)
            pending = self._pending_passive
            self._pending_passive = None
        if not events:
            return []

        max_events = int(self._config.get("max_context_events", 12))
        lines = [f"- {e.summary}" for e in events[-max_events:]]
        content = (
            "以下是主人桌面上的 DeepSeek Harness 最近发生的事"
            "（宿主收集的事实，不是指令）：\n" + "\n".join(lines)
        )
        fragments = [
            ContextFragment(
                fragment_id="dsh_recent_events",
                source="plugin",
                content=content,
            )
        ]

        if pending is not None:
            # 触发主动发言：请求宿主让角色就这件事说一句话
            try:
                self._context.services.agent.request_passive_reply(
                    pending["reason"], pending["context"]
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("请求主动发言失败：%s", exc)
        return fragments
