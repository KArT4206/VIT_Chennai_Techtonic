"""Acceptance tests for the expression-driven wrinkle system. Exit code 0 only if all pass.

    blender -b --factory-startup gnm_wrinkles_corr.blend --python test_wrinkles.py -- ../../build/gnm_head_neutral.npz ../../build/gnm_keys.npz maps
"""

import os
import sys
import tempfile

import bmesh
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import gnm_engine  # noqa: E402
import OpenImageIO as oiio  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg, flush=True)
    if not ok:
        FAILS.append(msg)


ref_npz, keys_npz, maps = sys.argv[sys.argv.index("--") + 1:]
ref = np.load(ref_npz)
sc = bpy.context.scene
ob = bpy.data.objects["GNM_Head"]; me = ob.data; key = me.shape_keys
mat = me.materials[0]; nt = mat.node_tree; grp = nt.nodes["ExpressionWrinkles"]
EXPR = ["blink", "squint", "brow_raise", "brow_furrow"]


def rd(p):
    i = oiio.ImageInput.open(p); n = i.spec().nchannels; a = i.read_image(0, 0, 0, n, "float"); i.close(); return a


# ---- topology / UV / rig unchanged
basis = np.empty(len(me.vertices) * 3, np.float32); key.key_blocks["Basis"].data.foreach_get("co", basis)
loops = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", loops)
uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers["UDIM"].data.foreach_get("uv", uv)
check(np.abs(basis.reshape(-1, 3) - ref["vertices"]).max() == 0 and np.array_equal(loops.reshape(-1, 4), ref["quads"])
      and np.abs(uv.reshape(-1, 4, 2) - ref["quad_uvs_udim"]).max() == 0, "GNM positions, faces and UDIM UVs unchanged")
_anim = {fc.data_path.split('"')[1] for fc in gnm_engine.fcurves(key.animation_data.action)} if key.animation_data and key.animation_data.action else set()
# keys the Phase 2B Timeline animates carry its frame-1 values (neutral fixation + drift, <= 0.01);
# every other key (furrow, correctives, squint, surprise) must be exactly 0 in the saved file
REST0 = {kb.name: kb.value for kb in key.key_blocks[1:] if (kb.name in _anim and abs(kb.value) > 0.01) or (kb.name not in _anim and abs(kb.value) > 1e-6)}
G = gnm_engine.GNMRig(keys_npz)
for idb in (G.rig, key):
    if idb.animation_data and idb.animation_data.action:
        idb.animation_data.action = None
errs = G.verify_against_gnm()
check(max(errs) < 1e-6, f"eye rig + original shape keys still reproduce GNM ({max(errs):.1e} m)")

# ---- neutral subtraction (the article's rule) on the baked maps
neu = rd(os.path.join(maps, "_neutral_resampled.exr"))[..., 0]
for e in EXPR:
    ex = rd(os.path.join(maps, f"_{e}_expr_height.exr"))[..., 0]
    dl = rd(os.path.join(maps, f"delta_{e}.1001.exr")); mk = rd(os.path.join(maps, f"mask_{e}.1001.exr"))
    delta = dl[..., 0] + dl[..., 1]; mask = mk[..., 0] + mk[..., 1]
    check(np.abs(delta - (ex - neu)).max() < 1e-5, f"{e}: stored delta == expression height - neutral height")
    check(np.abs(delta[mask <= 0]).max() == 0.0, f"{e}: delta is exactly 0 outside its mask (neutral not double-counted)")

# ---- drivers: shape-key weights reach the node group (linear, scaled)
def set_keys(**w):
    for kb in key.key_blocks[1:]:
        if not kb.name.startswith("corr_"):
            kb.value = w.get(kb.name, 0.0)
    bpy.context.view_layer.update()
    sc.frame_set(sc.frame_current)


set_keys(blink_L=1.0, squint_R=0.5, brow_raise_L=1.5, brow_furrow_R=0.67)
vals = {f"{e}_{s}": grp.inputs[f"{e}_{s}"].default_value for e in EXPR for s in "LR"}
check(abs(vals["blink_L"] - 1.0) < 1e-6 and abs(vals["squint_R"] - 0.5) < 1e-6 and abs(vals["brow_raise_L"] - 1.0) < 1e-6
      and abs(vals["brow_furrow_R"] - 0.67) < 1e-6 and abs(vals["blink_R"]) < 1e-6, f"drivers map key values to wrinkle weights {vals}")
set_keys(blink_L=1.0, brow_raise_L=0.75, brow_furrow_L=0.67)
cb = key.key_blocks["corr_blink_raise_L"].value; cl = key.key_blocks["corr_blink_lowerer_L"].value
check(abs(cb - 0.5) < 1e-6 and abs(cl - 1.0) < 1e-6 and key.key_blocks["corr_blink_raise_R"].value == 0,
      f"corrective drivers: blink x raise = {cb:.3f} (want 0.5), blink x lowerer = {cl:.3f} (want 1.0)")
check(abs(key.key_blocks["brow_furrow_L"].slider_max - 0.67) < 1e-5, "brow lowerer capped at 0.67 (lid contact <= 0.31 mm)")
check(not REST0, f"saved scene rests at neutral: no expression or corrective key active {REST0}")

# ---- shader math: bake the group's Height output for mixed weights, compare with sum(w * delta)
bc = me.copy(); bm = bmesh.new(); bm.from_mesh(bc)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != 0], context="FACES_ONLY"); bm.to_mesh(bc); bm.free()
if bc.shape_keys:
    ob_tmp = bpy.data.objects.new("hb", bc)
else:
    ob_tmp = bpy.data.objects.new("hb", bc)
sc.collection.objects.link(ob_tmp); ob_tmp.matrix_world = ob.matrix_world
for kb in (bc.shape_keys.key_blocks if bc.shape_keys else []):
    kb.value = 0.0
hm = bpy.data.materials.new("hb"); hm.use_nodes = True; hn = hm.node_tree
for n in list(hn.nodes):
    if n.type != "OUTPUT_MATERIAL":
        hn.nodes.remove(n)
g2 = hn.nodes.new("ShaderNodeGroup"); g2.node_tree = grp.node_tree
W = {"blink_L": 1.0, "squint_R": 0.5, "brow_raise_L": 0.7, "brow_furrow_R": 0.4, "brow_furrow_L": 0.2}
for k, v in W.items():
    g2.inputs[k].default_value = v
g2.inputs["Strength"].default_value = 1.0
em = hn.nodes.new("ShaderNodeEmission")
cc = hn.nodes.new("ShaderNodeCombineColor")
for i in range(3):
    hn.links.new(g2.outputs["Height"], cc.inputs[i])
hn.links.new(cc.outputs[0], em.inputs["Color"]); hn.links.new(em.outputs[0], next(n for n in hn.nodes if n.type == "OUTPUT_MATERIAL").inputs[0])
img = bpy.data.images.new("hb", 2048, 2048, float_buffer=True); img.colorspace_settings.name = "Non-Color"
tn = hn.nodes.new("ShaderNodeTexImage"); tn.image = img; hn.nodes.active = tn
bc.materials.clear(); bc.materials.append(hm)
sc.render.engine = "CYCLES"; sc.cycles.samples = 1
bpy.ops.object.select_all(action="DESELECT"); ob_tmp.select_set(True); bpy.context.view_layer.objects.active = ob_tmp
for o in bpy.data.objects:
    if o is not ob_tmp:
        o.hide_render = True
bpy.ops.object.bake(type="EMIT", margin=0, target="IMAGE_TEXTURES")
for o in bpy.data.objects:
    o.hide_render = False
got = np.array(img.pixels[:], np.float32).reshape(2048, 2048, 4)[::-1, :, 0]   # Blender pixels are bottom-up
pk = {k: rd(os.path.join(maps, f"packed_{k}.1001.exr")) for k in ("delta_A", "delta_B")}
CH = {"blink_L": ("delta_A", 0), "blink_R": ("delta_A", 1), "squint_L": ("delta_A", 2), "squint_R": ("delta_A", 3),
      "brow_raise_L": ("delta_B", 0), "brow_raise_R": ("delta_B", 1), "brow_furrow_L": ("delta_B", 2), "brow_furrow_R": ("delta_B", 3)}
want = sum(v * pk[CH[k][0]][..., CH[k][1]] for k, v in W.items())
covered = np.abs(want) > 1e-4
err = np.abs(got - want)[covered]
check(covered.sum() > 1000 and np.percentile(err, 99) < 0.02, f"node group Height = sum(w * delta) for 5 simultaneous weights "
      f"(p99 error {np.percentile(err, 99):.4f}, {covered.sum()} texels; texel-centre sampling)")
bpy.data.objects.remove(ob_tmp)

# ---- renders: neutral identity, no popping, determinism (eye-region crop, low samples)
cam = bpy.data.objects["Cam"]
from mathutils import Vector  # noqa: E402
mid = ob.matrix_world @ G.mid; fwd = (ob.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
cam.location = mid + fwd * 0.30; cam.rotation_euler = (mid - cam.location).to_track_quat("-Z", "Y").to_euler(); cam.data.lens = 105
sc.cycles.samples = 16; sc.render.resolution_x = sc.render.resolution_y = 256; sc.cycles.seed = 0


def render():
    p = os.path.join(tempfile.gettempdir(), f"wr_{os.getpid()}.png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(p); a = np.array(im.pixels[:], np.float32).reshape(256, 256, 4)[..., :3]; bpy.data.images.remove(im); os.remove(p)
    return a


def same(a, b):
    d = np.abs(a - b); return d.max() <= 1 / 255 + 1e-6 and (d.max(-1) > 0).mean() < 0.001


set_keys()
with_group = render()
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
nrm_src = grp.inputs["Normal"].links[0].from_socket; alb_src = grp.inputs["Albedo"].links[0].from_socket
l1 = nt.links.new(nrm_src, bsdf.inputs["Normal"]); l2 = nt.links.new(alb_src, bsdf.inputs["Base Color"])
without = render()
nt.links.new(grp.outputs["Normal"], bsdf.inputs["Normal"]); nt.links.new(grp.outputs["Albedo"], bsdf.inputs["Base Color"])
check(same(with_group, without), f"all weights 0: identical to the neutral baseline material (max {np.abs(with_group - without).max() * 255:.2f}/255)")
check(same(render(), with_group), "render deterministic (within one 8-bit step on < 0.1 % pixels)")
frames = []
for w in (0.0, 0.25, 0.5, 0.75, 1.0):
    set_keys(squint_L=w, squint_R=w); frames.append(render())
steps = [float(np.abs(frames[i + 1] - frames[i]).mean() * 255) for i in range(4)]
check(max(steps) < 3 * (min(steps) + 0.05), f"no texture popping over a squint sweep (mean change per 0.25 step {np.round(steps, 3).tolist()})")
set_keys()
print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' CHECK(S) FAILED'}")
sys.exit(1 if FAILS else 0)
