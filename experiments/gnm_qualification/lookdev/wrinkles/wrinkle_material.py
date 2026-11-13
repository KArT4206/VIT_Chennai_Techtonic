"""Expression-driven wrinkle / colour blending on the GNM skin (Adam Spring's method, our data).

    blender -b --factory-startup ../gnm_lookdev_strands.blend --python wrinkle_material.py -- maps furrow_keys.npz OUT_BLEND

Node group "GNM_ExpressionWrinkles" (inserted between the neutral normal map and the skin BSDF):
    height = sum_e ( w_e,L * delta_e,L + w_e,R * delta_e,R ) * Strength
             (delta = expression height - neutral height, baked and masked: neutral is NOT re-added;
              the neutral surface comes from the existing neutral normal map, exactly once)
    Normal = Bump(height, distance 0.15 mm, normal = neutral normal map)
    Colour = albedo * (1 + sum_e (w_e,L * mask_e,L + w_e,R * mask_e,R) * tint_e * Strength)
Weights are driven by the shape keys (linear, as in the article):
    blink_L/R          <- blink_L/R
    squint_L/R         <- squint_L/R
    brow_raise_L/R     <- brow_raise_L/R * 2/3   (key 1.0 = 2 mm; maps baked at 3 mm)
    brow_furrow_L/R    <- brow_furrow_L/R        (new keys: semantic DISGUST eye blocks x 1.5)
Maps: 2 packed delta + 2 packed mask RGBA half EXRs at 2048^2 (channels L/R per expression).
Tints (blood flow, deliberately small): squint +3 % red / -1 % g,b; brow_furrow +4 % red / -1.5 % g,b;
brow_raise -1 % red (stretch blanching); blink none.
"""

import os
import sys

import bpy
import numpy as np

a = sys.argv[sys.argv.index("--") + 1:]
maps, furrow_npz, out_blend = os.path.abspath(a[0]), a[1], a[2]
ob = bpy.data.objects["GNM_Head"]; me = ob.data
key = me.shape_keys
f = np.load(furrow_npz)
basis = np.empty(len(me.vertices) * 3, np.float32); key.key_blocks["Basis"].data.foreach_get("co", basis)
for n in ("brow_furrow_L", "brow_furrow_R"):
    kb = key.key_blocks.get(n) or ob.shape_key_add(name=n, from_mix=False)
    kb.data.foreach_set("co", basis + f[n].reshape(-1)); kb.slider_min, kb.slider_max = 0.0, 1.5

EXPR = ["blink", "squint", "brow_raise", "brow_furrow"]
PACK = {"blink": ("A", 0), "squint": ("A", 2), "brow_raise": ("B", 0), "brow_furrow": ("B", 2)}
TINT = {"blink": (0.0, 0.0, 0.0), "squint": (0.03, -0.01, -0.01), "brow_raise": (-0.01, 0.0, 0.0), "brow_furrow": (0.04, -0.015, -0.015)}
SCALE = {"blink": 1.0, "squint": 1.0, "brow_raise": 2.0 / 3.0, "brow_furrow": 1.0}


def load(name):
    im = bpy.data.images.load(os.path.join(maps, f"{name}.1001.exr")); im.colorspace_settings.name = "Non-Color"; return im


IMG = {k: load(f"packed_{k}") for k in ("delta_A", "delta_B", "mask_A", "mask_B")}

ng = bpy.data.node_groups.new("GNM_ExpressionWrinkles", "ShaderNodeTree")
io = ng.interface
io.new_socket("Normal", in_out="INPUT", socket_type="NodeSocketVector")
io.new_socket("Albedo", in_out="INPUT", socket_type="NodeSocketColor")
s = io.new_socket("Strength", in_out="INPUT", socket_type="NodeSocketFloat"); s.default_value = 1.0
for e in EXPR:
    for side in "LR":
        io.new_socket(f"{e}_{side}", in_out="INPUT", socket_type="NodeSocketFloat")
io.new_socket("Normal", in_out="OUTPUT", socket_type="NodeSocketVector")
io.new_socket("Albedo", in_out="OUTPUT", socket_type="NodeSocketColor")
io.new_socket("Height", in_out="OUTPUT", socket_type="NodeSocketFloat")
N, L = ng.nodes, ng.links
gi = N.new("NodeGroupInput"); go = N.new("NodeGroupOutput")
uv = N.new("ShaderNodeUVMap"); uv.uv_map = "UDIM"
tex, sep = {}, {}
for k, im in IMG.items():
    t = N.new("ShaderNodeTexImage"); t.image = im; t.interpolation = "Linear"; L.new(uv.outputs["UV"], t.inputs["Vector"])
    sp = N.new("ShaderNodeSeparateColor"); L.new(t.outputs["Color"], sp.inputs[0])
    tex[k], sep[k] = t, sp


def M(op, x, y):
    n = N.new("ShaderNodeMath"); n.operation = op
    for i, v in enumerate((x, y)):
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            L.new(v, n.inputs[i])
    return n.outputs[0]


def chan(kind, e, side):
    pack, base = PACK[e]
    k = f"{kind}_{pack}"
    idx = base + (0 if side == "L" else 1)
    return sep[k].outputs[idx] if idx < 3 else tex[k].outputs["Alpha"]


height = None; tint = [None, None, None]
for e in EXPR:
    for side in "LR":
        w = gi.outputs[f"{e}_{side}"]
        h = M("MULTIPLY", w, chan("delta", e, side))
        height = h if height is None else M("ADD", height, h)
        mw = M("MULTIPLY", w, chan("mask", e, side))
        for c in range(3):
            if TINT[e][c]:
                t = M("MULTIPLY", mw, TINT[e][c])
                tint[c] = t if tint[c] is None else M("ADD", tint[c], t)
height = M("MULTIPLY", height, gi.outputs["Strength"])
bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0; bump.inputs["Distance"].default_value = 0.00015
L.new(height, bump.inputs["Height"]); L.new(gi.outputs["Normal"], bump.inputs["Normal"])
L.new(bump.outputs["Normal"], go.inputs["Normal"]); L.new(height, go.inputs["Height"])
comb = N.new("ShaderNodeCombineColor")
for c in range(3):
    comb.inputs[c].default_value = 1.0
    if tint[c] is not None:
        L.new(M("ADD", 1.0, M("MULTIPLY", tint[c], gi.outputs["Strength"])), comb.inputs[c])
mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
L.new(gi.outputs["Albedo"], mul.inputs[6]); L.new(comb.outputs[0], mul.inputs[7]); L.new(mul.outputs[2], go.inputs["Albedo"])

# ---- insert into the skin material (tile 1001)
mat = me.materials[0]; nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
nrm_src = bsdf.inputs["Normal"].links[0].from_socket
alb_src = bsdf.inputs["Base Color"].links[0].from_socket
grp = nt.nodes.new("ShaderNodeGroup"); grp.node_tree = ng; grp.name = "ExpressionWrinkles"
nt.links.new(nrm_src, grp.inputs["Normal"]); nt.links.new(alb_src, grp.inputs["Albedo"])
nt.links.new(grp.outputs["Normal"], bsdf.inputs["Normal"]); nt.links.new(grp.outputs["Albedo"], bsdf.inputs["Base Color"])
for e in EXPR:
    for side in "LR":
        fc = nt.driver_add(f'nodes["ExpressionWrinkles"].inputs["{e}_{side}"].default_value')
        d = fc.driver; d.type = "SCRIPTED"
        v = d.variables.new(); v.name = "k"; v.type = "SINGLE_PROP"
        v.targets[0].id_type = "KEY"; v.targets[0].id = key; v.targets[0].data_path = f'key_blocks["{e}_{side}"].value'
        d.expression = f"k * {SCALE[e]}"
print("WRINKLE_GROUP", ng.name, "texture samples", len(IMG), "math nodes", sum(1 for n in N if n.type == "MATH"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
print("SAVED", out_blend)
