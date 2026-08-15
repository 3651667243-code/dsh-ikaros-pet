# -*- coding: utf-8 -*-
"""生成伊卡洛斯桌宠的占位立绘（程序绘制，无版权素材）。

生成 5 张 PNG：default / curious / worried / happy / angry。
这些是"占位立绘"——简单的天使剪影 + 光环 + 表情提示，
用于让角色包开箱可运行。替换方式见 characters/ikaros/README.md。

用法：python make_placeholder_portraits.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent

# 画布
W, H = 480, 720
# 头部中心 / 半径
HEAD_CX, HEAD_CY, HEAD_R = 240, 250, 110
# 光环
HALO_R = 150
# 发色 / 瞳色 / 肤色 / 衣色
PINK = (244, 164, 190)
PINK_DARK = (226, 128, 160)
SKIN = (255, 240, 240)
BLUE = (92, 158, 214)
RED = (214, 74, 74)
WHITE = (250, 250, 252)
BG = (255, 240, 245)
GRAY = (190, 178, 186)


def _base() -> Image.Image:
    img = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 大翅膀（左右两片，白色+浅灰描边）
    for flip in (1, -1):
        wing = [
            (HEAD_CX, 210),
            (HEAD_CX + 175 * flip, 120),
            (HEAD_CX + 205 * flip, 300),
            (HEAD_CX + 120 * flip, 380),
            (HEAD_CX, 330),
        ]
        d.polygon(wing, fill=(255, 255, 255, 235), outline=GRAY + (255,))
    # 光环
    d.ellipse(
        (HEAD_CX - HALO_R, HEAD_CY - HALO_R - 30, HEAD_CX + HALO_R, HEAD_CY + HALO_R - 30),
        outline=(255, 214, 130, 255),
        width=10,
    )
    # 双马尾（两侧大卷）
    for flip in (1, -1):
        d.arc(
            (HEAD_CX - 190 * flip - 80, HEAD_CY - 40, HEAD_CX - 60 * flip + 80, HEAD_CY + 330),
            start=150 if flip > 0 else 210,
            end=330 if flip > 0 else 30,
            fill=PINK,
            width=64,
        )
    return img


def _body(d: ImageDraw.ImageDraw, *, blush: bool = False, mouth: str = "flat") -> None:
    # 头发（头顶）
    d.arc(
        (HEAD_CX - HEAD_R, HEAD_CY - HEAD_R, HEAD_CX + HEAD_R, HEAD_CY + HEAD_R),
        start=180,
        end=360,
        fill=PINK,
        width=30,
    )
    # 脸
    d.ellipse(
        (HEAD_CX - HEAD_R, HEAD_CY - HEAD_R, HEAD_CX + HEAD_R, HEAD_CY + HEAD_R),
        fill=SKIN,
        outline=PINK_DARK + (255,),
        width=6,
    )
    # 眼睛（平时蓝色）
    eye_color = BLUE
    for flip in (1, -1):
        ex = HEAD_CX + 42 * flip
        ey = HEAD_CY + 8
        d.ellipse((ex - 20, ey - 26, ex + 20, ey + 6), fill=eye_color)
        d.ellipse((ex - 9, ey - 14, ex + 9, ey + 4), fill=(255, 255, 255, 255))
    if blush:
        for flip in (1, -1):
            d.ellipse(
                (HEAD_CX + 66 * flip - 14, HEAD_CY + 42, HEAD_CX + 66 * flip + 14, HEAD_CY + 66),
                fill=(255, 150, 165, 130),
            )
    # 嘴
    if mouth == "smile":
        d.arc(
            (HEAD_CX - 24, HEAD_CY + 46, HEAD_CX + 24, HEAD_CY + 84),
            start=15,
            end=165,
            fill=(190, 90, 110, 255),
            width=5,
        )
    elif mouth == "frown":
        d.arc(
            (HEAD_CX - 24, HEAD_CY + 34, HEAD_CX + 24, HEAD_CY + 72),
            start=195,
            end=345,
            fill=(190, 90, 110, 255),
            width=5,
        )
    else:
        d.line((HEAD_CX - 14, HEAD_CY + 62, HEAD_CX + 14, HEAD_CY + 62), fill=(190, 90, 110, 255), width=5)
    # 身体（白色衣装 + 粉饰）
    d.rounded_rectangle(
        (HEAD_CX - 85, HEAD_CY + HEAD_R - 10, HEAD_CX + 85, HEAD_CY + 420),
        radius=40,
        fill=WHITE,
        outline=GRAY + (255,),
        width=6,
    )
    d.rounded_rectangle(
        (HEAD_CX - 85, HEAD_CY + HEAD_R - 10, HEAD_CX + 85, HEAD_CY + HEAD_R + 60),
        radius=30,
        fill=PINK,
    )


def make(label: str, path: Path, **kw) -> None:
    img = _base()
    d = ImageDraw.Draw(img)
    _body(d, **kw)
    img.save(path)
    print(f"wrote {path.name}")


def main() -> None:
    make("default", OUT_DIR / "default.png", mouth="flat")
    make("curious", OUT_DIR / "curious.png", mouth="flat")
    make("worried", OUT_DIR / "worried.png", mouth="frown")
    make("happy", OUT_DIR / "happy.png", mouth="smile", blush=True)
    make("angry", OUT_DIR / "angry.png", mouth="frown")


if __name__ == "__main__":
    main()
