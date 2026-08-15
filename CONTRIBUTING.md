# 贡献指南（Contributing）

感谢你愿意为 **ikaros-dsh-pet**（伊卡洛斯桌宠）贡献代码！本项目是 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura)（MIT License）的扩展发行：通过官方扩展点（角色包、插件 SDK、外置 TTS 服务）接入，让桌宠感知 DeepSeek Harness 会话并免费语音开口，**不改动 Sakura 核心代码**。阅读并遵守本指南，能让你的贡献更顺畅地被合入。

---

## 1. 技术栈

| 层 | 内容 |
|---|---|
| 宿主 | Sakura Desktop Pet（Python / PySide6 桌面 Agent 框架），来自 Sakura Release，本仓库不包含其源码 |
| 角色包 | `characters/ikaros/`（`character.json` + `card.md` + `portraits/` 立绘） |
| 插件 | `plugins/dsh_watcher/`，Sakura 插件 SDK **`api_version: 2`**（见 `plugin.yaml`，权限 `context_provider` / `event.app`） |
| TTS 桥 | `tools/edge_tts_bridge/`：`server.py`（免费 edge-tts 版）；`vits_server.py`（本地 VITS 版，GPT-SoVITS 兼容协议）；`wsl_run_vits.sh`（WSL 内启动脚本） |
| 脚本 | `install.bat` / `start.bat` / `start_tts_bridge.bat` |
| 文档 | `docs/`（`SETUP.md` 安装配置、`PATCHES.md` 本地补丁、`ACKNOWLEDGEMENTS.md` 致谢） |

## 2. 开发环境

详细安装步骤见 [docs/SETUP.md](docs/SETUP.md)，这里只列与开发相关的要点：

1. **准备 Sakura Release**：下载 Windows 版 Release 并解压，确认目录含 `main.py` 与 `runtime/`（自带 Python 运行时）。建议与仓库同级放置（如 `D:\pet\Sakura` + `D:\pet\ikaros-dsh-pet`）。
2. **一键安装**：运行 `install.bat`（Sakura 不在默认位置时用 `install.bat <Sakura目录>`）。脚本会复制角色包 / 插件 / TTS 桥到 Sakura，并用 `runtime\python.exe` 安装依赖（`zstandard`、`edge-tts`）。
3. **迭代改代码**：改完本仓库文件后，重新运行 `install.bat`（或手动把对应目录复制进 Sakura），再重启 Sakura 验证。
4. **WSL VITS 桥（可选）**：`vits_server.py` 需要 PyTorch 与 VITS 模型文件（本地放置于 `tools/edge_tts_bridge/vits/saved_model/19/`，不入库），建议在 WSL 发行版内建独立 venv（参考 `wsl_run_vits.sh` 中的 `/root/ikaros-vits-venv` 示例）再启动；WSL 通过 `/mnt/...` 访问 Windows 侧文件。日常开发验证语音，用零依赖的 edge-tts 桥（`start_tts_bridge.bat`）即可。
5. **本地补丁**：若你修改了 Sakura 侧适配（见 [docs/PATCHES.md](docs/PATCHES.md) 两处补丁），注意升级 Sakura Release 后需重新应用。

## 3. 分支规范

- `main`：发布分支，唯一受支持的版本，始终可用。
- `dev`：开发集成分支（仓库尚无时先从 `main` 创建），日常开发都从这里切分支。
- 功能分支：**从 `dev` 分支切出**，按用途命名：
  - `feat/xxx` —— 新功能
  - `fix/xxx` —— 缺陷修复

```bat
git checkout dev
git checkout -b feat/dsh-watcher-new-event
```

## 4. 提交信息

提交信息使用**中文描述**，采用类型前缀（参考 Sakura AGENTS.md 的提交风格）：

```
feat: 新增 approval/asked 事件的主动发言规则
fix: 修复日志轮询在文件轮转时的越界读取
docs: 更新 README 的配置说明
chore: 更新 install.bat 的依赖安装命令
```

前缀只使用 `feat:` / `fix:` / `docs:` / `chore:`；一次提交只做一件事，描述写清「改了什么、为什么」。

## 5. 代码风格

- **Python 3.10+**，使用 type hints（参考 `plugins/dsh_watcher/` 中 `Path | None`、`dict[str, Any]` 的写法）。
- 模块顶部保留 `# -*- coding: utf-8 -*-` 与中文 docstring（本项目统一中文注释）。
- **保持向后兼容**：不要破坏 Sakura 插件 SDK `api_version: 2` 的接口契约与 `plugin.yaml` 权限声明；不要改变 `character.json` 中已公开的立绘/语音映射键名（新增可，改名需同步文档）。
- 新增文件保持现有目录结构与命名习惯；批处理脚本保持与现有 `.bat` 一致的风格。
- **不要提交**：任何 API Key / 敏感配置、`data/` `runtime/` `logs/` 等运行时数据（已 gitignore）、AI 生成或他人版权的立绘 / 模型文件。

## 6. 测试要求

改动**核心链路**（插件、TTS 桥、安装脚本、补丁）必须完成验证，否则请在 PR 中说明未验证原因：

1. **语法检查**：所有改动 Python 文件通过 `py_compile`：
   ```bat
   python -m py_compile plugins\dsh_watcher\plugin.py
   ```
2. **Sakura 上游测试**：Sakura 上游的测试在其仓库的 `tests/` 目录。若改动涉及 Sakura 侧补丁（`docs/PATCHES.md`），请用 Sakura 自带运行时跑上游相关用例，确保不破坏宿主。
3. **真实环境验证（本地扩展）**：按 `docs/SETUP.md` 完成一次完整流程 —— 运行 `install.bat` → 启动 TTS 桥 → 启动 Sakura，然后：
   - 确认 `~/.dsh/sessions/*/session.jsonl.zstd` 存在，对话中伊卡洛斯的上下文包含 DSH 会话摘要；
   - 触发关键节点（目标达成 / 工具失败 / 等待授权），观察是否按 `config.json` 规则主动发言（默认 120 秒冷却，注意间隔）；
   - 查看 Sakura 日志 `data\logs\sakura-runtime.log` 中的 `PluginUI` / `PluginTTS` / `PluginAgent` 记录。

## 7. PR 流程

1. 从 `dev` 分支新建功能分支（见第 3 节）；
2. 小步提交，按第 4 节规范写提交信息；
3. 推送分支后提 PR（目标分支默认 `main`；若仓库已建立 `dev` 集成分支，先合入 `dev` 再随版本合入 `main`）；
4. PR 使用 `.github/PULL_REQUEST_TEMPLATE.md` 模板，**描述用中文**，写明：变更类型、变更说明、测试情况（py_compile / 真实验证 / 未验证原因）、关联 Issue、版权声明；
5. 维护者 review 后合并，合并后如无继续维护需要可删除功能分支。

## 8. 其他

- 提交前先看一下 [README.md](README.md) 与 [docs/SETUP.md](docs/SETUP.md)，确保文档与行为一致；
- 有疑问或拿不准的设计，先开 Issue 讨论再动手；
- 行为准则见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)，安全相关说明见 [SECURITY.md](SECURITY.md)。

*命令吗？—— 伊卡洛斯，已确认与主人连接。*
