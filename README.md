# dsh-ikaros-pet — 伊卡洛斯桌宠

> 基于 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura) 框架（MIT License，作者 [Rvosy](https://github.com/Rvosy)）二次开发的伊卡洛斯桌宠（《天降之物》角色）。让桌宠能「看见」你的 DeepSeek Harness 会话、听懂你在让 AI 做什么，任务完成时主动开口，用伊卡洛斯声线（早见沙织风格 VITS 模型）说话。

![license](https://img.shields.io/badge/license-MIT-blue)
![platform](https://img.shields.io/badge/platform-Windows-0078d6)
![python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![based-on](https://img.shields.io/badge/based_on-Sakura%20Desktop%20Pet-ff69b4)
![voice](https://img.shields.io/badge/voice-VITS%20%2B%20edge--tts-9cf)

**本项目不改动 Sakura 核心代码**（仅两处本地适配补丁，见 [docs/PATCHES.md](docs/PATCHES.md)）。运行主体仍是 Sakura，本仓库通过其官方扩展点（角色包 + 插件 SDK `api_version: 2` + 外置 TTS 服务）接入，提供角色、DSH 感知、语音、安装脚本与文档。

## ✨ 功能特性

- **伊卡洛斯角色**：三无 + 天然呆 + 绝对忠诚，称呼主人「マスター」。角色包含人格卡与 5 张表情立绘（平静 / 疑惑 / 担心 / 开心 / 空之女王），对话时按语气自动切换立绘。
- **DSH 感知**：`dsh_watcher` 插件以帧边界增量方式只读 DSH 会话日志（`~/.dsh/sessions/*/session.jsonl.zstd`），识别关键节点（`turn/start`、`tool/call`、`tool/result`、`tool-workflow/run-*`、`goal/change`、`approval/asked` 等）并注入对话上下文。
- **主动开口**：目标完成、工具失败、等待授权时伊卡洛斯主动说话（角色化回复 + 语音），120 秒冷却防打扰。
- **伊卡洛斯声线**：VITS 语音桥（WSL 内运行，基于 Ikaros521/moe-tts 的 ikaros 模型，早见沙织声线训练），日语/中文自动识别发音；edge-tts 作为免部署备选。
- **双语字幕**：气泡显示「中文译文 + 日语原文注释」双行。
- **免费 LLM**：默认 DeepSeek-chat（极低成本，格式遵循稳定），可切换任意 OpenAI 兼容服务（智谱 GLM 等）。

## 🖼️ 效果预览

<img src="https://raw.githubusercontent.com/3651667243-code/dsh-ikaros-pet/main/assets/arch.png" alt="架构概念图" width="640"/>

> 概念图由 gpt-image-2 生成；运行截图待补充。

## 🏗️ 架构

```
┌────────────────────────────────────────────────────────────┐
│                    Sakura Desktop Pet（运行主体）            │
│   PySide6 桌面窗口 · 对话 · 角色系统 · 语音播放 · Agent 能力   │
└───────┬──────────────────────────┬─────────────────────────┘
        │ 官方扩展点                 │ 外置 TTS（HTTP :9880）
        ▼                           ▼
┌───────────────────┐      ┌──────────────────────────────┐
│ 角色包             │      │ VITS 语音桥（默认）           │
│ characters/ikaros/│      │ tools/edge_tts_bridge/       │
│ 人格卡 + 表情立绘   │      │ vits_server.py（WSL 内运行）  │
└───────────────────┘      │ Ikaros521/moe-tts 模型        │
┌───────────────────┐      └───────────┬──────────────────┘
│ dsh_watcher 插件   │                  │ edge-tts（备选，需联网）
│ 插件 SDK api v2    │                  ▼
└─────────┬─────────┘          早见沙织风格日语/中文语音
          │ 帧边界增量只读
          ▼
┌────────────────────────────────────────────────────────────┐
│ DeepSeek Harness（DSH）会话事件日志                          │
│ ~/.dsh/sessions/*/session.jsonl.zstd（zstd 多 frame 追加）  │
└────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

前置：Windows + Sakura Desktop Pet Release（含 `runtime/`）+ WSL2 Ubuntu（VITS 声线用；只用 edge-tts 可跳过）。

1. **下载 Sakura Release** 并解压，确认有 `main.py` 和 `runtime/`。
2. **放置仓库**：本仓库与 Sakura 目录同级。
3. **安装**：`install.bat`（自动复制角色包/插件/TTS 桥，并安装依赖 `zstandard`、`edge-tts`、`miniaudio`）。
4. **WSL 部署（声线）**：详见 [docs/SETUP.md](docs/SETUP.md)「WSL 部署」——在 WSL 内创建 venv、安装 torch CPU + pyopenjtalk + 依赖、下载模型文件放入 `tools/edge_tts_bridge/vits/saved_model/19/`。
5. **启动**：`start_tts_bridge.bat`（起 VITS 桥）→ `start.bat`（起 Sakura）。
6. **首次配置**：选角色「伊卡洛斯」→ API 填 DeepSeek/GLM → TTS 指向 `http://127.0.0.1:9880/tts`。

## ⚙️ 配置说明

### LLM（默认 DeepSeek-chat）

| 项 | 值 |
|---|---|
| Base URL | `https://api.deepseek.com/v1` |
| 模型名 | `deepseek-chat` |
| 说明 | 极低成本、格式遵循稳定；可切换智谱 GLM-4-Flash（免费）等其他 OpenAI 兼容服务 |

### TTS

| 项 | 默认值 |
|---|---|
| 监听地址 | `127.0.0.1:9880` |
| VITS 桥 | `tools/edge_tts_bridge/vits_server.py`（WSL 内，伊卡洛斯声线） |
| edge-tts 桥 | `tools/edge_tts_bridge/server.py`（备选，需联网与 `--proxy`） |

### dsh_watcher 插件（`plugins/dsh_watcher/config.json`）

| 项 | 默认值 | 说明 |
|---|---|---|
| `log_poll_interval_seconds` | 5 | 日志轮询间隔（帧增量读取，开销可忽略） |
| `max_recent_events` / `max_context_events` | 40 / 12 | 上下文注入的最近事件数 |
| `speak_on_*` | true | 各类关键节点是否主动发言 |
| `passive_cooldown_seconds` | 120 | 主动发言冷却 |
| `workspace_keyword` | `ikaros` | 锁定的 DSH 工作区关键字 |
| `reactions` | 日语台词 | 建议台词（日语可发声） |

## 📁 目录结构

```
dsh-ikaros-pet/
├── characters/ikaros/          # 角色包（character.json, card.md, portraits/, voice/）
├── plugins/dsh_watcher/        # DSH 感知插件（plugin.py, dsh_reader.py, event_summarizer.py, config.json）
├── tools/edge_tts_bridge/      # 语音桥（vits_server.py, server.py, wsl_run_vits.sh, requirements.txt）
├── docs/                       # SETUP / PATCHES / ACKNOWLEDGEMENTS
├── assets/                     # 概念图等
├── install.bat / start.bat / start_tts_bridge.bat
└── .github/                    # 规范模板（Issue/PR）
```

## 🙏 致谢

- **[Sakura Desktop Pet](https://github.com/Rvosy/Sakura)**（Rvosy，MIT）—— 运行主体与全部能力的来源，仅做扩展、不改核心；
- **[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)** —— 会话日志感知对象；
- **Ikaros521/moe-tts**（HuggingFace）—— 伊卡洛斯 VITS 声线模型来源；
- **edge-tts / zstandard / miniaudio / 智谱 / DeepSeek** —— 语音与模型能力；
- 《天降之物》角色设定 —— 角色扮演参考（版权归原作者水无月嵩/讲谈社等，本项目不包含任何官方素材）。

完整致谢见 [docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md)。

## 📜 License

MIT License，详见 [LICENSE](LICENSE)。运行主体为 Sakura Desktop Pet（MIT，作者 Rvosy），使用本项目即表示已了解并遵守 Sakura 的许可条款。本项目不包含《天降之物》官方素材；AI 生成立绘与声线模型仅供个人使用，请勿上传至仓库。

*命令吗？—— 伊卡洛斯，已确认与主人连接。*
