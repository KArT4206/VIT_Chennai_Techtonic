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
    L.data.energy *= float(E("EYELIGHT_GAIN", "0.12"))
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
    kz = np.array([0.053, 0.051, 0.041, 0.030, 0.012, -0.004, -0.020, -0.035, -0.065, -0.105, -0.118])
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
w = area * np.clip((dz + 0.001) / 0.002, 0, 1) * (1.0 + 2.0 * np.clip(1.0 - dz / 0.02, 0, 1))   # denser just behind the hairline
N = int(E("HAIR_N", "175000"))
tri = rng.choice(len(T), size=N * 2, p=w / w.sum())
r1, r2 = rng.random(N * 2), rng.random(N * 2); s = np.sqrt(r1)
B = np.stack([1 - s, s * (1 - r2), s * r2], 1)
roots = (A[tri] * B[:, :, None]).sum(1)
dz, phi = hair_mask(roots)
keep = rng.random(len(roots)) < np.clip(dz / 0.0015, 0, 1)
roots = roots[keep][:N]
print("HAIR roots", len(roots))

# ---- grow strands: loose hair, centre parting, falls freely over the shoulders ----
STEP = float(E("HAIR_STEP", "0.009"))
from mathutils.kdtree import KDTree  # noqa: E402
clump_c = roots[rng.choice(len(roots), size=max(1, len(roots) // 120), replace=False)]
kd = KDTree(len(clump_c))
for i, c in enumerate(clump_c):
    kd.insert(Vector(c), i)
kd.balance()
clump_wave = rng.uniform([0.003, 85, 0], [0.008, 125, 6.28], size=(len(clump_c), 3))
clump_len = rng.uniform(0.27, 0.37, len(clump_c))
DOWN = np.array([0, 0, -1.0]); BACK = np.array([0, 1.0, 0])

def snap(p, h):
    loc, nrm, _, _ = bvh.find_nearest(Vector(p))
    n = np.array(nrm[:])
    if np.dot(n, p - C) < 0:
        n = -n
    return np.array(loc[:]) + n * h, n

def collide(p, h):
    """Push a free point out of the head/neck/shoulders to at least h above the surface."""
    loc, nrm, _, dist = bvh.find_nearest(Vector(p))
    loc = np.array(loc[:]); n = np.array(nrm[:])
    if np.dot(n, loc - C) < 0 and loc[2] > mid[2] - 0.12:
        n = -n
    d = np.dot(p - loc, n)
    return (loc + n * h) if d < h else p

def comb(p):
    """Desired flow: away from the centre parting, down, and back from the face."""
    x = p[0] - mid[0]
    side = np.array([math.copysign(1.0, x if abs(x) > 1e-4 else rng.normal()), 0, 0])
    front = float(np.clip((C[1] + 0.04 - p[1]) / 0.05, 0, 1))         # near the face: sweep back
    topfront = float(np.clip((C[1] - 0.005 - p[1]) / 0.05, 0, 1))      # parting only on the top/front; the back just falls
    g = DOWN * (1.0 - 0.95 * front) + side * (0.9 - 0.5 * min(1.0, abs(x) / 0.06)) * topfront + BACK * (0.25 + 2.6 * front)
    return g / np.linalg.norm(g)

def face_hit(pts):
    q = pts - mid
    dzp, _ = hair_mask(pts)
    return np.any((dzp < -0.006) & (np.abs(q[:, 0]) < 0.062) & (q[:, 1] < 0.035) & (q[:, 2] > -0.12))

pos_all, rad_all, sizes = [], [], []
dropped = 0
for i, r in enumerate(roots):
    ci = kd.find(Vector(r))[1]
    dzr = float(hair_mask(r[None])[0][0])
    layer = (0.0018 + 0.012 * rng.random() ** 0.6) * float(np.clip(dzr / 0.040, 0.03, 1.0)) ** 1.3   # loose volume
    wa, wf, wp = clump_wave[ci] * np.array([rng.uniform(0.7, 1.3), 1, 1]) + np.array([0, 0, rng.normal(0, 0.5)])
    fly = rng.random() < 0.008
    Ltot = clump_len[ci] * rng.uniform(0.80, 1.08)
    p, n = snap(r, -0.0002)
    pts = [p]; L_ = 0.0; free = False; v = None; Lfree = 0.0; gx = None
    cxz = np.array(clump_c[ci])
    while L_ < Ltot:
        L_ += STEP
        if not free:
            g = comb(p); d = g - n * np.dot(g, n); d /= np.linalg.norm(d) + 1e-9
            lift = max(0.0009, min(layer, 0.0008 + 0.22 * L_))
            q, n = snap(p + d * STEP, lift)
            dzq = float(hair_mask(q[None])[0][0])
            under = n[2] < -0.35                                   # under the occipital curve: hair leaves the skull
            if dzq < 0.0 or under or L_ > 0.20:
                free = True; v = (q - p) / (np.linalg.norm(q - p) + 1e-9); fn = n; Lfree = L_
        else:
            v = v * 0.6 + DOWN * 0.4; v[0] *= 0.9; v /= np.linalg.norm(v)
            q = p + v * STEP
            side = np.cross(v, fn); side /= np.linalg.norm(side) + 1e-9
            ramp = min(1.0, (L_ - Lfree) / 0.05)
            q = q + side * wa * ramp * (math.sin(wf * L_ + wp) - math.sin(wf * (L_ - STEP) + wp)) + fn * 0.5 * wa * ramp * (math.cos(wf * L_ + wp) - math.cos(wf * (L_ - STEP) + wp))   # soft waves
            fr = (L_ - Lfree) / max(0.02, Ltot - Lfree)
            if gx is None:
                gx = q.copy()
            q = q + (np.array([cxz[0] - q[0], (cxz[1] - q[1]) * 0.5, 0])) * 0.18 * math.sin(math.pi * min(1.0, fr * 0.85))   # locks
            q = collide(q, layer * 0.5 + 0.002)
            if q[2] < mid[2] - 0.17:                               # near the shoulders: slide back/out, do not pile up
                v = v + np.array([0, 0.12, 0]); v[0] *= 0.5; v /= np.linalg.norm(v)
            for sx in (-1.0, 1.0):                                 # flow smoothly over each ear (rounded shell), never wrap into it
                ec = mid + np.array([sx * 0.080, C[1] - mid[1] + 0.000, -0.030])
                rr = (q - ec) / np.array([0.040, 0.034, 0.048])
                dn = np.linalg.norm(rr)
                if dn < 1.0 and (q[0] - mid[0]) * sx > 0.05:
                    q = ec + (q - ec) / (dn + 1e-9)
            if fly:
                q = q + fn * 0.0015
        pts.append(q); p = q
    pts = np.array(pts)
    if face_hit(pts):
        dropped += 1; continue
    inear = (np.abs(pts[:, 0] - mid[0]) > 0.077) & (pts[:, 2] - mid[2] < 0.022) & (pts[:, 2] - mid[2] > -0.08) & (pts[:, 1] > C[1] - 0.035) & (pts[:, 1] < C[1] + 0.03)
    if inear[:len(pts) // 3].any():            # roots/scalp part must not run through the ear (falling hair may cover it)
        dropped += 1; continue
    qf = pts - mid
    if np.any((qf[:, 1] < C[1] - mid[1] - 0.03) & (qf[:, 2] < -0.005) & (np.abs(qf[:, 0]) < 0.12)):   # no strands hanging in front of the ears
        dropped += 1; continue
    pos_all.append(pts); sizes.append(len(pts))
    rad_all.append(np.concatenate([np.linspace(0.00007, 0.00004, max(1, len(pts) - 8)), np.linspace(0.00004, 0.00001, min(8, len(pts)))])[:len(pts)])
    if i % 20000 == 0:
        print("HAIR grown", i, flush=True)

# baby hairs: short, fine, irregular strands along the hairline
nb = int(E("BABY_N", "20000")); nbaby = 0
cand = (A[tri] * B[:, :, None]).sum(1)
bdz, bphi = hair_mask(cand)
nearear = (np.abs(cand[:, 0] - mid[0]) > 0.064) & (cand[:, 2] - mid[2] < 0.012) & (cand[:, 1] < C[1] + 0.06)
band = cand[(bdz > -0.004) & (bdz < 0.010) & ~nearear][:nb]
for r in band:
    p, n = snap(r, -0.0001)
    g = comb(p); d = g - n * np.dot(g, n); d /= np.linalg.norm(d) + 1e-9
    side = np.cross(n, d); ang = rng.normal(0, 0.8)
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

# photographic backdrop (camera rays only; scene lighting unchanged) + softer key light on the face
w = sc.world; w.use_nodes = True; wn = w.node_tree
bgn = next(nn for nn in wn.nodes if nn.type == "BACKGROUND"); wout = next(nn for nn in wn.nodes if nn.type == "OUTPUT_WORLD")
lp = wn.nodes.new("ShaderNodeLightPath"); bd = wn.nodes.new("ShaderNodeBackground"); mxw = wn.nodes.new("ShaderNodeMixShader")
tcw = wn.nodes.new("ShaderNodeTexCoord"); vm = wn.nodes.new("ShaderNodeVectorMath"); vm.operation = "DISTANCE"; vm.inputs[1].default_value = (0.5, 0.62, 0)
cr = wn.nodes.new("ShaderNodeValToRGB"); cr.color_ramp.elements[0].position = 0.0; cr.color_ramp.elements[0].color = (0.30, 0.29, 0.28, 1)
cr.color_ramp.elements[1].position = 0.85; cr.color_ramp.elements[1].color = (0.07, 0.07, 0.075, 1)
wn.links.new(tcw.outputs["Window"], vm.inputs[0]); wn.links.new(vm.outputs["Value"], cr.inputs[0]); wn.links.new(cr.outputs[0], bd.inputs["Color"])
bd.inputs["Strength"].default_value = 1.0
wn.links.new(bgn.outputs[0], mxw.inputs[1]); wn.links.new(bd.outputs[0], mxw.inputs[2]); wn.links.new(lp.outputs["Is Camera Ray"], mxw.inputs[0])
wn.links.new(mxw.outputs[0], wout.inputs["Surface"])
kl = bpy.data.objects.get("KeyLight")
if kl is not None:
    kl.data.size *= 2.0
fl = bpy.data.objects.get("FillLight")
if fl is not None:
    fl.data.energy *= 1.25

# eyes: softer whites (the scanned eyeball texture reads too bright under the studio key)
for o in bpy.data.objects:
    if o.name.startswith("Realtime Eyeball") and o.active_material and o.active_material.use_nodes:
        em = o.active_material; ent = em.node_tree
        if em.get("sclera_softened"):
            continue
        pe = next((nn for nn in ent.nodes if nn.type == "BSDF_PRINCIPLED"), None)
        if pe is not None and pe.inputs["Base Color"].is_linked:
            srcs = pe.inputs["Base Color"].links[0].from_socket
            mx = ent.nodes.new("ShaderNodeMix"); mx.data_type = "RGBA"; mx.blend_type = "MULTIPLY"; mx.inputs[0].default_value = 1.0
            mx.inputs[7].default_value = (float(E("SCLERA_GAIN", "0.80")), float(E("SCLERA_GAIN", "0.80")) * 0.98, float(E("SCLERA_GAIN", "0.80")) * 0.95, 1)
            ent.links.new(srcs, mx.inputs[6]); ent.links.new(mx.outputs[2], pe.inputs["Base Color"])
            em["sclera_softened"] = True; print("EYE sclera softened", o.name)

hmesh = head.data
Vb = (np.c_[np.array([v.co[:] for v in hmesh.vertices]), np.ones(len(hmesh.vertices))] @ np.array(head.matrix_world).T)[:, :3]
hm, _ = hair_mask(Vb)
tint = 0.55 * np.clip(hm / 0.012, 0, 1)
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
try:
    hc.set_types(type="CATMULL_ROM")          # smooth curves through fewer stored points
except Exception as ex:
    print("HAIR curve type", ex)
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
for k, v in (("Melanin", float(E("HAIR_MELANIN", "0.69"))), ("Melanin Redness", 0.20), ("Roughness", 0.40),
             ("Radial Roughness", 0.30), ("Coat", 0.0), ("Random Color", 0.25), ("Random Roughness", 0.20)):
    if k in hb.inputs:
        hb.inputs[k].default_value = v
nt.links.new(hb.outputs[0], outn.inputs[0])
hc.materials.append(m)
# soft overhead light, linked to the hair only: crown sheen without changing the face lighting
top = bpy.data.lights.new("CrownLight", "AREA"); top.size = 0.6; top.energy = float(E("CROWN_W", "2.5"))
to_ = bpy.data.objects.new("CrownLight", top); sc.collection.objects.link(to_)
to_.location = Vector(mid) + Vector((0.05, 0.30, 0.38)); to_.rotation_euler = (Vector(mid) + Vector((0, 0.06, 0.08)) - to_.location).to_track_quat("-Z", "Y").to_euler()
hcol = bpy.data.collections.new("HairOnly"); hcol.objects.link(ob)
to_.light_linking.receiver_collection = hcol
print("HAIR dropped", dropped); print("HAIR strands", len(sizes), "points", len(P))
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("GROOM_SAVED", out)
