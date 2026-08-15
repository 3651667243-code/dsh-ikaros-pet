# edge-tts 语音桥（edge_tts_bridge）

让 Sakura Desktop Pet 通过标准的 **GPT-SoVITS 外置服务接口**，使用微软 Edge 神经语音（**免费**）进行合成。

- 纯 Python 标准库 + [edge-tts](https://github.com/rany2/edge-tts)，无 GPU、无模型下载；
- 默认日文语音 `ja-JP-NanamiNeural`（偏安静、适合三无系角色），中文 `zh-CN-XiaoyiNeural`；
- 网络受限时可用 `--proxy` 走代理。

## 用途

Sakura Desktop Pet 支持「外置 TTS 服务」模式（典型实现为 GPT-SoVITS：本地起一个 HTTP 服务，Sakura 把要合成的话 POST 过去，服务返回 wav 播放）。本项目用免费的 edge-tts 实现同一份协议，因此 **Sakura 侧无需任何改动**，只需把 TTS 指向本桥地址，即可获得免费语音。

## 协议对齐（GPT-SoVITS 兼容）

本桥模拟 Sakura 所对接的 GPT-SoVITS 外置服务协议（对应 `app/voice/tts_synthesis.py` / `tts_service.py`）：

| 方法与路径 | 行为 |
|---|---|
| `GET /` | 返回 200 文本，用于 Sakura 的就绪探测 |
| `GET /set_gpt_weights` | 返回 200（edge-tts 无权重概念，返回空成功） |
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
- `text_lang` 以 `zh` 开头时用中文语音，其余默认用日文语音；
- 参考音频等其他字段（GPT-SoVITS 专用）**全部忽略**。

## 安装

```bat
pip install edge-tts
```

> 在本项目的一键安装流程中，`install.bat` 会把依赖装进 Sakura 自带运行时（`runtime\python.exe -m pip install edge-tts`），通常无需手动安装。

## 启动

```bat
python server.py
```

默认监听 `127.0.0.1:9880`，就绪后输出：

```
[edge-tts-bridge] 就绪：http://127.0.0.1:9880/tts  (ja=ja-JP-NanamiNeural, zh=zh-CN-XiaoyiNeural)
```

### 常用参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 监听地址 |
| `--port` | `9880` | 监听端口 |
| `--ja-voice` | `ja-JP-NanamiNeural` | 日文语音 |
| `--zh-voice` | `zh-CN-XiaoyiNeural` | 中文语音 |
| `--rate` | `+0%` | 语速，如 `+10%` / `-10%` |
| `--volume` | `+0%` | 音量，如 `+10%` / `-10%` |
| `--proxy` | 无 | HTTP(S) 代理地址（如 `http://127.0.0.1:7890`），网络受限时需要 |

示例（改端口 + 代理）：

```bat
python server.py --port 9881 --proxy http://127.0.0.1:7890
```

> 改了端口后，Sakura 侧的 `api_url` 也要同步修改。

## 在 Sakura 中配置

1. 先启动本桥（保持窗口开着）；
2. Sakura 设置中，TTS Provider 选择**外置服务（gpt-sovits）**；
3. `api_url` 填：`http://127.0.0.1:9880/tts`；
4. 测试发言，应能听到伊卡洛斯的合成语音。

## 依赖

- 运行时依赖：`edge-tts`（见 `requirements.txt`）；
- 无其他第三方依赖（HTTP 服务基于 Python 标准库 `http.server`）。

## 常见问题

- **没有声音**：确认桥已就绪、`api_url` 填了 `/tts` 完整地址、系统音量正常；网络受限时加 `--proxy`。
- **合成失败 / 超时**：edge-tts 需要访问微软语音服务，国内网络不稳定时可加代理；也可更换语音（`--ja-voice` / `--zh-voice`，可用 `edge-tts --list-voices` 查看可选语音）。
