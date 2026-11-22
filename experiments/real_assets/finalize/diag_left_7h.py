"""PRIVATE: Phase 2N.7H step 2 - re-diagnose the LEFT flap + tip spike on UNTOUCHED v5 (read-only).

    blender -b <v6_recon_00_checkpoint_start.blend> --python diag_left_7h.py -- <out.json>

Criterion (camera evidence, not area growth): a closed skin surface viewed from outside never shows its back side.
For jaw 0/25/50/75/100 %, smile+jaw and big-grin+jaw, rays are cast from the three left-corner cameras
(same as render_eyes.py cornerL_front/34/side). Every head face hit FIRST by a ray from its BACK side is a defect face.
Also records: per-vertex motion source (upper lip / jaw / mixed), visibility at rest, components, materials.
"""
import json, math, sys
import bpy, numpy as np
from mathutils import Vector

_a = sys.argv[sys.argv.index("--") + 1:]; out_p = _a[0]; OBN = _a[1] if len(_a) > 1 else "GNM_Head"
ob = bpy.data.objects[OBN]; me = ob.data
for o in bpy.data.objects:
    if o.type == "MESH" and o.name not in (OBN, "OralCavity"): o.hide_viewport = True; o.hide_render = True
mats = [m.name for m in me.materials]
kb = me.shape_keys.key_blocks
def K(n): a = np.empty(len(me.vertices) * 3); kb[n].data.foreach_get("co", a); return a.reshape(-1, 3)
B = K("Basis"); J = K("jaw_open") - B
rig = bpy.data.objects["GNM_Rig"]
mid = (rig.matrix_world @ rig.data.bones["left_eye"].head_local + rig.matrix_world @ rig.data.bones["right_eye"].head_local) / 2
tgt = mid + Vector((0.022, 0, -0.066))
CAMS = {"front": Vector((0.0, -0.11, 0.0)), "34": Vector((0.075, -0.085, 0.0)), "side": Vector((0.11, -0.035, 0.0))}
POSES = {"rest": {}, "jaw25": {"jaw_open": .25}, "jaw50": {"jaw_open": .5}, "jaw75": {"jaw_open": .75}, "jaw100": {"jaw_open": 1.0},
         "smile_jaw100": {"jaw_open": 1, "mouth_smile_L": .8, "mouth_smile_R": .8, "corr_jaw_smile_L": .8, "corr_jaw_smile_R": .8},
         "biggrin_jaw100": {"jaw_open": 1, "mouth_smile_L": 1, "mouth_smile_R": 1, "cheek_raise_L": .8, "cheek_raise_R": .8, "upper_lip_raise_L": .7,
                            "upper_lip_raise_R": .7, "lower_lip_depress_L": .6, "lower_lip_depress_R": .6, "corr_jaw_smile_L": 1, "corr_jaw_smile_R": 1}}
sc = bpy.context.scene; sc.render.resolution_x, sc.render.resolution_y = 1000, 700
cam = bpy.data.objects.new("C", bpy.data.cameras.new("C")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 85
back = {}; front_hits = {}; bcnt = {}
Mw = ob.matrix_world
for pn, w in POSES.items():
    for k in kb[1:]: k.value = w.get(k.name, 0.0)
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    for cn, off in CAMS.items():
        cam.location = tgt + off; cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler(); bpy.context.view_layer.update()
        tr, br, bl, tl = [cam.matrix_world @ v for v in cam.data.view_frame(scene=sc)]
        for py in range(0, 700, 4):
            for px in range(0, 1000, 4):
                u, v = px / 1000, py / 700; p = (tl + (tr - tl) * u) + ((bl + (br - bl) * u) - (tl + (tr - tl) * u)) * v
                d = (p - cam.location).normalized(); r = sc.ray_cast(dg, cam.location, d)
                if r[0] and r[4].name == OBN:
                    f = r[3]
                    if r[2].dot(d) > 0: back.setdefault(f, set()).add(pn); bcnt[(pn, f)] = bcnt.get((pn, f), 0) + 1
                    else: front_hits.setdefault(f, set()).add(pn)
for k in kb[1:]: k.value = 0.0
# keep only the LEFT mouth zone (x 5..32 mm from the midline, within 12 mm of the mouth line)
Mwn = np.array(Mw); W = (np.c_[B, np.ones(len(B))] @ Mwn.T)[:, :3] - np.array(mid)
def in_zone(f):
    c = W[list(me.polygons[f].vertices)].mean(0) * 1000
    return 5 < c[0] < 32 and -78 < c[2] < -52
defect = sorted(f for f in back if in_zone(f) and mats[me.polygons[f].material_index] == "Skin")
# components of the defect faces (edge-connected)
adjf = {}
ekey = {}
for p in me.polygons:
    for e in p.edge_keys: ekey.setdefault(e, []).append(p.index)
comp = {}; cid = 0
for f in defect:
    if f in comp: continue
    st = [f]; comp[f] = cid
    while st:
        g = st.pop()
        for e in me.polygons[g].edge_keys:
            for h in ekey[e]:
                if h in back and h in defect and h not in comp: comp[h] = cid; st.append(h)
    cid += 1
jm = np.linalg.norm(J, axis=1) * 1000
# upper lip motion ~ small jaw_open, lower ~ large; classify relative to the face's spread
rows = []
for f in defect:
    vs = list(me.polygons[f].vertices)
    rows.append({"face": f, "component": comp[f], "material": mats[me.polygons[f].material_index], "verts": vs,
                 "jaw_mm": [round(float(jm[v]), 1) for v in vs], "mixed_motion": bool(max(jm[vs]) - min(jm[vs]) > 3.0),
                 "backface_seen_in": sorted(back[f]), "frontface_seen_in": sorted(front_hits.get(f, [])),
                 "centre_mm": [round(float(x), 1) for x in W[vs].mean(0) * 1000]})
bf_pixels = {pn: sum(c for (q, f), c in bcnt.items() if q == pn and f in set(defect)) for pn in POSES}
print("BACKFACE_RAYS", json.dumps(bf_pixels))
json.dump({"criterion": "head face hit first from its back side by a left-corner camera ray", "backface_rays_per_pose": bf_pixels, "defect_faces": rows,
           "components": cid, "rest_visible_faces": sorted(f for f in front_hits if "rest" in front_hits[f] and in_zone(f))}, open(out_p, "w"), indent=1)
print("DEFECTS", len(defect), "components", cid)
for r in rows: print("F", r["face"], "c", r["component"], r["jaw_mm"], "mixed" if r["mixed_motion"] else "", r["backface_seen_in"], r["centre_mm"])
