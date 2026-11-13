"""Contact sheet of a bundle's renders, laid out on the clockwise ring they were sampled on.

    python3 tools/contact_sheet.py <bundle_dir> [out.png]      (needs numpy and pillow)

Each tile is the eye region of one frame, labelled with k, theta and (h, v), with the
metadata pupil centres marked so the ground truth can be checked by eye.
"""

import json
import os
import sys

from PIL import Image, ImageDraw

CROP = (300, 455, 724, 575)          # eye region of the 1024x1024 render
SCALE = 1.0
TILE_W = int((CROP[2] - CROP[0]) * SCALE)
TILE_H = int((CROP[3] - CROP[1]) * SCALE)
LABEL_H = 22


def tile(root, rec):
    im = Image.open(os.path.join(root, rec["file"])).convert("RGB").crop(CROP)
    im = im.resize((TILE_W, TILE_H), Image.LANCZOS)
    draw = ImageDraw.Draw(im)
    for side in "LR":
        x, y = rec[f"pupil_center_2D_{side}"]
        x, y = (x - CROP[0]) * SCALE, (y - CROP[1]) * SCALE
        draw.line((x - 5, y, x + 5, y), fill=(0, 255, 120), width=1)
        draw.line((x, y - 5, x, y + 5), fill=(0, 255, 120), width=1)
    out = Image.new("RGB", (TILE_W, TILE_H + LABEL_H), (24, 24, 26))
    out.paste(im, (0, LABEL_H))
    h, v = rec["input"]["h"], rec["input"]["v"]
    ImageDraw.Draw(out).text((6, 5), f"k={rec['frame']}  theta={rec['theta']:.3f}  h={h:+.3f} v={v:+.3f}",
                             fill=(230, 230, 230))
    return out


# (column, row) of each frame k: a ring read clockwise from the top, with no overlaps.
GRID = {0: (1, 0), 1: (2, 1), 2: (2, 2), 3: (2, 3), 4: (2, 4),
        5: (1, 5), 6: (0, 4), 7: (0, 3), 8: (0, 2), 9: (0, 1)}
GAP = 12
TOP = 40


def main(root, out_path):
    meta = json.load(open(os.path.join(root, "metadata.json")))
    cell_w, cell_h = TILE_W + GAP, TILE_H + LABEL_H + GAP
    w = 3 * cell_w + GAP
    h = TOP + 6 * cell_h + GAP
    sheet = Image.new("RGB", (w, h), (14, 14, 16))
    for rec in meta["frames"]:
        col, row = GRID[rec["frame"]]
        sheet.paste(tile(root, rec), (GAP + col * cell_w, TOP + row * cell_h))
    centre = Image.open(os.path.join(root, meta["frames"][0]["file"])).convert("RGB")
    size = min(4 * cell_h - GAP, cell_w - GAP)
    sheet.paste(centre.resize((size, size), Image.LANCZOS),
                (GAP + cell_w + (cell_w - GAP - size) // 2, TOP + cell_h + (4 * cell_h - GAP - size) // 2))
    ImageDraw.Draw(sheet).text(
        (16, 12), "Track 1 - 10 clockwise renders (theta_k = 2*pi*k/10, h = sin, v = cos), green = metadata pupil centres",
        fill=(240, 240, 240))
    sheet.save(out_path)
    print("wrote", out_path, sheet.size)


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    main(root, sys.argv[2] if len(sys.argv) > 2 else os.path.join(root, "contact_sheet.png"))
