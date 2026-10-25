"""Draws assets/converz.ico and converz.png (run once; output is committed)."""
import math
import os
from PIL import Image, ImageDraw

S = 1024
here = os.path.dirname(os.path.abspath(__file__))


def draw(size=S):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    k = size / S
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(230 * k), fill=(108, 92, 231, 255))
    c, ro, ri = size / 2, 330 * k, 165 * k
    n, gap = 6, 9
    for i in range(n):
        a0 = -90 + i * 360 / n + gap / 2
        a1 = a0 + 360 / n - gap
        col = (52, 211, 153, 255) if i == 1 else (255, 255, 255, 255)
        d.pieslice([c - ro, c - ro, c + ro, c + ro], a0, a1, fill=col)
    d.ellipse([c - ri, c - ri, c + ri, c + ri], fill=(108, 92, 231, 255))
    # small file in the middle
    w, h = 120 * k, 150 * k
    d.rounded_rectangle([c - w / 2, c - h / 2, c + w / 2, c + h / 2], radius=int(18 * k), fill=(255, 255, 255, 255))
    return im


big = draw(1024)
big.resize((256, 256), Image.LANCZOS).save(os.path.join(here, "converz.png"))
big.save(os.path.join(here, "converz.ico"), sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
print("ok")
