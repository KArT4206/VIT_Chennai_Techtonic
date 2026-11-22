"""Cinematic look for the scan-head Track 1 scene (lighting, skin, grade, optional hair). Geometry, rig, eyes and
camera are untouched, so the eye calibration and metadata stay valid. Lighting stays constant across frames.

    blender -b scene.blend --factory-startup -P tools/scan_look.py -- <scan_original.blend> <out.blend> [--hair <makehuman_scene.blend>]

  * world: the vendor's own HDRI (soft, wrapping light) at HDRI_STRENGTH; studio key reduced, fill/rim kept, so the
    hard shadow down the nose softens;
  * skin: vendor specular scaled by SPEC_GAIN and roughness raised a little (removes the oily cheek patches);
  * grade: AgX with a gentle contrast look;
  * --hair: the MakeHuman scene's short strand haircut, re-seated on the scan scalp (each strand translated so its
    root sits on the nearest scalp point), with hair shading darkened to a natural brown-black.
"""
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[:2]
hair_src = argv[argv.index("--hair") + 1] if "--hair" in argv else None
E = os.environ.get
sc = bpy.context.scene

# ---- world: vendor HDRI ----
with bpy.data.libraries.load(src, link=False) as (df, dt):
    dt.images = [n for n in df.images if n == "HDRI.exr"]
hdri = dt.images[0]; hdri.pack()
w = sc.world; w.use_nodes = True; nt = w.node_tree
# the production world already mixes: camera rays see the teal backdrop, other rays see a neutral light.
# Only the LIGHTING branch (mix input 1, used when 'Is Camera Ray' = 0) gets the HDRI.
mix = next(n for n in nt.nodes if n.type == "MIX_SHADER")
light_bg = mix.inputs[1].links[0].from_node
env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = hdri
mp = nt.nodes.new("ShaderNodeMapping"); tc = nt.nodes.new("ShaderNodeTexCoord")
mp.inputs["Rotation"].default_value[2] = float(E("HDRI_ROT", "0.0"))
nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
nt.links.new(env.outputs[0], light_bg.inputs["Color"])
light_bg.inputs["Strength"].default_value = float(E("HDRI_STRENGTH", "0.5"))
for n, g in (("KeyLight", float(E("KEY_GAIN", "0.55"))), ("FillLight", float(E("FILL_GAIN", "0.8"))), ("RimLight", 1.0), ("EyeLight", 1.0)):
    o = bpy.data.objects.get(n)
    if o: o.data.energy *= g
    if o and n == "KeyLight": o.data.size = o.data.size * float(E("KEY_SIZE", "2.0"))   # bigger source -> softer shadow edge

# ---- skin ----
skin = bpy.data.materials.get("Material.001")
p = next(n for n in skin.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
spec = p.inputs.get("Specular IOR Level")
if spec is not None:
    if spec.is_linked:
        mul = skin.node_tree.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = float(E("SPEC_GAIN", "0.55"))
        skin.node_tree.links.new(spec.links[0].from_socket, mul.inputs[0]); skin.node_tree.links.new(mul.outputs[0], spec)
    else:
        spec.default_value *= float(E("SPEC_GAIN", "0.55"))
rough = p.inputs["Roughness"]
if rough.is_linked:
    add = skin.node_tree.nodes.new("ShaderNodeMath"); add.operation = "ADD"; add.inputs[1].default_value = float(E("ROUGH_ADD", "0.08")); add.use_clamp = True
    skin.node_tree.links.new(rough.links[0].from_socket, add.inputs[0]); skin.node_tree.links.new(add.outputs[0], rough)
else:
    rough.default_value = min(1.0, rough.default_value + float(E("ROUGH_ADD", "0.08")))

# ---- grade ----
try:
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = E("LOOK", "AgX - Medium High Contrast")
except TypeError:
    pass
sc.view_settings.exposure += float(E("EXPOSURE_ADD", "0.0"))

# ---- optional hair ----
if hair_src:
    with bpy.data.libraries.load(hair_src, link=False) as (df, dt):
        dt.objects = [n for n in df.objects if n == "HairStrands"]
    hair = dt.objects[0]; sc.collection.objects.link(hair)
    hair.parent = None; hair.modifiers.clear()
    head = bpy.data.objects["Head"]
    me = head.data; M = head.matrix_world
    co = np.array([(M @ v.co)[:] for v in me.vertices])
    mid = np.array(sc["eye_midpoint"])
    scalp = co[(co[:, 2] > mid[2] + 0.02)]                        # above the brow line
    kd = KDTree(len(scalp))
    for i, v in enumerate(scalp): kd.insert(Vector(v), i)
    kd.balance()
    cd = hair.data
    pos = np.array([p.vector[:] for p in cd.attributes["position"].data])
    Mh = np.array(hair.matrix_world); posw = (np.c_[pos, np.ones(len(pos))] @ Mh.T)[:, :3]
    offs = list(cd.curve_offset_data) if hasattr(cd, "curve_offset_data") else None
    starts = [c.first_point_index for c in cd.curves]; sizes = [c.points_length for c in cd.curves]
    sink = float(E("HAIR_SINK_MM", "0.6")) / 1000
    keep = np.ones(len(starts), bool)
    for ci, (s0, n) in enumerate(zip(starts, sizes)):
        root = posw[s0]
        _, j, d = kd.find(Vector(root))
        if root[2] < mid[2] + 0.035:                             # never in front of the forehead / near the eyes
            keep[ci] = False; continue
        tgt = np.array(kd.find(Vector(root))[0][:])
        nrm = (tgt - (mid + np.array([0, 0.03, 0.0]))); nrm /= np.linalg.norm(nrm)
        posw[s0:s0 + n] += (tgt - nrm * sink) - root
    Minv = np.linalg.inv(Mh); pos = (np.c_[posw, np.ones(len(posw))] @ Minv.T)[:, :3]
    cd.attributes["position"].data.foreach_set("vector", pos.ravel())
    if not keep.all():
        sel = np.repeat(~keep, sizes)
        bpy.context.view_layer.objects.active = hair
        # remove curves whose root would sit too low (hairline control)
        rm = [i for i, k in enumerate(keep) if not k]
        cd.remove_curves(indices=rm) if hasattr(cd, "remove_curves") else None
    hm = hair.data.materials[0] if hair.data.materials else None
    if hm and hm.use_nodes:
        hp = next((n for n in hm.node_tree.nodes if n.type in ("BSDF_HAIR_PRINCIPLED", "BSDF_HAIR")), None)
        if hp is not None and hp.type == "BSDF_HAIR_PRINCIPLED":
            try: hp.parametrization = "MELANIN"
            except Exception: pass
            if "Melanin" in hp.inputs: hp.inputs["Melanin"].default_value = float(E("HAIR_MELANIN", "0.85"))
    print("HAIR curves kept", int(keep.sum()), "of", len(keep))
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("LOOK_SAVED", out)
