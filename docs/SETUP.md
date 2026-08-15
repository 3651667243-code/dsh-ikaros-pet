# 安装与配置教程

本文面向第一次接触本项目的用户，从零开始把伊卡洛斯桌宠跑起来。整个安装过程约 10 分钟。

> 快速回顾：本项目的**运行主体是 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura)**（MIT License，作者 Rvosy）。本仓库只是它的扩展，通过官方扩展点（角色包 + 插件 SDK `api_version: 2` + 外置 TTS 服务）接入，因此安装的第一步是准备好一个 Sakura Release。

---

## 1. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows（Sakura 官方提供 Windows Release） |
| Python | 3.10+，**由 Sakura Release 自带**（`runtime/python.exe`），无需单独安装 |
| Sakura Release | 必须解压完整，含 `main.py` 与 `runtime/` 目录 |
| 网络 | 配置 LLM 与 TTS 均需联网；网络受限时见「常见问题」的 `--proxy` 说明 |

## 2. 获取 Sakura Release

1. 打开 [Sakura Desktop Pet Releases](https://github.com/Rvosy/Sakura/releases)，下载 Windows 版压缩包；
2. 解压到任意目录（推荐解压到一个干净的目录，比如 `D:\pet\Sakura`）；
3. 确认解压后的目录里有：
   - `main.py` —— Sakura 入口；
   - `runtime/` —— 自带 Python 运行时（**缺少它 install.bat 无法安装依赖**）。

> 建议目录布局（本仓库默认按此布局查找 Sakura）：
> ```
> D:\pet\
> ├── Sakura\            ← Sakura Release 解压目录
> └── ikaros-dsh-pet\    ← 本仓库（克隆或解压到这里）
> ```

## 3. 一键安装：install.bat

1. 把本仓库放到 Sakura 目录**旁边**（同级目录，见上）；
2. 双击运行 `install.bat`（或在命令行执行 `install.bat`）。脚本会依次完成：

   | 步骤 | 内容 |
   |---|---|
   | 1/4 | 定位 Sakura 目录（默认取旁边的 `..\Sakura`，找不到会提示手动输入） |
   | 2/4 | 复制角色包 → `Sakura\characters\ikaros\` |
   | 3/4 | 复制插件 → `Sakura\plugins\dsh_watcher\` |
   | 4/4 | 复制 TTS 桥 → `Sakura\tools\edge_tts_bridge\` |
   | 5/4 | 用 `runtime\python.exe` 安装依赖 `zstandard`、`edge-tts` |

3. 看到「安装完成！」即成功。

> 提示：如果 Sakura 不在默认位置，可显式指定：`install.bat D:\somewhere\Sakura`。若你的 Sakura Release 缺少 `runtime/`，脚本会提示手动执行依赖安装命令（见输出中的提示），先补全 Release 再装。

## 4. 配置 LLM：智谱 GLM-4-Flash（免费）

GLM-4-Flash 是智谱开放平台的免费模型，OpenAI 兼容接口，支持 function calling（Sakura 的 Agent 能力需要它）。

1. 注册并登录 [智谱开放平台](https://open.bigmodel.cn/)；
2. 在「API 密钥」页面创建 API Key（形如 `xxxxxxxx.xxxxxxxx`）；
3. 启动 Sakura 后，在设置 / 首次引导中填写：

   | 配置项 | 值 |
   |---|---|
   | Provider / 接口类型 | OpenAI 兼容接口 |
   | Base URL | `https://open.bigmodel.cn/api/paas/v4` |
   | Model / 模型名 | `glm-4-flash` |
   | API Key | 你创建的密钥 |

4. 保存后测试对话，伊卡洛斯应能正常回复。

> 切换其他服务（如 DeepSeek）：在同样的位置把 Base URL、模型名、API Key 换成目标服务的 OpenAI 兼容参数即可，无需改代码。

## 5. 启动 TTS 语音桥

TTS 桥是独立于 Sakura 的免费语音服务进程，监听 `127.0.0.1:9880`。

1. 双击 `start_tts_bridge.bat`；
2. 看到输出：
   ```
   [edge-tts-bridge] 就绪：http://127.0.0.1:9880/tts  (ja=ja-JP-NanamiNeural, zh=zh-CN-XiaoyiNeural)
   ```
   即成功。保持该窗口开着。

### 5.1 网络受限时加代理

edge-tts 需要访问微软语音服务，部分网络环境连不上。给桥加 `--proxy` 参数即可：

```bat
python server.py --proxy http://127.0.0.1:7890
```

> 7890 是本机常见代理端口示例；换成你自己的代理地址。手动运行前请先激活 Sakura 自带运行时（见 FAQ：如何手动运行桥）。

### 5.2 常用参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--port` | `9880` | 监听端口，改后需同步修改 Sakura 侧 URL |
| `--ja-voice` | `ja-JP-NanamiNeural` | 日文语音 |
| `--zh-voice` | `zh-CN-XiaoyiNeural` | 中文语音 |
| `--rate` | `+0%` | 语速，如 `+10%` / `-10%` |
| `--volume` | `+0%` | 音量，如 `+10%` / `-10%` |
| `--proxy` | 无 | HTTP(S) 代理地址，网络受限时使用 |

## 6. 启动 Sakura 并完成首次引导

1. 双击 `start.bat` 启动 Sakura；
2. 首次启动按引导完成配置：
   - **角色**：选择「伊卡洛斯」；
   - **LLM**：按第 4 节填写 GLM-4-Flash；
   - **TTS**：Provider 选外置服务（gpt-sovits），`api_url` 填 `http://127.0.0.1:9880/tts`；
3. 伊卡洛斯向你问好（默认开场白：「……伊卡洛斯，已确认与主人连接。有什么吩咐吗？」），即配置成功。

至此，桌宠会在对话中使用免费 GLM 思考、用免费 edge 语音开口，并通过 `dsh_watcher` 插件感知你的 DeepSeek Harness 会话，在关键时刻主动开口。

## 7. 角色包与立绘替换

角色包位于 `characters/ikaros/`，复制到 Sakura 后位于 `Sakura\characters\ikaros\`。

### 7.1 角色包结构

| 文件 | 作用 |
|---|---|
| `character.json` | 角色配置：ID、显示名、人格卡引用、立绘映射、主题色、开场白、语音设置 |
| `card.md` | 人格卡：伊卡洛斯的性格设定与说话风格 |
| `portraits/` | 立绘目录 |
| `make_placeholder_portraits.py` | 生成占位立绘的脚本（当前 5 张 PNG 即由它生成） |

### 7.2 替换立绘

当前立绘是**程序生成的占位图**，欢迎用自己画的或 AI 生成的图替换。命名规则与 `character.json` 中 `portrait.expressions` 的映射保持一致：

| 表情键 | 文件名 | 对应情绪 |
|---|---|---|
| 平静 | `portraits/default.png` | 默认立绘（也用于「平静」） |
| 疑惑 | `portraits/curious.png` | 疑惑 |
| 担心 | `portraits/worried.png` | 担心 |
| 开心 | `portraits/happy.png` | 开心 |
| 生气 | `portraits/angry.png` | 生气 |

替换步骤：

1. 准备 5 张立绘（推荐 PNG，透明背景更佳，尺寸参考原占位图比例）；
2. 按上表命名并放入 `portraits/`，覆盖对应文件；
3. 若使用了不同文件名，请同步修改 `character.json` 的 `portrait.expressions` 映射；
4. 重启 Sakura 生效。

> 想重置为占位图？重新运行 `make_placeholder_portraits.py` 即可重新生成。

## 8. 常见问题（FAQ）

**Q1：TTS 没有声音？**

按顺序排查：
1. 确认桥窗口显示「就绪」，且 Sakura 的 `api_url` 填的是 `http://127.0.0.1:9880/tts`（不是根路径）；
2. 浏览器或命令行访问 `http://127.0.0.1:9880/`，应返回 200 文本（探测接口）；
3. 确认 Windows 音量、Sakura 语音开关正常；
4. 网络受限导致合成失败时，给桥加 `--proxy`（见 5.1）。

**Q2：网络受限（连不上微软语音 / 智谱接口）？**

- TTS：按 5.1 给桥加 `--proxy`；
- LLM：在 Sakura 设置中给 API 请求配置代理（取决于 Sakura 支持的代理设置），或使用可达的 OpenAI 兼容服务。

**Q3：提示缺少 zstandard 依赖？**

`install.bat` 应已把 `zstandard` 装进 Sakura 运行时。若仍报错，手动补装：

```bat
Sakura\runtime\python.exe -m pip install zstandard
```

安装后重启 Sakura。注意：请使用 Sakura 自带运行时安装，不要用系统 Python 装到别处。

**Q4：如何手动运行 TTS 桥？**

先激活 Sakura 自带运行时再执行（注意 `--port` 等参数要一致）：

```bat
Sakura\runtime\python.exe -m pip install edge-tts
Sakura\runtime\python.exe Sakura\tools\edge_tts_bridge\server.py
```

**Q5：`install.bat` 找不到 Sakura？**

默认在仓库同级找 `..\Sakura`。目录布局不一致时，用 `install.bat <Sakura安装目录>` 显式指定；或把仓库与 Sakura 放在同级目录。

**Q6：如何确认 dsh_watcher 插件在读取日志？**

插件的配置在 `Sakura\plugins\dsh_watcher\config.json`（`dsh_home` 默认取 `~/.dsh`；DSH 装在非常规位置时把它填为 DSH 数据目录）。对话时留意伊卡洛斯的上下文是否包含 DSH 会话摘要、以及在目标达成 / 工具失败等节点是否主动开口。默认 120 秒冷却，连续触发时不会每次都说话。

**Q7：插件 / 角色没生效？**

确认 `Sakura\characters\ikaros\` 与 `Sakura\plugins\dsh_watcher\` 存在（install.bat 复制过）；插件在 `plugin.yaml` 中 `enabled: true`；然后重启 Sakura。仍不行可重新运行一次 `install.bat`。

**Q8：想重置所有配置？**

删除 Sakura 的配置目录后重启（具体位置见 Sakura 文档），再按首次引导重新配置角色 / LLM / TTS 即可。

---

遇到本文未覆盖的问题，欢迎在项目仓库提交 Issue，附上桥窗口与 Sakura 的日志输出。
