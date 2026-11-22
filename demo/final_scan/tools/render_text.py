"""Render text overlays for the demo cards with Blender text objects (OIIO in Blender's Python has no
FreeType, and this ffmpeg build has no drawtext).

    blender -b --factory-startup -P render_text.py -- <spec.json> <out_dir>

spec.json: {card_name: [[x, y_baseline, string, size_px, [r,g,b], "sans"|"mono"], ...]}
Writes <out_dir>/<card_name>.png, 1920x1080 RGBA, transparent background, 1 px = 1 Blender unit.
"""
import json
import os
import sys

import bpy

spec_path, out = sys.argv[sys.argv.index("--") + 1:][:2]
spec = json.load(open(spec_path)); os.makedirs(out, exist_ok=True)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
sc = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
    try:
        sc.render.engine = eng; break
    except TypeError:
        pass
if sc.render.engine == "CYCLES":
    sc.cycles.samples = 4
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1920, 1080, 100
sc.render.film_transparent = True; sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA"
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 1920; cam.location = (960, -540, 100)
FONTS = {}
for key, cands in (("sans", ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf", "/System/Library/Fonts/SFNS.ttf"]),
                   ("mono", ["/System/Library/Fonts/SFNSMono.ttf", "/System/Library/Fonts/Supplemental/Courier New.ttf"])):
    FONTS[key] = None
    for c in cands:
        if os.path.exists(c):
            try:
                FONTS[key] = bpy.data.fonts.load(c); break
            except RuntimeError:
                pass
print("FONTS", {k: (v.filepath if v else "builtin") for k, v in FONTS.items()}, "ENGINE", sc.render.engine, flush=True)
mats = {}


def mat(rgb):
    k = tuple(round(c, 3) for c in rgb)
    if k not in mats:
        m = bpy.data.materials.new(str(k)); m.use_nodes = True; nt = m.node_tree
        for n in list(nt.nodes):
            if n.type != "OUTPUT_MATERIAL":
                nt.nodes.remove(n)
        e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*[c ** 2.2 for c in rgb], 1); e.inputs[1].default_value = 1.0
        nt.links.new(e.outputs[0], next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL").inputs[0]); mats[k] = m
    return mats[k]


for card, items in spec.items():
    objs = []
    for x, y, s, size, rgb, font in items:
        cu = bpy.data.curves.new("t", "FONT"); cu.body = s; cu.size = size * 0.92
        if FONTS.get(font):
            cu.font = FONTS[font]
        o = bpy.data.objects.new("t", cu); o.location = (x, -y, 0); sc.collection.objects.link(o)
        cu.materials.append(mat(rgb)); objs.append(o)
    sc.render.filepath = os.path.join(out, card + ".png")
    bpy.ops.render.render(write_still=True)
    for o in objs:
        cu = o.data; bpy.data.objects.remove(o, do_unlink=True); bpy.data.curves.remove(cu)
print("TEXT_DONE", len(spec), flush=True)
