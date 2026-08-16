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
    except Exception:
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
    except Exception as exc:
        log_event("PluginAgent", "主动事件启动失败", {"error": str(exc)})
```

**效果**：`dsh_watcher` 插件检测到 DSH 关键节点（目标完成 / 工具失败 / 等待授权）时，
能触发伊卡洛斯主动开口（角色化回复 + 字幕 + 立绘 + TTS 语音）；用户刚交互后的
30 秒内不会抢答。

## 2. 主动事件回复不写入对话历史（`app/ui/pet_window.py`）

**文件**：`<Sakura>/app/ui/pet_window.py`

**背景**：主动事件（被动发言 / 主动感知）的回复原本与正常对话一样写入
`chat_history`，导致下次对话时这些「无对应用户消息的旁白」进入 LLM 上下文，
模型会惯性延续/重复自己说过的话——表现为「很久没对话后再对话会重复回复」。

**补丁内容**：`_handle_event_reply` 与 `_handle_event_error` 中改为不写历史
（气泡与语音展示不受影响，仅不进对话历史）：

```python
# _handle_event_reply 内（原为 self._consume_agent_result(result)）：
self._consume_agent_result(result, record_history=False)

# _handle_event_error 的 reminder 兜底分支：
self._consume_agent_result(result, record_history=False)
```

**配合**：`plugins/dsh_watcher/plugin.py` 新增 `passive_dedup_seconds`（默认 600）：
相同事件摘要指纹在窗口内不重复触发主动发言，避免长时间静默期对相似 DSH 事件
反复开口；同一事件 seq 也不重复发言（防重放）。配置项：

```json
{ "passive_dedup_seconds": 600 }
```

## 3. 双语字幕显示（`app/llm/chat_reply.py`）

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

## 4. TTS 语言守卫放宽（`app/voice/text_language_guard.py`）

**文件**：`<Sakura>/app/voice/text_language_guard.py`

**背景**：Sakura 默认「目标语音为日语时，明显中文的文本不送入 TTS」。但本项目
VITS / edge-tts 桥支持**日语+中文双语自动发音**（按文本内容检测），屏幕观察
（视觉模型 GLM-4V-Flash）等场景会产生中文长描述回复，会被默认守卫静默跳过，
导致「有字幕没声音」。

**补丁内容**：守卫只拒绝「既不含日语假名也不含中日韩汉字」的异常文本
（乱码/纯符号/纯英文），中文文本允许正常合成：

```python
def should_skip_tts_text(text: str, target_lang: str) -> bool:
    if not text.strip():
        return False
    normalized_lang = target_lang.strip().lower()
    if normalized_lang not in {"ja", "all_ja"}:
        return False
    return _looks_non_speech(text)  # 无假名且无 CJK → 跳过；中日文均放行
```

## 5. 屏幕截图排除桌宠自身窗口（`app/agent/screen_observation.py`）

**文件**：`<Sakura>/app/agent/screen_observation.py`

**背景**：主动屏幕感知/视觉观察截取全屏时，桌宠自己的立绘窗口也在画面里，
视觉模型会"看到自己"并一本正经地描述——对主人来说是废话。

**补丁内容**：`capture_screen_image` 原本忽略 `excluded_widget` 参数（`_ = excluded_widget`），
现实现为把桌宠自身窗口区域（按 DPR 映射到物理像素）涂黑后再返回：

```python
# 注意：QRect 属于 PySide6.QtCore，不在 QtGui（import 错误会导致 observe_screen 崩溃卡死）
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QCursor, QPainter

if excluded_widget is not None:
    try:
        if excluded_widget.isVisible():
            geo = excluded_widget.frameGeometry()
            dpr = float(excluded_widget.devicePixelRatioF() or 1.0)
            rect = QRect(round(geo.x() * dpr), round(geo.y() * dpr),
                         round(geo.width() * dpr), round(geo.height() * dpr))
            rect = rect.intersected(image.rect())
            if not rect.isEmpty():
                painter = QPainter(image)
                painter.fillRect(rect, QColor(0, 0, 0))
                painter.end()
    except Exception:
        pass
```

**配合**：`characters/ikaros/card.md` 增加「屏幕观察规则」——截图里的动漫立绘是
自己，不要描述、评论或提及。

## 6. 屏幕感知指令改为情境化回应（`app/agent/runtime.py`）

**文件**：`<Sakura>/app/agent/runtime.py`

**背景**：Sakura 默认屏幕感知指令是「基于屏幕内容找话题……不要把时间或停留时长
自动泛化成休息建议」。但角色策略需要**按屏幕内容情境化回应**（学习→鼓励、
SolidWorks/建模/长时间作业→提醒休息），默认指令与角色卡冲突。

**补丁内容**：`_format_event_for_model` 的 `screen_awareness_check` 指令改为：

```python
"主动屏幕感知事件如下，请根据屏幕内容按角色卡「屏幕观察回应策略」回应："
"学习/课程/文档→轻声鼓励陪伴；工程建模/设计/长时间连续作业→关心主人健康、"
"委婉提醒休息（不要每次都说）；一般工作/代码→安静陪伴或简短询问；"
"娱乐/游戏/视频→保持安静；内容无法判断→保持安静。"
"不要描述屏幕上的动漫立绘（那是你自己）。"
```

**配合**：`characters/ikaros/card.md` 的「屏幕观察回应策略」表格（学习/建模/工作/
娱乐分类回应，含日语示例）。

## 7. 角色包占位参考音频（`<Sakura>/ref/VO01_2210.ogg`）

**背景**：Sakura 的 GPT-SoVITS TTS 校验要求存在默认参考音频
（`data/config/api.yaml` 的 `tts.gpt_sovits` 未显式配置时，默认指向
`<Sakura>/ref/VO01_2210.ogg`）。Release 包不带该文件，启用 TTS 会报
`参考音频不存在` 并降级为静音。

**解决**：创建占位文件即可（edge-tts / VITS 桥会忽略参考音频内容）：

```
<空文件或任意字节>  <Sakura>/ref/VO01_2210.ogg
```

角色包内已提供合法参考音频配置（本地 `characters/ikaros/voice/refs/ref.txt` +
`tone_refs/neutral.ogg`，属本地个人素材不入库）；全新 clone 需自行放置
`voice/refs/tone_refs/neutral.ogg`（任意合法音频即可，VITS/edge-tts 桥忽略内容），
否则实际 TTS 请求会使用默认文件；此文件仅为通过 Sakura 启动校验。

## 应用方式

每次升级/重装 Sakura Release 后，按上面七处重新应用即可。
`install.bat` 已负责复制角色包、插件与 TTS 桥；补丁需手动或按需执行。
