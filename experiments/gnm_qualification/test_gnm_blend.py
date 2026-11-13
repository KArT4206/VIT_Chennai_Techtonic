"""Blender-level tests of gnm_expression_test.blend. Exit code 0 only if all pass.

    blender -b --factory-startup gnm_expression_test.blend --python test_gnm_blend.py -- build/gnm_head_neutral.npz build/gnm_keys.npz
"""

import os
import sys
import tempfile

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gnm_engine  # noqa: E402

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg, flush=True)
    if not ok:
        FAILS.append(msg)


a = sys.argv[sys.argv.index("--") + 1:]
ref = np.load(a[0])
check(bpy.data.filepath.endswith("gnm_expression_test.blend"), f"scene loads ({os.path.basename(bpy.data.filepath)})")
ob = bpy.data.objects.get("GNM_Head"); rig = bpy.data.objects.get("GNM_Rig")
check(ob is not None and rig is not None, "GNM_Head and GNM_Rig present")
me = ob.data

# topology / UV preservation (basis shape key == GNM template)
basis = np.empty(len(me.vertices) * 3, np.float32); me.shape_keys.key_blocks["Basis"].data.foreach_get("co", basis)
check(len(me.vertices) == 17821 and np.abs(basis.reshape(-1, 3) - ref["vertices"]).max() == 0.0, "basis positions bit-identical to GNM template")
loops = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", loops)
check(len(me.polygons) == 17662 and np.array_equal(loops.reshape(-1, 4), ref["quads"]), "face order and corner order identical to GNM quads")
uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers["UDIM"].data.foreach_get("uv", uv)
check(np.abs(uv.reshape(-1, 4, 2) - ref["quad_uvs_udim"]).max() == 0.0, "UDIM UVs bit-identical")
mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
check(np.array_equal(mi + 1001, ref["quad_udim_tiles"].astype(int)), "material slot per face == UDIM tile")

# eye pivots
for side in ("left", "right"):
    j = list(ref["joint_names"]).index(f"{side}_eye")
    head = np.array(rig.data.bones[f"{side}_eye"].head_local)
    err = np.linalg.norm(head - ref["joint_positions"][j]) * 1000
    check(err < 1e-3, f"{side}_eye bone head at GNM joint ({err:.5f} mm)")

# shape keys + armature reproduce GNM (actions detached for direct posing)
G = gnm_engine.GNMRig(a[1])
saved = {}
for idb in (G.rig, me.shape_keys):
    saved[idb] = idb.animation_data.action if idb.animation_data else None
    if idb.animation_data:
        idb.animation_data.action = None
errs = G.verify_against_gnm()
check(max(errs) < 1e-6, f"shape keys + eye bones reproduce GNM on {len(errs)} reference poses (max {max(errs):.1e} m)")
check(set(G.key_names) <= set(me.shape_keys.key_blocks.keys()), f"{len(G.key_names)} control shape keys present")
for idb, act in saved.items():
    if act:
        idb.animation_data.action = act

# Timeline
ar = bpy.data.actions.get(gnm_engine.ACTION_RIG); ak = bpy.data.actions.get(gnm_engine.ACTION_KEYS)
check(ar is not None and ak is not None, f"actions {gnm_engine.ACTION_RIG} and _ShapeKeys exist")
check(rig.animation_data.action == ar and me.shape_keys.animation_data.action == ak, "both actions active")
sc = bpy.context.scene
check((sc.frame_start, sc.frame_end, sc.render.fps) == (1, 288, 24), f"Timeline 1-288 @ 24 fps ({sc.frame_start}-{sc.frame_end} @ {sc.render.fps})")
fck = gnm_engine.fcurves(ak)
vals = {fc.data_path: [fc.evaluate(f) for f in range(1, 289)] for fc in fck}
bl = vals['key_blocks["blink_L"].value']; br = vals['key_blocks["blink_R"].value']
check(max(bl) >= 0.999 and max(br) >= 0.999, "Timeline contains a complete blink (both eyes)")
check(any(0.25 < v < 0.6 for v in bl), "Timeline contains a partial blink")
lf = vals['key_blocks["lid_follow_L"].value']
check(max(lf) > 1.0 and min(lf) < -0.6, f"Timeline contains upward and downward gaze with lids following (lid_follow {min(lf):.2f}..{max(lf):.2f})")
check(abs(bl[0]) < 1e-6 and abs(bl[-1]) < 1e-6 and abs(lf[0]) < 0.05 and abs(lf[-1]) < 0.05, "starts and ends at neutral")
check(len(gnm_engine.fcurves(ar)) == 8 and min(len(fc.keyframe_points) for fc in gnm_engine.fcurves(ar)) == 288, "eye bones keyed every frame")

# render reproducibility (same frame, same settings, twice)
sc.cycles.samples = 16
sc.render.resolution_x = sc.render.resolution_y = 256
sc.frame_set(64)
imgs = []
for k in range(2):
    p = os.path.join(tempfile.gettempdir(), f"gnm_repro_{os.getpid()}_{k}.png")
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(p); imgs.append(np.array(im.pixels[:])); bpy.data.images.remove(im); os.remove(p)
check(np.array_equal(imgs[0], imgs[1]), f"render is reproducible (max pixel diff {np.abs(imgs[0] - imgs[1]).max():.2e})")

print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' CHECK(S) FAILED'}")
sys.exit(1 if FAILS else 0)
