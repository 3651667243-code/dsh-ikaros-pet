# ikaros-dsh-pet — 伊卡洛斯桌宠

> 基于 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura) 框架（MIT License，作者 [Rvosy](https://github.com/Rvosy)）二次开发的伊卡洛斯桌宠（《天降之物》角色），让桌宠能「看见」你的 DeepSeek Harness 会话、听懂你在让 AI 做什么，并随时用免费语音开口说话。

![license](https://img.shields.io/badge/license-MIT-blue)
![platform](https://img.shields.io/badge/platform-Windows-0078d6)
![python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![based-on](https://img.shields.io/badge/based_on-Sakura%20Desktop%20Pet-ff69b4)

**本项目不修改 Sakura 核心代码**。运行主体仍是 Sakura，本仓库只是它的一个扩展发行：通过官方扩展点（角色包 + 插件 SDK `api_version: 2` + 外置 TTS 服务）接入，提供角色、DSH 感知、语音、安装脚本与文档。

---

## ✨ 功能特性

- **伊卡洛斯角色**：三无 + 天然呆 + 绝对忠诚，称呼用户「主人」，标志性台词「命令吗？」「我会守护主人」「铭刻」。角色包位于 `characters/ikaros/`，含人格卡与 5 张程序生成占位立绘（平静 / 疑惑 / 担心 / 开心 / 生气），可自行替换。
- **DSH 感知**：`dsh_watcher` 插件后台线程增量读取 DeepSeek Harness 会话事件日志（`~/.dsh/sessions/*/session.jsonl.zstd`，只读不修改），识别关键节点（`turn/start`、`tool/call`、`tool/result`、`step/start`、`tool-workflow/run-start`、`goal/change`、`approval/asked` 等）并整理成中文摘要，注入每次对话上下文。
- **主动发言**：工作流完成、目标达成、工具失败、等待授权时，伊卡洛斯会按规则主动开口（`services.agent.request_passive_reply`），带 120 秒冷却，不会吵到主人。
- **免费语音**：`tools/edge_tts_bridge/` 是免费的 edge-tts 语音桥，模拟 GPT-SoVITS 外置服务协议，日语默认 `ja-JP-NanamiNeural`，中文默认 `zh-CN-XiaoyiNeural`，网络受限时可加 `--proxy`。
- **免费 LLM**：默认配置智谱 GLM-4-Flash（免费、OpenAI 兼容、支持 function calling），也支持切换 DeepSeek 等其他 OpenAI 兼容服务。

## 🖼️ 效果预览

> 占位：此处预留桌宠运行截图（角色立绘 + 对话框 + 气泡 + TTS 控制）位置，待项目正式发布后补充。当前立绘为程序生成的占位图，替换方法见 [docs/SETUP.md](docs/SETUP.md)。

## 🏗️ 架构

```
┌────────────────────────────────────────────────────────────┐
│                     Sakura Desktop Pet（运行主体）           │
│  PySide6 桌面窗口 · 对话 · 角色系统 · 语音播放 · Agent 能力   │
└───────┬──────────────────────────┬─────────────────────────┘
        │ 官方扩展点                 │ 外置 TTS（HTTP）
        ▼                           ▼
┌───────────────────┐      ┌──────────────────────┐
│ 角色包             │      │ edge-tts 语音桥       │
│ characters/ikaros/│      │ tools/edge_tts_bridge/│
│ 人格卡 + 立绘      │      │ 127.0.0.1:9880        │
└───────────────────┘      └──────────┬───────────┘
┌───────────────────┐                 │ edge-tts（微软神经语音）
│ dsh_watcher 插件   │                 ▼
│ 插件 SDK api v2    │        Microsoft Edge TTS 服务
└─────────┬─────────┘
          │ 只读增量读取
          ▼
┌────────────────────────────────────────────────────────────┐
│ DeepSeek Harness（DSH）会话事件日志                          │
│ ~/.dsh/sessions/*/session.jsonl.zstd（zstd 多 frame 追加）  │
└────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

前置：一台 Windows 电脑 + 一个已解压的 Sakura Desktop Pet Release（**必须含 `runtime/` 目录**）。

1. **下载 Sakura Release**：到 [Sakura Desktop Pet Releases](https://github.com/Rvosy/Sakura/releases) 下载 Windows 版并解压，确认目录下有 `main.py` 和 `runtime/`。
2. **放置仓库**：把本仓库放在 Sakura 目录旁边（同级目录），保持默认布局：
   ```
   D:\pet\
   ├── Sakura\            ← Sakura Release 解压目录
   └── ikaros-dsh-pet\    ← 本仓库
   ```
3. **一键安装**：双击运行 `install.bat`。脚本会自动把角色包、`dsh_watcher` 插件、TTS 桥复制进 Sakura，并用 Sakura 自带运行时安装依赖（`zstandard`、`edge-tts`）。
4. **启动语音桥**：双击 `start_tts_bridge.bat`，看到 `就绪：http://127.0.0.1:9880/tts` 即成功。
5. **启动 Sakura**：双击 `start.bat`。
6. **首次启动引导配置**：
   - 选择角色「**伊卡洛斯**」；
   - API 配置智谱 **GLM-4-Flash**（见下表）；
   - TTS 选择外置服务（gpt-sovits），`api_url` 填 `http://127.0.0.1:9880/tts`。

详细步骤与排错见 [docs/SETUP.md](docs/SETUP.md)。

## ⚙️ 配置说明

### LLM（智谱 GLM-4-Flash，默认）

| 项 | 值 |
|---|---|
| Provider | OpenAI 兼容接口（BigModel 智谱开放平台） |
| Base URL | `https://open.bigmodel.cn/api/paas/v4` |
| 模型名 | `glm-4-flash` |
| 说明 | 免费、支持 function calling；在[智谱开放平台](https://open.bigmodel.cn/)注册并创建 API Key 即可 |

> 想换 DeepSeek 等其他 OpenAI 兼容服务？把 Base URL / 模型名 / API Key 换成对应服务的即可，无需改代码。

### TTS（edge-tts 语音桥）

| 项 | 默认值 |
|---|---|
| 监听地址 | `127.0.0.1:9880` |
| Sakura 侧 API URL | `http://127.0.0.1:9880/tts` |
| 日文语音 | `ja-JP-NanamiNeural` |
| 中文语音 | `zh-CN-XiaoyiNeural` |
| 可选参数 | `--port` / `--ja-voice` / `--zh-voice` / `--rate` / `--volume` / `--proxy` |

### dsh_watcher 插件（`plugins/dsh_watcher/config.json`）

| 项 | 默认值 | 说明 |
|---|---|---|
| `log_poll_interval_seconds` | 5 | 日志轮询间隔（秒） |
| `max_recent_events` | 40 | 内存中保留的最近事件数 |
| `max_context_events` | 12 | 每次注入上下文的最近事件数 |
| `speak_on_workflow_done` / `goal_done` / `tool_failed` / `approval` | true | 各类关键节点是否主动发言 |
| `passive_cooldown_seconds` | 120 | 主动发言冷却（秒） |
| `dsh_home` | 空（默认 `~/.dsh`） | DSH 数据目录，非常规安装时手动指定 |

## 📁 目录结构

```
ikaros-dsh-pet/
├── characters/ikaros/          # 角色包（character.json, card.md, portraits/, make_placeholder_portraits.py）
├── plugins/dsh_watcher/        # DSH 感知插件（plugin.yaml, plugin.py, dsh_reader.py, event_summarizer.py, config.json）
├── tools/edge_tts_bridge/      # edge-tts 语音桥（server.py, requirements.txt）
├── install.bat / start.bat / start_tts_bridge.bat
└── docs/
```

## 🙏 致谢

本项目站在巨人的肩膀上，衷心感谢：

- **[Sakura Desktop Pet](https://github.com/Rvosy/Sakura)**（作者 Rvosy，MIT License）—— 本项目运行主体与所有能力的来源，仅做扩展、不改核心；
- **[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)**（DSH）生态 —— 会话事件日志读取的灵感来源与感知对象；
- **edge-tts** 项目 —— 免费语音合成能力；
- **zstandard** —— zstd 日志读取能力；
- **智谱 GLM-4-Flash** —— 免费可用的对话模型；
- 《天降之物》及其角色设定 —— 角色扮演参考（作品版权归原作者水无月嵩 / 讲谈社等，本项目**不包含任何官方素材**，立绘为程序生成占位图）。

完整致谢见 [docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md)。

## 📜 License

本项目采用 **MIT License**，详见 [LICENSE](LICENSE)。

> ⚠️ 请注意：本项目的运行主体是 **Sakura Desktop Pet（MIT License，作者 Rvosy）**，其版权归原作者所有；使用本项目即表示您已了解并遵守 Sakura 的许可条款。本项目不包含《天降之物》的任何官方素材，立绘为程序生成占位图，可自行替换（替换方法见 [docs/SETUP.md](docs/SETUP.md) 的「角色包与立绘替换」章节）。

---

*命令吗？—— 伊卡洛斯，已确认与主人连接。*
