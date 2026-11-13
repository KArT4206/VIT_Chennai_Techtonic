"""Bake expression wrinkle maps from the measured GNM strain, and derive neutral-subtracted deltas.

    blender -b --factory-startup ../../gnm_head_test.blend --python bake_wrinkles.py -- strain.npz ../baseline_v1/skin_height.1001.exr maps/ 4096

Adam Spring's workflow (methodological reference only, no assets used):
  1. expression displacement map; 2. subtract the neutral displacement from it ("expression map"),
  so compositing neutral + weighted expression maps never counts neutral twice; 3. masks, driven by
  the expression weight, isolate each expression's region.
Here the expression detail is not scanned (no licensed scans exist in this project): for each
expression it is the neutral height plus creases that run perpendicular to the measured compression
direction (strain.py), with depth following the compression amount:
    expr_height = neutral_height + mask(c) * A * crease(phi / spacing + phase noise) * length_break
    mask(c)     = smoothstep(c0, c1, compression)
Then (numpy, after baking): delta = expr_height - neutral_height, split into a left (R) and right (G)
channel by side, and the mask likewise. The neutral texture is sampled with Closest interpolation so
the subtraction is exact wherever no crease was added.
Units: the neutral bump's height units (x 0.15 mm in the shader).
"""

import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index("--") + 1:]
strain = np.load(a[0]); neutral_exr = os.path.abspath(a[1]); out = os.path.abspath(a[2]); res = int(a[3])
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene; sc.render.engine = "CYCLES"; sc.cycles.samples = 1
p = bpy.context.preferences.addons["cycles"].preferences
try:
    p.compute_device_type = "METAL"; p.get_devices()
    for dv in p.devices:
        dv.use = dv.type == "METAL"
    sc.cycles.device = "GPU"
except TypeError:
    pass

# (spacing m, amplitude in height units, c0, c1): crease spacing by expression and region type
PARAMS = {
    "blink": (0.0012, 0.60, 0.04, 0.35),        # fine eyelid creases
    "squint": (0.0020, 0.85, 0.03, 0.30),       # crow's feet / lower lid
    "brow_raise": (0.0045, 1.00, 0.02, 0.12),   # forehead lines
    "brow_furrow": (0.0028, 1.00, 0.03, 0.22),  # glabellar lines
}

src = bpy.data.objects["GNM_Head"]
me = src.data.copy(); me.name = "wr_bake"
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != 0], context="FACES_ONLY")   # keep GNM vertex indices
bm.to_mesh(me); bm.free()
me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
me.uv_layers.active = me.uv_layers["UDIM"]
ob = bpy.data.objects.new("wr_bake", me); sc.collection.objects.link(ob); ob.matrix_world = Matrix.Identity(4)
nv = len(me.vertices)
assert nv == len(strain["side_left"]), "bake copy must keep GNM vertex indexing"
side = me.attributes.new("side_left", "FLOAT", "POINT"); side.data.foreach_set("value", strain["side_left"])
for name in PARAMS:
    at = me.attributes.new(f"c_{name}", "FLOAT", "POINT"); at.data.foreach_set("value", strain[f"{name}_comp"])
    at = me.attributes.new(f"phi_{name}", "FLOAT", "POINT"); at.data.foreach_set("value", strain[f"{name}_phi"])

neutral = bpy.data.images.load(neutral_exr); neutral.colorspace_settings.name = "Non-Color"
mat = bpy.data.materials.new("wr"); mat.use_nodes = True
nt = mat.node_tree; N, L = nt.nodes, nt.links
for n in list(N):
    N.remove(n)
outn = N.new("ShaderNodeOutputMaterial"); emit = N.new("ShaderNodeEmission"); L.new(emit.outputs[0], outn.inputs["Surface"])
tc = N.new("ShaderNodeTexCoord")
tex = N.new("ShaderNodeTexImage"); tex.image = neutral; tex.interpolation = "Closest"
uvn = N.new("ShaderNodeUVMap"); uvn.uv_map = "UDIM"; L.new(uvn.outputs["UV"], tex.inputs["Vector"])
sepn = N.new("ShaderNodeSeparateColor"); L.new(tex.outputs["Color"], sepn.inputs[0])
target = N.new("ShaderNodeTexImage")
me.materials.clear(); me.materials.append(mat)


def M(op, x, y=None, clamp=False):
    n = N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
    for i, s in enumerate((x, y)):
        if s is None:
            continue
        if isinstance(s, (int, float)):
            n.inputs[i].default_value = s
        else:
            L.new(s, n.inputs[i])
    return n.outputs[0]


def attrf(n):
    a_ = N.new("ShaderNodeAttribute"); a_.attribute_name = n; return a_


def combine(r, g, b):
    n = N.new("ShaderNodeCombineColor")
    for i, s in enumerate((r, g, b)):
        if isinstance(s, (int, float)):
            n.inputs[i].default_value = s
        else:
            L.new(s, n.inputs[i])
    return n.outputs[0]


def bake_float(colour_socket, path):
    im = bpy.data.images.new(os.path.basename(path), res, res, float_buffer=True); im.colorspace_settings.name = "Non-Color"
    target.image = im; N.active = target
    L.new(colour_socket, emit.inputs["Color"])
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type="EMIT", margin=16, target="IMAGE_TEXTURES")
    px = np.array(im.pixels[:], np.float32).reshape(res, res, 4)
    im.filepath_raw = path; im.file_format = "OPEN_EXR"; im.save()
    return px


neutral_px = bake_float(combine(sepn.outputs[0], sepn.outputs[0], sepn.outputs[0]), os.path.join(out, "_neutral_resampled.exr"))
sidel = attrf("side_left").outputs["Fac"]
report = {}
for name, (spacing, amp, c0, c1) in PARAMS.items():
    c = attrf(f"c_{name}").outputs["Fac"]
    phi = attrf(f"phi_{name}").outputs["Fac"]   # least-squares stripe phase (strain.py); not P . d (rings)
    ph = N.new("ShaderNodeTexNoise"); ph.noise_dimensions = "4D"; ph.inputs["Scale"].default_value = 1.0 / (spacing * 6)
    ph.inputs["W"].default_value = hash(name) % 97 / 10.0; L.new(tc.outputs["Object"], ph.inputs["Vector"])
    s = M("ADD", M("MULTIPLY", phi, 6.283185 / spacing), M("MULTIPLY", ph.outputs["Fac"], 1.5))
    crease = M("SUBTRACT", 0.0, M("POWER", M("MAXIMUM", M("COSINE", s), 0.0), 6.0))   # thin valleys
    brk = N.new("ShaderNodeTexNoise"); brk.noise_dimensions = "4D"; brk.inputs["Scale"].default_value = 1.0 / (spacing * 4)
    brk.inputs["W"].default_value = 3.3 + hash(name) % 13; L.new(tc.outputs["Object"], brk.inputs["Vector"])
    length = M("MINIMUM", M("MAXIMUM", M("SUBTRACT", M("MULTIPLY", brk.outputs["Fac"], 2.2), 0.55), 0.0), 1.0)
    t = M("DIVIDE", M("SUBTRACT", c, c0), c1 - c0, True)
    mask = M("MULTIPLY", M("MULTIPLY", t, t), M("SUBTRACT", 3.0, M("MULTIPLY", t, 2.0)))   # smoothstep
    expr = M("ADD", sepn.outputs[0], M("MULTIPLY", M("MULTIPLY", M("MULTIPLY", crease, length), mask), amp))
    expr_px = bake_float(combine(expr, expr, expr), os.path.join(out, f"_{name}_expr_height.exr"))
    mask_px = bake_float(combine(mask, sidel, 0.0), os.path.join(out, f"_{name}_mask_side.exr"))
    delta = expr_px[..., 0] - neutral_px[..., 0]            # the article's neutral subtraction
    sl = mask_px[..., 1]
    dl, dr = delta * sl, delta * (1 - sl)
    ml, mr = mask_px[..., 0] * sl, mask_px[..., 0] * (1 - sl)
    for kind, (r_, g_) in (("delta", (dl, dr)), ("mask", (ml, mr))):
        im = bpy.data.images.new(f"{kind}_{name}", res, res, float_buffer=True); im.colorspace_settings.name = "Non-Color"
        arr = np.zeros((res, res, 4), np.float32); arr[..., 0] = r_; arr[..., 1] = g_; arr[..., 3] = 1
        im.pixels.foreach_set(arr.reshape(-1))
        im.filepath_raw = os.path.join(out, f"{kind}_{name}.1001.exr"); im.file_format = "OPEN_EXR"; im.save()
    outside = mask_px[..., 0] <= 0.0
    report[name] = (float(np.abs(delta[outside]).max()) if outside.any() else 0.0, float((~outside).mean() * 100),
                    float(delta.min()), float(np.abs(delta).max()))
    print(f"WRINKLE {name}: |delta| outside mask max {report[name][0]:.3e} | mask covers {report[name][1]:.2f} % of tile | "
          f"delta min {report[name][2]:.3f} | max |delta| {report[name][3]:.3f}")
