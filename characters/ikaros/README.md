# 伊卡洛斯角色包（characters/ikaros）

《天降之物》风格的桌宠角色包，基于 Sakura Desktop Pet 角色包规范。

## 目录结构

```
characters/ikaros/
├── character.json              # 角色清单（manifest）
├── card.md                     # 人格卡（系统提示词核心）
├── portraits/                  # 立绘
│   ├── default.png             # 默认立绘（占位图）
│   ├── curious.png             # 疑惑（占位图）
│   ├── worried.png             # 担心（占位图）
│   ├── happy.png               # 开心（占位图）
│   └── angry.png               # 生气（占位图）
└── make_placeholder_portraits.py  # 占位图生成脚本（PIL）
```

## 关于立绘（重要）

仓库内 5 张立绘是**程序生成的占位图**（天使剪影风格，MIT 可自由使用），
**不包含《天降之物》官方素材**（官方立绘/音乐受版权保护，请勿上传到本仓库）。

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
