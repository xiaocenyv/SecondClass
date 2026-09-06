# -*- coding: utf-8 -*-
"""构建辅助：生成应用图标 assets/app.ico（仅构建时需要 Pillow，非运行时依赖）。"""
import os

from PIL import Image, ImageDraw


def make_icon(path: str, size: int = 256) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 圆角底色（深蓝渐变简化为纯色）
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius,
                        fill=(31, 111, 178, 255))
    # 底部书本
    bw = size * 0.62
    bh = size * 0.30
    x0 = (size - bw) / 2
    y0 = size * 0.62
    d.rounded_rectangle([x0, y0, x0 + bw / 2 - 2, y0 + bh], radius=int(size * 0.03),
                        fill=(255, 255, 255, 255))
    d.rounded_rectangle([x0 + bw / 2 + 2, y0, x0 + bw, y0 + bh], radius=int(size * 0.03),
                        fill=(214, 232, 248, 255))
    # 对勾
    lw = int(size * 0.10)
    p1 = (size * 0.28, size * 0.44)
    p2 = (size * 0.44, size * 0.60)
    p3 = (size * 0.74, size * 0.26)
    d.line([p1, p2], fill=(255, 255, 255, 255), width=lw)
    d.line([p2, p3], fill=(255, 255, 255, 255), width=lw)
    img.save(path, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets", "app.ico")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    make_icon(out)
    print("icon ->", out)
