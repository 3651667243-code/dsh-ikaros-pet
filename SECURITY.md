# 安全说明（Security）

## 项目性质与安全边界

**ikaros-dsh-pet 是桌宠扩展，不是安全边界产品。**

本项目运行在 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura) 宿主之上，由三部分组成：

- **`dsh_watcher` 插件**：以用户权限在宿主机上运行，只读读取 DeepSeek Harness（DSH）会话日志；
- **TTS 语音桥**：`edge_tts_bridge`（edge-tts 版）与 `vits_server.py`（VITS 版）均为本地 HTTP 服务，默认只监听 `127.0.0.1:9880`；
- **角色包**：纯配置与立绘素材。

以上组件都会联网调用 LLM / 语音合成服务，并且**在宿主环境（Windows / WSL）以你的用户权限执行代码**。项目不提供认证、加密、沙箱或权限隔离机制，请在可信环境、可信配置下使用，不要把本仓库代码当作安全边界来依赖。

## 报告漏洞

如果你发现安全问题（如日志越权读取、配置泄露、服务被非本机访问等），请通过以下方式之一报告：

- **GitHub Issues**：新建 Issue 并勾选「这是安全相关问题」；描述请只写现象与影响，**不要粘贴任何密钥或敏感配置原文**；
- **GitHub 私密漏洞报告**：若仓库启用了 Security Advisory，请优先使用私密报告入口；
- **联系维护者**：`[维护者联系方式占位：GitHub @3651667243-code，或仓库 README 中的联系方式]`。

我们会尽快响应；在问题修复前，请勿公开披露细节。

## 安全注意事项

### API Key 管理

- 本项目支持 GLM / DeepSeek / OpenAI 中转等 OpenAI 兼容服务，**API Key 只在本地 Sakura 配置中填写**（Sakura 的本地配置文件，如 `data/config/api.yaml`）；
- **绝不把 API Key 写入本仓库**，包括：代码、配置文件、注释、提交信息、Issue、PR；
- 粘贴日志、配置片段时，先隐去 `sk-` 等密钥前缀内容；`plugins/dsh_watcher/config.json` 中不含任何密钥，请勿向其中添加。

### 模型与立绘版权

- 仓库内立绘为程序生成的占位图（`characters/ikaros/make_placeholder_portraits.py` 生成），**不包含《天降之物》的任何官方素材**；
- **AI 生成立绘与角色模型仅供个人使用，请勿提交进仓库**；
- `vits_server.py` 所需的 VITS 模型文件（`tools/edge_tts_bridge/vits/saved_model/19/`）涉及训练声线等版权问题，**不入库**，需使用者自行准备；
- 提交代码前，请确认没有把任何版权受限的素材、模型权重或他人代码混入 PR。

### DSH 日志读取

- `dsh_watcher` **只读**：以增量方式只读解析 `~/.dsh/sessions/*/session.jsonl.zstd`，绝不修改 DSH 的任何数据；
- 插件有**截断式脱敏设计**：事件摘要的文本字段限制在 40~60 字符内（见 `event_summarizer.py` 的 `_text()`），工具参数与结果只保留一句话摘要，不完整回显长文本；
- 但摘要仍可能包含截断后的消息内容。**如果你的 DSH 会话包含高度敏感的内容，请知悉这些内容会以摘要形式进入桌宠的 LLM 上下文**，必要时可关闭插件的 `context_provider` 功能或停止使用本插件。

### 最小权限

- 插件在 `plugin.yaml` 中仅声明所需权限（`context_provider`、`event.app`），新增功能时请保持权限最小化，不要扩大权限范围。

## 支持的版本

**本项目只维护 `main` 分支**。安全修复只会合入 `main`，其余分支、历史提交与第三方分发不提供安全支持；请始终使用 `main` 上的最新版本。

---

如有任何安全问题，欢迎按上文方式联系我们。
