"""Measure where the scan eyeball's painted pupil really is, vs the wrapper's pupil model.

    blender -b --factory-startup <bundle>/scene.blend -P research/pupil_geometry_probe.py -- <out.json>

Reports: wrapper pupil depth from the eye centre; eyeball-mesh depth (along the primary axis) of vertices whose UV
falls in the pupil / iris / sclera rings; dark-texel centroids of the eyeball texture at several linear thresholds;
and, for the 11 poses (10 ring + reset), the unrefracted image projection of a pupil placed at several depths
(used to fit the depth that best explains the image-detected pupils).
"""
import json, math, sys
import bpy
import numpy as np
out = sys.argv[sys.argv.index("--") + 1:][0]
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper")); import eyes  # noqa: E402
eyes.reset(); R = {}
for s, ob in (("L", "Realtime Eyeball Left"), ("R", "Realtime Eyeball Right")):
    c = eyes._eye_centre(s); ax = eyes._state["axis_" + s]
    R[f"wrapper_pupil_depth_mm_{s}"] = round((eyes.mesh_pupils()[s] - c).length * 1000, 3)
    e = bpy.data.objects[ob].evaluated_get(bpy.context.evaluated_depsgraph_get()); M = e.matrix_world; me = e.data; uv = me.uv_layers.active.data
    acc = {}
    for poly in me.polygons:
        for li in poly.loop_indices:
            u, v = uv[li].uv; r = math.hypot(u - 0.5008, v - 0.4943); d = ((M @ me.vertices[me.loops[li].vertex_index].co) - c).dot(ax) * 1000
            for lo, hi, k in ((0, .034, "pupil"), (.034, .112, "iris"), (.13, .2, "sclera")):
                if lo <= r < hi: acc.setdefault(k, []).append(d)
    R[f"mesh_depth_mm_{s}"] = {k: [round(min(v), 3), round(sum(v) / len(v), 3), round(max(v), 3)] for k, v in acc.items()}
t = bpy.data.materials["Realtime Eyeball Left"].node_tree
img = next(n for n in t.nodes if n.type == "TEX_IMAGE" and n.image and "Diffuse" in n.image.name).image
w, h = img.size; a = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)[..., :3].mean(2)
cy, cx, r = int(.4943 * h), int(.5008 * w), int(.12 * w); sub = a[cy - r:cy + r, cx - r:cx + r]
R["texture_dark_centroid_uv"] = {}
for T in (.05, .1, .3):
    ys, xs = np.nonzero(sub < T)
    R["texture_dark_centroid_uv"][str(T)] = [round((cx - r + xs.mean() + .5) / w, 5), round((cy - r + ys.mean() + .5) / h, 5), round(math.sqrt(len(xs) / math.pi) / w, 4)]
proj = {}
for k, _, hh, vv in list(eyes.sequence_inputs()) + [(10, None, 0.0, 0.0)]:
    eyes.move(hh, vv)
    for s in "LR":
        c = eyes._eye_centre(s); q = eyes._world_rotation(s, eyes.target_point(hh, vv)); ax = eyes._state["axis_" + s]
        proj[f"{k:02d}{s}"] = {str(d): eyes._project(c + q @ (ax * d / 1000)) for d in (14.19, 15.0, 15.5, 15.8, 16.0, 16.3, 16.6, 17.0)}
R["projection_by_depth_mm"] = proj
eyes.reset(); json.dump(R, open(out, "w"), indent=1); print("PROBE_DONE", flush=True)
