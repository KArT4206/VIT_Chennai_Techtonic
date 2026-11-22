"""WS1 extended depth probe (Blender side): pose-by-pose projections of a pupil placed at many depths, plus the
detector-free geometric prediction of where the PAINTED pupil is.

    blender -b --factory-startup <bundle>/scene.blend -P research/depth_probe_extended.py -- <out.json> [--dmin 12] [--dmax 20] [--step 0.05]

For the 11 fit poses (ring k=0..9 + reset, ids 0..10) and the 14 held-out poses (ids 20..33, see
render_ablation.heldout_poses), for each eye:
  * projection_by_depth[d]: unrefracted image projection of c + q @ (axis * d) for d in [dmin, dmax] step `step` (mm),
    where c = eye pivot, q = the wrapper's own rotation for that gaze, axis = calibrated primary axis;
  * wrapper: the wrapper's own pupil_center_2D (refracted) and pupil_center_2D_unrefracted;
  * painted_surface: the 3-D point ON THE EYEBALL MESH under the texture's painted-pupil UV centroid (found by
    barycentric lookup in the evaluated, posed mesh) and its projection. This uses only mesh + texture, no detector.
Mesh/UV inspection (reset pose, axis = eye centre -> wrapper pupil): painted-pupil UV centroid and radius per eye-material texture at several linear
thresholds, the UV disc centre the wrapper assumes, and the depth/lateral position of that surface point.
"""
import json, math, sys
import bpy
import numpy as np
from mathutils import Vector
from mathutils.geometry import barycentric_transform, intersect_point_tri_2d

a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]
dmin = float(a[a.index("--dmin") + 1]) if "--dmin" in a else 12.0
dmax = float(a[a.index("--dmax") + 1]) if "--dmax" in a else 20.0
step = float(a[a.index("--step") + 1]) if "--step" in a else 0.05
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper")); import eyes  # noqa: E402
EYEOB = {"L": "Realtime Eyeball Left", "R": "Realtime Eyeball Right"}


def blob_at(mask, y, x):
    """4-connected component of `mask` containing (y, x) (Blender's Python has no scipy)."""
    seen = np.zeros_like(mask); st = [(y, x)]; seen[y, x] = True
    while st:
        cy, cx = st.pop()
        for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
            if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True; st.append((ny, nx))
    return seen


def texture_centroids(mat_name):
    t = bpy.data.materials[mat_name].node_tree
    img = next(n for n in t.nodes if n.type == "TEX_IMAGE" and n.image and "Diffuse" in n.image.name).image
    w, h = img.size; px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3].mean(2)
    cy, cx, r = int(.4943 * h), int(.5008 * w), int(.12 * w); sub = px[cy - r:cy + r, cx - r:cx + r]
    res = {}
    for T in (0.045, 0.05, 0.06, 0.08, 0.1):
        ys, xs = np.nonzero(sub < T)
        # keep only the connected blob around the centre (exclude dark specks in the iris)
        if sub[r, r] < T:
            ys, xs = np.nonzero(blob_at(sub < T, r, r))
        res[str(T)] = dict(u=(cx - r + xs.mean() + .5) / w, v=(cy - r + ys.mean() + .5) / h,
                           r_uv=math.sqrt(len(xs) / math.pi) / w, n_texels=int(len(xs)))
    return img.name, [w, h], res


def surface_point(side, u, v):
    """World point on the posed eyeball mesh whose UV is (u, v) (image-row convention converted to Blender UV)."""
    ob = bpy.data.objects[EYEOB[side]].evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ob.data; uvl = me.uv_layers.active.data; M = ob.matrix_world
    me.calc_loop_triangles()
    target = Vector((u, v))
    best = None
    for tri in me.loop_triangles:
        uvs = [uvl[li].uv.copy() for li in tri.loops]
        if intersect_point_tri_2d(target, *uvs):
            co = [me.vertices[vi].co for vi in tri.vertices]
            p = barycentric_transform(target.to_3d(), *(x.to_3d() for x in uvs), *co)
            c = M @ p; c_cam = (c - bpy.context.scene.camera.matrix_world.translation).length
            if best is None or c_cam < best[1]:      # front-most hit (UV islands can overlap at the back)
                best = (c, c_cam)
    return best[0] if best else None


R = dict(params=dict(dmin=dmin, dmax=dmax, step=step), blender=bpy.app.version_string)
mats = {s: bpy.data.objects[EYEOB[s]].material_slots[0].material.name for s in "LR"}
R["eye_materials"] = mats
R["texture"] = {}
for s in "LR":
    name, size, cents = texture_centroids(mats[s]); R["texture"][s] = dict(image=name, size=size, dark_blob_centroid=cents)
R["wrapper_assumed_pupil_uv"] = [0.5008, 0.4943]
# bpy image.pixels is stored bottom-up, so a row index into it divided by the height IS Blender's UV v.
T_USE = "0.05"

eyes.reset()
for s in "LR":
    c = R["texture"][s]["dark_blob_centroid"][T_USE]
    p = surface_point(s, c["u"], c["v"]); ce = eyes._eye_centre(s)
    q = eyes.mesh_pupils()[s]; ax = (q - ce).normalized()   # current (reset-pose) gaze axis through the wrapper pupil
    R.setdefault("reset_pose", {})[s] = dict(
        wrapper_pupil_depth_mm=(q - ce).length * 1000,
        painted_surface_depth_along_axis_mm=(p - ce).dot(ax) * 1000 if p else None,
        painted_surface_dist_from_centre_mm=(p - ce).length * 1000 if p else None,
        painted_surface_lateral_offset_from_axis_mm=((p - ce) - ax * (p - ce).dot(ax)).length * 1000 if p else None,
        painted_surface_lateral_offset_world_mm=[round(x * 1000, 4) for x in ((p - ce) - ax * (p - ce).dot(ax))] if p else None,
        wrapper_pupil_minus_painted_world_mm=[round(x * 1000, 4) for x in (q - p)] if p else None)


def heldout():
    out = []
    for k in range(10):
        th = 2 * math.pi * k / 10 + math.pi / 10
        out.append((20 + k, 0.5 * math.sin(th), 0.5 * math.cos(th)))
    for j, (h, v) in enumerate(((0.7, 0.7), (0.7, -0.7), (-0.7, -0.7), (-0.7, 0.7))):
        out.append((30 + j, h, v))
    return out


poses = [(k, h, v) for k, _, h, v in eyes.sequence_inputs()] + [(10, 0.0, 0.0)] + heldout()
depths = [round(dmin + i * step, 4) for i in range(int(round((dmax - dmin) / step)) + 1)]
R["depths_mm"] = depths
R["poses"] = {}
for k, h, v in poses:
    eyes.move(h, v); st = eyes.state(); rec = dict(input=[h, v], set="fit" if k <= 10 else "heldout")
    for s in "LR":
        ce = eyes._eye_centre(s); q = eyes._world_rotation(s, eyes.target_point(h, v)); ax = eyes._state["axis_" + s]
        rec[s] = dict(proj=[eyes._project(ce + q @ (ax * d / 1000)) for d in depths],
                      wrapper_2D=st[f"pupil_center_2D_{s}"], wrapper_2D_unrefracted=st[f"pupil_center_2D_unrefracted_{s}"])
        c = R["texture"][s]["dark_blob_centroid"][T_USE]; p = surface_point(s, c["u"], c["v"])
        rec[s]["painted_surface_2D"] = eyes._project(p) if p else None
    R["poses"][f"{k:02d}"] = rec
eyes.reset()
json.dump(R, open(out, "w"))
print("DEPTH_PROBE_DONE", len(poses), "poses", len(depths), "depths", flush=True)
