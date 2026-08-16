# 安装与配置教程（从零复现）

本文面向第一次接触本项目的用户，从零开始把伊卡洛斯桌宠完整跑起来（约 15~30 分钟，
取决于模型下载速度）。**按本文操作，任何环境都能复现**；遇到问题先看文末 FAQ，
再不行到仓库提 Issue。

> 快速回顾：**运行主体是 [Sakura Desktop Pet](https://github.com/Rvosy/Sakura)**
> （MIT，作者 Rvosy）。本仓库是它的扩展（角色包 + 插件 SDK `api_version: 2` +
> 外置 TTS 服务）。因此安装 = 准备 Sakura → 复制扩展 → **应用本地补丁** →
> 配置模型 → 部署语音桥 → 启动。

---

## 1. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11（Sakura 官方提供 Windows Release） |
| Python | 3.10+，**由 Sakura Release 自带**（`runtime/python.exe`），无需单独安装 |
| Sakura Release | 完整解压，含 `main.py` 与 `runtime/` 目录 |
| WSL2 + Ubuntu | **VITS 声线需要**（只用 edge-tts 可跳过，见 6.2） |
| 网络 | 下载模型、调用 LLM/TTS 需联网；国内可配合代理或镜像（见各节） |

## 2. 获取 Sakura Release

1. 打开 [Sakura Desktop Pet Releases](https://github.com/Rvosy/Sakura/releases)，下载 Windows 版压缩包；
2. 解压到**纯英文路径**（PySide6 中文路径会崩溃），推荐目录布局：
   ```
   D:\pet\
   ├── Sakura\            ← Sakura Release 解压目录（含 main.py、runtime\）
   └── ikaros-dsh-pet\    ← 本仓库（git clone 或下载解压）
   ```
3. 确认 `Sakura\main.py` 与 `Sakura\runtime\python.exe` 存在。

## 3. 一键安装扩展：install.bat

```bat
cd /d D:\pet\ikaros-dsh-pet
install.bat
```

脚本自动完成：复制角色包 → `Sakura\characters\ikaros\`；复制插件 →
`Sakura\plugins\dsh_watcher\`；复制 TTS 桥 → `Sakura\tools\edge_tts_bridge\`；
用 Sakura 自带运行时安装依赖（edge-tts / zstandard / miniaudio，见
`tools/edge_tts_bridge/requirements.txt`）。任一步失败会报错退出。

Sakura 不在默认位置时：`install.bat D:\somewhere\Sakura`。

## 4. 应用本地适配补丁（必需，最容易漏的一步）

Sakura 原生不支持「插件主动发言」「双语字幕」「中文 TTS 放行」等能力，
仓库提供**自动补丁脚本**（幂等，可重复执行）：

```bat
Sakura\runtime\python.exe tools\apply_patches.py D:\pet\Sakura
```

输出全部 `[OK]` 即完成；`--list` 只看状态，`--dry-run` 只检查不修改。
**Sakura 升级后必须重新运行本脚本**。补丁明细见 `docs/PATCHES.md`。

> 不应用补丁的后果：插件能读 DSH 日志但**不会主动开口**，字幕无双语，中文回复无声。

## 5. 配置模型（文本 + 视觉）

支持「文本模型 + 视觉模型」双槽位（`model_slots`）：含图片的消息自动走视觉模型，
纯文本走聊天模型。

**方案 A（推荐，免费视觉）**：DeepSeek-chat（文本）+ GLM-4V-Flash（视觉，免费）

1. 注册 [DeepSeek 开放平台](https://platform.deepseek.com/) 与
   [智谱开放平台](https://open.bigmodel.cn/)，各创建 API Key；
2. 首次启动 Sakura（第 7 节）后，在设置中：
   - 聊天模型（chat 槽位）：Base URL `https://api.deepseek.com/v1`，模型 `deepseek-chat`，填 DeepSeek Key；
   - 视觉模型（vision_chat 槽位）：Base URL `https://open.bigmodel.cn/api/paas/v4`，模型 `glm-4v-flash`，填智谱 Key；
   - 记忆整理模型：留空（继承聊天模型）。

也可直接编辑 `Sakura\data\config\api.yaml`（等价）：

```yaml
llm:
  base_url: https://api.deepseek.com/v1
  api_key: <你的DeepSeek Key>
  model: deepseek-chat
  timeout_seconds: 60
api_profiles:
- id: glm-profile
  alias: GLM
  base_url: https://open.bigmodel.cn/api/paas/v4
  api_key: <你的智谱 Key>
  models:
  - name: glm-4v-flash
- id: ds-profile
  alias: DeepSeek
  base_url: https://api.deepseek.com/v1
  api_key: <你的DeepSeek Key>
  models:
  - name: deepseek-chat
model_slots:
  chat:
    profile_id: ds-profile
    model: deepseek-chat
  vision_chat:
    profile_id: glm-profile
    model: glm-4v-flash
```

**方案 B（全免费）**：智谱 GLM-4-Flash 同时做文本与视觉（`glm-4-flash` 文本 +
`glm-4v-flash` 视觉，同一个 Key）。视觉槽位切换后屏幕观察能力不变。

> 密钥只存在本地 `api.yaml`，**切勿提交到仓库 / Issue / 聊天**；泄露后立即到服务商撤销。

## 6. 部署语音

两条路任选：**VITS 伊卡洛斯声线（推荐，本地推理）** 或 **edge-tts（免部署，在线）**。

### 6.1 VITS 声线（WSL 内运行，伊卡洛斯音色）

**6.1.1 准备 WSL Ubuntu**（没有则先 `wsl --install -d Ubuntu`，之后 `wsl -d Ubuntu` 进入）：

```bash
# 进入 WSL 后：
sudo apt update && sudo apt install -y python3-venv python3-pip
cd ~
python3 -m venv ikaros-vits-venv
source ikaros-vits-venv/bin/activate

# 核心依赖（CPU 推理）
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu
pip install pyopenjtalk==0.4.1 numba scipy tqdm numpy onnxruntime \
    opencv-python-headless jieba cn2an OpenCC eng-to-ipa inflect jamo ko-pron
```

> pyopenjtalk 为预编译 wheel（cp310 等）；若 pip 找不到对应 Python 版本的轮子，
> 按报错提示安装编译工具（`sudo apt install -y build-essential cmake`）后重试。

**6.1.2 下载模型权重**（约 151MB，声线模型不入库）：

⚠️ 该模型是 **Gated（受限）模型**：先注册 [HuggingFace](https://huggingface.co/join)，
在浏览器打开 <https://huggingface.co/Ikaros521/moe-tts> 点击「Agree and access repository」
同意条款，再在 Settings → Access Tokens 生成 read 令牌。然后在 **Windows** 侧执行：

```bat
set HF_TOKEN=hf_你的令牌
Sakura\runtime\python.exe tools\edge_tts_bridge\download_model.py
:: 国内网络慢/失败时用镜像（同样需要 token）：
Sakura\runtime\python.exe tools\edge_tts_bridge\download_model.py --mirror --token hf_你的令牌
```

脚本把 `model.pth` 放到 `tools\edge_tts_bridge\vits\saved_model\19\`
（`config.json` 已随仓库提供）。模型许可证不明确，**仅供个人使用，禁止再分发与商用**。

**6.1.3 启动桥**：

双击 `start_tts_bridge.bat`（默认用 WSL 默认发行版；多发行版先
`set WSL_DISTRO=你的发行版名`）。模型加载约 30~60 秒，就绪后：

```bat
curl http://127.0.0.1:9880/   :: 返回 ok 即就绪
```

**6.1.4（可选）访问令牌**：桥监听 `0.0.0.0`（WSL2 localhost 转发需要）。
防局域网误调用可配令牌：`set VITS_AUTH=一串随机字符` 后启动桥，Sakura 的
TTS 地址填 `http://127.0.0.1:9880/tts?token=<那串字符>`。无令牌请求返回 401。

### 6.2 edge-tts 备选（免 WSL，需联网）

不想要 VITS 时，直接跑 edge-tts 桥（install.bat 已装好依赖）：

```bat
Sakura\runtime\python.exe Sakura\tools\edge_tts_bridge\server.py
:: 网络受限加代理：--proxy http://127.0.0.1:7890
```

声音为微软神经语音（日文 ja-JP-NanamiNeural / 中文 zh-CN-XiaoyiNeural），
非伊卡洛斯音色，但部署零成本。

## 7. 启动 Sakura 并完成首次配置

1. 双击 `start.bat`（仓库与 Sakura 同级时自动找到 Sakura）；
2. 首次启动按引导配置：
   - **角色**：选择「伊卡洛斯」；
   - **LLM**：按第 5 节填文本模型（视觉模型在设置 → 模型槽位里配）；
   - **TTS**：Provider 选外置服务（gpt-sovits），`api_url` 填
     `http://127.0.0.1:9880/tts`（启用了令牌则带 `?token=`）；
3. 伊卡洛斯开场白：「……伊卡洛斯，已确认与主人连接。有什么吩咐吗？」——成功。

**验证扩展是否生效**：
- 对话里说「看看我的屏幕」→ 她会截图并用视觉模型描述（自己窗口已被排除，不会描述自己）；
- 打开 DSH 跑任务 → 关键节点（目标完成/工具失败）她会主动开口；
- 屏幕上长时间建模/学习 → 每 10 分钟她按情境鼓励或提醒休息。

## 8. 立绘说明（个人素材，不入库）

`characters/ikaros/portraits/` 是**本地个人素材**（AI 生成/自绘，涉及角色形象权利，
请自行确认使用边界），已加入 `.gitignore` 不随仓库分发。全新 clone 后：

```bat
python characters\ikaros\make_placeholder_portraits.py   :: 生成 MIT 占位图（天使剪影）
```

再按需替换为你自己的立绘（命名与 `character.json` 的 `portrait.expressions` 一致）。
详见 `characters/ikaros/README.md`。

## 9. 常见问题（FAQ）

**Q1：apply_patches.py 报「找不到锚点」？**
Sakura 版本已变化，补丁文本对不上。请到仓库 Issue 报告你的 Sakura 版本号，
或对照 `docs/PATCHES.md` 手动应用。

**Q2：TTS 没声音？**
1. `curl http://127.0.0.1:9880/` 应返回 `ok`（VITS）或 200（edge-tts）；
2. 若返回 503，等模型加载完再试；`curl http://127.0.0.1:9880/tts -X POST -d "{\"text\":\"test\"}"`
   看错误信息（缺模型/缺依赖/401 令牌）；
3. 401 = 桥启用了令牌而 Sakura 地址没带 `?token=`；
4. 仍无声 → 查 Sakura 日志 `Sakura\data\logs\sakura-runtime.log` 里的 `tts` 条目。

**Q3：屏幕观察报「模型不支持图片」？**
视觉槽位（vision_chat）没配或配成了纯文本模型。按第 5 节配置 `glm-4v-flash` 并重启。

**Q4：插件没生效 / 不主动开口？**
1. 确认补丁已应用（第 4 节，`--list` 全 OK）；
2. `Sakura\plugins\dsh_watcher\plugin.yaml` 的 `enabled: true`（默认即是）；
3. `config.json` 的 `workspace_keyword` 填你的 DSH 工作区关键字（如 `ikaros`），
   `dsh_home` 默认 `~/.dsh`，DSH 数据目录非常规位置时显式填写；
4. 重启 Sakura；DSH 有活动（目标完成/工具失败/等待授权）时观察 120 秒冷却内的开口。

**Q5：她盯着别的项目/工作区看？**
`workspace_keyword` 是**严格匹配**：目录名不含该关键字的 DSH 工作区一律不读
（无匹配时静默）。把关键字改成你实际的工作区名。

**Q6：模型下载太慢/失败？**
用 `--mirror`（hf-mirror.com 镜像）；或浏览器直连
`https://huggingface.co/Ikaros521/moe-tts/resolve/main/saved_model/19/model.pth`
下载后放到 `tools\edge_tts_bridge\vits\saved_model\19\model.pth`。

**Q7：想重置全部配置？**
删除 `Sakura\data\config\` 后重启 Sakura，按首次引导重新配置。

**Q8：WSL 里 pip 装 pyopenjtalk 失败？**
预编译轮子按 Python 版本提供（venv 默认 Python 3.10/3.12 均有）。失败时：
`sudo apt install -y build-essential cmake` 后重试；再不行用
`pip install lemon-pyopenjtalk-prebuilt`（社区预编译包）。

---

遇到本文未覆盖的问题，在仓库提 Issue，附上：
`apply_patches.py --list` 输出、`curl http://127.0.0.1:9880/` 结果、
`Sakura\data\logs\sakura-runtime.log` 最近 30 行（先隐去密钥）。
