# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw

for size in (192, 512):
    img = Image.new("RGB", (64, 64), "#14532d")
    d = ImageDraw.Draw(img)
    d.text((20, 26), "SO", fill="white")
    img.resize((size, size), Image.NEAREST).save(f"public/icon-{size}.png")
print("ok")
