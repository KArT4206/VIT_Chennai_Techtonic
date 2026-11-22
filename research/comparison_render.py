"""WS8: render the three eye-articulation models under identical conditions (Blender side).

    blender -b --factory-startup <bundle>/scene.blend -P research/comparison_render.py -- <out_dir> [--samples 64]

Same scene, camera, lights, samples and poses (left, right, up, down, two diagonals, reset). Models:
  anatomical : wrapper move(h, v): eyeball rotates about its pivot, lids follow, cornea refracts (submitted model)
  sphere     : same rotation, lids follow, corneal Lens meshes hidden (no refraction)
  planar     : NO rotation; the eye bone is TRANSLATED parallel to the image plane so the projected anatomical
               pupil centre lands on the anatomical model's ground-truth pixel; lids stay at rest (a 2-D sliding pupil)
For each pose and model: <out_dir>/<model>/<pose>.png and a JSON with the wrapper state and the translation used.
research/comparison_eval.py measures the image differences.
"""
import json, math, os, sys
import bpy
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]; samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 64
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402
sc = bpy.context.scene; eyes.use_best_device(); sc.cycles.samples = samples
band = None
if "--fast" in a:                     # eye band + persistent data; only after WS6 bench_compare accepts it
    import speed; band = speed.apply()
rig = eyes._rig(); lens = [o for o in bpy.data.objects if o.name.startswith("Lens")]
POSES = [("reset", 0, 0), ("left", -1, 0), ("right", 1, 0), ("up", 0, 1), ("down", 0, -1), ("up_right", .707, .707), ("down_left", -.707, -.707)]
for m in ("anatomical", "sphere", "planar"):
    os.makedirs(os.path.join(out, m), exist_ok=True)

def render(m, name, extra):
    p = os.path.join(out, m, name + ".png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    json.dump(extra, open(p[:-4] + ".json", "w"), indent=1)

def clear_translation():
    for s in "LR":
        rig.pose.bones[eyes.EYE_BONES[s]].location = (0, 0, 0)
    bpy.context.view_layer.update()

for name, h, v in POSES:
    clear_translation()
    for o in lens: o.hide_render = False
    st = eyes.move(h, v); render("anatomical", name, dict(state=st))
    for o in lens: o.hide_render = True
    render("sphere", name, dict(state=st))
    for o in lens: o.hide_render = False
    # planar: rest rotation (reset pose of eyes AND lids), then translate each eye bone in the camera's image plane
    eyes.reset(); rest = eyes.state(); trans = {}
    cam = sc.camera.matrix_world.to_3x3(); right, up = cam @ Vector((1, 0, 0)), cam @ Vector((0, 1, 0))
    for s in "LR":
        pb = rig.pose.bones[eyes.EYE_BONES[s]]
        target = Vector(st[f"pupil_center_2D_{s}"])
        world = Vector((0, 0, 0))
        for _ in range(6):                      # Newton on the 2-D apparent pupil position (refraction included)
            def apparent(wd):
                M = rig.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()
                pb.location = M.inverted() @ wd; bpy.context.view_layer.update()
                return Vector(eyes.apparent_pupil(s, eyes.mesh_pupils()[s])[0])
            f = apparent(world) - target
            if f.length < 1e-3: break
            e = 1e-4; fx = apparent(world + right * e) - target; fy = apparent(world + up * e) - target
            J = [[(fx - f).x / e, (fy - f).x / e], [(fx - f).y / e, (fy - f).y / e]]
            det = J[0][0] * J[1][1] - J[0][1] * J[1][0]
            dx = (J[1][1] * f.x - J[0][1] * f.y) / det; dy = (-J[1][0] * f.x + J[0][0] * f.y) / det
            world = world - right * dx - up * dy
        apparent(world)
        trans[s] = dict(translation_world_m=[round(c, 7) for c in world], translation_mm=round(world.length * 1000, 4),
                        residual_px=round((Vector(eyes.apparent_pupil(s, eyes.mesh_pupils()[s])[0]) - target).length, 5))
    render("planar", name, dict(state_anatomical=st, rest_state=rest, planar=trans))
    print("CMP", name, json.dumps(trans), flush=True)
clear_translation(); eyes.reset()
json.dump(dict(poses=POSES, samples=samples, band_px=band, blender=bpy.app.version_string), open(os.path.join(out, "info.json"), "w"), indent=1)
print("CMP_DONE", flush=True)
