"""Fair GNM vs MakeHuman comparison inside the production scene (scene.blend is never saved).

    blender -b --factory-startup ../../scene.blend --python compare_mh.py -- gnm_expression_test.blend build/gnm_keys.npz renders/compare build/compare_scene.blend

Same camera (production EyeCam: 40 cm from the eye midpoint), same lights and world, same render
settings (Cycles, Metal, 128 samples, 1024^2), same gaze targets (35 cm fixation plane,
eyes.move(h, v) convention: h, v in [-1, 1] -> +-5 cm), same blink definition (full closure).
GNM is placed so that its eye midpoint coincides with MakeHuman's, face along -Y, real scale.
"""

import json
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "wrapper"))
sys.path.insert(0, os.path.join(ROOT, "expression"))
import eyes        # noqa: E402  production wrapper (read only use)
import engine      # noqa: E402  Phase 1B engine (read only use)
import gnm_engine  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
gnm_blend, keys_npz, rdir, out_blend = a
os.makedirs(rdir, exist_ok=True)
scene = bpy.context.scene
print("RENDER_DEVICE", eyes.use_best_device())
scene.cycles.samples = 128

with bpy.data.libraries.load(gnm_blend, link=False) as (src, dst):
    dst.objects = ["GNM_Head", "GNM_Rig"]
for o in dst.objects:
    scene.collection.objects.link(o)
G = gnm_engine.GNMRig(keys_npz)
for idb in (G.rig, G.ob.data.shape_keys):
    if idb.animation_data:
        idb.animation_data.action = None          # pose directly, not from the Timeline
eyes._calibrate()
mh_mid = eyes._state["midpoint"]
g_mid_world = G.rig.matrix_world @ G.mid
G.rig.matrix_world = Matrix.Translation(mh_mid - g_mid_world) @ G.rig.matrix_world
G.ob.matrix_world = Matrix.Translation(mh_mid - g_mid_world) @ G.ob.matrix_world
bpy.context.view_layer.update()
print("GNM_EYE_MID_WORLD", tuple(round(c, 5) for c in (G.rig.matrix_world @ G.mid)), "MH", tuple(round(c, 5) for c in mh_mid))

MH_OBJECTS = [o for o in bpy.data.objects if o.type in ("MESH", "CURVES") and not o.name.startswith("GNM")]


def show(model):
    for o in MH_OBJECTS:
        o.hide_render = model != "mh"
    for o in (G.ob,):
        o.hide_render = model != "gnm"


def render(name):
    scene.render.filepath = os.path.join(rdir, name)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    print("RENDERED", name, f"{dt:.2f}s")
    return dt


def gnm_gaze(h, v):
    """GNM eyes at eyes.py's target for (h, v): 35 cm ahead of the midpoint, (h, v) * 5 cm."""
    t_world = eyes.target_point(h, v)
    t_gnm = G.rig.matrix_world.inverted() @ t_world                       # into GNM (armature) space
    w = {}
    for side, L in (("left", "L"), ("right", "R")):
        G.set_eye_quat(side, G.eye_rotation(side, t_gnm))
        w[f"lid_follow_{L}"] = G.elevation(side, t_gnm) / 10.0
    return w, t_gnm


times = {"mh": [], "gnm": []}
metrics = {}
for tag, (h, v, blink) in {"neutral": (0, 0, 0), "right_h+1": (1, 0, 0), "up_v+1": (0, 1, 0), "blink": (0, 0, 1)}.items():
    # MakeHuman: production wrapper, plus the Phase 1B lid blend for the blink
    show("mh")
    eyes.move(h, v)
    if blink:
        for side in eyes.EYE_BONES:
            tgt = eyes.target_point(h, v)
            up, lo = engine._lid_angles(side, tgt, 1.0)
            from mathutils import Quaternion
            eyes._set_bone_world_rotation(eyes.UPPER_LID_BONES[side], Quaternion(Vector((1, 0, 0)), math.radians(up)))
            eyes._set_bone_world_rotation(eyes.LOWER_LID_BONES[side], Quaternion(Vector((1, 0, 0)), math.radians(lo)))
        bpy.context.view_layer.update()
    times["mh"].append(render(f"mh_{tag}.png"))
    # GNM
    show("gnm")
    w, t_gnm = gnm_gaze(h, v)
    if blink:
        w = {**{k: 0.0 for k in w}, "blink_L": 1.0, "blink_R": 1.0}
    G.set_keys(**w)
    bpy.context.view_layer.update()
    times["gnm"].append(render(f"gnm_{tag}.png"))
    # convergence / rotation metrics (degrees)
    def vergence_mh():
        dl = (eyes.target_point(h, v) - eyes._eye_centre("L")).normalized()
        dr = (eyes.target_point(h, v) - eyes._eye_centre("R")).normalized()
        return math.degrees(dl.angle(dr))
    def vergence_gnm():
        dl = (t_gnm - G.centre["left"]).normalized(); dr = (t_gnm - G.centre["right"]).normalized()
        return math.degrees(dl.angle(dr))
    metrics[tag] = {"vergence_deg_mh": round(vergence_mh(), 3), "vergence_deg_gnm": round(vergence_gnm(), 3)}
eyes.reset()
show("mh")
metrics["render_seconds"] = {k: [round(x, 2) for x in v] for k, v in times.items()}
metrics["ipd_mm"] = {"mh": round((eyes._eye_centre("L") - eyes._eye_centre("R")).length * 1000, 2),
                     "gnm": round((G.centre["left"] - G.centre["right"]).length * 1000, 2)}
with open(os.path.join(rdir, "compare_metrics.json"), "w") as fh:
    json.dump(metrics, fh, indent=1)
print("METRICS", json.dumps(metrics))
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), copy=True, compress=True)
print("SAVED_COPY", out_blend)
