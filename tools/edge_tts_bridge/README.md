# 语音桥（edge_tts_bridge）

让 Sakura Desktop Pet 通过标准的 **GPT-SoVITS 外置服务接口**获得语音合成，两个实现：

| 实现 | 说明 | 前置 |
|---|---|---|
| `vits_server.py`（**推荐**） | 伊卡洛斯 VITS 声线，WSL 内本地推理 | WSL2 + venv（`vits-requirements.txt`）+ 模型（`download_model.py`） |
| `server.py` | edge-tts 在线合成（免部署） | 仅 `pip install edge-tts`，需联网 |

两者协议一致，Sakura 侧无需改动，只改 `api_url`。

## VITS 声线桥（默认推荐）

本地推理，伊卡洛斯音色，无需联网合成。部署步骤见 `docs/SETUP.md`「6.1 VITS 声线」：

1. WSL 内建 venv 并安装依赖：`pip install -r vits-requirements.txt`（torch 用 CPU 轮）；
2. 下载模型权重：`python download_model.py [--mirror] [--token hf_xxx]`
   （⚠️ Gated 模型：需 HF 账号同意条款后提供 Access Token；`model.pth` 约 151MB，不入库）；
3. 启动：`wsl_run_vits.sh`（或 Windows 侧 `start_tts_bridge.bat`），模型加载约 30~60 秒；
4. 可选令牌：`VITS_AUTH=<token>` 环境变量启动，Sakura 的 `api_url` 带 `?token=<token>`。

`vits/` 目录为 VITS 推理代码（含 `text/` 文本前端，MIT，版权见 `vits/text/LICENSE`）；
`vits/saved_model/19/config.json` 随仓库提供，`model.pth` 需下载。

## edge-tts 桥（备选）

纯 Python 标准库 + [edge-tts](https://github.com/rany2/edge-tts)，无 GPU、无模型下载：
- 默认日文语音 `ja-JP-NanamiNeural`（偏安静、适合三无系角色），中文 `zh-CN-XiaoyiNeural`；
- 网络受限时可用 `--proxy` 走代理。

## 协议对齐（GPT-SoVITS 兼容）

本桥模拟 Sakura 所对接的 GPT-SoVITS 外置服务协议（对应 `app/voice/tts_synthesis.py` / `tts_service.py`）：

| 方法与路径 | 行为 |
|---|---|
| `GET /` | 返回 200 文本，用于 Sakura 的就绪探测 |
| `GET /set_gpt_weights` | 返回 200（无权重概念，返回空成功） |
| `GET /set_sovits_weights` | 返回 200（同上） |
| `POST /tts` | 返回音频字节（`audio/wav`） |

`POST /tts` 请求体为 JSON：

```json
{
  "text": "要合成的话",
  "text_lang": "ja",
  "ref_audio_path": "..."
}
```

- 只使用 `text` 与 `text_lang` 两个字段；
- VITS 桥按文本内容自动检测语言（含假名→日语发音，否则按中文）；
- edge-tts 桥 `text_lang` 以 `zh` 开头时用中文语音，其余默认用日文语音；
- 参考音频等其他字段（GPT-SoVITS 专用）**全部忽略**。

## 安全（访问令牌）

两个桥都支持 `--auth-token <token>`：配置后 `/tts` 与权重接口需带
`Authorization: Bearer <token>` 或 `?token=<token>`，否则返回 401；健康检查 `/` 放行。
WSL 部署时通过 `VITS_AUTH` 环境变量传入（见 `wsl_run_vits.sh`）。
