"""Validation renders for the expression-wrinkle system (eye-region close-up, Metal, fixed seed).

    blender -b --factory-startup gnm_wrinkles_corr.blend --python render_validation.py -- OUTDIR SAMPLES

Variants per state:  geom = shape keys on, wrinkle maps off (Strength 0)
                     tex  = neutral geometry, maps on with the state's weights (drivers muted)
                     comb = shape keys on, maps on via the drivers (the real system)
neutral is rendered once (all weights 0). 200 % = the same framing at 2048^2, centre 1024 crop.
"""

import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import gnm_engine  # noqa: E402

out, spp = sys.argv[sys.argv.index("--") + 1:]; spp = int(spp); os.makedirs(out, exist_ok=True)
sc = bpy.context.scene; sc.cycles.samples = spp; sc.cycles.seed = 0
p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
G = gnm_engine.GNMRig(os.path.join(HERE, "..", "..", "build", "gnm_keys.npz"))
ob = G.ob; key = ob.data.shape_keys
for idb in (G.rig, key):
    if idb.animation_data:
        idb.animation_data.action = None
mat = ob.data.materials[0]; grp = mat.node_tree.nodes["ExpressionWrinkles"]
drivers = [d for d in mat.node_tree.animation_data.drivers]
EXPR = ["blink", "squint", "brow_raise", "brow_furrow"]
SCALE = {"blink": 1.0, "squint": 1.0, "brow_raise": 2.0 / 3.0, "brow_furrow": 1.0}
STATES = {
    "blink": ({"blink": 1.0}, (0, 0)),
    "squint": ({"squint": 1.0}, (0, 0)),
    "brow_raise": ({"brow_raise": 1.5}, (0, 0)),
    "brow_lowerer": ({"brow_furrow": 0.67}, (0, 0)),   # capped (add_correctives.py)
    "blink_up_gaze": ({"blink": 1.0}, (0, 12)),
    "squint_side_gaze": ({"squint": 1.0}, (15, 0)),
}
rig = G.rig
mid = ob.matrix_world @ G.mid
fwd = (ob.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
cam = bpy.data.objects["Cam"]
cam.location = mid + fwd * 0.30; cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = 105
times = {}


def pose(weights, gaze, geom, tex):
    kw = {}
    for e in EXPR:
        for s in "LR":
            kw[f"{e}_{s}"] = weights.get(e, 0.0) if geom else 0.0
    t = G.target(*gaze)
    for side, s in (("left", "L"), ("right", "R")):
        G.set_eye_quat(side, G.eye_rotation(side, t))
        kw[f"lid_follow_{s}"] = G.elevation(side, t) / 10.0 * (1 - (weights.get("blink", 0.0) if geom else 0.0))
    for kb in key.key_blocks[1:]:
        if not kb.name.startswith("corr_"):           # correctives follow their drivers
            kb.value = kw.get(kb.name, 0.0)
    if tex and not geom:                        # texture-only: drive the group by hand
        for d in drivers:
            d.mute = True
        for e in EXPR:
            for s in "LR":
                grp.inputs[f"{e}_{s}"].default_value = weights.get(e, 0.0) * SCALE[e]
    else:
        for d in drivers:
            d.mute = False
    grp.inputs["Strength"].default_value = 1.0 if tex else 0.0
    bpy.context.view_layer.update()


def shot(name, res=1024):
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.filepath = os.path.join(out, name)
    t = time.time(); bpy.ops.render.render(write_still=True); times[name] = round(time.time() - t, 2)
    print("RENDERED", name, times[name], flush=True)


pose({}, (0, 0), True, True); shot("neutral.png"); shot("neutral_200src.png", 2048)
for st, (w, gz) in STATES.items():
    pose(w, gz, True, False); shot(f"{st}_geom.png")
    pose(w, gz, False, True); shot(f"{st}_tex.png")
    pose(w, gz, True, True); shot(f"{st}_comb.png"); shot(f"{st}_comb_200src.png", 2048)
json.dump(times, open(os.path.join(out, "times.json"), "w"), indent=1)
