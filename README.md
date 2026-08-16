<p align="center">
  <img src="https://raw.githubusercontent.com/3651667243-code/dsh-ikaros-pet/main/assets/header.svg" alt="dsh-ikaros-pet 伊卡洛斯桌宠" width="820"/>
</p>

# dsh-ikaros-pet — 伊卡洛斯桌宠

> 基于 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura) 框架（MIT License，作者 [Rvosy](https://github.com/Rvosy)）二次开发的伊卡洛斯风格桌宠（《天降之物》角色扮演）。让桌宠能「看见」你的 DeepSeek Harness 会话、听懂你在让 AI 做什么，任务完成时主动开口，用日语角色声线 VITS 模型说话。**本项目是非官方个人同人项目，与《天降之物》及其权利方无任何官方关联。**

![license](https://img.shields.io/badge/license-MIT-blue)
![platform](https://img.shields.io/badge/platform-Windows-0078d6)
![python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![based-on](https://img.shields.io/badge/based_on-Sakura%20Desktop%20Pet-ff69b4)
![voice](https://img.shields.io/badge/voice-VITS%20%2B%20edge--tts-9cf)

**本项目不改动 Sakura 核心逻辑，但需在 Sakura 安装目录应用若干本地适配补丁**（目前七处，见 [docs/PATCHES.md](docs/PATCHES.md)——补丁为 Sakura 升级后需重新应用的手工步骤，`install.bat` 不负责应用）。运行主体仍是 Sakura，本仓库通过其扩展点（角色包 + 插件 SDK `api_version: 2` + 外置 TTS 服务）接入，提供角色、DSH 感知、语音、安装脚本与文档。

## ✨ 功能特性

- **伊卡洛斯角色**：三无 + 天然呆 + 绝对忠诚，称呼主人「マスター」。角色包含人格卡与 5 张表情立绘（平静 / 疑惑 / 担心 / 开心 / 空之女王），对话时按语气自动切换立绘。立绘为本地个人素材（不入库），见 [characters/ikaros/README.md](characters/ikaros/README.md)。
- **DSH 感知**：`dsh_watcher` 插件以帧边界增量方式只读 DSH 会话日志（`~/.dsh/sessions/*/session.jsonl.zstd`），识别关键节点（`turn/start`、`tool/call`、`tool/result`、`tool-workflow/run-*`、`goal/change`、`approval/asked` 等）并注入对话上下文。
- **屏幕互动**：能「看见」你的屏幕——默认每 10 分钟主动看一眼（可配置）：学习时轻声鼓励、长时间建模/设计时心疼地提醒休息、忙碌时安静陪伴；也可以直接说「看看我的屏幕」让她立刻看。视觉理解用免费 GLM-4V-Flash；她能看到屏幕但**看不到自己**（桌宠窗口已自动排除，不会傻乎乎地描述自己）。
- **主动开口**：目标完成、工具失败、等待授权时伊卡洛斯主动说话（角色化回复 + 语音），120 秒冷却防打扰。
- **伊卡洛斯声线**：VITS 语音桥（WSL 内运行，基于 Ikaros521/moe-tts 的 ikaros 模型，日语角色声线），日语/中文自动识别发音；edge-tts 作为免部署备选。
- **双语字幕**：气泡显示「中文译文 + 日语原文注释」双行。
- **低成本 LLM**：默认 DeepSeek-chat（低成本、格式遵循稳定），可切换任意 OpenAI 兼容服务（智谱 GLM-4-Flash 等，按服务商计费规则使用）。

## 🖼️ 效果预览

<img src="https://raw.githubusercontent.com/3651667243-code/dsh-ikaros-pet/main/assets/screenshot.png" alt="运行效果：伊卡洛斯等待回复（双语字幕）" width="520"/>

> 本机运行截图：伊卡洛斯「等待回复」的样子，气泡显示「中文译文 + 日语原文」双语字幕。

## 🧩 版本兼容矩阵

| 组件 | 支持版本 |
|---|---|
| Windows | 10 / 11（部署目录须为纯英文路径） |
| Python | 3.10+（Sakura Release 自带 runtime/） |
| Sakura Desktop Pet | 上游 Release 最新版（补丁见 [docs/PATCHES.md](docs/PATCHES.md)） |
| 插件 SDK | `api_version: 2` |
| WSL | WSL2 Ubuntu 22.04+（仅 VITS 声线需要） |
| DSH | 支持 `~/.dsh/sessions/*/session.jsonl.zstd`（zstd 多 frame 追加） |

## 🏗️ 架构

<img src="https://raw.githubusercontent.com/3651667243-code/dsh-ikaros-pet/main/assets/arch.png" alt="系统架构示意图" width="800"/>

> 架构图由 gpt-image-2 生成。核心链路：
> - **DSH 日志 → dsh_watcher**：插件只读增量解析 `~/.dsh/sessions/*/session.jsonl.zstd`（zstd 多 frame，帧边界扫描），识别关键节点（`turn/start`、`tool/call`、`goal/change`、`approval/asked` 等）并注入上下文；
> - **Sakura 桌宠**：角色包（人格卡 + 5 张立绘按语气自动切换）+ 插件 SDK `api_version: 2`；
> - **语音**：桌宠 → WSL 内 VITS 桥（HTTP :9880）→ 伊卡洛斯声线输出；edge-tts 免部署备选；
> - **LLM**：DeepSeek-chat / 智谱 GLM 等 OpenAI 兼容 API。

## 🚀 快速开始

前置：Windows + Sakura Desktop Pet Release（含 `runtime/`）+ WSL2 Ubuntu（VITS 声线用；只用 edge-tts 可跳过）。

1. **下载 Sakura Release** 并解压，确认有 `main.py` 和 `runtime/`。
2. **放置仓库**：本仓库与 Sakura 目录同级。
3. **安装**：`install.bat`（自动复制角色包/插件/TTS 桥，并安装依赖 `zstandard`、`edge-tts`、`miniaudio`）。
4. **应用本地补丁（必需）**：`python tools/apply_patches.py <Sakura目录>`（幂等，自动应用七处适配补丁；升级 Sakura 后重跑一次即可。补丁明细见 [docs/PATCHES.md](docs/PATCHES.md)）。
5. **WSL 部署（声线）**：详见 [docs/SETUP.md](docs/SETUP.md)「WSL 部署」——在 WSL 内创建 venv、安装 torch CPU + pyopenjtalk + 依赖、下载模型文件放入 `tools/edge_tts_bridge/vits/saved_model/19/`。
6. **启动**：`start_tts_bridge.bat`（起 VITS 桥）→ `start.bat`（起 Sakura）。
7. **首次配置**：选角色「伊卡洛斯」→ API 填 DeepSeek/GLM → TTS 指向 `http://127.0.0.1:9880/tts`（若桥启用了 `--auth-token`，地址需带 `?token=<令牌>`）。

## ⚙️ 配置说明

### LLM（默认 DeepSeek-chat + GLM-4V 视觉）

| 项 | 值 |
|---|---|
| 文本模型 | `deepseek-chat` @ `https://api.deepseek.com/v1` |
| 视觉模型（屏幕观察/看图） | `glm-4v-flash` @ `https://open.bigmodel.cn/api/paas/v4`（智谱，免费；付费可换 `glm-4v`） |
| 说明 | `model_slots` 支持按用途分模型：含图片的消息自动走视觉槽位，纯文本走聊天槽位（见 `data/config/api.yaml`） |

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

### 主动屏幕感知（`data/config/system_config.yaml`）

| 项 | 默认值 | 说明 |
|---|---|---|
| `screen_awareness.enabled` | `true` | 定时截图让伊卡洛斯"看见"屏幕并找话题 |
| `check_interval_minutes` | 10 | 每隔几分钟看一次屏幕 |
| `cooldown_minutes` | 10 | 发言后冷却，避免频繁打扰 |
| 视觉模型 | `glm-4v-flash` | 屏幕内容理解（智谱免费视觉模型，见上文 LLM 表） |

## 🔐 API Key 与隐私

- **API Key 只填写在 Sakura 本地的配置文件里**（如 `data/config/api.yaml`），本仓库任何文件都不应包含真实 Key；
- 不要通过 Issue、PR、聊天或截图公开你的 Key；Key 泄露后请立即到服务商后台撤销并重新生成；
- `dsh_watcher` 插件**只读**增量解析 `~/.dsh/sessions/*/session.jsonl.zstd`，绝不修改 DSH 数据；事件摘要的文本字段限制在 40~60 字符内，工具参数与结果只保留一句话摘要（见 `plugins/dsh_watcher/event_summarizer.py`）；
- 摘要仍会以截断形式进入桌宠的 LLM 上下文——若你的 DSH 会话含高度敏感内容，请知悉此行为，或把 `plugins/dsh_watcher/config.json` 中 `speak_on_*` 全部设为 `false`、并将插件 `enabled` 设为 `false` 后重启桌宠，即可完全关闭监听；
- TTS 文本会发送到本地语音桥（`127.0.0.1:9880`）或 edge-tts 在线服务，请按需选择。

## ❓ 常见问题

| 现象 | 处理 |
|---|---|
| TTS 无声音 | 确认 `start_tts_bridge.bat` 已启动且服务健康（浏览器访问 `http://127.0.0.1:9880/` 返回 200）；端口 9880 被占用时换端口并同步修改 Sakura 的 TTS 地址 |
| 提示「找不到模型文件」 | WSL 内模型未就位，按 [docs/SETUP.md](docs/SETUP.md)「WSL 部署」下载模型放入 `tools/edge_tts_bridge/vits/saved_model/19/` |
| 没有立绘/显示占位图 | 立绘是本地个人素材（不入库），先运行 `python characters/ikaros/make_placeholder_portraits.py` 生成占位图，再按 [characters/ikaros/README.md](characters/ikaros/README.md) 替换 |
| 中文路径崩溃 | 确保 Sakura 部署目录为纯英文路径（PySide6 限制） |
| 桌宠不说话 | 检查 LLM API 配置与网络；`dsh_watcher` 有 120 秒发言冷却与启动 30 秒保护，属正常设计 |

## 📁 目录结构

```
dsh-ikaros-pet/
├── characters/ikaros/          # 角色包（character.json, card.md, portraits/, voice/）
├── plugins/dsh_watcher/        # DSH 感知插件（plugin.py, dsh_reader.py, event_summarizer.py, config.json）
├── tools/edge_tts_bridge/      # 语音桥（vits_server.py, server.py, wsl_run_vits.sh, requirements.txt）
├── docs/                       # SETUP / PATCHES / ACKNOWLEDGEMENTS
├── assets/                     # 运行截图 / 架构图（gpt-image-2 生成）
├── install.bat / start.bat / start_tts_bridge.bat
└── .github/                    # 规范模板（Issue/PR）
```

## 🙏 致谢

- **[Sakura Desktop Pet](https://github.com/Rvosy/Sakura)**（Rvosy，MIT）—— 运行主体与全部能力的来源，仅做扩展、不改核心；
- **[DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)** —— 会话日志感知对象；
- **Ikaros521/moe-tts**（HuggingFace）—— 伊卡洛斯 VITS 声线模型来源；
- **edge-tts / zstandard / miniaudio / 智谱 / DeepSeek** —— 语音与模型能力；
- 《天降之物》角色设定 —— 角色扮演参考（版权归原作者水无月嵩/讲谈社等，本项目不包含任何官方素材）。

完整致谢见 [docs/ACKNOWLEDGEMENTS.md](docs/ACKNOWLEDGEMENTS.md)，第三方组件与许可证清单见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 📜 License 与声明

MIT License，详见 [LICENSE](LICENSE)。运行主体为 Sakura Desktop Pet（MIT，作者 Rvosy），**Sakura 本体不随本仓库分发**，需从[上游](https://github.com/Rvosy/Sakura)单独获取；使用本项目即表示已了解并遵守 Sakura 的许可条款。

**非官方同人声明**：本项目是非官方个人同人项目，与《天降之物》及其权利方（水无月嵩 / 讲谈社等）无任何官方关联。仓库不包含《天降之物》官方素材，也不分发立绘、参考音频与声线模型权重；相关素材由用户本地自行准备，其版权、肖像、声音、模型许可及使用边界由用户自行确认与负责。请勿将未获授权的素材上传到本仓库、Release 或任何公开渠道。VITS 模型（Ikaros521/moe-tts）许可证不明确，默认视为**不可公开再分发**；不得用于冒充真实人物、误导性对话、商业配音或任何违法用途。

*命令吗？—— 伊卡洛斯，已确认与主人连接。*
