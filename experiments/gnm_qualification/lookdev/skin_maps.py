"""Region-aware procedural skin micro-detail, evaluated in 3D on the GNM template and baked to tile 1001.

    blender -b --factory-startup ../gnm_head_test.blend --python skin_maps.py -- ../textures/gnm_skin_cc0.1001.png textures/ 4096

PROCEDURAL, not photographic: no licensed photogrammetric face micro-scan was found (Phase 2C
licence search: the CC0/free skin materials available are tiling 1-2K sets of unverified provenance).
Detail is computed from 3D object coordinates (metres) on the GNM template, so it has no UV seams
and no tiling, then baked into GNM's own 1001 UV layout.

Regions come from GNM's own vertex groups, smoothed over the mesh into weights:
    nose, forehead (incl. brows), cheeks (cheek + zygomatic + infraorbital), chin, lids (orbital),
    lips, rest (scalp, ears, neck)
Bands (height), each modulated by low-frequency noise so no two areas look stamped:
    pores      3 Voronoi pit fields, spacing 0.40 / 0.60 / 0.85 mm, mixed per region
    creases    two anisotropic noise bands ~0.25 mm at different orientations (cross-hatch)
    undulation 3 mm noise, very low amplitude
    lines      forehead horizontal lines (~9 mm apart, broken by noise), vertical lip lines
Outputs (4096^2):
    skin_albedo.1001.png     sRGB   CC0 base colour x procedural variation (redness, spots, mottling)
    skin_roughness.1001.png  linear region roughness + pores rougher + noise
    skin_normal.1001.png     linear tangent-space normal of the height bands (UDIM UV tangents)
The CC0 base colour is 2048^2 and is only resampled here; new detail comes from the procedural bands.
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

a = sys.argv[sys.argv.index("--") + 1:]
cc0_png, out, res = a[0], os.path.abspath(a[1]), int(a[2])
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
sc.render.engine = "CYCLES"
p = bpy.context.preferences.addons["cycles"].preferences
try:
    p.compute_device_type = "METAL"; p.get_devices()
    for d in p.devices:
        d.use = d.type == "METAL"
    sc.cycles.device = "GPU"
except TypeError:
    pass
sc.cycles.samples = 4

src = bpy.data.objects["GNM_Head"]
REGIONS = {
    "nose": ["nose_region"],
    "forehead": ["forehead_region", "left_brow_region", "right_brow_region", "middle_brow_region", "left_temple_region", "right_temple_region"],
    "cheek": ["left_cheek_region", "right_cheek_region", "left_zygomatic_region", "right_zygomatic_region",
              "left_infraorbital_region", "right_infraorbital_region", "left_parotid_region", "right_parotid_region"],
    "chin": ["chin_region"],
    "lid": ["left_orbital_region", "right_orbital_region"],
    "lip": ["upper_lip_region", "lower_lip_region", "upper_lip", "lower_lip"],
}

# ---- bake copy: template GNM, skin faces only (tile 1001), smooth
me = src.data.copy(); me.name = "skin_bake"
if me.shape_keys:
    for kb in list(me.shape_keys.key_blocks)[::-1]:
        pass
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != 0], context="FACES")
bm.to_mesh(me); bm.free()
me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
ob = bpy.data.objects.new("skin_bake", me); sc.collection.objects.link(ob)
ob.matrix_world = Matrix.Identity(4)             # object space == GNM metres (Y up)
me.uv_layers.active = me.uv_layers["UDIM"]

# ---- region weights: group membership smoothed over mesh neighbours (12 iterations)
nv = len(me.vertices)
gidx = {g.name: g.index for g in src.vertex_groups}
memb = {}
for v in me.vertices:
    memb[v.index] = {g.group for g in v.groups}
edges = np.array([e.vertices[:] for e in me.edges])
W = {}
for r, groups in REGIONS.items():
    ids = {gidx[f"gnm_{g}"] for g in groups if f"gnm_{g}" in gidx}
    w = np.array([1.0 if memb[i] & ids else 0.0 for i in range(nv)])
    for _ in range(12):
        acc = np.zeros(nv); cnt = np.zeros(nv)
        np.add.at(acc, edges[:, 0], w[edges[:, 1]]); np.add.at(acc, edges[:, 1], w[edges[:, 0]])
        np.add.at(cnt, edges[:, 0], 1); np.add.at(cnt, edges[:, 1], 1)
        w = 0.5 * w + 0.5 * acc / np.maximum(cnt, 1)
    W[r] = w
tot = sum(W.values())
W["rest"] = np.clip(1.0 - tot, 0.0, 1.0)
norm = sum(W.values())
for r in W:
    W[r] = W[r] / np.maximum(norm, 1e-6)
    at = me.attributes.new(f"w_{r}", "FLOAT", "POINT"); at.data.foreach_set("value", W[r].astype(np.float32))
print("REGION_COVERAGE", {r: round(float((w > 0.5).mean()), 3) for r, w in W.items()})

# per-region parameters
PORE = {  # (weight of 0.40 mm, 0.60 mm, 0.85 mm fields, overall depth)
    "nose": (0.75, 0.25, 0.0, 1.00), "forehead": (0.25, 0.65, 0.10, 0.60), "cheek": (0.10, 0.55, 0.35, 0.70),
    "chin": (0.30, 0.60, 0.10, 0.70), "lid": (0.90, 0.10, 0.0, 0.12), "lip": (0.0, 0.0, 0.0, 0.0), "rest": (0.0, 0.30, 0.70, 0.30)}
ROUGH = {"nose": 0.33, "forehead": 0.38, "cheek": 0.50, "chin": 0.45, "lid": 0.46, "lip": 0.36, "rest": 0.55}
RED = {"nose": 0.10, "forehead": 0.02, "cheek": 0.08, "chin": 0.04, "lid": 0.05, "lip": 0.0, "rest": 0.03}

mat = bpy.data.materials.new("skin_detail_bake"); mat.use_nodes = True
nt = mat.node_tree; N = nt.nodes; Lk = nt.links
for n in list(N):
    N.remove(n)
outn = N.new("ShaderNodeOutputMaterial")
tc = N.new("ShaderNodeTexCoord")


def val(v):
    n = N.new("ShaderNodeValue"); n.outputs[0].default_value = v; return n.outputs[0]


def math_(op, x, y=None, clamp=False):
    n = N.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
    for i, s in enumerate((x, y)):
        if s is None:
            continue
        if isinstance(s, (int, float)):
            n.inputs[i].default_value = s
        else:
            Lk.new(s, n.inputs[i])
    return n.outputs[0]


def attr(name):
    n = N.new("ShaderNodeAttribute"); n.attribute_name = name; return n.outputs["Fac"]


def region_sum(table, idx=None):
    s = None
    for r, v in table.items():
        c = v if idx is None else v[idx]
        term = math_("MULTIPLY", attr(f"w_{r}"), c)
        s = term if s is None else math_("ADD", s, term)
    return s


def noise(scale, detail=2.0, rough=0.5, vec=None, w=0.0):
    n = N.new("ShaderNodeTexNoise"); n.noise_dimensions = "4D"
    n.inputs["Scale"].default_value = scale; n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough; n.inputs["W"].default_value = w
    Lk.new(vec if vec is not None else tc.outputs["Object"], n.inputs["Vector"])
    return n.outputs["Fac"]


def pore_field(spacing_m, seed):
    v = N.new("ShaderNodeTexVoronoi"); v.voronoi_dimensions = "4D"; v.feature = "F1"
    v.inputs["Scale"].default_value = 1.0 / spacing_m; v.inputs["W"].default_value = seed
    v.inputs["Randomness"].default_value = 1.0
    Lk.new(tc.outputs["Object"], v.inputs["Vector"])
    # pit radius varies per pore (via its random colour) between 25 and 45 % of the spacing
    sep = N.new("ShaderNodeSeparateColor"); Lk.new(v.outputs["Color"], sep.inputs[0])
    rad = math_("ADD", 0.25, math_("MULTIPLY", sep.outputs[0], 0.20))
    d = math_("DIVIDE", math_("MULTIPLY", v.outputs["Distance"], 1.0), rad)
    pit = math_("SUBTRACT", 1.0, math_("POWER", math_("MINIMUM", d, 1.0), 2.0))   # 1 at centre -> 0 at rim
    depth = math_("ADD", 0.5, math_("MULTIPLY", sep.outputs[1], 0.5))               # per-pore depth 0.5..1
    return math_("MULTIPLY", pit, depth)


pores = None
for k, (sp, seed) in enumerate(((0.00040, 1.7), (0.00060, 5.3), (0.00085, 9.1))):
    term = math_("MULTIPLY", pore_field(sp, seed), region_sum(PORE, k))
    pores = term if pores is None else math_("ADD", pores, term)
pore_depth = region_sum(PORE, 3)
pore_mod = math_("ADD", 0.45, math_("MULTIPLY", noise(180.0, 2.0), 1.1))          # regional intensity drift
pores = math_("MULTIPLY", math_("MULTIPLY", pores, pore_depth), pore_mod)


def aniso(scale_along, scale_across, angle_deg, seed):
    mp = N.new("ShaderNodeMapping"); Lk.new(tc.outputs["Object"], mp.inputs["Vector"])
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(angle_deg))
    mp.inputs["Scale"].default_value = (scale_across, scale_along, scale_across)
    return noise(1.0, 3.0, 0.55, mp.outputs["Vector"], seed)


creases = math_("ADD", aniso(1200.0, 4200.0, 35.0, 2.2), aniso(1200.0, 4200.0, -40.0, 4.4))
creases = math_("ABSOLUTE", math_("SUBTRACT", math_("MULTIPLY", creases, 0.5), 0.5))
creases = math_("SUBTRACT", 0.0, math_("MULTIPLY", math_("SUBTRACT", 1.0, math_("MULTIPLY", creases, 12.0), True),
                                       math_("SUBTRACT", 1.0, attr("w_lip"))))            # thin grooves, none on lips
und = math_("MULTIPLY", math_("SUBTRACT", noise(330.0, 3.0), 0.5), 0.6)

sepo = N.new("ShaderNodeSeparateXYZ"); Lk.new(tc.outputs["Object"], sepo.inputs[0])
fl = math_("SINE", math_("ADD", math_("MULTIPLY", sepo.outputs["Y"], 2 * math.pi / 0.009), math_("MULTIPLY", noise(90.0), 3.0)))
fl = math_("POWER", math_("MAXIMUM", fl, 0.0), 6.0)
fore_lines = math_("MULTIPLY", math_("SUBTRACT", 0.0, fl), math_("MULTIPLY", attr("w_forehead"), 0.5))
lip_lines = math_("MULTIPLY", math_("SUBTRACT", aniso(250.0, 2600.0, 90.0, 7.7), 0.5), math_("MULTIPLY", attr("w_lip"), 0.8))

height = math_("ADD", math_("ADD", math_("ADD", math_("SUBTRACT", 0.0, pores), math_("MULTIPLY", creases, 0.28)),
                                  math_("ADD", und, fore_lines)), lip_lines)

bump = N.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 1.0
bump.inputs["Distance"].default_value = 0.00015   # 40 um gave +-2-4 deg normals (measured): pores invisible
Lk.new(height, bump.inputs["Height"])

rough = math_("ADD", region_sum(ROUGH), math_("ADD", math_("MULTIPLY", pores, 0.12),
                                              math_("MULTIPLY", math_("SUBTRACT", noise(60.0, 2.0), 0.5), 0.10)), True)

# albedo variation over the CC0 base colour
img = bpy.data.images.load(os.path.abspath(cc0_png)); img.colorspace_settings.name = "sRGB"
tex = N.new("ShaderNodeTexImage"); tex.image = img; tex.interpolation = "Cubic"
uvn = N.new("ShaderNodeUVMap"); uvn.uv_map = "UDIM"; Lk.new(uvn.outputs["UV"], tex.inputs["Vector"])
redness = math_("MULTIPLY", region_sum(RED), math_("ADD", 0.4, math_("MULTIPLY", noise(45.0, 3.0), 1.2)))
spots_v = N.new("ShaderNodeTexVoronoi"); spots_v.voronoi_dimensions = "4D"; spots_v.inputs["Scale"].default_value = 1.0 / 0.006
spots_v.inputs["W"].default_value = 3.3; Lk.new(tc.outputs["Object"], spots_v.inputs["Vector"])
spsep = N.new("ShaderNodeSeparateColor"); Lk.new(spots_v.outputs["Color"], spsep.inputs[0])
spot = math_("MULTIPLY", math_("GREATER_THAN", spsep.outputs[0], 0.93),
             math_("SUBTRACT", 1.0, math_("MINIMUM", math_("DIVIDE", spots_v.outputs["Distance"], 0.12), 1.0)))
spot = math_("MULTIPLY", spot, math_("SUBTRACT", 1.0, math_("ADD", attr("w_lip"), attr("w_lid")), True))
mottle = math_("MULTIPLY", math_("SUBTRACT", noise(900.0, 2.0), 0.5), 0.07)
def rgb(r, g, b_):
    n = N.new("ShaderNodeCombineColor")
    for i, s in enumerate((r, g, b_)):
        if isinstance(s, (int, float)):
            n.inputs[i].default_value = s
        else:
            Lk.new(s, n.inputs[i])
    return n.outputs[0]
fac_r = math_("ADD", math_("ADD", 1.0, math_("MULTIPLY", redness, 0.6)), math_("SUBTRACT", mottle, math_("MULTIPLY", spot, 0.18)))
fac_g = math_("ADD", math_("SUBTRACT", 1.0, math_("MULTIPLY", redness, 0.9)), math_("SUBTRACT", mottle, math_("MULTIPLY", spot, 0.28)))
fac_b = math_("ADD", math_("SUBTRACT", 1.0, math_("MULTIPLY", redness, 0.8)), math_("SUBTRACT", mottle, math_("MULTIPLY", spot, 0.32)))
pore_dark = math_("SUBTRACT", 1.0, math_("MULTIPLY", pores, 0.10))
mul = N.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"; mul.inputs["Factor"].default_value = 1.0
Lk.new(tex.outputs["Color"], mul.inputs[6])
Lk.new(rgb(math_("MULTIPLY", fac_r, pore_dark), math_("MULTIPLY", fac_g, pore_dark), math_("MULTIPLY", fac_b, pore_dark)), mul.inputs[7])

emit = N.new("ShaderNodeEmission")
bsdf = N.new("ShaderNodeBsdfDiffuse"); Lk.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
target = N.new("ShaderNodeTexImage")
me.materials.clear(); me.materials.append(mat)


def bake(kind, colour, path, space):
    im = bpy.data.images.new(os.path.basename(path), res, res, float_buffer=(space == "Non-Color"))
    im.colorspace_settings.name = space
    target.image = im; N.active = target
    if kind == "EMIT":
        Lk.new(colour, emit.inputs["Color"]); Lk.new(emit.outputs[0], outn.inputs["Surface"])
    else:
        Lk.new(bsdf.outputs[0], outn.inputs["Surface"])
    bpy.ops.object.select_all(action="DESELECT"); ob.select_set(True); bpy.context.view_layer.objects.active = ob
    kw = dict(type=kind, margin=16, target="IMAGE_TEXTURES")
    if kind == "NORMAL":
        kw["normal_space"] = "TANGENT"
    bpy.ops.object.bake(**kw)
    im.filepath_raw = path; im.file_format = "PNG"
    if space == "Non-Color":
        im.save();
    else:
        im.save()
    print("BAKED", path, res)


bake("EMIT", mul.outputs[2], os.path.join(out, "skin_albedo.1001.png"), "sRGB")
bake("EMIT", rgb(rough, rough, rough), os.path.join(out, "skin_roughness.1001.png"), "Non-Color")
bake("NORMAL", None, os.path.join(out, "skin_normal.1001.png"), "Non-Color")
