"""Controlled GNM vs MakeHuman comparison: identical camera, portrait lights, samples, colour management.

    blender -b --factory-startup ../../../scene.blend --python compare_lookdev.py -- {mh|gnm} gnm_lookdev_strands.blend OUTDIR SAMPLES

Runs one model per process (so peak memory is per model). scene.blend is only read, never saved.
Both models: production EyeCam (40 cm, 1024^2), the same portrait rig (production lights hidden,
including the MakeHuman-only linked eye light), AgX, Cycles on Metal, fixed seed.
Gaze targets are eyes.py's (35 cm plane, (h, v) * 5 cm) for both; blink = full / half closure:
MakeHuman via the Phase 1B lid blend, GNM via its blink shape keys.
Views: front, three-quarter, eyes close-up, gaze h-1, h+1, v+1, v-1, blink, half blink, 200% zoom
(2048 render of the front framing, centre 1024 crop), plus a second-seed front render for noise.
"""

import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (HERE, os.path.join(HERE, ".."), os.path.join(ROOT, "wrapper"), os.path.join(ROOT, "expression")):
    sys.path.insert(0, p)
import eyes, engine, gnm_engine, portrait  # noqa: E402,E401

model, gnm_blend, out, spp = sys.argv[sys.argv.index("--") + 1:]
spp = int(spp); os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
dev = eyes.use_best_device()
sc.cycles.samples = spp; sc.cycles.seed = 0
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "None"
sc.render.resolution_x = sc.render.resolution_y = 1024
eyes._calibrate()
mid = eyes._state["midpoint"]
for o in bpy.data.objects:
    if o.type == "LIGHT":
        o.hide_render = True
portrait.build(sc, mid, Vector((0, -1, 0)))

MH = [o for o in bpy.data.objects if o.type in ("MESH", "CURVES")]
G = None
if model == "gnm":
    for o in MH:
        o.hide_render = True
    names = ["GNM_Head", "GNM_Rig", "GNM_Hair", "GNM_Brows", "GNM_Lashes"]
    with bpy.data.libraries.load(gnm_blend, link=False) as (src, dst):
        dst.objects = list(names)          # the loader replaces the list in place
    for o in dst.objects:
        sc.collection.objects.link(o)
    bpy.context.view_layer.update()     # appended objects' matrix_world is identity until evaluated
    G = gnm_engine.GNMRig(os.path.join(HERE, "..", "build", "gnm_keys.npz"))
    for idb in (G.rig, G.ob.data.shape_keys):
        if idb.animation_data:
            idb.animation_data.action = None
    shift = Matrix.Translation(mid - G.rig.matrix_world @ G.mid)
    for n in names:
        o = bpy.data.objects[n]
        if o.parent is None:
            o.matrix_world = shift @ o.matrix_world
    bpy.context.view_layer.update()
    for n in names:
        o = bpy.data.objects[n]
        print("PLACED", n, tuple(round(x, 3) for x in o.matrix_world.to_euler()), tuple(round(x, 4) for x in o.matrix_world.translation))
    print("PLACED mid", tuple(round(c, 4) for c in mid), "gnm", tuple(round(c, 4) for c in (G.rig.matrix_world @ G.mid)))
if os.environ.get("PLACE_ONLY"):
    sys.exit(0)


def pose(h, v, blink):
    if model == "mh":
        eyes.move(h, v)
        if blink:
            tgt = eyes.target_point(h, v)
            for side in eyes.EYE_BONES:
                up, lo = engine._lid_angles(side, tgt, blink)
                eyes._set_bone_world_rotation(eyes.UPPER_LID_BONES[side], Quaternion(Vector((1, 0, 0)), math.radians(up)))
                eyes._set_bone_world_rotation(eyes.LOWER_LID_BONES[side], Quaternion(Vector((1, 0, 0)), math.radians(lo)))
    else:
        t = G.rig.matrix_world.inverted() @ eyes.target_point(h, v)
        w = {}
        for side, L in (("left", "L"), ("right", "R")):
            G.set_eye_quat(side, G.eye_rotation(side, t))
            w[f"lid_follow_{L}"] = G.elevation(side, t) / 10.0 * (1 - blink)
            w[f"blink_{L}"] = blink
        G.set_keys(**w)
    bpy.context.view_layer.update()


cam = sc.camera
home = cam.matrix_world.copy(); lens0 = cam.data.lens
rec = {"model": model, "device": dev, "samples": spp, "views": {}}


def shot(name, res=1024, seed=0):
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.cycles.seed = seed
    sc.render.filepath = os.path.join(out, f"{model}_{name}.png")
    t = time.time(); bpy.ops.render.render(write_still=True); dt = time.time() - t
    rec["views"][name] = {"seconds": round(dt, 2), "resolution": res}
    print("RENDERED", model, name, f"{dt:.1f}s", flush=True)


def place(pos, tgt, lens):
    cam.location = pos; cam.rotation_euler = (tgt - pos).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = lens


views = [("front", (0, 0, 0)), ("gaze_h-1", (-1, 0, 0)), ("gaze_h+1", (1, 0, 0)), ("gaze_v+1", (0, 1, 0)),
         ("gaze_v-1", (0, -1, 0)), ("blink", (0, 0, 1.0)), ("half_blink", (0, 0, 0.5))]
for name, (h, v, b) in views:
    pose(h, v, b)
    cam.matrix_world = home; cam.data.lens = lens0
    shot(name)
pose(0, 0, 0)
shot("front_seed2", seed=7)
shot("zoom200_src", res=2048)
place(mid + Vector((0, -0.30, 0)), mid, 105); shot("eyes")
place(mid + Vector((-0.24, -0.33, 0.02)), mid + Vector((0, 0, -0.03)), 60); shot("three_quarter")
cam.matrix_world = home; cam.data.lens = lens0
with open(os.path.join(out, f"{model}_times.json"), "w") as fh:
    json.dump(rec, fh, indent=1)
