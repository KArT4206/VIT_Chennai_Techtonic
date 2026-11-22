"""Render-time savings for research renders that do not change what is measured.

    import speed; speed.apply(eye_band=True)

* persistent data: Blender keeps textures, hair and BVH between renders in one process (pixels unchanged).
* eye band: render only a horizontal strip around both eyes; the PNG is still 1024x1024 (crop off),
  so pixel coordinates and K are unchanged. Pixels outside the strip are empty (alpha 0).
  The strip is computed from the wrapper's eye centres and pupils over the full +-1 input range, plus margin.
Never used for the official renders (wrapper/eyes.py render_sequence), only for research/*.py outputs.
"""
import bpy


def eye_band(margin_px=110):
    import eyes
    sc = bpy.context.scene
    xs, ys = [], []
    for h, v in ((-1, 0), (1, 0), (0, 1), (0, -1), (0, 0)):
        s = eyes.move(h, v)
        for side in "LR":
            x, y = s[f"pupil_center_2D_{side}"]; xs.append(x); ys.append(y)
    eyes.reset()
    W, H = sc.render.resolution_x, sc.render.resolution_y
    x0, x1 = max(0, min(xs) - margin_px), min(W, max(xs) + margin_px)
    y0, y1 = max(0, min(ys) - margin_px), min(H, max(ys) + margin_px)
    r = sc.render
    r.use_border, r.use_crop_to_border = True, False
    r.border_min_x, r.border_max_x = x0 / W, x1 / W
    r.border_min_y, r.border_max_y = 1 - y1 / H, 1 - y0 / H     # Blender border origin is bottom-left
    return [round(x0), round(y0), round(x1), round(y1)]


def apply(eye_band_on=True, margin_px=110):
    sc = bpy.context.scene
    sc.render.use_persistent_data = True
    box = eye_band(margin_px) if eye_band_on else None
    print("[speed] persistent_data on; eye band", box, flush=True)
    return box
