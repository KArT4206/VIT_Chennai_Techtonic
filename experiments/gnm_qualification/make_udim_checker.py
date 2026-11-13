"""Write a 7-tile UDIM checker set: textures/checker.<1001..1007>.png (1024^2 each).

Each tile has its own hue, an 8x8 checker, a grid, an orientation arrow (up = +v) and its tile
number drawn as large 7-segment digits, so a render shows which tile and which way up each region
maps. Pure NumPy + OpenImageIO (Blender's Python), no external assets.

    <blender python> make_udim_checker.py textures/
"""

import os
import sys

import numpy as np
import OpenImageIO as oiio

HUES = {1001: (0.85, 0.55, 0.45), 1002: (0.30, 0.55, 0.95), 1003: (0.35, 0.85, 0.95),
        1004: (0.95, 0.35, 0.55), 1005: (0.95, 0.75, 0.30), 1006: (0.55, 0.90, 0.40), 1007: (0.75, 0.45, 0.95)}
SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
       "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg"}


def digit(img, ch, x0, y0, w, h, t, col):
    segs = {"a": (x0, y0, x0 + w, y0 + t), "b": (x0 + w - t, y0, x0 + w, y0 + h // 2),
            "c": (x0 + w - t, y0 + h // 2, x0 + w, y0 + h), "d": (x0, y0 + h - t, x0 + w, y0 + h),
            "e": (x0, y0 + h // 2, x0 + t, y0 + h), "f": (x0, y0, x0 + t, y0 + h // 2),
            "g": (x0, y0 + h // 2 - t // 2, x0 + w, y0 + h // 2 + t // 2)}
    for s in SEG[ch]:
        a, b, c, e = segs[s]
        img[b:e, a:c] = col


def tile(n, size=1024):
    base = np.array(HUES[n], np.float32)
    yy, xx = np.mgrid[0:size, 0:size]
    chk = ((xx // (size // 8) + yy // (size // 8)) % 2).astype(np.float32)
    img = (base[None, None] * (0.55 + 0.45 * chk[..., None])).astype(np.float32)
    grid = (xx % (size // 32) == 0) | (yy % (size // 32) == 0)
    img[grid] *= 0.7
    s = str(n)
    w, h, t = 150, 260, 34
    x = (size - (4 * w + 3 * 40)) // 2
    for i, ch in enumerate(s):
        digit(img, ch, x + i * (w + 40), 140, w, h, t, np.array((0.05, 0.05, 0.05), np.float32))
    # arrow pointing to +v (top of the image in UV space, row 0 after the flip below)
    cx = size // 2
    for r in range(160):
        half = max(4, (160 - r) // 2) if r < 80 else 10
        img[size - 380 - r, cx - half:cx + half] = (0.98, 0.98, 0.98)
    return img          # row 0 is the top of the image, i.e. v = 1 in Blender


def main(out):
    os.makedirs(out, exist_ok=True)
    for n in HUES:
        a = (np.clip(tile(n), 0, 1) * 255).astype(np.uint8)
        p = os.path.join(out, f"checker.{n}.png")
        o = oiio.ImageOutput.create(p)
        o.open(p, oiio.ImageSpec(a.shape[1], a.shape[0], 3, "uint8"))
        o.write_image(a)
        o.close()
        print("wrote", p)


if __name__ == "__main__":
    main(sys.argv[1])
