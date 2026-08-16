# 本地补丁清单（Sakura 适配）

ikaros-dsh-pet 作为 Sakura Desktop Pet 的扩展发行，**不改动 Sakura 核心逻辑**，
通过官方扩展点接入（角色包/插件/TTS 桥）。为启用「插件主动发言、双语字幕、
中文 TTS 放行、屏幕排除自身、感知指令、视觉修复、DSH 上下文占用指示器、
动漫化对话框」等能力，需要在 Sakura 安装目录应用**本地适配补丁**
（`tools/apply_patches.py` 自动应用，共 13 项：P1、P2、P3a、P3b、P3c、P4、
P5、P6、P7、P8、P9、P10、P11a、P11b），升级 Sakura 后需重新运行补丁脚本。

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

## 8. 视觉回复修复剥离图片（`app/agent/runtime.py`）

**文件**：`<Sakura>/app/agent/runtime.py`

**背景**：屏幕观察链路中，免费视觉模型（GLM-4V-Flash）对 Sakura 的分段 JSON
回复协议遵循较弱，可能输出普通文本导致「最终回复结构异常」。Sakura 的修复请求
若仍带截图，会再次路由回视觉模型，反复失败（表现为「看看我在干什么」返回无关回复）。

**补丁内容**：修复请求前剥离消息中的图片块（保留文本），使修复请求路由到
格式稳定的文本模型（DeepSeek），由它基于视觉模型的文字输出生成规范回复——
「视觉模型负责看，文本模型负责说」：

```python
# _repair 内、repair_messages 构建后：
repair_messages = _strip_images_from_messages(repair_messages)
```

并在模块顶部新增 `_strip_images_from_messages()`（去掉 content 列表中的
`image_url` 块，保留 `text` 块）。

## 9. 角色包占位参考音频（`<Sakura>/ref/VO01_2210.ogg`）

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

## 9. DSH 上下文占用指示器控件（`app/ui/context_meter.py`，P9 创建文件）

**文件**：`<Sakura>/app/ui/context_meter.py`（由补丁脚本创建，源码内嵌于
`tools/apply_patches.py` 的 `_CONTEXT_METER_SOURCE`，修改时两处同步）

**背景**：桌宠需要一个「小面积但醒目」的指示器，显示 DeepSeek Harness
当前会话的上下文占用百分比，风格贴合天降之物（伊卡洛斯）。V1.2 采用
gpt-5.6-sol 咨询产出的**悬浮光环式**布局（推荐方案）：椭圆 Angeloid 状态环
悬浮在立绘头顶后上方（中心 L+0.52W, T+0.07H），椭圆光环兼进度弧、中间显示
百分比、左端嵌小羽翼，像角色自身的状态环而非外挂标签。

**控件行为**：

- 数据源：`<Sakura>/data/dsh_context_state.json`，由 `dsh_watcher` 插件（v0.2.0）
  在后台线程写入，字段：
  `percent`（min(100, round(提示侧 token / contextWindow × 100))，与 DSH Web UI
  的 context occupancy 同口径）、`usedTokens`、`contextWindow`、`session`、
  `updatedAt`（毫秒时间戳）；
- 宿主用 QTimer 每 2 秒调用 `refresh()` 读文件；数据超过 120 秒未更新显示 `--%`
  并转为灰蓝调；
- 占用 ≥80% 时进度弧与文字转蜜桃橙提醒；
- 点击穿透（WA_TransparentForMouseEvents）；tooltip 显示 `12% · 125,000/1,000,000
  tokens · 会话名`；
- 造型：96×30 椭圆光环，白→天空蓝渐变 70% 透明盘 + 1px 淡粉顶部高光弧
  （4 秒呼吸微光）+ 进度轨道环与白色进度弧（12 点方向顺时针）+ 左端 12px
  小羽翼图标（`<Sakura>/characters/ikaros/ui/dsh_ctx_badge.png`，gpt-5.6-sol
  出 prompt + gpt-image-2 生成、flood-fill 去底，仓库 `assets/dsh_ctx_badge.png`
  有副本），素材缺失时程序化绘制小天使翼回退；
- 动效：数值变化时百分比与进度弧平滑补间（30ms 步进，无跳变）。

**配套（插件侧，仓库代码非补丁）**：`plugins/dsh_watcher` 新增上下文占用统计——
`dsh_reader.py` 白名单加入 `request/context` 事件并新增纯函数 `context_percent`；
`plugin.py` 跟踪 `request/context` 的 `contextWindow` 与 `assistant/message`
`usage` 的提示侧 token（inputTokens + cacheReadTokens + cacheWriteTokens），
按节流（`context_state_min_interval_seconds`，默认 2s）原子写状态文件；
`config.json` 新增 `context_state_file`（默认 `<Sakura>/data/dsh_context_state.json`，
可绝对路径或相对 Sakura 根）。

## 10. 指示器挂载进主窗口（`app/ui/pet_window.py`，P10）

**文件**：`<Sakura>/app/ui/pet_window.py`

**补丁内容**：

1. 导入：`from app.ui.context_meter import ContextMeter`；
2. `__init__` 中（气泡构建前）创建控件与 2 秒 QTimer：
   `context_meter_enabled = self._load_context_meter_enabled()`（system_config.yaml
   的 `ui.context_meter_enabled`，默认开启）、`ContextMeter(self)`、`_refresh_context_meter`
   定时刷新；
3. `_place_pet_children` 中把指示器悬浮在立绘头顶后上方（中心
   `L+0.52W, T+0.07H`，窗口右/上缘不足时收进窗口内），并按开关显隐；
4. 新增 `_load_context_meter_enabled` / `_refresh_context_meter` 两个方法。

指示器是可见直接子控件，自动并入舞台碰撞遮罩的可见区域；`WA_TransparentForMouseEvents`
保证不拦截点击。

## 11. 动漫化对话框样式与字体（V1.2，P11a/P11b）

**文件**：`<Sakura>/app/ui/theme.py`（P11a）、`<Sakura>/app/ui/pet_window.py`（P11b）

**背景**：V1.2 视觉升级（gpt-5.6-sol 咨询产出）：桌宠整体缩小（立绘 55%、
对话框 440×104、输入栏 440×44，主窗口 656×585 → 536×500），对话框与字体
动漫化。

**P11a（theme.py QSS）**：

- 气泡 `#speechBubble`：白→淡蓝垂直渐变（`qlineargradient`，stop:0
  rgba(255,255,255,242) → stop:1 rgba(229,245,255,238)）+ 1px 淡蓝边框
  `rgba(169,217,243,210)` + 圆角 18px（原为单色 20px）；
- 输入栏 `#inputBar[solid]`：奶白→淡蓝渐变 + 圆角 16px；
- 输入框 `#petInput`：圆角 16px + `font-family: "LXGW WenKai"`；
- 按钮 `#sendButton/#screenshotButton`：浅蓝底 `rgba(221,242,255,235)` +
  深蓝字 `rgba(84,134,168,235)` + 圆角 12px；hover 淡粉 `rgba(248,221,234,242)`
  （伊卡洛斯蓝白粉配色）；
- 名字/正文 `#speakerName/#speechText`：`font-family: "LXGW WenKai"`；
- 新增装饰 QSS：`#bubbleWingBadge`（羽翼角标透明底）、`#bubbleTail`
  （气泡底部 12×10 三角尾角，QSS border 三角，颜色与气泡渐变底一致）。

**P11b（pet_window.py）**：

1. `__init__` 中（QApplication 创建后）加载动漫字体：
   `data/fonts/LXGWWenKai-Regular.ttf`（霞鹜文楷，OFL，中文+日文假名混排），
   `QFontDatabase.addApplicationFont`；**注意**：模块级加载会在 QApplication
   创建前触碰 Qt 字体系统导致原生崩溃（0xC0000005），必须放 `__init__`；
2. 气泡装饰：左上角 20×20 羽翼角标（`characters/ikaros/ui/dsh_ctx_badge.png`
   缩小，素材缺失时空白）+ 底部中央 12×10 三角尾角；
3. 气泡布局左边距 22 → 40（给角标让位）；
4. `_place_pet_children` 中尾角跟随气泡底边中央（气泡自适应高度时同步）。

**配套（非补丁）**：`<Sakura>/data/config/system_config.yaml` 尺寸调整——
`portrait_scale_percent: 55`、`control_panel_width: 440`、`bubble_height: 104`；
字体文件 `data/fonts/LXGWWenKai-Regular.ttf`（24.4MB，OFL，不入库，从
<https://github.com/lxgw/LxgwWenKai/releases> 下载，缺失时回退系统字体如幼圆）。

## 应用方式

**推荐**：运行自动补丁脚本（幂等，可重复执行，含锚点校验与 dry-run）：

```bat
<仓库>\runtime_or_系统python tools\apply_patches.py <Sakura安装目录>
python tools\apply_patches.py <Sakura安装目录> --dry-run   :: 只检查不修改
python tools\apply_patches.py <Sakura安装目录> --list      :: 查看状态
```

Sakura 升级后重新运行一次即可。脚本锚点不匹配（Sakura 版本变化）时，按
下面各节手动应用。`install.bat` 负责复制角色包、插件与 TTS 桥；补丁需
另行应用（自动脚本或手动）。
