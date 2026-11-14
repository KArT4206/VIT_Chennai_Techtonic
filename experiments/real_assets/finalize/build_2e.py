"""Phase 2E build: corrected eye maps, distinct right iris, brow-lowerer keys, switchable skin displacement.

    blender -b --factory-startup --disable-autoexec ../3dscanstore/build/gnm_scan.blend --python build_2e.py -- \
        ../3dscanstore/build/phase2e

Reads gnm_scan.blend (not modified) and saves phase2e/gnm_scan_2e.blend. GNM topology, face order, UVs, the
7 UDIM materials and the eye joints are untouched (checked at the end).

1. Eye maps. Root cause of the side-gaze pink patch: the vendor "realtime" eyeball map is authored for a
   fixed straight gaze. Only a four-lobed region around the cornea is painted as sclera (white with vessels,
   out to ~45-60 deg from the corneal axis); everything beyond is a flat salmon fill. At 15-20 deg gaze the
   abducted eye shows sclera up to ~75 deg from its axis at the outer canthus, i.e. the fill.
   Fix: re-bake from the same vendor eyeball with an angular remap of the SOURCE mesh about the corneal
   axis. alpha <= 30 deg is untouched (iris, limbus, near sclera are pixel-identical in angle), the
   per-azimuth sclera boundary alpha_b(phi) (measured on the vendor map, pinkness < 0.2) is moved out to
   82 deg, and the fill is compressed behind it. Only original photographic pixels are used; no colour is
   painted.
2. Right iris. Same vendor eye (one texture ships), varied anatomically: the iris (alpha < 20 deg, fading to
   zero by 26 deg, so the limbal ring and pupil stay put) is turned 137 deg about the optical axis, so crypts
   and furrows land in different places, then a low-frequency radial/angular pigment modulation (+-5 %, mean
   preserved, hue preserved) is applied to the baked iris annulus. Not mirrored.
3. brow_furrow_L/R keys: Phase 2D brow lowerer (0.67 x semantic DISGUST eye blocks) on the scan base.
4. Skin material copy "Skin_2E" (vendor Material.001 untouched) with a Displacement node fed by the vendor
   16-bit map; controlled by node groups/values so render scripts can choose variants A-D.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
import OpenImageIO as oiio
from mathutils import Matrix, Vector

out_dir = os.path.abspath(sys.argv[sys.argv.index("--") + 1]); os.makedirs(out_dir, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "..", "3dscanstore", "build")
TEX = os.path.join(HERE, "..", "3dscanstore", "extracted", "Textures")
sc = bpy.context.scene
p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
gh = bpy.data.objects["GNM_Head"]; me = gh.data; V2W = gh.matrix_world.copy(); nv = len(me.vertices)
K = np.load(os.path.join(BUILD, "gnm_scan_keys.npz")); names = [str(n) for n in K["joint_names"]]
basis = np.empty(nv * 3, np.float32); me.shape_keys.key_blocks["Basis"].data.foreach_get("co", basis); basis = basis.reshape(-1, 3)
# fingerprints for the topology/UV check at the end
fp_faces = np.empty(sum(len(f.vertices) for f in me.polygons), np.int32); me.polygons.foreach_get("vertices", fp_faces)
fp_uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers["UDIM"].data.foreach_get("uv", fp_uv)
fp_mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", fp_mi)
gi = {g.name: g.index for g in gh.vertex_groups}
memb = [set(g.group for g in v.groups) for v in me.vertices]
diffuse = oiio.ImageBuf(os.path.join(TEX, "TGA", "Eyes", "Eyes_Balls_Diffuse.tga")).get_pixels(oiio.FLOAT)[..., :3]
DH, DW = diffuse.shape[:2]
ALPHA_KEEP, THETA_T, IRIS_IN, IRIS_OUT, IRIS_TURN = 30.0, 82.0, 20.0, 26.0, 137.0
log = {}


def frame(axis):
    a = Vector(axis).normalized(); t = Vector((1, 0, 0)) - a * a.x; t.normalize(); b = a.cross(t)
    return a, t, b


def bake_eye(side, name, slot, u_shift, iris_turn):
    c = Vector(K["joints"][names.index(f"{side}_eye")].tolist())
    pu = [i for i in range(nv) if gi["gnm_pupils"] in memb[i] and gi[f"gnm_{side}_eye"] in memb[i]]
    primary = (Vector(basis[pu].mean(0).tolist()) - c).normalized()
    ball = bpy.data.objects[f"Realtime Eyeball {name}"]; lens = bpy.data.objects[f"Lens {name}"]
    W2G = V2W.inverted()   # hidden vendor objects are not re-evaluated after load: matrix_world is stale, use matrix_basis (no parents)
    # vendor corneal axis (lens apex) in the GNM frame
    L = np.array([(W2G @ lens.matrix_basis @ v.co)[:] for v in lens.data.vertices])
    apex = L[np.argmax(np.linalg.norm(L - np.array(c[:]), axis=1))]
    axis_s = Vector((apex - np.array(c[:])).tolist()).normalized()
    q = axis_s.rotation_difference(primary)
    src = ball.data.copy()
    P = np.array([(q @ ((W2G @ ball.matrix_basis @ v.co) - c))[:] for v in src.vertices])   # eye-centred, aligned
    a_, t_, b_ = frame(primary)
    A = np.array(a_[:]); T = np.array(t_[:]); B = np.array(b_[:])
    r = np.linalg.norm(P, axis=1); dn = P / r[:, None]
    alpha = np.degrees(np.arccos(np.clip(dn @ A, -1, 1)))
    phi = np.degrees(np.arctan2(dn @ B, dn @ T)) % 360
    # vendor-map pinkness at each source vertex (first-loop UV)
    uvs = np.empty(len(src.loops) * 2, np.float32); src.uv_layers.active.data.foreach_get("uv", uvs); uvs = uvs.reshape(-1, 2)
    lv = np.empty(len(src.loops), np.int32); src.loops.foreach_get("vertex_index", lv)
    vuv = np.zeros((len(P), 2)); vuv[lv] = uvs
    col = diffuse[np.clip(((1 - vuv[:, 1] % 1) * DH).astype(int), 0, DH - 1), np.clip((vuv[:, 0] % 1 * DW).astype(int), 0, DW - 1)]
    pink = (col[:, 0] - col[:, 1]) / np.maximum(col[:, 0], 1e-3)
    nb = 36; ab = np.zeros(nb)
    for k in range(nb):
        sel = (np.abs(((phi - (k + 0.5) * 360 / nb + 180) % 360) - 180) < 360 / nb) & (alpha > ALPHA_KEEP) & (alpha < 95)
        ok = sel & (pink < 0.2)
        ab[k] = alpha[ok].max() if ok.any() else ALPHA_KEEP + 12
    ab = np.array([np.median(np.take(ab, [k - 1, k, (k + 1) % nb])) for k in range(nb)])
    ab = np.maximum(ab, ALPHA_KEEP + 8)
    # per-vertex boundary (circular linear interpolation)
    x = phi / (360 / nb) - 0.5; k0 = np.floor(x).astype(int) % nb; f = x - np.floor(x)
    abv = ab[k0] * (1 - f) + ab[(k0 + 1) % nb] * f
    new = alpha.copy()
    m1 = (alpha > ALPHA_KEEP) & (alpha <= abv)
    new[m1] = ALPHA_KEEP + (alpha[m1] - ALPHA_KEEP) * (THETA_T - ALPHA_KEEP) / (abv[m1] - ALPHA_KEEP)
    m2 = alpha > abv
    new[m2] = THETA_T + (alpha[m2] - abv[m2]) * (180 - THETA_T) / (180 - abv[m2])
    turn = np.zeros(len(P))
    if iris_turn:
        w = np.clip((IRIS_OUT - alpha) / (IRIS_OUT - IRIS_IN), 0, 1); w = w * w * (3 - 2 * w)
        turn = iris_turn * w
    phin = np.radians(phi + turn); an = np.radians(new)
    Dn = np.cos(an)[:, None] * A + np.sin(an)[:, None] * (np.cos(phin)[:, None] * T + np.sin(phin)[:, None] * B)
    Pn = Dn * r[:, None] + np.array(c[:])
    log[side] = dict(boundary_deg=np.round(ab, 1).tolist(), stretch_max=float(((THETA_T - ALPHA_KEEP) / (ab - ALPHA_KEEP)).max()),
                     axis_alignment_deg=math.degrees(axis_s.angle(primary)))
    print(f"EYE {side}: sclera boundary alpha_b min {ab.min():.1f} max {ab.max():.1f} deg -> {THETA_T}; iris turn {iris_turn}")
    src.vertices.foreach_set("co", Pn.astype(np.float32).reshape(-1))
    tmp = bpy.data.objects.new(f"eyesrc_{side}", src); sc.collection.objects.link(tmp); tmp.matrix_world = V2W.copy()
    bm_mat = ball.material_slots[0].material.copy()
    next(n for n in bm_mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Subsurface Weight"].default_value = 0.0
    src.materials.clear(); src.materials.append(bm_mat)
    # target: GNM eye interior faces of this eye at rest, u shifted into 0-1
    tm = me.copy()
    bm = bmesh.new(); bm.from_mesh(tm)
    bmesh.ops.delete(bm, geom=[fc for fc in bm.faces if fc.material_index != slot], context="FACES")
    uvl = bm.loops.layers.uv["UDIM"]
    for fc in bm.faces:
        for lp in fc.loops:
            lp[uvl].uv = (lp[uvl].uv.x - u_shift, lp[uvl].uv.y)
    bm.to_mesh(tm); bm.free()
    tm.polygons.foreach_set("use_smooth", [True] * len(tm.polygons))
    tgt = bpy.data.objects.new(f"eyetgt_{side}", tm); sc.collection.objects.link(tgt); tgt.matrix_world = V2W.copy()
    bpy.context.view_layer.update()
    for o in (tmp, tgt):
        bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
        if o.data.shape_keys:
            o.shape_key_clear()
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    img = bpy.data.images.new(f"eye2e_{side}", 2048, 2048); img.colorspace_settings.name = "sRGB"
    mt = bpy.data.materials.new(f"eye2e_bake_{side}"); mt.use_nodes = True
    tn = mt.node_tree.nodes.new("ShaderNodeTexImage"); tn.image = img; mt.node_tree.nodes.active = tn
    tm.materials.clear(); tm.materials.append(mt)
    bpy.ops.object.select_all(action="DESELECT"); tmp.select_set(True); tgt.select_set(True); bpy.context.view_layer.objects.active = tgt
    sc.cycles.samples = 16
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, use_selected_to_active=True, cage_extrusion=0.3, max_ray_distance=0.6, margin=16)
    tile = 1002 if side == "left" else 1004
    path = os.path.join(out_dir, f"scan_eye_albedo_2e.{tile}.png")
    img.filepath_raw = path; img.file_format = "PNG"; img.save()
    bpy.data.objects.remove(tmp); bpy.data.objects.remove(tgt)
    return path, tile


paths = {}
for side, name, slot, sh, turn in (("left", "Left", 1, 1.0, 0.0), ("right", "Right", 3, 3.0, 0.0)):
    paths[side] = bake_eye(side, name, slot, sh, turn)

# right iris pigment modulation (2-D, in the baked tile, iris annulus only)
uv = fp_uv.reshape(-1, 2); lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv)
vuv = np.zeros((nv, 2)); vuv[lv] = uv
path, tile = paths["right"]
pu = [i for i in range(nv) if gi["gnm_pupils"] in memb[i] and gi["gnm_right_eye"] in memb[i]]
ir = [i for i in range(nv) if gi["gnm_irises"] in memb[i] and gi["gnm_right_eye"] in memb[i]]
cu = vuv[pu].mean(0) - [3.0, 0.0]
r_p = np.linalg.norm(vuv[pu] - [3.0, 0.0] - cu, axis=1).max(); r_i = np.linalg.norm(vuv[ir] - [3.0, 0.0] - cu, axis=1).max()
buf = oiio.ImageBuf(path); px = buf.get_pixels(oiio.FLOAT); H, W = px.shape[:2]
yy, xx = np.mgrid[0:H, 0:W]; u = (xx + 0.5) / W - cu[0]; v = (1 - (yy + 0.5) / H) - cu[1]
rr = np.hypot(u, v); th = np.arctan2(v, u)
# (a) turn the iris about the pupil centre by IRIS_TURN in the baked map (exact rigid image rotation,
#     bilinear) out to 1.00 r_iris, then a plain crossfade (no twist) to the original over 1.00-1.12 r_iris,
#     where both are the soft, rotation-symmetric limbal gradient. Earlier attempts that twisted the turn
#     across a band (source-mesh twist: folded triangles; 2-D twist: spiral streaks) were rejected on inspection.
ca, sa = np.cos(np.radians(IRIS_TURN)), np.sin(np.radians(IRIS_TURN))
su = (cu[0] + u * ca + v * sa) * W - 0.5; sv = (1 - (cu[1] - u * sa + v * ca)) * H - 0.5
x0 = np.clip(np.floor(su).astype(int), 0, W - 2); y0 = np.clip(np.floor(sv).astype(int), 0, H - 2)
fx = np.clip(su - x0, 0, 1)[..., None]; fy = np.clip(sv - y0, 0, 1)[..., None]
rot = (px[y0, x0] * (1 - fx) * (1 - fy) + px[y0, x0 + 1] * fx * (1 - fy) + px[y0 + 1, x0] * (1 - fx) * fy + px[y0 + 1, x0 + 1] * fx * fy)
wt = np.clip((r_i * 1.12 - rr) / (r_i * 0.12), 0, 1); wt = (wt * wt * (3 - 2 * wt))[..., None]
px = rot * wt + px * (1 - wt)
# (b) low-frequency pigment modulation (+-5 %), iris annulus only
rng = np.random.default_rng(20261114)
mod = np.zeros_like(rr)
for k in range(2, 10):
    a1, a2 = rng.normal(0, 1, 2) / k
    mod += a1 * np.cos(k * th + rng.uniform(0, 2 * np.pi)) * np.sin(np.pi * np.clip((rr - r_p) / (r_i - r_p), 0, 1) * (1 + k % 3))
    mod += a2 * np.sin(k * th) * 0.5
win = np.clip((rr - r_p * 1.08) / (r_p * 0.15), 0, 1) * np.clip((r_i * 0.97 - rr) / (r_i * 0.08), 0, 1)
mod = mod / (np.abs(mod[win > 0.5]).max() + 1e-9) * 0.05 * win
sel = win > 0
mod[sel] -= mod[sel].mean()                     # brightness-neutral on average
px[..., :3] *= (1 + mod)[..., None]
px = np.clip(px, 0, 1)
outb = oiio.ImageBuf(oiio.ImageSpec(W, H, px.shape[2], oiio.UINT8)); outb.set_pixels(oiio.ROI(), px.astype(np.float32)); outb.write(path)
log["iris_uv"] = dict(centre=cu.tolist(), r_pupil=float(r_p), r_iris=float(r_i), modulation_max=float(np.abs(mod).max()))
print("IRIS right: pupil r", round(float(r_p), 4), "iris r", round(float(r_i), 4), "UV centre", np.round(cu, 4))

# eye materials -> new UDIM image
img = bpy.data.images.load(paths["left"][0]); img.source = "TILED"; img.name = "scan_eye_albedo_2e_udim"; img.colorspace_settings.name = "sRGB"
print("UDIM tiles:", [t.number for t in img.tiles])
for i in (1, 3):
    for n in me.materials[i].node_tree.nodes:
        if n.type == "TEX_IMAGE":
            n.image = img

# brow lowerer keys
off = np.load(os.path.join(out_dir, "brow_furrow_offsets.npz"))
for k in ("brow_furrow_L", "brow_furrow_R"):
    kb = me.shape_keys.key_blocks.get(k) or gh.shape_key_add(name=k, from_mix=False)
    kb.data.foreach_set("co", (basis + off[k]).reshape(-1)); kb.slider_min, kb.slider_max = 0.0, 1.0; kb.value = 0.0

# skin displacement (material copy; vendor Material.001 untouched)
skin = me.materials[0].copy(); skin.name = "Skin_2E"; me.materials[0] = skin
nt = skin.node_tree; nodes = nt.nodes
outn = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
dimg = bpy.data.images.load(os.path.join(TEX, "Displacement", "Face_Displacement.tif")); dimg.colorspace_settings.name = "Non-Color"
dt = nodes.new("ShaderNodeTexImage"); dt.image = dimg; dt.name = "DISP_TEX"; dt.interpolation = "Cubic"
uvn = nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UDIM"; nt.links.new(uvn.outputs["UV"], dt.inputs["Vector"])
dn = nodes.new("ShaderNodeDisplacement"); dn.name = "DISP"; dn.space = "OBJECT"
dn.inputs["Midlevel"].default_value = 0.436                    # mean inside the UV island (measured)
dn.inputs["Scale"].default_value = 0.0                         # variant A by default
nt.links.new(dt.outputs["Color"], dn.inputs["Height"]); nt.links.new(dn.outputs["Displacement"], outn.inputs["Displacement"])
skin.displacement_method = "BUMP"
nmap = next(n for n in nodes if n.type == "NORMAL_MAP"); nmap.name = "NMAP"
mixn = next(l.to_node for l in nt.links if l.from_node.name == "Image Texture.003"); mixn.name = "NMIX"
print("NMIX", mixn.data_type, mixn.blend_type, [(i.name, getattr(i, 'default_value', None) if not hasattr(i.default_value, '__len__') else tuple(i.default_value)) for i in mixn.inputs if i.enabled][:3])
log["normal_mix"] = dict(blend=mixn.blend_type, data_type=mixn.data_type)

# checks: topology / UV / materials / joints untouched
f2 = np.empty_like(fp_faces); me.polygons.foreach_get("vertices", f2)
u2 = np.empty_like(fp_uv); me.uv_layers["UDIM"].data.foreach_get("uv", u2)
m2 = np.empty_like(fp_mi); me.polygons.foreach_get("material_index", m2)
b2 = np.empty(nv * 3, np.float32); me.shape_keys.key_blocks["Basis"].data.foreach_get("co", b2)
print("CHECK faces identical", bool((f2 == fp_faces).all()), "| UV identical", bool((u2 == fp_uv).all()),
      "| material idx identical", bool((m2 == fp_mi).all()), "| basis identical", bool((b2.reshape(-1, 3) == basis).all()),
      "| vertices", nv, "| polygons", len(me.polygons))
import json  # noqa: E402
json.dump(log, open(os.path.join(out_dir, "build_2e.json"), "w"), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "gnm_scan_2e.blend"), relative_remap=True)
print("SAVED")
