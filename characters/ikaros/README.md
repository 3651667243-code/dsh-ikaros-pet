# 伊卡洛斯角色包（characters/ikaros）

《天降之物》风格的桌宠角色包，基于 Sakura Desktop Pet 角色包规范。

## 目录结构

```
characters/ikaros/
├── character.json              # 角色清单（manifest）
├── card.md                     # 人格卡（系统提示词核心）
├── portraits/                  # 立绘（本地个人素材，不入库）
│   ├── default.png             # 默认立绘
│   ├── curious.png             # 疑惑
│   ├── worried.png             # 担心
│   ├── happy.png               # 开心
│   └── angry.png               # 生气
└── make_placeholder_portraits.py  # 占位图生成脚本（PIL，MIT）
```

## 关于立绘（重要）

**立绘为本地个人素材，不随仓库分发**（AI 生成或自绘，涉及角色形象的权利来源，
请自行确认使用边界）。`portraits/` 目录已加入 `.gitignore`，即使放在工作区
也不会被提交；参考音频 `voice/refs/tone_refs/` 同理。

仓库内 `make_placeholder_portraits.py` 可生成 MIT 可自由使用的天使剪影占位图
（无任何第三方角色元素），clone 后没有立绘时先跑它：

```bash
python characters/ikaros/make_placeholder_portraits.py
```

想要更还原的立绘，推荐两种方式：

1. **AI 生成**：用你喜欢的 AI 绘图工具生成"粉色双马尾、白色羽翼、天使光环"的
   原创角色形象（避免直接模仿官方原画），导出为透明背景 PNG。
2. **自己绘制**：手绘/板绘后导出 PNG。

替换方法：

- 直接覆盖 `portraits/` 下同名 PNG（建议 512×768 或相近比例，透明背景最佳）；
- 如需新增表情，在 `portraits/` 放入新图，并在 `character.json` 的
  `portrait.expressions` 中登记（键为语气标签，值相对路径）；
- 在 Sakura 的角色工作室（start_studio.bat）里也可以可视化导入立绘并导出 `.char`。

## 角色包字段速览

| 字段 | 说明 |
|---|---|
| `id` / `display_name` | 角色 ID 与显示名 |
| `card` | 人格卡文件（markdown） |
| `portrait.default` / `portrait.expressions` | 默认立绘与语气→表情映射 |
| `theme` | UI 主题色（伊卡洛斯粉白蓝配色） |
| `reply.tones` | 语气标签白名单：平静/疑惑/担心/开心/生气 |
| `voice` | 语音配置（text_lang: ja 日语朗读） |
