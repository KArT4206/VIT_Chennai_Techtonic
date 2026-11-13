"""Build experiments/gnm_qualification/gnm_expression_test.blend and its verification renders.

    blender -b --factory-startup gnm_head_test.blend --python build_prototype.py -- build/gnm_keys.npz textures OUT_BLEND RENDER_DIR

- original GNM geometry (template identity), GNM topology and UVs untouched;
- shape keys for the exact GNM lid/brow controls; armature eye joints for gaze;
- materials: CC0-derived skin bake (1001) and eye-interior bakes (1002/1004) as one UDIM image,
  glass corneas (1003/1005, IOR 1.376), simple teeth/tongue;
- Timeline: Phase 1B "generate" sequence (complete blinks, a partial blink, up and down gaze, eye
  roll, brows), keyed per frame into Competition_GNM_Natural_Eye_Expression (+ _ShapeKeys);
- renders: neutral at the evaluator camera (40 cm, 1024^2), eye close-up, three-quarter, and
  Timeline frames (complete blink, partial blink, up gaze, down gaze).
"""

import math
import os
import shutil
import sys
import time

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gnm_engine  # noqa: E402
import gnm_look    # noqa: E402
import motion      # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
keys_npz, tex_dir, out_blend, rdir = a
os.makedirs(rdir, exist_ok=True)
scene = bpy.context.scene
dev = gnm_look.metal(scene, 256)
print("RENDER_DEVICE", dev)
bpy.data.objects["GNM_Head"].data.polygons.foreach_set("use_smooth", [True] * len(bpy.data.objects["GNM_Head"].data.polygons))
G = gnm_engine.GNMRig(keys_npz)
G.ensure_keys()
errs = G.verify_against_gnm()
print("VERIFY_MAX_ABS_ERR_M", max(errs), errs)

# ---- UDIM texture set (skin 1001, eye interiors 1002/1004)
udim = os.path.join(tex_dir, "gnm_udim")
os.makedirs(udim, exist_ok=True)
for src, tile in (("gnm_skin_cc0.1001.png", 1001), ("gnm_eye_interior.1002.png", 1002), ("gnm_eye_interior.1004.png", 1004)):
    shutil.copyfile(os.path.join(tex_dir, src), os.path.join(udim, f"gnm_tex.{tile}.png"))
img = bpy.data.images.load(os.path.join(udim, "gnm_tex.1001.png"))
img.source = "TILED"
img.name = "GNM_texture_set"
img.colorspace_settings.name = "sRGB"
print("UDIM_TILES", sorted(t.number for t in img.tiles))
img.pack()

ob = G.ob
# cornea_cap: 1 on eye-exterior vertices beyond the sclera radius (the corneal bulge), else 0
import numpy as np  # noqa: E402
co = np.empty(len(ob.data.vertices) * 3, np.float32); ob.data.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
cap = np.zeros(len(co), np.float32)
ext = ob.vertex_groups["gnm_eye_exteriors"].index
for side in ("left", "right"):
    sg = ob.vertex_groups[f"gnm_{side}_eye"].index
    c = np.array(G.centre[side])
    for v in ob.data.vertices:
        gs = {g.group for g in v.groups}
        if ext in gs and sg in gs and np.linalg.norm(co[v.index] - c) > 0.01475:
            cap[v.index] = 1.0
# Face domain, hard edge: a face is cornea only if all its corners are. A per-vertex value blended
# glass/transparent across the boundary faces and showed as an arc in side gaze.
fcap = np.array([float(all(cap[i] > 0.5 for i in p.vertices)) for p in ob.data.polygons], np.float32)
if "cornea_cap" in ob.data.attributes:
    ob.data.attributes.remove(ob.data.attributes["cornea_cap"])
attr = ob.data.attributes.new("cornea_cap", "FLOAT", "FACE")
attr.data.foreach_set("value", fcap)
print("CORNEA_CAP_VERTICES", int(cap.sum()), "FACES", int(fcap.sum()))
for i, mat in enumerate(ob.data.materials):
    nt = mat.node_tree
    for n in [n for n in nt.nodes if n.type in ("TEX_IMAGE", "UVMAP", "ATTRIBUTE")]:
        nt.nodes.remove(n)
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tile = 1001 + i
    if tile in (1001, 1002, 1004):
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
        uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UDIM"
        nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
        if tile == 1001:
            b.inputs["Roughness"].default_value = 0.45
            b.inputs["Subsurface Weight"].default_value = 0.2
            b.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
            b.inputs["Subsurface Scale"].default_value = 0.004
        else:
            b.inputs["Roughness"].default_value = 0.3
            b.inputs["Subsurface Weight"].default_value = 0.0
    elif tile in (1003, 1005):
        # GNM's "exterior" is a CLOSED shell around the whole eyeball (r 14.38-16.09 mm) whose back
        # half lies inside the sclera (<= 14.64 mm). Solid glass there gave milky, swirled eyes.
        # Only the corneal cap (shell beyond the sclera, attribute cornea_cap = 1) refracts; the rest
        # of the shell is a transparent pass-through. Geometry is untouched.
        b.inputs["Base Color"].default_value = (1, 1, 1, 1)
        b.inputs["Transmission Weight"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.0
        b.inputs["IOR"].default_value = 1.376
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "cornea_cap"
        nt.links.new(at.outputs["Fac"], mix.inputs["Fac"])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(b.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    elif tile == 1006:
        b.inputs["Base Color"].default_value = (0.85, 0.82, 0.75, 1)
    else:
        b.inputs["Base Color"].default_value = (0.6, 0.25, 0.25, 1)

# ---- Timeline: Phase 1B generate sequence
samples = motion.generate().frames()
G.bake(samples)
scene.frame_start, scene.frame_end = 1, len(samples)
scene.render.fps = motion.FPS
print("TIMELINE", gnm_engine.ACTION_RIG, gnm_engine.ACTION_KEYS, len(samples), "frames")

# ---- camera / lights (evaluator-style: 40 cm from the eye midpoint, 60 mm lens like the production K)
RX = ob.matrix_world.to_3x3()
mid_w = ob.matrix_world @ G.mid
gnm_look.lights(scene, mid_w)
fwd = RX @ Vector((0, 0, 1))
scene.frame_set(1)
gnm_look.camera(scene, mid_w + fwd * 0.40, mid_w, 60)    # saved file opens with the evaluator-style camera
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
print("SAVED", out_blend)


def shot(name, pos, target, lens, frame=1):
    gnm_look.camera(scene, pos, target, lens)
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(rdir, name)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name, f"{time.time() - t:.1f}s")


def frame_of(pred):
    return 1 + next(s["frame"] for s in samples if pred(s))


shot("gnm_neutral_40cm.png", mid_w + fwd * 0.40, mid_w, 60)
shot("gnm_closeup.png", mid_w + fwd * 0.30, mid_w, 105)
shot("gnm_three_quarter.png", mid_w + (RX @ Vector((0.27, 0.02, 0.33))), mid_w + RX @ Vector((0, -0.03, -0.02)), 60)
fb = frame_of(lambda s: s["blink"] >= 0.999)
fp = frame_of(lambda s: 0.3 < s["blink"] < 0.36 and s["time_s"] > 10.5)
fu = frame_of(lambda s: s["pitch_deg"] > 12.5)
fd = frame_of(lambda s: s["pitch_deg"] < -6.5)
for n, f in (("complete_blink", fb), ("partial_blink", fp), ("up_gaze", fu), ("down_gaze", fd)):
    shot(f"gnm_timeline_{n}_f{f:03d}.png", mid_w + fwd * 0.30, mid_w, 105, f)
