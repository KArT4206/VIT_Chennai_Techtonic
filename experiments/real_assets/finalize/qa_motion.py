"""Phase 2N.5 motion QA on the PRIVATE web GLB (read-only; nothing is saved back).

    blender -b --factory-startup --python qa_motion.py -- <glb> <out_dir>

Measures, for each of the 12 shape keys and a set of combinations, on the head, brow and lash meshes:
displacement, affected region, spikes, strand attachment (floating brows / detached lashes) and
eyelid/lash penetration into the eyeballs. Fits spheres to the eyeball geometry (excluding corneas)
and compares them with the eye-bone pivots, then renders neutral / left / right / up / down gaze.
Results: <out_dir>/qa_motion.json and gaze_*.png (scan-derived: keep private).
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

glb, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
bpy.context.view_layer.update()

objs = {o.name: o for o in bpy.data.objects}
head = next(o for o in objs.values() if o.type == "MESH" and o.name.startswith("GNM_Head"))
brows = next(o for o in objs.values() if o.type == "MESH" and o.name.startswith("Brows"))
lashes = next(o for o in objs.values() if o.type == "MESH" and o.name.startswith("Lashes"))
rig = next(o for o in objs.values() if o.type == "ARMATURE")
MM = 1000.0  # GLB is in metres


def world(o, co):
    return np.array([tuple(o.matrix_world @ Vector(c)) for c in co])


def key_arrays(o):
    kb = o.data.shape_keys.key_blocks
    n = len(o.data.vertices)
    base = np.empty(n * 3); kb[0].data.foreach_get("co", base); base = base.reshape(-1, 3)
    M = np.array(o.matrix_world)
    R, T = M[:3, :3], M[:3, 3]
    out_ = {"__basis": base @ R.T + T}
    for k in kb[1:]:
        a = np.empty(n * 3); k.data.foreach_get("co", a)
        out_[k.name] = (a.reshape(-1, 3) - base) @ R.T
    return out_


H, B, L = key_arrays(head), key_arrays(brows), key_arrays(lashes)
KEYS = [k for k in H if not k.startswith("__")]
mat_idx = np.array([p.material_index for p in head.data.polygons])
mats = [m.name if m else "" for m in head.data.materials]


def verts_of(matname):
    ids = set()
    for p in head.data.polygons:
        if mats[p.material_index].startswith(matname):
            ids.update(p.vertices)
    return np.array(sorted(ids))


skin_ids = verts_of("Skin")
eye_ids = {"L": verts_of("Eye_L"), "R": verts_of("Eye_R")}
cornea_ids = verts_of("Cornea")


def fit_sphere(P):
    A = np.c_[2 * P, np.ones(len(P))]
    b = (P ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    c = x[:3]
    return c, math.sqrt(x[3] + c @ c)


def robust_sphere(P):
    keep = P
    for _ in range(4):
        c, r = fit_sphere(keep)
        res = np.abs(np.linalg.norm(keep - c, axis=1) - r)
        keep = keep[res <= np.percentile(res, 80)]
    c, r = fit_sphere(keep)
    res = np.abs(np.linalg.norm(keep - c, axis=1) - r)
    return c, r, float(res.mean()), len(keep)


# eye bones (armature at rest == bind)
bones = {}
for side, name in (("L", "left_eye"), ("R", "right_eye")):
    b = rig.data.bones[name]
    bones[side] = np.array(tuple(rig.matrix_world @ b.head_local))

eyes = {}
for s in ("L", "R"):
    P = H["__basis"][eye_ids[s]]
    c, r, rms, n = robust_sphere(P)
    eyes[s] = {"centre": c, "radius": r}
    eyes[s]["report"] = {
        "verts_total": int(len(P)), "verts_on_sphere": n, "radius_mm": round(r * MM, 2), "fit_mean_residual_mm": round(rms * MM, 3),
        "bone_pivot_error_mm": round(float(np.linalg.norm(bones[s] - c)) * MM, 2),
        "bone_offset_xyz_mm": [round(float(v) * MM, 2) for v in (bones[s] - c)],
    }

# region labels relative to the eye midpoint (Blender Z up, -Y forward after glTF import)
mid = (eyes["L"]["centre"] + eyes["R"]["centre"]) / 2


def region(P):
    c = P.mean(0) - mid
    side = "+X (char. left)" if c[0] > 0.004 else "-X (char. right)" if c[0] < -0.004 else "centre"
    z = c[2] * MM
    reg = "brow/forehead" if z > 12 else "eyes/lids" if z > -12 else "cheek/below eyes"
    return reg, side, round(float(z), 1)


skin_bvh_cache = {}


def skin_bvh(D):
    """BVH of the skin surface with displacement D applied (world)."""
    P = H["__basis"] + D
    polys = [list(p.vertices) for p in head.data.polygons if mats[p.material_index].startswith("Skin")]
    return BVHTree.FromPolygons([Vector(v) for v in P], polys)


# strand islands and roots (vertex nearest the rest skin)
def islands(o):
    n = len(o.data.vertices); parent = list(range(n))
    def f(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for e in o.data.edges:
        a, b = f(e.vertices[0]), f(e.vertices[1])
        if a != b: parent[a] = b
    return np.array([f(i) for i in range(n)])


rest_bvh = skin_bvh(np.zeros_like(H["__basis"]))
strands = {}
for nm, A, o in (("brows", B, brows), ("lashes", L, lashes)):
    isl = islands(o)
    P = A["__basis"]
    d = np.array([rest_bvh.find_nearest(Vector(p))[3] for p in P])
    roots = {}
    for i, (g, di) in enumerate(zip(isl, d)):
        if g not in roots or di < d[roots[g]]:
            roots[g] = i
    r = np.array(list(roots.values()))
    strands[nm] = {"roots": r, "rest_dist": d[r], "count": len(r)}


def evaluate(weights):
    DH = sum((H[k] * w for k, w in weights.items() if k in H), np.zeros_like(H["__basis"]))
    DB = sum((B[k] * w for k, w in weights.items() if k in B), np.zeros_like(B["__basis"]))
    DL = sum((L[k] * w for k, w in weights.items() if k in L), np.zeros_like(L["__basis"]))
    res = {}
    for nm, D, base in (("head", DH, H["__basis"]), ("brows", DB, B["__basis"]), ("lashes", DL, L["__basis"])):
        m = np.linalg.norm(D, axis=1)
        moved = m > 1e-4
        e = {"max_mm": round(float(m.max()) * MM, 2), "verts_moved": int(moved.sum())}
        if moved.any():
            e["region"], e["side"], e["height_mm"] = region(base[moved])
            wc = (base * m[:, None]).sum(0) / m.sum() - mid  # displacement-weighted centre
            pk = base[int(m.argmax())] - mid
            e["weighted_centre_xyz_mm"] = [round(float(v) * MM, 1) for v in wc]
            e["peak_vertex_xyz_mm"] = [round(float(v) * MM, 1) for v in pk]
            p999 = float(np.percentile(m[moved], 99.9))
            e["spike_ratio_max_over_p99_9"] = round(float(m.max()) / p999, 2) if p999 > 0 else None
        res[nm] = e
    # strand attachment: root-to-skin distance change after deformation
    bvh = skin_bvh(DH)
    for nm, A, D in (("brows", B, DB), ("lashes", L, DL)):
        s = strands[nm]
        P = A["__basis"][s["roots"]] + D[s["roots"]]
        d1 = np.array([bvh.find_nearest(Vector(p))[3] for p in P])
        ch = (d1 - s["rest_dist"]) * MM
        res[nm]["root_gap_change_mm"] = {"max": round(float(ch.max()), 3), "min": round(float(ch.min()), 3), "p99_abs": round(float(np.percentile(np.abs(ch), 99)), 3)}
        res[nm]["strands_lifted_over_0_5mm"] = int((ch > 0.5).sum())
    # penetration into the eyeballs (radius - 0.3 mm tolerance)
    pen = {}
    for s in ("L", "R"):
        c, r = eyes[s]["centre"], eyes[s]["radius"] - 0.0003
        sk = H["__basis"][skin_ids] + DH[skin_ids]
        la = L["__basis"] + DL
        pen[s] = {"skin_verts_inside": int((np.linalg.norm(sk - c, axis=1) < r).sum()), "lash_verts_inside": int((np.linalg.norm(la - c, axis=1) < r).sum())}
    res["eye_penetration"] = pen
    return res


results = {"keys": {}, "combos": {}, "eyes": {s: eyes[s]["report"] for s in eyes}, "strand_counts": {k: v["count"] for k, v in strands.items()},
           "materials": mats, "notes": "Eyeball spheres fitted to Eye_L / Eye_R material vertices only (corneas excluded; the GLB has no tearline mesh)."}
results["neutral"] = evaluate({})
for k in KEYS:
    if k.startswith("corr_"): continue
    results["keys"][k] = evaluate({k: 1.0})
COMBOS = {k: v for k, v in {
    "blink_both": {"blink_L": 1, "blink_R": 1},
    "left_wink_squint_R": {"blink_L": 1, "squint_R": 0.2},
    "sleepy_peak": {"blink_L": 0.55, "blink_R": 0.55, "lid_follow_L": 0.5, "lid_follow_R": 0.5},
    "blink_plus_lid_follow": {"blink_L": 1, "blink_R": 1, "lid_follow_L": 1, "lid_follow_R": 1},
    "wide_open": {"surprise_L": 1, "surprise_R": 1, "brow_raise_L": 0.4, "brow_raise_R": 0.4},
    "surprise_full_brows": {"surprise_L": 1, "surprise_R": 1, "brow_raise_L": 1, "brow_raise_R": 1},
    "squint_furrow": {"squint_L": 1, "squint_R": 1, "brow_furrow_L": 0.3, "brow_furrow_R": 0.3},
    "raise_and_furrow": {"brow_raise_L": 1, "brow_raise_R": 1, "brow_furrow_L": 1, "brow_furrow_R": 1},
    "blink_and_squint": {"blink_L": 1, "blink_R": 1, "squint_L": 1, "squint_R": 1},
    "all_keys_max_stress": {k: 1 for k in KEYS},
    "left_wink_with_cheek": {"blink_L": 1, "squint_R": 0.2, "cheek_raise_L": 0.6},
    "squint_with_cheek": {"squint_L": 1, "squint_R": 1, "brow_furrow_L": 0.3, "brow_furrow_R": 0.3, "cheek_raise_L": 0.7, "cheek_raise_R": 0.7},
    "blink_squint_cheek": {"blink_L": 1, "blink_R": 1, "squint_L": 1, "squint_R": 1, "cheek_raise_L": 1, "cheek_raise_R": 1},
    "blink_squint_cheek_corrected": {"blink_L": 1, "blink_R": 1, "squint_L": 1, "squint_R": 1, "cheek_raise_L": 1, "cheek_raise_R": 1, "corr_blink_squint_L": 1, "corr_blink_squint_R": 1},
    "cheek_raise_both": {"cheek_raise_L": 1, "cheek_raise_R": 1},
    "furrow_both": {"brow_furrow_L": 1, "brow_furrow_R": 1},
    "blink_and_squint_corrected": {"blink_L": 1, "blink_R": 1, "squint_L": 1, "squint_R": 1, "corr_blink_squint_L": 1, "corr_blink_squint_R": 1},
}.items() if all(x in KEYS or x in L for x in v)}
for n, w in COMBOS.items():
    results["combos"][n] = {"weights": w, **evaluate(w)}

with open(os.path.join(out, "qa_motion.json"), "w") as f:
    json.dump(results, f, indent=1, default=float)
print("QA_JSON_WRITTEN")

# ---------- gaze renders ----------
scene = bpy.context.scene
for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = eng; break
    except TypeError:
        pass
scene.render.resolution_x, scene.render.resolution_y = 1400, 700
scene.render.film_transparent = False
w = bpy.data.worlds.new("W"); scene.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[1].default_value = 0.25
try:
    scene.view_settings.view_transform = "AgX"
except TypeError:
    pass
# corneas: make them invisible for the render (EEVEE without raytracing shows transmission as black)
for m in bpy.data.materials:
    if m.name.startswith("Cornea") and m.use_nodes:
        p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        p.inputs["Alpha"].default_value = 0.0
        try:
            m.surface_render_method = "DITHERED"
        except Exception:
            pass
mv = Vector(tuple(mid))
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam")); scene.collection.objects.link(cam); scene.camera = cam
cam.data.lens = 85
cam.location = mv + Vector((0, -0.36, 0.0))
cam.rotation_euler = (math.radians(90), 0, 0)
for loc, e in (((0.3, -0.6, 0.3), 25), ((-0.4, -0.5, 0.1), 10)):
    lt = bpy.data.objects.new("L", bpy.data.lights.new("L", "AREA")); lt.data.energy = e; lt.data.size = 0.5
    lt.location = mv + Vector(loc); scene.collection.objects.link(lt)
    lt.rotation_euler = (mv - lt.location).to_track_quat("-Z", "Y").to_euler()

bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="POSE")
# about +X a negative angle tips the -Y gaze upward
GAZE = {"neutral": (0, 0), "left": (20, 0), "right": (-20, 0), "up": (0, -15), "down": (0, 15)}
eye_rest = {n: rig.data.bones[n].matrix_local.copy() for n in ("left_eye", "right_eye")}
renders = []
for g, (yaw, pitch) in GAZE.items():
    R = (Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(math.radians(pitch), 4, "X"))
    for n in ("left_eye", "right_eye"):
        pb = rig.pose.bones[n]; rest = eye_rest[n]
        hd = rest.to_translation()
        pb.matrix = Matrix.Translation(hd) @ R @ Matrix.Translation(-hd) @ rest
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(out, f"gaze_{g}.png")
    bpy.ops.render.render(write_still=True)
    renders.append(scene.render.filepath)
print("RENDERS", renders)
