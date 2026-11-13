"""Assemble the GNM look-development scene from the Phase 2B prototype + lookdev textures.

    blender -b --factory-startup ../gnm_expression_test.blend --python build_lookdev.py -- textures OUT_BLEND [RENDER_DIR]

Geometry, UVs, shape keys, rig and Timeline come unchanged from gnm_expression_test.blend.
Materials (all values documented in REPORT):
  skin (1001)     albedo / roughness / tangent normal maps (4096^2, UDIM UVs), Principled:
                  Subsurface Weight 0.35, Radius (1.0, 0.36, 0.20), Scale 1.2 mm (measured skin mean
                  free paths are ~1 mm red); IOR 1.40; Specular IOR Level 0.5; normal strength 1.0
  eye interiors   one UDIM albedo + normal set for 1002/1004 (two seeded irises), split by GNM's own
  (1002/1004)     iris/pupil groups (attribute iris_mask): iris/pupil = no specular (it sits in aqueous
                  humour, production rule), rough 0.8; sclera = SSS 0.4 / 2 mm, rough 0.35, wet coat
                  (weight 1, rough 0.04, IOR 1.336)
  corneas         refractive cap only (Phase 2B fix), rest of GNM's closed eye shell transparent
"""

import os
import shutil
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import portrait  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
tex, out_blend = os.path.abspath(a[0]), a[1]
rdir = a[2] if len(a) > 2 else None
sc = bpy.context.scene
ob = bpy.data.objects["GNM_Head"]
me = ob.data

udim = os.path.join(tex, "udim"); os.makedirs(udim, exist_ok=True)
for src, dst in (("skin_albedo.1001.png", "albedo.1001.png"), ("eye_albedo.1002.png", "albedo.1002.png"),
                 ("eye_albedo.1004.png", "albedo.1004.png"), ("skin_normal.1001.png", "normal.1001.png"),
                 ("eye_normal.1002.png", "normal.1002.png"), ("eye_normal.1004.png", "normal.1004.png"),
                 ("skin_roughness.1001.png", "roughness.1001.png")):
    shutil.copyfile(os.path.join(tex, src), os.path.join(udim, dst))


def tiled(name, space):
    im = bpy.data.images.load(os.path.join(udim, f"{name}.1001.png"))
    im.source = "TILED"; im.name = f"GNM_{name}"; im.colorspace_settings.name = space
    return im


ALB, NRM, RGH = tiled("albedo", "sRGB"), tiled("normal", "Non-Color"), tiled("roughness", "Non-Color")
print("UDIM", {i.name: sorted(t.number for t in i.tiles) for i in (ALB, NRM, RGH)})

# iris mask from GNM groups (iris + pupil vertices of both eyes)
gi = {g.name: g.index for g in ob.vertex_groups}
mask = np.array([1.0 if {gi["gnm_irises"], gi["gnm_pupils"]} & {g.group for g in v.groups} else 0.0 for v in me.vertices], np.float32)
at = me.attributes.get("iris_mask") or me.attributes.new("iris_mask", "FLOAT", "POINT")
at.data.foreach_set("value", mask)


def texnode(nt, img, uvname="UDIM"):
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = "Cubic"
    u = nt.nodes.new("ShaderNodeUVMap"); u.uv_map = uvname
    nt.links.new(u.outputs["UV"], t.inputs["Vector"])
    return t


def normal_map(nt, img, strength=1.0):
    t = texnode(nt, img)
    n = nt.nodes.new("ShaderNodeNormalMap"); n.uv_map = "UDIM"; n.inputs["Strength"].default_value = strength
    nt.links.new(t.outputs["Color"], n.inputs["Color"])
    return n.outputs["Normal"]


def principled(nt):
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    return b, out


for i, mat in enumerate(me.materials):
    tile = 1001 + i
    nt = mat.node_tree
    if tile == 1001:
        for n in [n for n in nt.nodes if n.type in ("TEX_IMAGE", "UVMAP")]:
            nt.nodes.remove(n)
        b, _ = principled(nt)
        nt.links.new(texnode(nt, ALB).outputs["Color"], b.inputs["Base Color"])
        r = texnode(nt, RGH); nt.links.new(r.outputs["Color"], b.inputs["Roughness"])
        nt.links.new(normal_map(nt, NRM, 1.0), b.inputs["Normal"])
        b.inputs["Subsurface Weight"].default_value = 0.35   # iter7: 1.0 read pale and waxy next to MakeHuman
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.36, 0.20)
        b.inputs["Subsurface Scale"].default_value = 0.0012
        b.inputs["IOR"].default_value = 1.40
        b.inputs["Specular IOR Level"].default_value = 0.5
    elif tile in (1002, 1004):
        for n in list(nt.nodes):
            if n.type != "OUTPUT_MATERIAL":
                nt.nodes.remove(n)
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        col = texnode(nt, ALB).outputs["Color"]
        nrm = normal_map(nt, NRM, 1.0)
        iris = nt.nodes.new("ShaderNodeBsdfPrincipled"); scl = nt.nodes.new("ShaderNodeBsdfPrincipled")
        for b in (iris, scl):
            nt.links.new(col, b.inputs["Base Color"]); nt.links.new(nrm, b.inputs["Normal"])
        iris.inputs["Specular IOR Level"].default_value = 0.0
        iris.inputs["Roughness"].default_value = 0.8
        scl.inputs["Roughness"].default_value = 0.35
        scl.inputs["Subsurface Weight"].default_value = 0.4
        scl.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.25)
        scl.inputs["Subsurface Scale"].default_value = 0.002
        scl.inputs["Coat Weight"].default_value = 1.0
        scl.inputs["Coat Roughness"].default_value = 0.04
        scl.inputs["Coat IOR"].default_value = 1.336
        m = nt.nodes.new("ShaderNodeMixShader")
        am = nt.nodes.new("ShaderNodeAttribute"); am.attribute_name = "iris_mask"
        nt.links.new(am.outputs["Fac"], m.inputs["Fac"])
        nt.links.new(scl.outputs[0], m.inputs[1]); nt.links.new(iris.outputs[0], m.inputs[2])
        nt.links.new(m.outputs[0], out.inputs["Surface"])
    elif tile in (1003, 1005):
        # Smooth cornea: IOR ramps 1.376 -> 1.0 with the shell's distance from the eye centre
        # (attribute cornea_w), so refraction fades out instead of stopping at a polygon edge
        # (iter1 showed a ticked ring at the hard Phase 2B cap boundary).
        for n in list(nt.nodes):
            if n.type != "OUTPUT_MATERIAL":
                nt.nodes.remove(n)
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        g = nt.nodes.new("ShaderNodeBsdfPrincipled")
        g.inputs["Base Color"].default_value = (1, 1, 1, 1)
        g.inputs["Transmission Weight"].default_value = 1.0
        g.inputs["Roughness"].default_value = 0.0
        aw = nt.nodes.new("ShaderNodeAttribute"); aw.attribute_name = "cornea_w"
        ior = nt.nodes.new("ShaderNodeMath"); ior.operation = "MULTIPLY_ADD"
        nt.links.new(aw.outputs["Fac"], ior.inputs[0]); ior.inputs[1].default_value = 0.376; ior.inputs[2].default_value = 1.0
        nt.links.new(ior.outputs[0], g.inputs["IOR"])
        nt.links.new(g.outputs[0], out.inputs["Surface"])

# cornea_w: smoothstep of the shell vertex's distance from its eye centre, 14.65 mm -> 0, 15.6 mm -> 1
rig_b = bpy.data.objects["GNM_Rig"].data.bones
cw = np.zeros(len(me.vertices), np.float32)
for side in ("left", "right"):
    c = np.array(rig_b[f"{side}_eye"].head_local)
    for v in me.vertices:
        gs = {g.group for g in v.groups}
        if gi["gnm_eye_exteriors"] in gs and gi[f"gnm_{side}_eye"] in gs:
            t = min(max((np.linalg.norm(np.array(v.co) - c) - 0.01465) / (0.0156 - 0.01465), 0.0), 1.0)
            cw[v.index] = t * t * (3 - 2 * t)
at = me.attributes.get("cornea_w") or me.attributes.new("cornea_w", "FLOAT", "POINT")
at.data.foreach_set("value", cw)
print("CORNEA_W >0.5:", int((cw > 0.5).sum()), "vertices")

cam = bpy.data.objects.get("Cam")
mid = ob.matrix_world @ __import__("mathutils").Vector(tuple(np.mean([b.head_local for b in (bpy.data.objects["GNM_Rig"].data.bones["left_eye"], bpy.data.objects["GNM_Rig"].data.bones["right_eye"])], axis=0)))
fwd = (ob.matrix_world.to_3x3() @ __import__("mathutils").Vector((0, 0, 1))).normalized()
for o in [o for o in bpy.data.objects if o.type == "LIGHT"]:
    bpy.data.objects.remove(o)
portrait.build(sc, mid, fwd)
sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "None"
sc.cycles.samples = 256
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
print("SAVED", out_blend)
