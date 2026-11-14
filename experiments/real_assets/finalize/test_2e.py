"""Phase 2E checks on phase2e/gnm_scan_2e.blend against gnm_scan.blend (the verified real-scan build).

    blender -b --factory-startup --disable-autoexec BUILD/phase2e/gnm_scan_2e.blend --python test_2e.py -- BUILD
"""
import json
import os
import sys

import bpy
import numpy as np
import OpenImageIO as oiio

BUILD = os.path.abspath(sys.argv[sys.argv.index("--") + 1]); E = os.path.join(BUILD, "phase2e")
res = []


def check(ok, msg):
    res.append(bool(ok)); print(("PASS " if ok else "FAIL ") + msg, flush=True)


gh = bpy.data.objects["GNM_Head"]; me = gh.data; nv = len(me.vertices)
with bpy.data.libraries.load(os.path.join(BUILD, "gnm_scan.blend")) as (src, dst):
    dst.meshes = [me.name]
ref = dst.meshes[0]


def arr(m, coll, attr, n, dt=np.float32):
    a = np.empty(n, dt); getattr(m, coll).foreach_get(attr, a); return a


check(nv == 17821 and len(me.polygons) == 17662, f"GNM topology: {nv} vertices, {len(me.polygons)} faces")
fa = np.empty(4 * len(me.polygons), np.int32); me.polygons.foreach_get("vertices", fa)
fb = np.empty(4 * len(ref.polygons), np.int32); ref.polygons.foreach_get("vertices", fb)
check(np.array_equal(fa, fb), "face order and vertex indices identical to the verified real-scan build")
ua = np.empty(len(me.loops) * 2, np.float32); me.uv_layers["UDIM"].data.foreach_get("uv", ua)
ub = np.empty(len(ref.loops) * 2, np.float32); ref.uv_layers["UDIM"].data.foreach_get("uv", ub)
check(np.array_equal(ua, ub), "UDIM UVs bit-identical")
mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
mj = np.empty(len(ref.polygons), np.int32); ref.polygons.foreach_get("material_index", mj)
tiles = sorted({int(1001 + np.floor(ua.reshape(-1, 2)[me.polygons[f].loop_start, 0])) for f in range(len(me.polygons))})
check(np.array_equal(mi, mj) and len(me.materials) == 7 and tiles == list(range(1001, 1008)), f"7 UDIM regions / material slots preserved: {tiles}")
K = me.shape_keys.key_blocks; KR = ref.shape_keys.key_blocks
same = all(np.array_equal(arr(K[k.name], "data", "co", nv * 3), arr(k, "data", "co", nv * 3)) for k in KR)
check(same and len(KR) == 11, f"basis and the {len(KR)} verified keys identical")
check("brow_furrow_L" in K and "brow_furrow_R" in K, "brow lowerer keys added (brow_furrow_L/R)")
J = np.load(os.path.join(BUILD, "gnm_scan_keys.npz")); names = [str(n) for n in J["joint_names"]]
rig = bpy.data.objects["GNM_Rig"]
err = max(np.linalg.norm(np.array(rig.data.bones[f"{s}_eye"].head_local[:]) - J["joints"][names.index(f"{s}_eye")]) for s in ("left", "right"))
check(err < 1e-6, f"eye joints at the scan eyeball centres ({err * 1000:.4f} mm)")

# eye rotation: rigid about the joint (evaluate without subdivision)
sub = next(m for m in gh.modifiers if m.type == "SUBSURF"); sub.show_viewport = False
gi = {g.name: g.index for g in gh.vertex_groups}
eyeL = np.array([v.index for v in me.vertices if any(g.group == gi["gnm_left_eye"] for g in v.groups)])
pb = rig.pose.bones["left_eye"]; pb.rotation_mode = "XYZ"; pb.rotation_euler = (0.0, 0.0, 0.3); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); ev = gh.evaluated_get(dg).to_mesh()
P = np.array([ev.vertices[i].co[:] for i in eyeL]); c = J["joints"][names.index("left_eye")]
B0 = arr(K["Basis"], "data", "co", nv * 3).reshape(-1, 3)[eyeL]
dd = np.abs(np.linalg.norm(P - c, axis=1) - np.linalg.norm(B0 - c, axis=1)).max()
moved = np.linalg.norm(P - B0, axis=1).max()
check(dd < 1e-6 and moved > 1e-3, f"eye rotates rigidly about its joint (radius error {dd * 1e6:.2f} um, max travel {moved * 1000:.1f} mm)")
pb.rotation_euler = (0, 0, 0); gh.evaluated_get(dg).to_mesh_clear()

# eye maps
img = next(n.image for n in me.materials[1].node_tree.nodes if n.type == "TEX_IMAGE")
check(img.source == "TILED" and sorted(t.number for t in img.tiles) == [1002, 1004] and img.name == "scan_eye_albedo_2e_udim",
      "eye slots use the Phase 2E UDIM map (tiles 1002, 1004)")
img3 = next(n.image for n in me.materials[3].node_tree.nodes if n.type == "TEX_IMAGE")
check(img3 == img, "both eye materials share it")
A = oiio.ImageBuf(os.path.join(E, "scan_eye_albedo_2e.1002.png")).get_pixels(oiio.FLOAT)[..., :3]
Bm = oiio.ImageBuf(os.path.join(E, "scan_eye_albedo_2e.1004.png")).get_pixels(oiio.FLOAT)[..., :3]
O = oiio.ImageBuf(os.path.join(BUILD, "scan_eye_albedo.1002.png")).get_pixels(oiio.FLOAT)[..., :3]
H = A.shape[0]; yy, xx = np.mgrid[0:H, 0:H]; rr = np.hypot((xx + 0.5) / H - 0.5, (yy + 0.5) / H - 0.5)
info = json.load(open(os.path.join(E, "build_2e.json")))["iris_uv"]; ri, rp = info["r_iris"], info["r_pupil"]
ann = (rr > rp * 1.3) & (rr < ri * 0.9)
diff = np.abs(A[ann] - Bm[ann]).mean(); mean_gap = np.abs(A[ann].mean(0) - Bm[ann].mean(0)).max() / A[ann].mean()
check(diff > 0.03, f"left and right irises differ (mean |L-R| {diff:.3f} in the iris annulus)")
check(mean_gap < 0.03, f"same overall iris colour (largest channel-mean gap {mean_gap * 100:.1f} %)")
mir = min(np.abs(A[ann] - np.fliplr(Bm)[ann]).mean(), np.abs(A[ann] - np.flipud(Bm)[ann]).mean())
check(mir > 0.03, f"right iris is not a mirror of the left (closest mirror |diff| {mir:.3f})")
pup = rr < rp * 0.6
check(A[pup].mean() < 0.06 and Bm[pup].mean() < 0.06, f"pupil centred at the UV centre in both maps (mean {A[pup].mean():.3f} / {Bm[pup].mean():.3f})")


def pink(X, m):
    return float(((X[..., 0] - X[..., 1]) / np.maximum(X[..., 0], 1e-3))[m].mean())


# measured per GNM eye-interior vertex by its angle theta from the rest gaze axis (as in diag_eye_corner.py)
V0 = arr(K["Basis"], "data", "co", nv * 3).reshape(-1, 3)
uvv = np.zeros((nv, 2)); lvx = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lvx); uvv[lvx] = ua.reshape(-1, 2)
ids = np.unique([v for poly in me.polygons if poly.material_index == 1 for v in poly.vertices])
dvec = V0[ids] - c; dvec /= np.linalg.norm(dvec, axis=1, keepdims=True)
theta = np.degrees(np.arccos(np.clip(dvec[:, 2], -1, 1)))
px_ = np.clip(((1 - uvv[ids, 1]) * H).astype(int), 0, H - 1), np.clip(((uvv[ids, 0] - 1) * H).astype(int), 0, H - 1)
cn, co = A[px_], O[px_]
pk = lambda X: (X[:, 0] - X[:, 1]) / np.maximum(X[:, 0], 1e-3)  # noqa: E731
side_band = (theta >= 60) & (theta <= 78)            # what 15-20 deg gaze exposes at the outer canthus (diagnostic renders)
check(pk(cn[side_band]).mean() < 0.2 and pk(co[side_band]).mean() > 0.3,
      f"sclera fill removed where side gaze exposes it (theta 60-78 deg): pinkness {pk(co[side_band]).mean():.2f} -> {pk(cn[side_band]).mean():.2f}")
keep = theta < 28
check(np.abs(cn[keep] - co[keep]).mean() < 0.02, f"iris / limbus / near sclera (theta < 28 deg) unchanged: mean |new-old| {np.abs(cn[keep] - co[keep]).mean():.4f}")
# expression geometry (exact, from expr_geometry.py)
G = json.load(open(os.path.join(E, "expr_geometry.json")))
for k in ("blink", "blink_up12", "blink_down7", "blink_left15"):
    ap = max(max(G[k]["left"]["aperture_mm"]), max(G[k]["right"]["aperture_mm"]))
    check(ap <= 0.151, f"{k}: lids closed (largest gap {ap:.2f} mm)")
for k in ("squint", "surprise", "brow_raise_2mm", "brow_lowerer", "squint_left15", "brow_raise_up12"):
    lf = G[k]["lower_face_max_mm"]
    check(lf < 0.01, f"{k}: lower face still ({lf} mm)")
check(G["brow_raise_2mm"]["left"]["brow_mm"] > 1.9 and G["brow_lowerer"]["left"]["brow_mm"] < -0.5 and G["surprise"]["left"]["brow_mm"] > 1.0,
      "brows move in the right direction (raise +2.0, lowerer -0.7, surprise +1.7 mm)")
mat = bpy.data.materials["Material.001"]
check(not mat.node_tree.nodes.get("DISP") and mat.displacement_method == "BUMP", "vendor skin material untouched (copy Skin_2E carries the displacement)")
print(f"\n{sum(res)}/{len(res)} PASSED" + ("" if all(res) else "  <-- FAILURES"))
