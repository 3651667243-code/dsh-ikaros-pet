# -*- coding: utf-8 -*-
"""event_summarizer.py —— 把 DSH 会话日志事件（SessionEventMap）整理成
桌宠模型能读懂的中文短摘要。

输入：session.jsonl 里的一行 JSON（事件对象）。
输出：人类可读的一句话摘要 + 一个"事件类别"（用于主动发言规则）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

# 主动发言规则关注的事件类别
CATEGORY_WORKFLOW_DONE = "workflow_done"
CATEGORY_GOAL_DONE = "goal_done"
CATEGORY_TOOL_FAILED = "tool_failed"
CATEGORY_APPROVAL_ASKED = "approval_asked"
CATEGORY_INFO = "info"


@dataclass(frozen=True)
class SummarizedEvent:
    category: str
    summary: str
    seq: int = 0
    time: str = ""


def _text(value: Any, limit: int = 40) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\n", " ").replace("\r", " ")
    if len(text) > limit:
        text = text[:limit] + "…"
    return text


def _data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data") or {}
    return data if isinstance(data, dict) else {}


def _tool_result_details(data: dict[str, Any]) -> tuple[bool, str]:
    """从 tool/result 的 data 里提取 (是否成功, 简要结果文本)。"""
    message = data.get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return True, ""
    is_error = False
    texts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("isError"):
            is_error = True
        inner = block.get("content")
        if isinstance(inner, list):
            for part in inner:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(str(part.get("text") or ""))
    return (not is_error), _text(" ".join(texts), 60)


def summarize_event(
    raw: str | dict[str, Any],
    tool_names: dict[str, str] | None = None,
) -> SummarizedEvent | None:
    """解析一行事件；无法识别或无需关注的返回 None。

    tool_names：可选的 callId → 工具名 映射；tool/call 事件会就地更新它，
    tool/result 事件用同一 callId 反查工具名。
    """
    if isinstance(raw, str):
        try:
            event = json.loads(raw)
        except (ValueError, TypeError):
            return None
    else:
        event = raw
    if not isinstance(event, dict):
        return None

    etype = str(event.get("type") or "")
    data = _data(event)
    seq = int(event.get("seq") or 0)
    time = _text(event.get("time") or "", 24)
    call_id = _text(data.get("callId"), 64)

    # ---- 对话 ----
    if etype == "user/message":
        content = data.get("content")
        text = ""
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = str(block.get("text") or "")
                    break
        return SummarizedEvent(CATEGORY_INFO, f"主人发来消息：「{_text(text)}」", seq, time)
    if etype == "assistant/message":
        return SummarizedEvent(CATEGORY_INFO, "Agent 完成了一次回复。", seq, time)

    # ---- Agent 步骤 ----
    if etype == "turn/start":
        return SummarizedEvent(CATEGORY_INFO, "Agent 开始新一轮思考。", seq, time)
    if etype == "turn/end":
        return SummarizedEvent(CATEGORY_INFO, "Agent 完成了一轮思考。", seq, time)
    if etype == "step/start":
        return SummarizedEvent(CATEGORY_INFO, "Agent 进入下一步处理。", seq, time)
    if etype == "step/end":
        return SummarizedEvent(CATEGORY_INFO, "Agent 完成一步处理。", seq, time)

    # ---- 工具 ----
    if etype == "tool/call":
        name = _text(data.get("name"))
        if tool_names is not None and call_id:
            tool_names[call_id] = name
        args = _text(data.get("arguments"), 60)
        return SummarizedEvent(CATEGORY_INFO, f"Agent 正在调用工具 {name}（{args}）", seq, time)
    if etype == "tool/result":
        name = _text(data.get("name") or data.get("toolName"))
        if not name:
            # tool/result 的 callId 在 data.message.source.callId 里
            message = data.get("message")
            source = message.get("source") if isinstance(message, dict) else None
            result_call_id = (
                _text(source.get("callId"), 64)
                if isinstance(source, dict)
                else ""
            )
            if tool_names is not None and result_call_id:
                name = tool_names.get(result_call_id, "")
        ok, detail = _tool_result_details(data)
        if ok:
            return SummarizedEvent(CATEGORY_INFO, f"工具 {name} 执行成功。", seq, time)
        return SummarizedEvent(CATEGORY_TOOL_FAILED, f"工具 {name} 执行失败：{detail}", seq, time)

    # ---- 工作流 ----
    if etype == "tool-workflow/run-start":
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        name = _text(meta.get("name") or data.get("name"), 30)
        return SummarizedEvent(CATEGORY_INFO, f"主人启动了一个工作流：「{name}」", seq, time)
    if etype == "tool-workflow/run-end":
        stop_reason = _text(data.get("stopReason") or data.get("status") or data.get("error") or "completed")
        if str(stop_reason).lower() in ("completed", "success", "done", "完成"):
            return SummarizedEvent(CATEGORY_WORKFLOW_DONE, "工作流结束了：完成", seq, time)
        return SummarizedEvent(CATEGORY_TOOL_FAILED, f"工作流结束了：{stop_reason}", seq, time)
    if etype == "tool-workflow/agent-start":
        return SummarizedEvent(CATEGORY_INFO, "工作流派出一个子代理开始干活。", seq, time)
    if etype == "tool-workflow/agent-end":
        return SummarizedEvent(CATEGORY_INFO, "工作流的一个子代理完成了任务。", seq, time)

    # ---- 目标 / 任务 ----
    if etype == "goal/change":
        goal = data.get("goal") if isinstance(data.get("goal"), dict) else {}
        operation = _text(data.get("operation") or goal.get("operation"))
        phase = _text(goal.get("phase") or data.get("phase") or data.get("status"))
        objective = _text(goal.get("objective") or data.get("objective"), 40)
        if operation in ("complete", "completed", "done") or phase in ("complete", "completed"):
            return SummarizedEvent(CATEGORY_GOAL_DONE, f"目标完成了：{objective}", seq, time)
        return SummarizedEvent(CATEGORY_INFO, f"目标状态更新（{operation or phase}）：{objective}", seq, time)
    if etype == "todo/write":
        return SummarizedEvent(CATEGORY_INFO, "Agent 更新了任务清单。", seq, time)

    # ---- 授权 ----
    if etype == "approval/asked":
        tool = _text(data.get("tool") or data.get("name"), 30)
        return SummarizedEvent(CATEGORY_APPROVAL_ASKED, f"Agent 请求主人批准操作（{tool}）", seq, time)
    if etype == "approval/decided":
        granted = bool(data.get("granted") or data.get("allowed"))
        return SummarizedEvent(
            CATEGORY_INFO,
            "主人的授权被批准了。" if granted else "主人的授权被拒绝了。",
            seq,
            time,
        )

    # ---- 子代理 ----
    if etype == "subagent/descriptor":
        return SummarizedEvent(CATEGORY_INFO, "Agent 派出一个子代理去处理任务。", seq, time)

    # ---- 会话 ----
    if etype == "session/title":
        return SummarizedEvent(CATEGORY_INFO, f"会话标题：「{_text(data.get('title'))}」", seq, time)

    return None
