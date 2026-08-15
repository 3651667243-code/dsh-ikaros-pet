# 本地补丁清单（Sakura 适配）

ikaros-dsh-pet 作为 Sakura Desktop Pet 的扩展发行，**不改动 Sakura 核心代码**
（角色包/插件/TTS 桥全部走官方扩展点）。但有两处**本地适配补丁**需要手动应用到
Sakura 安装目录，升级 Sakura 后需重新应用。

## 1. 插件服务后端注入（`app/ui/pet_window.py`）

**文件**：`<Sakura>/app/ui/pet_window.py`

**背景**：Sakura 的插件服务门面（`app/plugins/services.py`）预留了
`bubble_sink` / `tts_sink` / `passive_reply_sink` 注入接口，但宿主
`PetWindow._wire_plugin_service_backends()` 只注入了输入框与手机端后端，
**没有注入气泡 / TTS / 主动发言后端**——导致插件调用 `services.ui.show_bubble`、
`services.tts.speak`、`services.agent.request_passive_reply` 时全部走空实现
（只写日志，不产生任何效果）。

**补丁内容**：

1. `PySide6.QtCore` import 增加 `Signal` 已存在；在 `PetWindow` 类内新增三个信号：

```python
# ikaros-dsh-pet 本地适配：插件服务后端信号（后台线程 emit → UI 线程处理）
plugin_bubble_requested = Signal(str)
plugin_tts_requested = Signal(str, bool)
plugin_passive_requested = Signal(str, object)
```

2. `__init__` 中连接信号（在 `plugin_input_text_requested.connect(...)` 附近）：

```python
self.plugin_bubble_requested.connect(self._plugin_bubble_ui)
self.plugin_tts_requested.connect(self._plugin_tts_ui)
self.plugin_passive_requested.connect(self._handle_plugin_passive_reply)
```

3. `_wire_plugin_service_backends()` 的 `set_backends(...)` 增加三个参数：

```python
services.set_backends(
    input_text_sink=self._request_fill_input_text,
    bubble_sink=self._plugin_show_bubble,
    tts_sink=self._plugin_tts_speak,
    passive_reply_sink=self._plugin_request_passive_reply,
    mobile_characters_sink=self._mobile_characters,
    mobile_history_sink=self._mobile_history,
    mobile_chat_sink=self._mobile_chat,
    mobile_theme_sink=self._mobile_theme,
)
```

4. 新增以下方法（放在 `_wire_plugin_service_backends` 之后）：

```python
# ---- ikaros-dsh-pet 本地适配：插件服务真实后端（线程 marshal 到 UI 线程） ----

def _plugin_show_bubble(self, text: str, source: str | None = None) -> None:
    try:
        self.plugin_bubble_requested.emit(text)
    except Exception as exc:
        log_event("PluginUI", "气泡请求失败", {"error": str(exc)})

@Slot(str)
def _plugin_bubble_ui(self, text: str) -> None:
    try:
        self.subtitle_controller.show_text_immediately(text)
    except Exception as exc:
        log_event("PluginUI", "气泡显示失败", {"error": str(exc)})

def _plugin_tts_speak(self, text: str, interrupt: bool = False) -> None:
    try:
        self.plugin_tts_requested.emit(text, bool(interrupt))
    except Exception as exc:
        log_event("PluginTTS", "TTS 请求失败", {"error": str(exc)})

@Slot(str, bool)
def _plugin_tts_ui(self, text: str, interrupt: bool = False) -> None:
    try:
        provider = getattr(self, "tts_provider", None)
        if provider is not None:
            provider.speak(text)
    except Exception as exc:
        log_event("PluginTTS", "TTS 播放失败", {"error": str(exc)})

def _plugin_request_passive_reply(
    self,
    reason: str,
    context: dict[str, Any] | None = None,
) -> None:
    """插件请求主动发言：信号 marshal 到 UI 线程后走主动事件链路（LLM 角色化回复+语音）。"""
    try:
        self.plugin_passive_requested.emit(reason, context)
    except Exception as exc:
        log_event("PluginAgent", "主动发言请求失败", {"error": str(exc)})

@Slot(str, object)
def _handle_plugin_passive_reply(self, reason: str, context: object) -> None:
    if getattr(self, "startup_initializing", False):
        return
    if self.worker_thread is not None or self.active_event is not None:
        log_event("PluginAgent", "桌宠忙，跳过主动发言", {"reason": reason})
        return
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
    except Exception as exc:
        log_event("PluginAgent", "主动事件启动失败", {"error": str(exc)})
```

**效果**：`dsh_watcher` 插件检测到 DSH 关键节点（目标完成 / 工具失败 / 等待授权）时，
能触发伊卡洛斯主动开口（角色化回复 + 字幕 + 立绘 + TTS 语音）。

## 2. 双语字幕显示（`app/llm/chat_reply.py`）

**文件**：`<Sakura>/app/llm/chat_reply.py`

**背景**：Sakura 气泡默认只显示单一语言（zh 或 ja）。我们希望显示
「中文译文 + 日语原文注释」双行。

**补丁内容**：修改 `ChatSegment.display_text`：

```python
def display_text(self, subtitle_language: str) -> str:
    """按字幕语言返回气泡显示文本；缺少译文时回退日文原文。

    本地适配（ikaros-dsh-pet）：zh 模式显示「中文译文 + 日语注释」双行。
    """
    if subtitle_language == "zh" and self.translation.strip():
        main_text = self.translation.strip()
        if self.text.strip():
            return f"{main_text}\n（{self.text.strip()}）"
        return main_text
    return self.text
```

## 3. 角色包占位参考音频（`<Sakura>/ref/VO01_2210.ogg`）

**背景**：Sakura 的 GPT-SoVITS TTS 校验要求存在默认参考音频
（`data/config/api.yaml` 的 `tts.gpt_sovits` 未显式配置时，默认指向
`<Sakura>/ref/VO01_2210.ogg`）。Release 包不带该文件，启用 TTS 会报
`参考音频不存在` 并降级为静音。

**解决**：创建占位文件即可（edge-tts / VITS 桥会忽略参考音频内容）：

```
<空文件或任意字节>  <Sakura>/ref/VO01_2210.ogg
```

角色包内已提供合法参考音频配置（`characters/ikaros/voice/refs/ref.txt` +
`tone_refs/neutral.ogg`），因此实际 TTS 请求会使用角色参考音频而非默认文件；
此文件仅为通过 Sakura 启动校验。

## 应用方式

每次升级/重装 Sakura Release 后，按上面三处重新应用即可。
`install.bat` 已负责复制角色包、插件与 TTS 桥；补丁需手动或按需执行。
