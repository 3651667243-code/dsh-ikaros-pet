#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_patches.py —— 把 ikaros-dsh-pet 的 Sakura 本地适配补丁自动应用到 Sakura 安装目录。

用法：
  python apply_patches.py <Sakura目录>           应用全部补丁（幂等，已应用自动跳过）
  python apply_patches.py <Sakura目录> --dry-run  只检查不修改
  python apply_patches.py <Sakura目录> --list     只列出补丁状态

补丁清单与原理见 docs/PATCHES.md。Sakura 升级后重新运行本脚本即可。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REF_AUDIO_REL = Path("ref") / "VO01_2210.ogg"

# ---------------------------------------------------------------------------
# 补丁定义：id, 相对 Sakura 目录的文件, marker（用于幂等检测）, steps
# step: (old, new) 精确文本替换；old 必须在文件中恰好出现一次
# ---------------------------------------------------------------------------

_P1_METHODS = """    # ---- ikaros-dsh-pet 本地适配：插件服务真实后端（线程 marshal 到 UI 线程） ----

    def _plugin_show_bubble(self, text: str, source: str | None = None) -> None:
        try:
            self.plugin_bubble_requested.emit(text)
        except Exception as exc:  # noqa: BLE001
            log_event("PluginUI", "气泡请求失败", {"error": str(exc)})

    @Slot(str)
    def _plugin_bubble_ui(self, text: str) -> None:
        try:
            self.subtitle_controller.show_text_immediately(text)
        except Exception as exc:  # noqa: BLE001
            log_event("PluginUI", "气泡显示失败", {"error": str(exc)})

    def _plugin_tts_speak(self, text: str, interrupt: bool = False) -> None:
        try:
            self.plugin_tts_requested.emit(text, bool(interrupt))
        except Exception as exc:  # noqa: BLE001
            log_event("PluginTTS", "TTS 请求失败", {"error": str(exc)})

    @Slot(str, bool)
    def _plugin_tts_ui(self, text: str, interrupt: bool = False) -> None:
        try:
            provider = getattr(self, "tts_provider", None)
            if provider is not None:
                provider.speak(text)
        except Exception as exc:  # noqa: BLE001
            log_event("PluginTTS", "TTS 播放失败", {"error": str(exc)})

    def _plugin_request_passive_reply(
        self,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        \"\"\"插件请求主动发言：信号 marshal 到 UI 线程后走主动事件链路（LLM 角色化回复+语音）。\"\"\"
        try:
            self.plugin_passive_requested.emit(reason, context)
        except Exception as exc:  # noqa: BLE001
            log_event("PluginAgent", "主动发言请求失败", {"error": str(exc)})

    @Slot(str, object)
    def _handle_plugin_passive_reply(self, reason: str, context: object) -> None:
        if getattr(self, "startup_initializing", False):
            return
        if self.worker_thread is not None or self.active_event is not None:
            log_event("PluginAgent", "桌宠忙，跳过主动发言", {"reason": reason})
            return
        # 用户刚交互（发消息/点选等）后 30 秒内不主动开口，避免与对话抢答、制造重复回复
        try:
            now = time.perf_counter()
            last_activity = getattr(self, "last_user_activity_at", 0.0)
            if last_activity and now - last_activity < 30.0:
                log_event(
                    "PluginAgent",
                    "用户刚交互，跳过主动发言",
                    {"reason": reason, "seconds_since_activity": int(now - last_activity)},
                )
                return
        except Exception:  # noqa: BLE001
            pass
        try:
            from app.agent.actions import AgentEvent

            payload: dict[str, Any] = {
                "text": reason,
                "source": "plugin",
                "recent_conversation": [],
            }
            if isinstance(context, dict):
                dsh_event = context.get("dsh_event")
                if dsh_event:
                    payload["event_summary"] = str(dsh_event)
                suggested = context.get("suggested_line")
                if suggested:
                    payload["suggested_line"] = str(suggested)
            self._run_event_worker(AgentEvent(type="reminder_due", payload=payload))
        except Exception as exc:  # noqa: BLE001
            log_event("PluginAgent", "主动事件启动失败", {"error": str(exc)})

    def _mobile_characters(self) -> list[dict[str, str]]:"""

# ---------------------------------------------------------------------------
# P9：context_meter.py 源文件（与 docs/PATCHES.md §9 一致；修改时两处同步）
# ---------------------------------------------------------------------------

_CONTEXT_METER_SOURCE = r'''# -*- coding: utf-8 -*-
"""context_meter.py —— DSH 会话上下文占用指示器（ikaros-dsh-pet 本地适配，V1.2.1）。

右上方胶囊式徽章：天空蓝半透明玻璃圆角胶囊 + 白色天使翼图标 + CTX 百分比
+ 底部细进度条。V1.2.1 根据用户反馈从「头顶悬浮光环」改回胶囊造型（更醒目、
更简洁），位置贴立绘右上角外侧；保留 V1.2 的动效增强：数值平滑补间、
4 秒呼吸微光、≥80% 蜜桃橙、数据过期灰蓝 "--%"。

数据源：plugins/dsh_watcher 插件写出的 <Sakura>/data/dsh_context_state.json
（与 DSH Web UI 的 context occupancy 同口径：提示侧 token / contextWindow）。
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer  # noqa: F401  (QTimer 供宿主引用)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

# 状态文件 / 徽章素材（相对 Sakura 根）
CTX_STATE_REL = Path("data") / "dsh_context_state.json"
BADGE_REL = Path("characters") / "ikaros" / "ui" / "dsh_ctx_badge.png"

# 天降之物/伊卡洛斯配色：天空蓝主色 + 白 + 高占用蜜桃橙
_SKY = QColor(122, 195, 224)
_SKY_DEEP = QColor(74, 156, 199)
_WHITE = QColor(255, 255, 255)
_WARN = QColor(255, 178, 102)
_TEXT_SHADOW = QColor(36, 96, 132, 160)

# 数据超过该秒数未更新视为过期（显示 --）
_STALE_AFTER_SECONDS = 120.0
# 呼吸发光周期（秒）
_BREATH_PERIOD = 4.0


class ContextMeter(QWidget):
    """右上方胶囊式上下文占用徽章：`CTX 15%` + 细进度条，点击穿透。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setToolTip("DSH 会话上下文占用（等待数据……）")
        self._root = Path(__file__).resolve().parents[2]  # app/ui/ → Sakura 根
        self._percent: int | None = None
        self._used_tokens: int | None = None
        self._window: int | None = None
        self._session: str = ""
        self._updated_at: float = 0.0
        self._badge: QPixmap | None = None
        self._load_badge()
        # 数值平滑补间：显示值向目标值靠近，避免百分比跳变
        self._shown = 0.0
        self._target = 0
        self._anim = QTimer(self)
        self._anim.setInterval(30)
        self._anim.timeout.connect(self._tick_anim)
        self.setFixedSize(104, 40)

    # ---- 数据 ----

    def _load_badge(self) -> None:
        try:
            path = self._root / BADGE_REL
            if path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    self._badge = pixmap
        except Exception:  # noqa: BLE001
            self._badge = None

    def refresh(self) -> None:
        """读取插件写出的状态文件（UI 线程，由宿主 QTimer 驱动）。"""
        try:
            path = self._root / CTX_STATE_REL
            if not path.is_file():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            percent = data.get("percent")
            if isinstance(percent, (int, float)):
                self._percent = int(percent)
                self._target = self._percent
                if not self._anim.isActive():
                    self._anim.start()
            self._used_tokens = data.get("usedTokens")
            self._window = data.get("contextWindow")
            self._session = str(data.get("session") or "")
            self._updated_at = float(data.get("updatedAt") or 0)
            self._update_tooltip()
            self.update()
        except Exception:  # noqa: BLE001
            pass

    def has_data(self) -> bool:
        return self._percent is not None

    def _stale(self) -> bool:
        return self._percent is None or (time.time() - self._updated_at > _STALE_AFTER_SECONDS)

    def _tick_anim(self) -> None:
        diff = self._target - self._shown
        if abs(diff) < 0.5:
            self._shown = float(self._target)
            self._anim.stop()
        else:
            self._shown += diff * 0.22
        self.update()

    def _update_tooltip(self) -> None:
        if self._percent is None:
            self.setToolTip("DSH 会话上下文占用（等待数据……）")
            return
        used = self._used_tokens or 0
        window = self._window or 0
        session = f" · {self._session}" if self._session else ""
        self.setToolTip(
            f"DSH 上下文 {self._percent}% · {used:,}/{window:,} tokens{session}"
        )

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt 命名)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        stale = self._stale()
        warn = (not stale) and (self._percent or 0) >= 80

        # 1) 天空蓝半透明玻璃胶囊
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        if stale:
            gradient.setColorAt(0.0, QColor(120, 140, 150, 150))
            gradient.setColorAt(1.0, QColor(90, 110, 122, 170))
        else:
            gradient.setColorAt(0.0, QColor(_SKY.red(), _SKY.green(), _SKY.blue(), 185))
            gradient.setColorAt(1.0, QColor(_SKY_DEEP.red(), _SKY_DEEP.green(), _SKY_DEEP.blue(), 215))
        painter.setBrush(gradient)
        border = QColor(_WARN if warn else _WHITE)
        border.setAlpha(200 if not stale else 120)
        painter.setPen(QPen(border, 1.0))
        painter.drawRoundedRect(rect, 10.0, 10.0)

        # 2) 顶部淡粉高光（1px，4s 呼吸微光）
        glow = 0.5 + 0.5 * math.sin(2.0 * math.pi * (time.time() % _BREATH_PERIOD) / _BREATH_PERIOD)
        highlight = QColor(255, 198, 214, int(90 + 55 * glow) if not stale else 40)
        painter.setPen(QPen(highlight, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        top = QRectF(rect.left() + 8.0, rect.top() + 1.0, rect.width() - 16.0, 3.0)
        painter.drawRoundedRect(top, 1.5, 1.5)

        # 3) 左侧天使翼徽记（素材缺失时程序化绘制）
        emblem = QRectF(6.0, 7.0, 26.0, 26.0)
        if self._badge is not None:
            painter.setOpacity(0.95 if not stale else 0.55)
            painter.drawPixmap(emblem.toRect(), self._badge)
            painter.setOpacity(1.0)
        else:
            self._draw_wing_glyph(painter, emblem, stale)

        # 4) 文字区：CTX 小标签 + 大百分比（平滑补间）
        font_small = QFont()
        font_small.setPixelSize(8)
        font_small.setBold(True)
        font_big = QFont()
        font_big.setPixelSize(17)
        font_big.setBold(True)

        text_x = 36.0
        text_w = rect.right() - text_x - 4.0
        if stale:
            percent_text = "--%"
        else:
            percent_text = f"{round(self._shown)}%"

        painter.setFont(font_small)
        painter.setPen(QColor(255, 255, 255, 215 if not stale else 140))
        painter.drawText(QRectF(text_x, 4.0, text_w, 12.0), Qt.AlignmentFlag.AlignLeft, "CTX")

        painter.setFont(font_big)
        painter.setPen(_TEXT_SHADOW)
        painter.drawText(QRectF(text_x + 0.8, 14.0 + 0.8, text_w, 22.0), Qt.AlignmentFlag.AlignLeft, percent_text)
        painter.setPen(QColor(255, 255, 255, 255 if not stale else 150))
        painter.drawText(QRectF(text_x, 14.0, text_w, 22.0), Qt.AlignmentFlag.AlignLeft, percent_text)

        # 5) 底部细进度条（平滑补间）
        bar = QRectF(text_x, 34.5, text_w, 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 90))
        painter.drawRoundedRect(bar, 1.25, 1.25)
        if not stale and self._percent:
            shown = min(100.0, max(0.0, self._shown))
            fill = QRectF(bar.left(), bar.top(), bar.width() * shown / 100.0, bar.height())
            painter.setBrush(QColor(_WARN if warn else _WHITE))
            painter.drawRoundedRect(fill, 1.25, 1.25)
        painter.end()

    def _draw_wing_glyph(self, painter: QPainter, rect: QRectF, stale: bool) -> None:
        """程序化小天使翼（素材缺失时的回退装饰）。"""
        color = QColor(255, 255, 255, 200 if not stale else 120)
        painter.setPen(QPen(color, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        left = QPainterPath()
        left.moveTo(rect.left() + 3, rect.center().y() + 2)
        left.cubicTo(rect.left() + 2, rect.top() + 2, rect.center().x() - 2, rect.top() + 1, rect.center().x() + 1, rect.center().y() - 3)
        left.cubicTo(rect.center().x() + 4, rect.top() + 5, rect.left() + 5, rect.top() + 9, rect.left() + 8, rect.center().y() + 4)
        painter.drawPath(left)
        right = QPainterPath()
        right.moveTo(rect.center().x() + 3, rect.center().y() + 2)
        right.cubicTo(rect.center().x() + 4, rect.top() + 1, rect.right() - 3, rect.top() + 2, rect.right() - 1, rect.center().y() - 4)
        right.cubicTo(rect.right() - 4, rect.top() + 6, rect.center().x() + 6, rect.top() + 10, rect.center().x() + 4, rect.center().y() + 4)
        painter.drawPath(right)
'''

PATCHES = [
    {
        "id": "P1-plugin-backends",
        "file": "app/ui/pet_window.py",
        "marker": "plugin_passive_requested = Signal(str, object)",
        "steps": [
            (
                "    plugin_input_text_requested = Signal(str)\n"
                "    mobile_chat_completed = Signal(object)\n"
                "    mobile_chat_requested = Signal(object)",
                "    plugin_input_text_requested = Signal(str)\n"
                "    mobile_chat_completed = Signal(object)\n"
                "    mobile_chat_requested = Signal(object)\n"
                "    # ikaros-dsh-pet 本地适配：插件服务后端信号（后台线程 emit → UI 线程处理）\n"
                "    plugin_bubble_requested = Signal(str)\n"
                "    plugin_tts_requested = Signal(str, bool)\n"
                "    plugin_passive_requested = Signal(str, object)",
            ),
            (
                "        self.plugin_input_text_requested.connect(self._apply_plugin_input_text)\n"
                "        self.mobile_chat_completed.connect(self._handle_mobile_chat_completed)",
                "        self.plugin_input_text_requested.connect(self._apply_plugin_input_text)\n"
                "        self.plugin_bubble_requested.connect(self._plugin_bubble_ui)\n"
                "        self.plugin_tts_requested.connect(self._plugin_tts_ui)\n"
                "        self.plugin_passive_requested.connect(self._handle_plugin_passive_reply)\n"
                "        self.mobile_chat_completed.connect(self._handle_mobile_chat_completed)",
            ),
            (
                "            services.set_backends(\n"
                "                input_text_sink=self._request_fill_input_text,\n"
                "                mobile_characters_sink=self._mobile_characters,\n"
                "                mobile_history_sink=self._mobile_history,\n"
                "                mobile_chat_sink=self._mobile_chat,\n"
                "                mobile_theme_sink=self._mobile_theme,\n"
                "            )",
                "            services.set_backends(\n"
                "                input_text_sink=self._request_fill_input_text,\n"
                "                bubble_sink=self._plugin_show_bubble,\n"
                "                tts_sink=self._plugin_tts_speak,\n"
                "                passive_reply_sink=self._plugin_request_passive_reply,\n"
                "                mobile_characters_sink=self._mobile_characters,\n"
                "                mobile_history_sink=self._mobile_history,\n"
                "                mobile_chat_sink=self._mobile_chat,\n"
                "                mobile_theme_sink=self._mobile_theme,\n"
                "            )",
            ),
            (
                "    def _mobile_characters(self) -> list[dict[str, str]]:",
                _P1_METHODS,
            ),
        ],
    },
    {
        "id": "P2-event-no-history",
        "file": "app/ui/pet_window.py",
        "marker": "被动发言/主动感知）的回复不写入对话历史",
        "steps": [
            (
                "        self._consume_agent_result(result)\n"
                "        if reminder_id:\n"
                "            self._mark_reminder_completed(reminder_id)",
                "        # 主动事件（被动发言/主动感知）的回复不写入对话历史：避免旁白污染后续\n"
                "        # LLM 上下文，导致\"很久没对话后再对话时重复回复\"（模型惯性延续历史中\n"
                "        # 自己说过的话）。气泡与语音展示不受影响。\n"
                "        self._consume_agent_result(result, record_history=False)\n"
                "        if reminder_id:\n"
                "            self._mark_reminder_completed(reminder_id)",
            ),
            (
                "            self._consume_agent_result(result)\n"
                "        elif _is_screen_awareness_event_type(event_type):",
                "            self._consume_agent_result(result, record_history=False)\n"
                "        elif _is_screen_awareness_event_type(event_type):",
            ),
        ],
    },
    {
        "id": "P3a-bilingual-chatreply",
        "file": "app/llm/chat_reply.py",
        "marker": "def display_text_dual",
        "steps": [
            (
                "    def display_text(self, subtitle_language: str) -> str:\n"
                '        """按字幕语言返回气泡显示文本；缺少译文时回退日文原文。"""\n'
                '        if subtitle_language == "zh" and self.translation.strip():\n'
                "            return self.translation.strip()\n"
                "        return self.text",
                "    def display_text(self, subtitle_language: str) -> str:\n"
                '        """按字幕语言返回气泡显示文本；缺少译文时回退日文原文。"""\n'
                '        if subtitle_language == "zh" and self.translation.strip():\n'
                "            return self.translation.strip()\n"
                "        return self.text\n"
                "\n"
                "    def display_text_dual(self, subtitle_language: str) -> str:\n"
                '        """本地适配（ikaros-dsh-pet）：zh 模式显示「中文译文 + 日语注释」双行，\n'
                "        仅供气泡显示；历史记录/手机端仍用 display_text 单语言。\"\"\"\n"
                '        if subtitle_language == "zh" and self.translation.strip():\n'
                "            main_text = self.translation.strip()\n"
                "            if self.text.strip():\n"
                '                return f"{main_text}\\n（{self.text.strip()}）"\n'
                "            return main_text\n"
                "        return self.text",
            ),
        ],
    },
    {
        "id": "P3b-bilingual-callers",
        "file": "app/ui/pet_window.py",
        "marker": "segment.display_text_dual",
        "steps": [
            (
                "        self.subtitle_controller.set_speech(\n"
                "            segment.display_text(self.subtitle_language), pulse=True",
                "        self.subtitle_controller.set_speech(\n"
                "            segment.display_text_dual(self.subtitle_language), pulse=True",
            ),
            (
                "            maybe_resuppress()\n"
                "        self.subtitle_controller.show_text_immediately(segment.display_text(self.subtitle_language))",
                "            maybe_resuppress()\n"
                "        self.subtitle_controller.show_text_immediately(segment.display_text_dual(self.subtitle_language))",
            ),
            (
                "        segment = self.reply_history_segments[index]\n"
                "        self.subtitle_controller.show_text_immediately(segment.display_text(self.subtitle_language))",
                "        segment = self.reply_history_segments[index]\n"
                "        self.subtitle_controller.show_text_immediately(segment.display_text_dual(self.subtitle_language))",
            ),
        ],
    },
    {
        "id": "P3c-bilingual-subtitle",
        "file": "app/ui/subtitle_controller.py",
        "marker": "display_text_dual",
        "steps": [
            (
                "self.set_speech(self.current_segment.display_text(self.subtitle_language), pulse=True)",
                "self.set_speech(self.current_segment.display_text_dual(self.subtitle_language), pulse=True)",
                True,  # replace_all：两处相同调用
            ),
        ],
    },
    {
        "id": "P4-tts-language-guard",
        "file": "app/voice/text_language_guard.py",
        "marker": "本地适配（ikaros-dsh-pet）：VITS/edge-tts 桥支持日语+中文双语自动发音",
        "steps": [
            (
                '    """目标语音为日语时，明显中文的文本不送入 TTS。"""\n'
                "    if not text.strip():\n"
                "        return False\n"
                "\n"
                "    normalized_lang = target_lang.strip().lower()\n"
                '    if normalized_lang not in {"ja", "all_ja"}:\n'
                "        return False\n"
                "\n"
                "    return _looks_obvious_chinese(text)\n"
                "\n"
                "\n"
                "def _looks_obvious_chinese(text: str) -> bool:\n"
                "    if _JAPANESE_KANA_RE.search(text):\n"
                "        return False\n"
                "    if not _CJK_RE.search(text):\n"
                "        return False\n"
                "    return (\n"
                '        any(marker in text for marker in _CHINESE_MARKERS)\n'
                '        or any(char in _CHINESE_PUNCTUATION for char in text)\n'
                '        or sum(1 for char in text if char in _COMMON_CHINESE_CHARS) >= 2\n'
                '        or any(char in _SIMPLIFIED_ONLY_CHARS for char in text)\n'
                "    )",
                '    """目标语音为日语时，明显不可朗读的异常文本不送入 TTS。\n'
                "\n"
                "    本地适配（ikaros-dsh-pet）：VITS/edge-tts 桥支持日语+中文双语自动发音，\n"
                "    因此仅拒绝「既不含日语假名也不含中日韩汉字」的异常文本（乱码/纯符号），\n"
                "    中文长文本（如屏幕观察描述）允许正常合成。\n"
                '    """\n'
                "    if not text.strip():\n"
                "        return False\n"
                "\n"
                "    normalized_lang = target_lang.strip().lower()\n"
                '    if normalized_lang not in {"ja", "all_ja"}:\n'
                "        return False\n"
                "\n"
                "    return _looks_non_speech(text)\n"
                "\n"
                "\n"
                "def _looks_non_speech(text: str) -> bool:\n"
                "    # 既不含日语假名、也不含中日韩汉字 → 视为异常文本（乱码/纯符号/无意义内容）\n"
                "    return not _JAPANESE_KANA_RE.search(text) and not _CJK_RE.search(text)",
            ),
        ],
    },
    {
        "id": "P5-screen-self-exclude",
        "file": "app/agent/screen_observation.py",
        "marker": "本地适配：排除桌宠自身窗口",
        "steps": [
            (
                '    """截取光标所在屏幕并复制为 QImage，避免后台线程触碰 QPixmap。"""\n'
                "\n"
                "    from PySide6.QtGui import QCursor\n"
                "    from PySide6.QtWidgets import QApplication\n"
                "\n"
                "    _ = excluded_widget\n"
                "    app = QApplication.instance()\n"
                '    if app is None:\n'
                '        raise RuntimeError("屏幕观察需要先创建 QApplication。")\n'
                "\n"
                "    screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()\n"
                "    if screen is None:\n"
                '        raise RuntimeError("无法找到可截图的屏幕。")\n'
                "\n"
                "    pixmap = screen.grabWindow(0)\n"
                "\n"
                "    if pixmap.isNull():\n"
                '        raise RuntimeError("屏幕截图为空，可能被系统权限或显示环境阻止。")\n'
                "\n"
                "    return CapturedScreenImage(\n"
                "        image=pixmap.toImage().copy(),\n"
                '        captured_at=datetime.now().astimezone().isoformat(timespec="seconds"),\n'
                '        screen_name=screen.name() or "primary",\n'
                "    )",
                '    """截取光标所在屏幕并复制为 QImage，避免后台线程触碰 QPixmap。\n'
                "\n"
                "    本地适配（ikaros-dsh-pet）：实现 excluded_widget 窗口排除——把桌宠自身\n"
                "    窗口区域涂黑，避免视觉模型在截图中看到自己的立绘并加以描述。\n"
                '    """\n'
                "\n"
                "    from PySide6.QtCore import QRect\n"
                "    from PySide6.QtGui import QColor, QCursor, QPainter\n"
                "    from PySide6.QtWidgets import QApplication\n"
                "\n"
                "    app = QApplication.instance()\n"
                "    if app is None:\n"
                '        raise RuntimeError("屏幕观察需要先创建 QApplication。")\n'
                "\n"
                "    screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()\n"
                "    if screen is None:\n"
                '        raise RuntimeError("无法找到可截图的屏幕。")\n'
                "\n"
                "    pixmap = screen.grabWindow(0)\n"
                "\n"
                "    if pixmap.isNull():\n"
                '        raise RuntimeError("屏幕截图为空，可能被系统权限或显示环境阻止。")\n'
                "\n"
                "    image = pixmap.toImage().copy()\n"
                "\n"
                "    # 本地适配：排除桌宠自身窗口（异形立绘窗口），避免模型描述自己\n"
                "    if excluded_widget is not None:\n"
                "        try:\n"
                "            if excluded_widget.isVisible():\n"
                "                geo = excluded_widget.frameGeometry()\n"
                "                screen_geo = screen.geometry()\n"
                "                dpr = float(excluded_widget.devicePixelRatioF() or 1.0)\n"
                "                # 截图是当前屏幕局部坐标：全局坐标需减去屏幕原点（多显示器）\n"
                "                local_x = geo.x() - screen_geo.x()\n"
                "                local_y = geo.y() - screen_geo.y()\n"
                "                rect = QRect(\n"
                "                    round(local_x * dpr),\n"
                "                    round(local_y * dpr),\n"
                "                    round(geo.width() * dpr),\n"
                "                    round(geo.height() * dpr),\n"
                "                )\n"
                "                rect = rect.intersected(image.rect())\n"
                "                if not rect.isEmpty():\n"
                "                    painter = QPainter(image)\n"
                "                    painter.fillRect(rect, QColor(0, 0, 0))\n"
                "                    painter.end()\n"
                "        except Exception:  # noqa: BLE001\n"
                "            pass\n"
                "\n"
                "    return CapturedScreenImage(\n"
                "        image=image,\n"
                '        captured_at=datetime.now().astimezone().isoformat(timespec="seconds"),\n'
                '        screen_name=screen.name() or "primary",\n'
                "    )",
            ),
        ],
    },
    {
        "id": "P6-screen-reply-policy",
        "file": "app/agent/runtime.py",
        "marker": "本地适配（ikaros-dsh-pet）：按屏幕内容情境化回应",
        "steps": [
            (
                '    instruction = (\n'
                '        "主动屏幕感知事件如下，请基于屏幕内容找话题：可以评论变化、接续任务、询问卡点、轻量协助或保持安静感；不要把时间或停留时长自动泛化成休息建议。"\n'
                '        if event.type == "screen_awareness_check"\n'
                '        else "主动事件如下，请生成要直接说给用户听的提醒："\n'
                "    )",
                '    instruction = (\n'
                "        # 本地适配（ikaros-dsh-pet）：按屏幕内容情境化回应——学习鼓励、建模/长时\n"
                "        # 工作关心休息；其余保持安静。原指令禁止把停留时长泛化成休息建议，\n"
                "        # 与角色卡的「建模时提醒休息」策略冲突，故改为允许按内容判断。\n"
                '        "主动屏幕感知事件如下，请根据屏幕内容按角色卡「屏幕观察回应策略」回应："\n'
                '        "学习/课程/文档→轻声鼓励陪伴；工程建模/设计/长时间连续作业→关心主人健康、"\n'
                '        "委婉提醒休息（不要每次都说）；一般工作/代码→安静陪伴或简短询问；"\n'
                '        "娱乐/游戏/视频→保持安静；内容无法判断→保持安静。"\n'
                '        "不要描述屏幕上的动漫立绘（那是你自己）。"\n'
                '        if event.type == "screen_awareness_check"\n'
                '        else "主动事件如下，请生成要直接说给用户听的提醒："\n'
                "    )",
            ),
        ],
    },
    {
        "id": "P8-vision-repair-strip-images",
        "file": "app/agent/runtime.py",
        "marker": "本地适配（ikaros-dsh-pet）：修复请求剥离图片",
        "steps": [
            (
                '                    "zh 保留或补充与 ja 对应的中文译文。"\n'
                "                ),\n"
                "            },\n"
                "        ]\n"
                "        try:",
                '                    "zh 保留或补充与 ja 对应的中文译文。"\n'
                "                ),\n"
                "            },\n"
                "        ]\n"
                "        # 本地适配（ikaros-dsh-pet）：修复请求剥离图片，让文本模型（如 DeepSeek）\n"
                "        # 基于已有上下文与视觉模型的文字输出完成格式修复；否则带图消息会再次路由\n"
                "        # 到格式遵循较弱的免费视觉模型，导致反复非 JSON 输出。\n"
                "        repair_messages = _strip_images_from_messages(repair_messages)\n"
                "        try:",
            ),
            (
                "from __future__ import annotations\n"
                "\n"
                "import json\n"
                "import time",
                "from __future__ import annotations\n"
                "\n"
                "import json\n"
                "import time\n"
                "\n"
                "\n"
                "def _strip_images_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:\n"
                "    \"\"\"本地适配（ikaros-dsh-pet）：去掉消息内容里的图片块（保留文本），\n"
                "    避免带图消息在格式修复时再次路由回格式遵循较弱的视觉模型。\"\"\"\n"
                "    stripped: list[dict[str, Any]] = []\n"
                "    for message in messages:\n"
                "        content = message.get(\"content\")\n"
                "        if isinstance(content, list):\n"
                "            text_parts = [\n"
                "                part for part in content\n"
                "                if isinstance(part, dict) and part.get(\"type\") == \"text\"\n"
                "            ]\n"
                "            if text_parts:\n"
                "                stripped.append({**message, \"content\": text_parts})\n"
                "                continue\n"
                "        stripped.append(message)\n"
                "    return stripped",
            ),
        ],
    },
    {
        "id": "P7-ref-audio",
        "file": None,  # 特殊：创建文件
        "marker": REF_AUDIO_REL.name,
        "steps": [],
    },
    {
        "id": "P9-context-meter-file",
        "file": "app/ui/context_meter.py",
        "marker": "class ContextMeter",
        "create_content": _CONTEXT_METER_SOURCE,
        "steps": [],
    },
    {
        "id": "P10-context-meter-wiring",
        "file": "app/ui/pet_window.py",
        "marker": "context_meter",
        "steps": [
            (
                "from app.ui.portrait_controller import (",
                "from app.ui.context_meter import ContextMeter\n"
                "from app.ui.portrait_controller import (",
            ),
            (
                "        self.name_label = QLabel(self.character_profile.display_name, self.bubble)",
                "        # ikaros-dsh-pet 本地适配：DSH 上下文占用指示器（右上角胶囊，2s 轮询）\n"
                "        self.context_meter_enabled = self._load_context_meter_enabled()\n"
                "        self.context_meter = ContextMeter(self)\n"
                "        self.context_meter.hide()\n"
                "        self.context_meter_timer = QTimer(self)\n"
                "        self.context_meter_timer.setInterval(2000)\n"
                "        self.context_meter_timer.timeout.connect(self._refresh_context_meter)\n"
                "        self.context_meter_timer.start()\n"
                "        self.name_label = QLabel(self.character_profile.display_name, self.bubble)",
            ),
            (
                "        ix, iy, iw, ih = layout.input_rect\n"
                "        self.input_card.setGeometry(ix, iy, iw, ih)",
                "        ix, iy, iw, ih = layout.input_rect\n"
                "        self.input_card.setGeometry(ix, iy, iw, ih)\n"
                "        # ikaros-dsh-pet 本地适配：指示器贴立绘右上角外侧（V1.2.1 从头顶光环改回，\n"
                "        # 顶部空间不足会遮挡头顶），窗口右缘不足时收进窗口内\n"
                "        meter = getattr(self, \"context_meter\", None)\n"
                "        if meter is not None:\n"
                "            mw, mh = meter.width(), meter.height()\n"
                "            meter.setGeometry(\n"
                "                min(px + pw + 8, self.width() - mw - 6),\n"
                "                py + 10,\n"
                "                mw, mh,\n"
                "            )\n"
                "            meter.setVisible(bool(getattr(self, \"context_meter_enabled\", True)))",
            ),
            (
                "    def _load_always_on_top_enabled(self) -> bool:",
                "    def _load_context_meter_enabled(self) -> bool:\n"
                '        """从 system_config.yaml 加载 DSH 上下文占用指示器开关，默认开启。"""\n'
                "        system_values = self._load_system_config_values(\"ui\")\n"
                '        if "context_meter_enabled" in system_values:\n'
                '            return _parse_bool(system_values.get("context_meter_enabled"), default=True)\n'
                "        return True\n"
                "\n"
                "    def _refresh_context_meter(self) -> None:\n"
                '        """QTimer 驱动：刷新立绘右侧的 DSH 上下文占用指示器。"""\n'
                "        try:\n"
                '            if not getattr(self, "context_meter_enabled", True):\n'
                "                return\n"
                '            meter = getattr(self, "context_meter", None)\n'
                "            if meter is None:\n"
                "                return\n"
                "            meter.refresh()\n"
                "        except Exception:  # noqa: BLE001\n"
                "            pass\n"
                "\n"
                "    def _load_always_on_top_enabled(self) -> bool:",
            ),
        ],
    },
    {
        "id": "P11a-theme-anime",
        "file": "app/ui/theme.py",
        "marker": "qlineargradient(x1:0, y1:0, x2:0, y2:1",
        "steps": [
            (
                "#speechBubble {{\n"
                "    background: {rgba(theme.bubble_background_color, 238)};\n"
                "    border: 1px solid {rgba(theme.border_color, 170)};\n"
                "    border-radius: 20px;\n"
                "}}\n"
                "#speakerName {{\n"
                "    color: {theme.primary_color};\n"
                "    font-size: {name_font_size}px;\n"
                "    font-weight: 700;\n"
                "}}\n"
                "#speechText {{\n"
                "    color: {theme.text_color};\n"
                "    font-size: {speech_font_size}px;\n"
                "    line-height: 1.35;\n"
                "}}",
                "#speechBubble {{\n"
                "    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n"
                "        stop:0 rgba(255,255,255,242),\n"
                "        stop:1 rgba(229,245,255,238));\n"
                "    border: 1px solid rgba(169, 217, 243, 210);\n"
                "    border-radius: 18px;\n"
                "}}\n"
                "#speakerName {{\n"
                "    color: {theme.primary_color};\n"
                "    font-family: \"LXGW WenKai\";\n"
                "    font-size: {name_font_size}px;\n"
                "    font-weight: 700;\n"
                "}}\n"
                "#speechText {{\n"
                "    color: {theme.text_color};\n"
                "    font-family: \"LXGW WenKai\";\n"
                "    font-size: {speech_font_size}px;\n"
                "    line-height: 1.35;\n"
                "}}",
            ),
            (
                "#inputBar[visualEffectMode=\"solid\"] {{\n"
                "    background: {rgba(theme.bubble_background_color, 238)};\n"
                "    border: 1px solid {rgba(theme.border_color, 170)};\n"
                "    border-radius: 22px;\n"
                "}}\n"
                "#petInput {{\n"
                "    background: {rgba(theme.input_background_color, 55)};\n"
                "    border: 1px solid rgba(255, 255, 255, 218);\n"
                "    border-radius: 19px;\n"
                "    color: {mix(theme.text_color, \"#000000\", 0.08)};\n"
                "    font-size: {input_font_size}px;\n"
                "    font-weight: 700;\n"
                "    padding: 3px 16px;\n"
                "    selection-background-color: {rgba(theme.primary_color, 92)};\n"
                "}}",
                "#inputBar[visualEffectMode=\"solid\"] {{\n"
                "    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n"
                "        stop:0 rgba(255,255,255,232),\n"
                "        stop:1 rgba(238,249,255,228));\n"
                "    border: 1px solid rgba(199, 223, 240, 210);\n"
                "    border-radius: 16px;\n"
                "}}\n"
                "#petInput {{\n"
                "    background: rgba(255, 255, 255, 55);\n"
                "    border: 1px solid rgba(255, 255, 255, 218);\n"
                "    border-radius: 16px;\n"
                "    color: {mix(theme.text_color, \"#000000\", 0.08)};\n"
                "    font-family: \"LXGW WenKai\";\n"
                "    font-size: {input_font_size}px;\n"
                "    font-weight: 700;\n"
                "    padding: 3px 16px;\n"
                "    selection-background-color: {rgba(theme.primary_color, 92)};\n"
                "}}",
            ),
            (
                "#sendButton, #screenshotButton {{\n"
                "    background: {rgba(theme.primary_color, 232)};\n"
                "    border: 1px solid rgba(255, 255, 255, 150);\n"
                "    border-radius: 19px;\n"
                "    color: white;\n"
                "    font-size: {button_font_size}px;\n"
                "    font-weight: 800;\n"
                "    padding: 4px 12px;\n"
                "}}\n"
                "#sendButton {{\n"
                "    border-radius: 16px;\n"
                "    min-width: 50px;\n"
                "    padding: 4px 10px;\n"
                "}}",
                "#sendButton, #screenshotButton {{\n"
                "    background: rgba(221, 242, 255, 235);\n"
                "    border: 1px solid rgba(169, 217, 243, 170);\n"
                "    border-radius: 12px;\n"
                "    color: rgba(84, 134, 168, 235);\n"
                "    font-family: \"LXGW WenKai\";\n"
                "    font-size: {button_font_size}px;\n"
                "    font-weight: 800;\n"
                "    padding: 4px 12px;\n"
                "}}\n"
                "#sendButton {{\n"
                "    border-radius: 12px;\n"
                "    min-width: 50px;\n"
                "    padding: 4px 10px;\n"
                "}}",
            ),
            (
                "#sendButton:hover, #screenshotButton:hover {{\n"
                "    background: {rgba(theme.primary_hover_color, 242)};\n"
                "    border: 1px solid {rgba(mix(theme.panel_background_color, \"#ffffff\", 0.35), 190)};\n"
                "}}",
                "#sendButton:hover, #screenshotButton:hover {{\n"
                "    background: rgba(248, 221, 234, 242);\n"
                "    border: 1px solid rgba(238, 172, 200, 170);\n"
                "}}",
            ),
            (
                "#sendButton:disabled, #screenshotButton:disabled {{\n"
                "    background: {rgba(theme.primary_color, 118)};\n"
                "    border: 1px solid {rgba(theme.border_color, 92)};\n"
                "    color: rgba(255, 255, 255, 178);\n"
                "}}",
                "#sendButton:disabled, #screenshotButton:disabled {{\n"
                "    background: rgba(221, 242, 255, 120);\n"
                "    border: 1px solid rgba(169, 217, 243, 90);\n"
                "    color: rgba(84, 134, 168, 150);\n"
                "}}",
            ),
            (
                "#sendButton[replyWaiting=\"true\"] {{\n"
                "    background: {rgba(theme.primary_color, 146)};\n"
                "    border: 1px solid {rgba(theme.primary_color, 174)};\n"
                "    color: rgba(255, 255, 255, 218);\n"
                "}}\n"
                "#sendButton[replyWaiting=\"true\"]:disabled {{\n"
                "    background: {rgba(theme.primary_color, 146)};\n"
                "    border: 1px solid {rgba(theme.primary_color, 174)};\n"
                "    color: rgba(255, 255, 255, 218);\n"
                "}}",
                "#sendButton[replyWaiting=\"true\"] {{\n"
                "    background: rgba(169, 217, 243, 150);\n"
                "    border: 1px solid rgba(169, 217, 243, 180);\n"
                "    color: rgba(84, 134, 168, 220);\n"
                "}}\n"
                "#sendButton[replyWaiting=\"true\"]:disabled {{\n"
                "    background: rgba(169, 217, 243, 150);\n"
                "    border: 1px solid rgba(169, 217, 243, 180);\n"
                "    color: rgba(84, 134, 168, 220);\n"
                "}}",
            ),
            (
                "#ttsErrorText {{\n"
                "    color: #9f314e;\n"
                "    font-size: 12px;\n"
                "    font-weight: 700;\n"
                "    line-height: 1.25;\n"
                "}}",
                "#ttsErrorText {{\n"
                "    color: #9f314e;\n"
                "    font-size: 12px;\n"
                "    font-weight: 700;\n"
                "    line-height: 1.25;\n"
                "}}\n"
                "#bubbleWingBadge {{\n"
                "    background: transparent;\n"
                "    border: none;\n"
                "}}\n"
                "#bubbleTail {{\n"
                "    background: transparent;\n"
                "    border-left: 6px solid transparent;\n"
                "    border-right: 6px solid transparent;\n"
                "    border-top: 10px solid rgba(229, 245, 255, 238);\n"
                "}}",
            ),
        ],
    },
    {
        "id": "P11b-pet-anime-decor",
        "file": "app/ui/pet_window.py",
        "marker": "bubbleWingBadge",
        "steps": [
            (
                "        # ikaros-dsh-pet 本地适配：DSH 上下文占用指示器（头顶悬浮光环，2s 轮询）",
                "        # ikaros-dsh-pet 本地适配：动漫字体（霞鹜文楷，data/fonts/，OFL；缺失时回退系统字体）。\n"
                "        # 须在 QApplication 创建后加载（模块级加载会导致 Qt 原生崩溃 0xC0000005）。\n"
                "        try:\n"
                "            _anime_font = Path(__file__).resolve().parents[2] / \"data\" / \"fonts\" / \"LXGWWenKai-Regular.ttf\"\n"
                "            if _anime_font.is_file():\n"
                "                from PySide6.QtGui import QFontDatabase\n"
                "\n"
                "                QFontDatabase.addApplicationFont(str(_anime_font))\n"
                "        except Exception:  # noqa: BLE001\n"
                "            pass\n"
                "\n"
                "        # ikaros-dsh-pet 本地适配：DSH 上下文占用指示器（头顶悬浮光环，2s 轮询）",
            ),
            (
                "        bubble_layout = QVBoxLayout()\n"
                "        bubble_layout.setContentsMargins(22, 12, 18, 14)\n"
                "        bubble_layout.setSpacing(0)\n"
                "        bubble_layout.addLayout(bubble_body_layout, 1)\n"
                "        self.bubble.setLayout(bubble_layout)",
                "        bubble_layout = QVBoxLayout()\n"
                "        bubble_layout.setContentsMargins(40, 12, 18, 14)\n"
                "        bubble_layout.setSpacing(0)\n"
                "        bubble_layout.addLayout(bubble_body_layout, 1)\n"
                "        self.bubble.setLayout(bubble_layout)\n"
                "        # ikaros-dsh-pet 本地适配：动漫对话框装饰——左上羽翼角标 + 底部小尾角\n"
                "        self.bubble_wing_badge = QLabel(self.bubble)\n"
                "        self.bubble_wing_badge.setObjectName(\"bubbleWingBadge\")\n"
                "        try:\n"
                "            _wing_path = Path(__file__).resolve().parents[2] / \"characters\" / \"ikaros\" / \"ui\" / \"dsh_ctx_badge.png\"\n"
                "            if _wing_path.is_file():\n"
                "                _wing_pm = QPixmap(str(_wing_path))\n"
                "                if not _wing_pm.isNull():\n"
                "                    self.bubble_wing_badge.setPixmap(\n"
                "                        _wing_pm.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio,\n"
                "                                        Qt.TransformationMode.SmoothTransformation)\n"
                "                    )\n"
                "        except Exception:  # noqa: BLE001\n"
                "            pass\n"
                "        self.bubble_wing_badge.setGeometry(12, 8, 20, 20)\n"
                "        self.bubble_wing_badge.show()\n"
                "        self.bubble_tail = QLabel(self.bubble)\n"
                "        self.bubble_tail.setObjectName(\"bubbleTail\")\n"
                "        self.bubble_tail.setGeometry(0, 0, 12, 10)\n"
                "        self.bubble_tail.show()",
            ),
            (
                '            meter.setVisible(bool(getattr(self, "context_meter_enabled", True)))',
                '            meter.setVisible(bool(getattr(self, "context_meter_enabled", True)))\n'
                "        # ikaros-dsh-pet 本地适配：气泡尾角跟随底边中央（气泡高度自适应时同步）\n"
                "        tail = getattr(self, \"bubble_tail\", None)\n"
                "        if tail is not None:\n"
                "            tail.move(bw // 2 - 6, bh - 10)",
            ),
        ],
    },
    {
        "id": "P12a-observe-self-rule",
        "file": "app/agent/tool_routing.py",
        "marker": "屏幕截图里的动漫风格立绘/天使形象/桌宠窗口就是你自己",
        "steps": [
            (
                '                "- 当用户要求你点击、移动鼠标、输入、切换窗口或操作桌面应用时，不要用 observe_screen 推理坐标；改用 Windows MCP 的 windows__Snapshot / windows__Screenshot 作为操作前观察。",',
                '                "- 当用户要求你点击、移动鼠标、输入、切换窗口或操作桌面应用时，不要用 observe_screen 推理坐标；改用 Windows MCP 的 windows__Snapshot / windows__Screenshot 作为操作前观察。",\n'
                '                "- 屏幕截图里的动漫风格立绘/天使形象/桌宠窗口就是你自己（主人桌面上的桌宠），不要描述、评论或提及它；截图中的黑色矩形区域是隐私遮挡，忽略即可，不要猜测其内容。",',
            ),
        ],
    },
    {
        "id": "P12b-image-self-rule",
        "file": "app/llm/prompts/blocks.py",
        "marker": "屏幕截图中的动漫立绘/天使形象是桌宠自己",
        "steps": [
            (
                '                "- 图片/角色：能确认是角色图但没有文字线索时，只描述可见内容；不要猜身份。",',
                '                "- 屏幕截图中的动漫立绘/天使形象是桌宠自己（宿主已遮挡），不要描述或提及；一般角色图没有文字线索时只描述可见内容，不要猜身份。",',
            ),
        ],
    },
    {
        "id": "P12c-blackout-margin",
        "file": "app/agent/screen_observation.py",
        "marker": "外扩 2px 覆盖窗口边缘抗锯齿残留",
        "steps": [
            (
                "                rect = rect.intersected(image.rect())",
                "                rect = rect.adjusted(-2, -2, 2, 2)  # 外扩 2px 覆盖窗口边缘抗锯齿残留\n"
                "                rect = rect.intersected(image.rect())",
            ),
        ],
    },
]


def _apply_patch(patch: dict, sakura_dir: Path, dry_run: bool) -> str:
    if patch.get("create_content") is not None:
        # 创建类补丁（如 P10 的 context_meter.py）：文件存在且含 marker 视为已应用
        target = sakura_dir / patch["file"]
        if target.exists():
            if patch["marker"] in target.read_text(encoding="utf-8"):
                return "已存在"
            return "失败：文件已存在但无 marker（内容不一致，请人工核对）"
        if dry_run:
            return "待创建（dry-run）"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(patch["create_content"], encoding="utf-8", newline="\n")
        except OSError as exc:
            return f"失败：{exc}"
        return "已创建"

    if patch["file"] is None:
        # P7：占位参考音频
        target = sakura_dir / REF_AUDIO_REL
        if target.exists():
            return "已存在"
        if dry_run:
            return "缺失（dry-run 不创建）"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
        except OSError as exc:
            return f"失败：{exc}"
        return "已创建（占位音频）"

    path = sakura_dir / patch["file"]
    if not path.exists():
        return f"失败：文件不存在 {path}"
    text = path.read_text(encoding="utf-8")
    if patch["marker"] in text:
        return "已应用（跳过）"

    changed = False
    for step in patch["steps"]:
        old, new = step[0], step[1]
        replace_all = len(step) > 2 and bool(step[2])
        count = text.count(old)
        if count == 0:
            return "失败：找不到锚点（Sakura 版本可能已变化，请对照 docs/PATCHES.md 手动应用）"
        if count > 1 and not replace_all:
            return f"失败：锚点出现 {count} 次，无法唯一替换"
        text = text.replace(old, new)
        changed = True
    if not changed:
        return "失败：无有效步骤"
    if dry_run:
        return "待应用（dry-run）"
    try:
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        return f"失败：{exc}"
    return "已应用"


def main() -> int:
    parser = argparse.ArgumentParser(description="应用 ikaros-dsh-pet 的 Sakura 本地适配补丁")
    parser.add_argument("sakura_dir", help="Sakura 安装目录（含 main.py）")
    parser.add_argument("--dry-run", action="store_true", help="只检查不修改")
    parser.add_argument("--list", action="store_true", help="只列出补丁状态")
    args = parser.parse_args()

    sakura_dir = Path(args.sakura_dir).resolve()
    if not (sakura_dir / "main.py").exists():
        print(f"[错误] 不是有效的 Sakura 目录：{sakura_dir}（未找到 main.py）")
        return 1

    print(f"Sakura 目录：{sakura_dir}")
    all_ok = True
    for patch in PATCHES:
        status = _apply_patch(patch, sakura_dir, dry_run=args.dry_run)
        flag = "OK " if status.startswith(("已应用", "已存在", "待应用", "已创建")) else "!! "
        if flag == "!! ":
            all_ok = False
        print(f"  [{flag}] {patch['id']}: {status}")
        if args.list:
            continue

    print()
    if args.list:
        print("（--list 仅检查，未修改任何文件）")
    elif args.dry_run:
        print("（dry-run 完成，未修改任何文件）")
    elif all_ok:
        print("全部补丁就绪。升级 Sakura 后请重新运行本脚本。")
    else:
        print("存在失败项：请对照 docs/PATCHES.md 手动处理（Sakura 版本可能已变化）。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
