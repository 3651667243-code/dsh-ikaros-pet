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
                "                dpr = float(excluded_widget.devicePixelRatioF() or 1.0)\n"
                "                rect = QRect(\n"
                "                    round(geo.x() * dpr),\n"
                "                    round(geo.y() * dpr),\n"
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
        "id": "P7-ref-audio",
        "file": None,  # 特殊：创建文件
        "marker": REF_AUDIO_REL.name,
        "steps": [],
    },
]


def _apply_patch(patch: dict, sakura_dir: Path, dry_run: bool) -> str:
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
