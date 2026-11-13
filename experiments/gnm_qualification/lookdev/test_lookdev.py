"""Tests for the GNM look-development scene. Exit code 0 only if all pass.

    blender -b --factory-startup gnm_lookdev_strands.blend --python test_lookdev.py -- ../build/gnm_head_neutral.npz ../build/gnm_keys.npz
"""

import os
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import gnm_engine  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg, flush=True)
    if not ok:
        FAILS.append(msg)


ref_npz, keys_npz = sys.argv[sys.argv.index("--") + 1:]
ref = np.load(ref_npz)
sc = bpy.context.scene
ob = bpy.data.objects["GNM_Head"]; me = ob.data

# ---- geometry / UV / regions unchanged
basis = np.empty(len(me.vertices) * 3, np.float32); me.shape_keys.key_blocks["Basis"].data.foreach_get("co", basis)
check(np.abs(basis.reshape(-1, 3) - ref["vertices"]).max() == 0.0, "GNM vertex positions unchanged (bit-identical)")
loops = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", loops)
check(len(me.vertices) == 17821 and len(me.polygons) == 17662 and np.array_equal(loops.reshape(-1, 4), ref["quads"]),
      "vertex count, face count, face order and corners unchanged")
uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers["UDIM"].data.foreach_get("uv", uv)
check(np.abs(uv.reshape(-1, 4, 2) - ref["quad_uvs_udim"]).max() == 0.0, "UDIM UVs unchanged (bit-identical)")
mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
check(np.array_equal(mi + 1001, ref["quad_udim_tiles"].astype(int)) and len(me.materials) == 7, "7 UDIM regions keep their material slots")

# ---- controls still exact
G = gnm_engine.GNMRig(keys_npz)
saved = {}
for idb in (G.rig, me.shape_keys):
    saved[idb] = idb.animation_data.action if idb.animation_data else None
    if idb.animation_data:
        idb.animation_data.action = None
errs = G.verify_against_gnm()
check(max(errs) < 1e-6, f"eye rig + shape keys still reproduce GNM ({max(errs):.1e} m)")
check(bpy.data.actions.get(gnm_engine.ACTION_RIG) is not None and bpy.data.actions.get(gnm_engine.ACTION_KEYS) is not None,
      "Timeline actions present")

# ---- texture set
imgs = {i.name: i for i in bpy.data.images}
for name, space, tiles in (("GNM_albedo", "sRGB", [1001, 1002, 1004]), ("GNM_normal", "Non-Color", [1001, 1002, 1004]),
                           ("GNM_roughness", "Non-Color", [1001])):
    im = imgs.get(name)
    check(im is not None and im.source == "TILED" and sorted(t.number for t in im.tiles) == tiles and im.colorspace_settings.name == space,
          f"{name}: UDIM tiles {tiles}, colour space {space}")
tex = os.path.join(HERE, "textures")
import OpenImageIO as oiio  # noqa: E402  (bundled with Blender)
def rd(p):
    i = oiio.ImageInput.open(p); s = i.spec(); a = i.read_image(0, 0, 0, 3, "float"); i.close(); return a, s
sa, ss = rd(os.path.join(tex, "skin_albedo.1001.png")); check(ss.width == 4096, f"skin maps 4096^2 ({ss.width})")
la, ls = rd(os.path.join(tex, "eye_albedo.1002.png")); ra, rs = rd(os.path.join(tex, "eye_albedo.1004.png"))
c = slice(700, 1350)
diff = float(np.abs(la[c, c] - ra[c, c]).mean() * 255)
check(ls.width == 2048 and diff > 2.0, f"two distinct irises at 2048^2 (mean |L-R| {diff:.2f}/255 in the iris area)")

# ---- strands
hair, brows, lashes = (bpy.data.objects.get(n) for n in ("GNM_Hair", "GNM_Brows", "GNM_Lashes"))
check(hair and len(hair.data.curves) >= 50000, f"hair strands ({len(hair.data.curves) if hair else 0})")
check(brows and len(brows.data.curves) >= 1000, f"eyebrow strands ({len(brows.data.curves) if brows else 0})")
check(lashes and len(lashes.data.curves) >= 400, f"eyelash strands ({len(lashes.data.curves) if lashes else 0})")
check(brows.data.surface == ob and brows.data.surface_uv_map == "UDIM" and any(m.type == "NODES" for m in brows.modifiers),
      "GNM_Brows attached to GNM_Head (surface UV + Deform Curves on Surface)")
# Lashes: surface deformation only translated them (closed-lid lashes pointed up), so they use a lid hinge
# driven from blink/lid_follow with GNM's measured margin-rotation coefficients (REPORT D).
hinge = lashes.modifiers.get("LidHinge")
nd = len([d for d in (lashes.animation_data.drivers if lashes.animation_data else []) if "LidHinge" in d.data_path])
check(hinge is not None and nd == 4, f"GNM_Lashes use the GNM-driven lid hinge ({nd} drivers)")


def evaluated_points(o):
    dg = bpy.context.evaluated_depsgraph_get()
    return np.array([v.vector for v in o.evaluated_get(dg).data.position_data])


def eye_volume_bvh():
    """BVH of the evaluated eye exterior shells (closed) for point-in-volume parity tests."""
    dg = bpy.context.evaluated_depsgraph_get()
    em = ob.evaluated_get(dg).to_mesh()
    verts = [ob.matrix_world @ v.co for v in em.vertices]
    polys = [list(p.vertices) for p in em.polygons if p.material_index in (2, 4)]
    ob.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def inside(bvh, p):
    n, o, d = 0, Vector(p), Vector((0.3, 0.2, 0.93)).normalized()
    while True:
        hit = bvh.ray_cast(o, d)
        if hit[0] is None:
            return n % 2 == 1
        n += 1; o = hit[0] + d * 1e-6


# lashes follow the blink and never enter the eye
G.set_keys(); bpy.context.view_layer.update()
p_open = evaluated_points(lashes)
G.set_keys(blink_L=1.0, blink_R=1.0); bpy.context.view_layer.update()
p_closed = evaluated_points(lashes)
roots_move = np.linalg.norm(p_closed.reshape(-1, 5, 3)[:, 0] - p_open.reshape(-1, 5, 3)[:, 0], axis=1) * 1000
upper = roots_move > 1.0
check(upper.sum() >= 250, f"upper-lash roots move with the blink ({upper.sum()} lashes moved > 1 mm, max {roots_move.max():.1f} mm)")
worst, worst_root = 0, 0.0
for w, (yaw, pitch) in ((dict(), (0, 0)), (dict(blink_L=1.0, blink_R=1.0), (0, 0)), (dict(blink_L=0.5, blink_R=0.5), (0, 0)),
                        (dict(lid_follow_L=1.2, lid_follow_R=1.2), (0, 12)), (dict(lid_follow_L=-0.7, lid_follow_R=-0.7), (0, -7))):
    G.set_keys(**w)
    t = G.target(yaw, pitch)
    for side in ("left", "right"):
        G.set_eye_quat(side, G.eye_rotation(side, t))
    bpy.context.view_layer.update()
    bvh = eye_volume_bvh()
    pts = evaluated_points(lashes)
    shafts = [i for i in range(len(pts)) if i % 5 and inside(bvh, pts[i])]
    roots = [bvh.find_nearest(Vector(pts[i]))[3] * 1000 for i in range(0, len(pts), 5) if inside(bvh, pts[i])]
    worst = max(worst, len(shafts)); worst_root = max([worst_root] + roots)
check(worst == 0, f"no eyelash shaft point inside the eyeball/cornea in open, blink, half blink, up and down gaze ({worst})")
check(worst_root <= 0.31, f"lash roots touch the eye only as much as GNM's own lid skin does (<= 0.31 mm, Phase 2B): {worst_root:.3f} mm")
G.set_keys(); bpy.context.view_layer.update()
b0 = evaluated_points(brows)[:, 2].mean()
G.set_keys(brow_raise_L=1.0, brow_raise_R=1.0); bpy.context.view_layer.update()
b1 = evaluated_points(brows)[:, 2].mean()
check((b1 - b0) * 1000 > 1.0, f"eyebrows follow brow_raise ({(b1 - b0) * 1000:.2f} mm)")
G.set_keys()
for idb, act in saved.items():
    if act:
        idb.animation_data.action = act

# ---- render reproducibility
sc.cycles.samples = 8; sc.render.resolution_x = sc.render.resolution_y = 192; sc.frame_set(1)
px = []
for k in range(2):
    p = os.path.join(tempfile.gettempdir(), f"lookdev_repro_{os.getpid()}_{k}.png")
    sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(p); px.append(np.array(im.pixels[:])); bpy.data.images.remove(im); os.remove(p)
d = np.abs(px[0] - px[1]).reshape(-1, 4)[:, :3]
ndiff = int((d.max(1) > 0).sum()); frac = ndiff / len(d)
# GPU float nondeterminism (random-walk SSS) flips a few values across 8-bit rounding boundaries
check(d.max() <= 1.0 / 255 + 1e-6 and frac < 0.001,
      f"render reproducible within one 8-bit step on < 0.1 % of pixels (max {d.max()*255:.2f}/255, {ndiff} px = {frac*100:.3f} %)")
print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' CHECK(S) FAILED'}")
sys.exit(1 if FAILS else 0)
