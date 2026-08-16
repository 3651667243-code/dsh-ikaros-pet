# 第三方组件与许可证清单（Third Party Notices）

本项目基于开源生态构建。以下为已知的第三方组件、来源与许可证状态。
**许可证信息以各上游项目实际发布为准；标注「待核实」的组件请在使用前自行确认。**

| 组件 | 用途 | 来源 | 许可证 | 是否随本仓库分发 |
|---|---|---|---|---|
| [Sakura Desktop Pet](https://github.com/Rvosy/Sakura) | 运行主体（桌宠框架） | GitHub（作者 Rvosy） | MIT | 否（用户从上游单独获取） |
| [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) | 会话日志感知对象 | GitHub（DeepSeek AI） | 以其上游为准 | 否（仅只读其会话日志） |
| [Ikaros521/moe-tts](https://huggingface.co/Ikaros521/moe-tts) | VITS 声线模型（推理目标） | HuggingFace | 待核实（默认视为不可再分发、不可商用） | 否（模型权重不入库） |
| [edge-tts](https://github.com/rany2/edge-tts) | 备选 TTS（在线） | GitHub / PyPI | 以其上游为准（服务受微软条款约束） | 否（依赖安装） |
| [zstandard](https://github.com/facebook/zstd) | zstd 会话日志解压 | GitHub / PyPI | BSD-3-Clause | 否（依赖安装） |
| [miniaudio](https://github.com/mackron/miniaudio) | 音频格式转换/播放 | GitHub / PyPI | 公有领域 (Public Domain) / MIT | 否（依赖安装） |
| torch / pyopenjtalk 等（WSL 侧） | VITS 推理运行时 | PyPI | 以其上游为准 | 否（WSL 内自行安装） |
| DeepSeek / 智谱 GLM / OpenAI 兼容中转 | LLM 对话服务 | 各服务商 | 按服务商服务条款 | 否（在线 API） |
| gpt-image-2 | 概念图（assets/arch.png） | OpenAI 兼容服务 | 按服务商条款（个人使用） | 是（仅文档图） |

## 素材声明

- 本仓库**不包含**《天降之物》官方素材、角色立绘、参考音频与声线模型权重；
- 立绘为**本地个人素材（不入库）**，仓库仅提供 MIT 可自由使用的占位图生成脚本（`characters/ikaros/make_placeholder_portraits.py`）；
- `Ikaros521/moe-tts` 模型许可证不明确，默认视为不可公开再分发；不得用于冒充真实人物、误导性对话、商业配音或任何违法用途；
- 用户自行获取与使用任何第三方素材、模型或服务时，应自行确认其许可证、版权及使用边界，并自行承担相应责任。

## 上游许可证保留

Sakura Desktop Pet 的完整版权声明与 MIT License 文本已保留在本仓库 [LICENSE](LICENSE) 中；本项目未重新分发 Sakura 的完整运行时，用户应从上游官方渠道获取 Sakura。本仓库提供的适配补丁仅适用于对应上游版本（见 [docs/PATCHES.md](docs/PATCHES.md)），不代表本仓库拥有 Sakura 的版权。
