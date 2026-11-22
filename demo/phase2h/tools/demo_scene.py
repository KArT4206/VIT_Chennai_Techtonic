"""Phase 2H demo runner, Blender side. Runs INSIDE a fresh extraction of the release ZIP.

    blender -b --factory-startup <pkg>/scene.blend -P demo_scene.py -- <pkg> <out_dir> [--samples N]

Nothing is saved back: the packaged scene.blend, wrapper, renders and metadata are only read.

Produces in <out_dir>:
  calls/NN_<name>.png + .json   real eyes.reset()/eyes.move()/eyes.render() calls, in the demo order
  calls/call_log.txt            the exact calls, wall times and returned values (verbatim)
  scene/overview.png            the actual scene from a side observer camera, with markers drawn at the
                                scene's real eye centres, fixation target and render camera (see below)
  scene/eyes_cutaway.png        same scene with the skin and hair hidden so the eyeballs, eye-bone axes
                                and eye centres can be seen
  scene/annotations.json        3-D positions read from the scene and their pixel positions in each view
  scene/scene_facts.json        camera / target distances measured from the scene data

Markers are temporary in-memory objects placed at positions READ from the scene (eye bone heads, the
FixationTarget empty, the EyeCam camera); they exist only for these two observer renders and are
removed before any wrapper render.
"""
import json
import os
import sys
import time

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
pkg, out = argv[0], argv[1]
samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else None
sys.dont_write_bytecode = True          # importing must not add wrapper/__pycache__ to the package
sys.path.insert(0, os.path.join(pkg, "wrapper"))
import eyes  # noqa: E402  (the packaged wrapper, unmodified)

sc = bpy.context.scene
os.makedirs(os.path.join(out, "calls"), exist_ok=True); os.makedirs(os.path.join(out, "scene"), exist_ok=True)
device = eyes.use_best_device()
if samples:
    sc.cycles.samples = samples
log = [f"# demo_scene.py  Blender {bpy.app.version_string}  device {device}  samples {sc.cycles.samples}",
       f"# package: {os.path.abspath(pkg)}"]

# ------------------------------------------------------------------ 1. real wrapper calls
CALLS = [("reset", "eyes.reset()", lambda: eyes.reset()),
         ("left", "eyes.move(-1, 0)", lambda: eyes.move(-1, 0)),
         ("right", "eyes.move(1, 0)", lambda: eyes.move(1, 0)),
         ("up", "eyes.move(0, 1)", lambda: eyes.move(0, 1)),
         ("down", "eyes.move(0, -1)", lambda: eyes.move(0, -1)),
         ("reset_again", "eyes.reset()", lambda: eyes.reset())]
for i, (name, text, fn) in enumerate(CALLS):
    fn()
    path = os.path.join(out, "calls", f"{i:02d}_{name}.png")
    t = time.time(); s = eyes.render(path); dt = time.time() - t
    s = json.loads(json.dumps(s))
    json.dump(s, open(path[:-4] + ".json", "w"), indent=1)
    log.append(f">>> {text}")
    log.append(f">>> eyes.render('{os.path.basename(path)}')   # {dt:.1f} s")
    log.append("    input " + json.dumps(s["input"]) + "  pupil_center_2D_L " + json.dumps([round(x, 2) for x in s["pupil_center_2D_L"]])
               + "  pupil_center_2D_R " + json.dumps([round(x, 2) for x in s["pupil_center_2D_R"]]))
    print(log[-3], log[-2], log[-1], flush=True)
eyes.reset()
open(os.path.join(out, "calls", "call_log.txt"), "w").write("\n".join(log) + "\n")

# ------------------------------------------------------------------ 2. scene facts (read, not assumed)
rig = eyes._rig(); cam = sc.camera; tgt = bpy.data.objects[eyes.TARGET_NAME]
cL, cR = eyes._eye_centre("L"), eyes._eye_centre("R"); mid = (cL + cR) / 2
facts = dict(eye_centre_L=list(cL), eye_centre_R=list(cR), eye_midpoint=list(mid), camera=cam.name,
             camera_location=list(cam.matrix_world.translation), camera_distance_m=(cam.matrix_world.translation - mid).length,
             fixation_target=list(tgt.matrix_world.translation), fixation_distance_m=(tgt.matrix_world.translation - mid).length,
             interocular_mm=(cL - cR).length * 1000, eye_bones=[eyes.EYE_BONES["L"], eyes.EYE_BONES["R"]], rig=rig.name,
             lens_mm=cam.data.lens, resolution=[sc.render.resolution_x, sc.render.resolution_y], samples_scene=sc.cycles.samples)
json.dump(facts, open(os.path.join(out, "scene", "scene_facts.json"), "w"), indent=1)


# ------------------------------------------------------------------ 3. observer renders with markers
def emissive(name, rgb, strength=4.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_MATERIAL":
            nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission"); e.inputs[0].default_value = (*rgb, 1); e.inputs[1].default_value = strength
    nt.links.new(e.outputs[0], next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL").inputs[0]); return m


markers = []


def sphere(p, r, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=p, segments=24, ring_count=12)
    o = bpy.context.active_object; o.data.materials.append(mat); markers.append(o); return o


def rod(a, b, r, mat):
    d = b - a
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(a + b) / 2, vertices=12)
    o = bpy.context.active_object; o.rotation_mode = "QUATERNION"; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    o.data.materials.append(mat); markers.append(o); return o


Y = emissive("m_eye", (1.0, 0.75, 0.1)); G = emissive("m_target", (0.2, 1.0, 0.3)); C = emissive("m_cam", (0.3, 0.6, 1.0))
W = emissive("m_line", (0.9, 0.9, 0.9), 1.5); B = emissive("m_bone", (1.0, 0.3, 0.8))
for c in (cL, cR):
    sphere(c, 0.0016, Y)
for side in ("L", "R"):
    bone = rig.data.bones[eyes.EYE_BONES[side]]
    h = rig.matrix_world @ bone.head_local; t = rig.matrix_world @ bone.tail_local
    tip = h + (t - h).normalized() * 0.03
    rod(h, tip, 0.0007, B)
T = tgt.matrix_world.translation.copy(); P = cam.matrix_world.translation.copy()
sphere(T, 0.004, G); sphere(P, 0.006, C)
rod(mid, P, 0.0005, W)
for side_c in (cL, cR):
    rod(side_c, T, 0.0004, G)
# camera frustum (4 cm deep) from the real camera's frame
fr = [cam.matrix_world @ v for v in cam.data.view_frame(scene=sc)]
for v in fr:
    rod(P, P + (v - P).normalized() * 0.04, 0.0004, C)

obs_cam = bpy.data.objects.new("ObserverCam", bpy.data.cameras.new("ObserverCam")); sc.collection.objects.link(obs_cam)
obs_cam.data.lens = 35
annotations = {}


def look(cam_ob, eye_pos, at):
    f = (at - eye_pos).normalized(); r = f.cross(Vector((0, 0, 1))).normalized(); u = r.cross(f)
    M = Matrix(((r.x, u.x, -f.x), (r.y, u.y, -f.y), (r.z, u.z, -f.z))).to_4x4(); M.translation = eye_pos; cam_ob.matrix_world = M


def observe(name, eye_pos, at, hide=()):
    look(obs_cam, eye_pos, at)
    prev_cam = sc.camera; sc.camera = obs_cam
    rx, ry = sc.render.resolution_x, sc.render.resolution_y; sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    hidden = []
    for o in bpy.data.objects:
        if o.name in hide and not o.hide_render:
            o.hide_render = True; hidden.append(o)
    bpy.context.view_layer.update()
    pts = {"eye_centre_L": cL, "eye_centre_R": cR, "fixation_target_35cm": T, "render_camera_40cm": P, "eye_midpoint": mid}
    annotations[name] = {k: [v.x * 1920, (1 - v.y) * 1080] for k, v in ((k, world_to_camera_view(sc, obs_cam, p)) for k, p in pts.items())}
    sc.render.filepath = os.path.join(out, "scene", name + ".png")
    t = time.time(); bpy.ops.render.render(write_still=True); print("RENDERED", name, round(time.time() - t, 1), flush=True)
    for o in hidden:
        o.hide_render = False
    sc.render.resolution_x, sc.render.resolution_y = rx, ry; sc.camera = prev_cam


ss = sc.cycles.samples; sc.cycles.samples = min(ss, 256)
observe("overview", mid + Vector((0.62, -0.30, 0.16)), mid + Vector((0.0, -0.21, -0.02)))
observe("eyes_cutaway", mid + Vector((0.075, -0.13, 0.035)), mid + Vector((0, -0.01, 0)),
        hide={"Human", "Human.eyebrow009", "Human.eyelashes01", "Human.short04", "HairStrands", "EyeL.TearLine", "EyeR.TearLine",
              "EyeL.Cornea", "EyeR.Cornea", "EyeR.Sclera"})   # right sclera hidden: reveals its centre
sc.cycles.samples = ss
json.dump(dict(points={k: list(v) for k, v in (("eye_centre_L", cL), ("eye_centre_R", cR), ("fixation_target", T), ("render_camera", P))},
               pixels=annotations), open(os.path.join(out, "scene", "annotations.json"), "w"), indent=1)
for o in markers:
    bpy.data.objects.remove(o, do_unlink=True)
print("DEMO_SCENE_DONE", flush=True)
