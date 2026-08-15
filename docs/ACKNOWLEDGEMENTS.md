# 致谢 Acknowledgements

本项目的每一行「新增代码」都建立在他人的开源成果之上。在此郑重致谢所有直接或间接的贡献者。

> 一句话总述：**ikaros-dsh-pet 是 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura) 的扩展发行，运行主体仍是 Sakura，本仓库只通过其官方扩展点提供角色、插件与语音桥。** 使用本项目，即默认遵守 Sakura 及所有下游依赖的许可条款。

---

## 1. Sakura Desktop Pet（核心框架）

- **仓库**：<https://github.com/Rvosy/Sakura>
- **作者**：Rvosy
- **协议**：MIT License
- **致谢说明**：Sakura 是一个基于 Python / PySide6 的桌宠 Agent 框架，提供了桌面窗口、角色系统、对话、语音播放与 Agent 能力。**本项目的一切都运行在 Sakura 之上**：伊卡洛斯角色包是它的角色扩展，`dsh_watcher` 是它的插件（插件 SDK `api_version: 2`），edge-tts 语音桥是它的外置 TTS 服务。我们**没有修改 Sakura 的任何核心代码**，全部通过官方扩展点接入。向 Rvosy 的出色设计与开源分享致敬。

## 2. DeepSeek Harness（DSH）生态

- **仓库**：<https://github.com/deepseek-ai/deepseek-harness>
- **说明**：本项目中的 `dsh_watcher` 插件灵感来源于 DeepSeek Harness（DSH）的会话事件日志体系。插件以**只读**方式增量读取 DSH 会话日志（`~/.dsh/sessions/*/session.jsonl.zstd`，zstd 多 frame 追加格式），从中识别 `turn/start`、`tool/call`、`tool/result`、`step/start`、`tool-workflow/run-start`、`goal/change`、`approval/asked` 等关键节点，整理成中文摘要注入对话上下文，并在工作流完成、目标达成、工具失败、等待授权时触发主动发言。我们感谢 DSH 开放、可读的事件日志设计，让桌宠得以「看见」 Agent 的工作。插件**全程只读**，不修改 DSH 的任何数据。

## 3. edge-tts

- **说明**：`tools/edge_tts_bridge/` 的语音合成能力完全来自 [edge-tts](https://github.com/rany2/edge-tts)（微软 Edge 神经语音的免费调用封装）。桥本身只做协议翻译：把 Sakura 的 GPT-SoVITS 外置接口请求转成 edge-tts 调用，默认日文 `ja-JP-NanamiNeural`、中文 `zh-CN-XiaoyiNeural`。感谢 edge-tts 项目让免费高质量语音成为可能。

## 4. zstandard

- **说明**：DSH 会话日志是 zstd 压缩格式，`dsh_watcher` 依赖 [zstandard](https://github.com/facebook/zstd)（Facebook 的 Zstandard 压缩算法 Python 绑定）完成解压读取。感谢其高性能的压缩生态。

## 5. 智谱 GLM-4-Flash

- **说明**：本项目默认的对话模型是智谱开放平台的 **GLM-4-Flash**（免费、OpenAI 兼容接口、支持 function calling）。感谢智谱提供免费可用的中文大模型，让桌宠可以零成本拥有对话与工具调用能力。（也感谢所有其他可切换的 OpenAI 兼容服务，如 DeepSeek。）

## 6. 《天降之物》（Heaven's Lost Property）角色设定出处

- **作品**：《天降之物》（そらのおとしもの）
- **原作者**：水无月嵩（Mikazuki Minazuki）
- **版权归属**：作品版权归原作者水无月嵩 / 讲谈社（及相关版权方）所有。
- **声明**：本项目中的「伊卡洛斯」仅为**角色扮演参考**——借用其「三无、天然呆、绝对忠诚」的角色气质与「主人」「命令吗？」「我会守护主人」「铭刻」等标志性台词风格，向原作致敬。本项目**不包含《天降之物》的任何官方素材**：立绘为程序生成的占位图（`make_placeholder_portraits.py` 生成），欢迎用户用自己的创作替换。若您计划公开传播本项目，请自行确认是否符合当地法律与原作版权方要求；本项目不对任何第三方使用方式负责。

---

再次感谢每一位开源作者。愿开源精神长存。🪽
