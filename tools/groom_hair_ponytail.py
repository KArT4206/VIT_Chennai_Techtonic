"""Natural-look pass for the scan-head Track 1 scene: real strand hair + eye-only catch light.
Geometry of head/eyes, rig, camera and fixation target are untouched, so calibration and metadata stay valid.

    blender -b scene.blend --factory-startup -P tools/groom_hair.py -- <out.blend>

  * EyeLight is light-linked to the eyeballs / corneas only (it was flattening and hot-spotting the skin);
  * hair: N strands (env HAIR_N, default 70000) grown on the scalp with an irregular, density-ramped hairline,
    combed back over the skull toward the nape (pulled-back style: never in front of the brows or eyes),
    stacked in layers for volume, with clumping, waviness and a few flyaways; Principled Hair BSDF (melanin).
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
E = os.environ.get
sc = bpy.context.scene
rng = np.random.default_rng(int(E("HAIR_SEED", "7")))
mid = np.array(sc["eye_midpoint"])

# ---- eye catch light: eyes only ----
L = bpy.data.objects.get("EyeLight")
if L is not None:
    col = bpy.data.collections.new("EyeLightReceivers")
    for o in bpy.data.objects:
        if o.name.startswith(("Realtime Eyeball", "Lens", "Eye Wet")):
            col.objects.link(o)
    L.light_linking.receiver_collection = col
    L.data.energy *= float(E("EYELIGHT_GAIN", "0.3"))
    L.location = Vector(mid) + Vector((0.10, -0.46, 0.14))          # near the camera axis: even catch light in both eyes
    L.rotation_euler = (Vector(mid) - L.location).to_track_quat("-Z", "Y").to_euler()

# ---- scalp surface ----
head = bpy.data.objects["Head"]
dg = bpy.context.evaluated_depsgraph_get()
he = head.evaluated_get(dg); me = he.to_mesh()
Mw = np.array(he.matrix_world)
V = (np.c_[np.array([v.co[:] for v in me.vertices]), np.ones(len(me.vertices))] @ Mw.T)[:, :3]
me.calc_loop_triangles()
T = np.array([t.vertices[:] for t in me.loop_triangles])
he.to_mesh_clear()
bvh = BVHTree.FromPolygons([Vector(v) for v in V], [tuple(t) for t in T])
C = mid + np.array([0.0, 0.065, -0.005])               # rough skull centre (face looks to -y)

def hairline_z(phi):
    """Height above the eye midpoint where hair starts, by azimuth (0 = front, pi = back)."""
    a = np.abs(phi)
    kx = np.radians([0, 20, 40, 50, 60, 75, 90, 105, 125, 150, 180])
    kz = np.array([0.057, 0.055, 0.044, 0.030, 0.012, -0.004, -0.020, -0.035, -0.065, -0.105, -0.118])
    return np.interp(a, kx, kz)

def hair_mask(P):
    d = P - C
    phi = np.arctan2(d[:, 0], -d[:, 1])
    z = P[:, 2] - mid[2]
    hl = hairline_z(phi) + 0.0012 * np.sin(phi * 9.0) + 0.0007 * np.sin(phi * 31.0 + 1.3)   # irregular edge
    dz = z - hl
    ear = (np.abs(P[:, 0] - mid[0]) > 0.050) & (z < -0.001) & (z > -0.080) & (P[:, 1] > C[1] - 0.028) & (P[:, 1] < C[1] + 0.022) & (P[:, 1] < C[1] + 0.045) & (P[:, 1] > C[1] - 0.03)       # keep hair off the ears
    dz = np.where(ear, -1.0, dz)
    return dz, phi

# area-weighted root sampling, density ramps up over the first 6 mm past the hairline
A = V[T]; area = 0.5 * np.linalg.norm(np.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0]), axis=1)
cen = A.mean(1); dz, _ = hair_mask(cen)
w = area * np.clip((dz + 0.001) / 0.002, 0, 1)
N = int(E("HAIR_N", "200000"))
tri = rng.choice(len(T), size=N * 2, p=w / w.sum())
r1, r2 = rng.random(N * 2), rng.random(N * 2); s = np.sqrt(r1)
B = np.stack([1 - s, s * (1 - r2), s * r2], 1)
roots = (A[tri] * B[:, :, None]).sum(1)
dz, phi = hair_mask(roots)
keep = rng.random(len(roots)) < np.clip(dz / 0.0015, 0, 1)
roots = roots[keep][:N]
print("HAIR roots", len(roots))

# ---- grow strands: combed back over the skull into a low ponytail ----
STEP = 0.004
NPTS = int(E("HAIR_PTS", "80"))
from mathutils.kdtree import KDTree  # noqa: E402
clump_c = roots[rng.choice(len(roots), size=max(1, len(roots) // 80), replace=False)]
kd = KDTree(len(clump_c))
for i, c in enumerate(clump_c):
    kd.insert(Vector(c), i)
kd.balance()
clump_wave = rng.uniform([0.0004, 25, 0], [0.0013, 45, 6.28], size=(len(clump_c), 3))

def snap(p, h):
    loc, nrm, _, _ = bvh.find_nearest(Vector(p))
    n = np.array(nrm[:])
    if np.dot(n, p - C) < 0:
        n = -n
    return np.array(loc[:]) + n * h, n

# hair-tie point: on the back of the skull, low (occipital), lifted by the hair thickness
tie_s, tie_n = snap(mid + np.array([0.0, 0.30, -0.075]), 0.0)
TIE = tie_s + tie_n * 0.011
CROWN = mid + np.array([0.0, 0.22, 0.02])
TAIL_DIR = np.array([0.0, 0.22, -1.0]); TAIL_DIR /= np.linalg.norm(TAIL_DIR)
tb1 = np.array([1.0, 0, 0]); tb2 = np.cross(TAIL_DIR, tb1)
clump_off = rng.normal(0, 1, size=(len(clump_c), 2)); clump_off /= np.linalg.norm(clump_off, axis=1)[:, None]
clump_off *= np.sqrt(rng.random(len(clump_c)))[:, None]
clump_drift = rng.normal(0, 1, size=(len(clump_c), 3)); clump_len = rng.uniform(0.18, 0.30, len(clump_c))

pos_all, rad_all, sizes = [], [], []
dropped = 0
for i, r in enumerate(roots):
    ci = kd.find(Vector(r))[1]
    dzr = float(hair_mask(r[None])[0][0])
    layer = (0.0006 + 0.009 * rng.random() ** 0.7) * float(np.clip(dzr / 0.06, 0.02, 1.0)) ** 1.8
    wa, wf, wp = clump_wave[ci] * np.array([rng.uniform(0.8, 1.2), 1, 1]) + np.array([0, 0, rng.normal(0, 0.4)])
    fly = rng.random() < 0.006
    p, n = snap(r, -0.0002)
    pts = [p]; L_ = 0.0
    for k in range(1, NPTS):
        tgt = CROWN if p[1] < C[1] + 0.06 else TIE
        to = tgt - p
        d = to - n * np.dot(to, n); d /= np.linalg.norm(d) + 1e-9
        side = np.cross(n, d)
        L_ += STEP; t = min(1.0, L_ / 0.03)
        q, n = snap(p + d * STEP, max(0.0008, min(layer, 0.0006 + 0.08 * L_)) + t * 0.0004)   # clear of the displaced skin
        dist = np.linalg.norm(TIE - p)
        u = float(np.clip((0.06 - dist) / 0.035, 0, 1))          # gathered into the tie: leave the scalp
        q = q * (1 - u) + (p + (TIE - p) / (dist + 1e-9) * STEP) * u
        q = q + side * wa * math.sin(wf * L_ + wp) * t * (1 - u)
        if fly and L_ > 0.03:
            q = q + n * min(0.006, 0.0004 * (L_ - 0.03) / STEP)
        pts.append(q); p = q
        if dist < 0.012:
            break
    # tail: from the tie, falls with gravity, fans out a little, clumped
    own = rng.normal(0, 1, 2); own /= np.linalg.norm(own) + 1e-9; own *= math.sqrt(rng.random())
    off2 = 0.65 * clump_off[ci] + 0.35 * own
    Lt = clump_len[ci] * rng.uniform(0.9, 1.02)
    sv = np.arange(0.006, Lt, 0.006)
    for s_ in sv:
        f = s_ / Lt
        spread = 0.008 + 0.014 * math.sin(math.pi * min(1.0, f * 1.6)) ** 0.7 * (1 - 0.5 * f)
        q = (TIE + TAIL_DIR * s_ + np.array([0, 0.03 * (1 - math.exp(-s_ / 0.04)), 0])
             + (tb1 * off2[0] + tb2 * off2[1]) * spread
             + tb1 * wa * 1.5 * math.sin(wf * 0.6 * s_ + wp) * f)
        if f > 0.55:                                          # locks part near the tip
            q = q + clump_drift[ci] * 0.03 * (f - 0.55) ** 1.5
        if fly:
            q = q + tb1 * 0.02 * f ** 2 * math.copysign(1, off2[0])
        pts.append(q)
    pts = np.array(pts)
    dzp, php = hair_mask(pts)
    inear = (np.abs(pts[:, 0] - mid[0]) > 0.077) & (pts[:, 2] - mid[2] < 0.022) & (pts[:, 1] > C[1] - 0.035) & (pts[:, 1] < C[1] + 0.055)
    if inear.any():                                            # strand would pass through the ear
        dropped += 1; continue
    if np.any((dzp < -0.004) & (np.abs(php) < np.radians(70)) & (pts[:, 2] - mid[2] > -0.02)):     # never let a strand reach the face
        dropped += 1; continue
    pos_all.append(pts); sizes.append(len(pts))
    fine = 1.0
    rad_all.append(np.linspace(0.00007, 0.00003, len(pts)) * fine)
    if i % 20000 == 0:
        print("HAIR grown", i, flush=True)

# baby hairs: short, fine, irregular strands along the hairline (soft edge instead of a cut line)
nb = int(E("BABY_N", "14000")); nbaby = 0
cand = (A[tri] * B[:, :, None]).sum(1)
bdz, bphi = hair_mask(cand)
nearear = (np.abs(cand[:, 0] - mid[0]) > 0.064) & (cand[:, 2] - mid[2] < 0.012) & (cand[:, 1] < C[1] + 0.06)
band = cand[(bdz > -0.003) & (bdz < 0.006) & ~nearear][:nb]
for r in band:
    p, n = snap(r, -0.0001)
    to = (CROWN if p[1] < C[1] + 0.06 else TIE) - p; d = to - n * np.dot(to, n); d /= np.linalg.norm(d) + 1e-9
    side = np.cross(n, d); ang = rng.normal(0, 0.7)
    d = d * math.cos(ang) + side * math.sin(ang)
    Lb = rng.uniform(0.003, 0.013); curl = rng.normal(0, 40)
    pts = [p]
    for k in range(1, 7):
        sk = Lb * k / 6
        dd = d * math.cos(curl * sk) + np.cross(n, d) * math.sin(curl * sk)
        q, _ = snap(pts[-1] + dd * Lb / 6, 0.0004 + 0.25 * sk)
        pts.append(q)
    pts = np.array(pts)
    dzp, php = hair_mask(pts)
    if np.any((dzp < -0.006) & (np.abs(php) < np.radians(70)) & (pts[:, 2] - mid[2] > -0.02)):
        continue
    pos_all.append(pts); sizes.append(len(pts)); rad_all.append(np.linspace(0.000025, 0.000008, len(pts))); nbaby += 1
print("HAIR baby hairs", nbaby)

# hair tie
bpy.ops.mesh.primitive_torus_add(major_radius=0.0115, minor_radius=0.0035, location=tuple(TIE + TAIL_DIR * 0.004))
tie = bpy.context.active_object; tie.name = "HairTie"
tie.rotation_euler = Vector(TAIL_DIR).to_track_quat("Z", "Y").to_euler()
tm = bpy.data.materials.new("HairTie"); tm.use_nodes = True
tp = next(n for n in tm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
tp.inputs["Base Color"].default_value = (0.02, 0.018, 0.018, 1); tp.inputs["Roughness"].default_value = 0.7
tie.data.materials.append(tm)

hmesh = head.data
Vb = (np.c_[np.array([v.co[:] for v in hmesh.vertices]), np.ones(len(hmesh.vertices))] @ np.array(head.matrix_world).T)[:, :3]
hm, _ = hair_mask(Vb)
tint = 0.55 * np.clip(hm / 0.010, 0, 1)
at = hmesh.attributes.get("scalp_tint") or hmesh.attributes.new("scalp_tint", "FLOAT", "POINT")
if len(hmesh.vertices) == len(tint):
    at.data.foreach_set("value", tint.astype(np.float32))
    skin = next((m for m in hmesh.materials if m and m.use_nodes), None)
    if skin is not None:
        snt = skin.node_tree; pb = next(n for n in snt.nodes if n.type == "BSDF_PRINCIPLED")
        bc = pb.inputs["Base Color"]
        if bc.is_linked:
            src_sock = bc.links[0].from_socket
            an = snt.nodes.new("ShaderNodeAttribute"); an.attribute_name = "scalp_tint"
            mx = snt.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MIX"
            mx.inputs[7].default_value = (0.025, 0.017, 0.012, 1)
            snt.links.new(an.outputs["Fac"], mx.inputs[0]); snt.links.new(src_sock, mx.inputs[6])
            snt.links.new(mx.outputs[2], bc)
            print("HAIR scalp tint applied")
hc = bpy.data.hair_curves.new("ScalpHair")
hc.add_curves(sizes)
P = np.concatenate(pos_all)
hc.attributes["position"].data.foreach_set("vector", P.ravel())
ra = hc.attributes.get("radius") or hc.attributes.new("radius", "FLOAT", "POINT")
ra.data.foreach_set("value", np.concatenate(rad_all))
ob = bpy.data.objects.new("ScalpHair", hc)
sc.collection.objects.link(ob)

m = bpy.data.materials.new("Hair_natural"); m.use_nodes = True; nt = m.node_tree
bs = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"); outn = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
nt.nodes.remove(bs)
hb = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
try:
    hb.parametrization = "MELANIN"
except Exception:
    pass
for k, v in (("Melanin", float(E("HAIR_MELANIN", "0.62"))), ("Melanin Redness", 0.42), ("Roughness", 0.30),
             ("Radial Roughness", 0.30), ("Coat", 0.0), ("Random Color", 0.25), ("Random Roughness", 0.20)):
    if k in hb.inputs:
        hb.inputs[k].default_value = v
nt.links.new(hb.outputs[0], outn.inputs[0])
hc.materials.append(m)
# soft overhead light, linked to the hair only: crown sheen without changing the face lighting
top = bpy.data.lights.new("CrownLight", "AREA"); top.size = 0.6; top.energy = float(E("CROWN_W", "5"))
to_ = bpy.data.objects.new("CrownLight", top); sc.collection.objects.link(to_)
to_.location = Vector(mid) + Vector((0.05, 0.20, 0.42)); to_.rotation_euler = (Vector(mid) + Vector((0, 0.06, 0.08)) - to_.location).to_track_quat("-Z", "Y").to_euler()
hcol = bpy.data.collections.new("HairOnly"); hcol.objects.link(ob)
to_.light_linking.receiver_collection = hcol
print("HAIR dropped", dropped); print("HAIR strands", len(sizes), "points", len(P))
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("GROOM_SAVED", out)
