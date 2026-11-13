"""Original 3D Scan Store head vs GNM carrying its appearance: identical cameras, HDRI, light, samples.

    blender -b --factory-startup --disable-autoexec build/gnm_scan.blend --python render_compare_scan.py -- OUTDIR SAMPLES gnm_scan_keys.npz

scan  = vendor Head / eyeballs / lenses / teeth / tongue, vendor brows+lashes+eye wet at their authored
        positions (Surface Deform off)
gnm   = GNM_Head (GNM topology/UVs, scan-shaped basis, vendor skin material) + baked scan eyes, vendor
        brows/lashes/eye wet following GNM via Surface Deform
GNM expression tests use the verified GNM controls and eye rig (gnm_engine) at the 35 cm fixation plane.
"""

import json
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gnm_qualification"))
import gnm_engine  # noqa: E402

out, spp, keys = sys.argv[sys.argv.index("--") + 1:][:3]   # optional 4th: --expr-only
spp = int(spp); os.makedirs(out, exist_ok=True)
sc = bpy.context.scene; sc.cycles.samples = spp; sc.cycles.seed = 0
p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
VENDOR = ["Head", "Realtime Eyeball Left", "Realtime Eyeball Right", "Lens Left", "Lens Right", "Teeth", "Tongue"]
FOLLOW = ["Brows", "Lashes", "Eye Wet"]
G = gnm_engine.GNMRig(keys)
times = {}


def mode(m):
    for n in VENDOR:
        o = bpy.data.objects[n]; o.hide_render = o.hide_viewport = (m != "scan")
    for n in ("GNM_Head",):
        o = bpy.data.objects[n]; o.hide_render = (m != "gnm"); o.hide_viewport = False
    for n in FOLLOW:
        for md in bpy.data.objects[n].modifiers:
            if md.type == "SURFACE_DEFORM":
                md.show_render = md.show_viewport = (m == "gnm")
    bpy.context.view_layer.update()


def shot(name, cam, rx, ry):
    sc.camera = bpy.data.objects[cam]
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.filepath = os.path.join(out, name)
    t = time.time(); bpy.ops.render.render(write_still=True); times[name] = round(time.time() - t, 1)
    print("RENDERED", name, times[name], flush=True)


VIEWS = [("front", "V_front", 1024, 1024), ("three_quarter", "V_34", 1024, 1024), ("eyes", "V_eyes", 1024, 1024),
         ("skin", "V_skin", 2048, 2048), ("brows_lashes", "V_brow", 1024, 1024), ("vendor_full", "Full Shot", 1400, 608),
         ("vendor_eyes", "Eyes Shot", 1400, 608)]
G.set_keys()
for m in (() if "--expr-only" in sys.argv else ("scan", "gnm")):
    mode(m)
    if m == "gnm":
        t = G.target(0, 0)
        for side in ("left", "right"):
            G.set_eye_quat(side, G.eye_rotation(side, t))
        bpy.context.view_layer.update()
    for v, cam, rx, ry in VIEWS:
        shot(f"{m}_{v}.png", cam, rx, ry)
mode("gnm")
for name, w, (yaw, pitch) in (("blink", dict(blink_L=1.0, blink_R=1.0), (0, 0)), ("half_blink", dict(blink_L=0.5, blink_R=0.5), (0, 0)),
                              ("look_left", {}, (15, 0)), ("look_right", {}, (-15, 0)), ("look_up", {}, (0, 12)), ("look_down", {}, (0, -7))):
    t = G.target(yaw, pitch)
    kw = dict(w)
    for side, s in (("left", "L"), ("right", "R")):
        G.set_eye_quat(side, G.eye_rotation(side, t))
        kw[f"lid_follow_{s}"] = G.elevation(side, t) / 10.0 * (1 - w.get(f"blink_{s}", 0.0))
    G.set_keys(**kw); bpy.context.view_layer.update()
    shot(f"gnm_expr_{name}.png", "V_eyes", 1024, 1024)
G.set_keys()
json.dump(times, open(os.path.join(out, "times.json"), "w"), indent=1)
