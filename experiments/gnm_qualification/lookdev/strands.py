"""Strand hair, eyebrows and eyelashes grown on the GNM head (no MakeHuman meshes copied across).

    blender -b --factory-startup gnm_lookdev.blend --python strands.py -- OUT_BLEND

All three are real Blender Curves. Brows and lashes are attached to GNM_Head by UV (UDIM 1001
skin tile, unique) and deformed with "Deform Curves on Surface", so they follow GNM's blink, lid and
brow shape keys and the eye rig without any extra controls. GNM geometry is not modified.

hair    roots on GNM skin outside GNM's face mask (hockey_mask), ears and neck, above a hairline
        taken from the production generator (tools/hair_strands.below_hairline), thinning out over
        6 mm; shape, combing, clumps and the melanin hair shader reuse the production generator
        (tools/hair_strands.grow / hair_material). No hair cap: no cap edge can show.
brows   roots on GNM left/right brow regions, accepted by a brow profile (thick medially 5 mm,
        3 mm at the tail, faded ends); growth up-and-out medially, out-and-slightly-down laterally,
        12 deg off the skin; 7-10 mm.
lashes  roots on the skin boundary loop that rims each eye opening; upper 120 / lower 60 per eye;
        length 9 mm centre -> 5 mm corners (lower 5 -> 3 mm), forward with a 45 deg upward curl
        (upper) or down (lower).
Seeds are fixed: rebuilding gives identical strands.
"""

import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import hair_strands  # noqa: E402  (production generator, MIT, this project)

out_blend = sys.argv[sys.argv.index("--") + 1]
rng = np.random.default_rng(2026)
sc = bpy.context.scene
ob = bpy.data.objects["GNM_Head"]; rig = bpy.data.objects["GNM_Rig"]
me = ob.data
MW = np.array(ob.matrix_world)

# ---- template (basis) surface, skin faces only, triangulated, in world space
co = np.empty(len(me.vertices) * 3, np.float32); me.shape_keys.key_blocks["Basis"].data.foreach_get("co", co)
Vl = co.reshape(-1, 3).astype(np.float64)
Vw = (MW[:3, :3] @ Vl.T).T + MW[:3, 3]
uvl = me.uv_layers["UDIM"].data
mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
gi = {g.name: g.index for g in ob.vertex_groups}
vgroups = [set(g.group for g in v.groups) for v in me.vertices]
def vmask(name):
    return np.array([gi[f"gnm_{name}"] in s for s in vgroups])
tri_v, tri_uv = [], []
for p in me.polygons:
    if mi[p.index] != 0:
        continue
    vs = list(p.vertices); ls = list(p.loop_indices)
    for a, b in ((0, 1), (0, 2) if False else (1, 2), ):
        pass
    for t in ((0, 1, 2), (0, 2, 3)):
        tri_v.append([vs[k] for k in t]); tri_uv.append([tuple(uvl[ls[k]].uv) for k in t])
tri_v = np.array(tri_v); tri_uv = np.array(tri_uv)
A, B, C = Vw[tri_v[:, 0]], Vw[tri_v[:, 1]], Vw[tri_v[:, 2]]
tri_n = np.cross(B - A, C - A); tri_area = 0.5 * np.linalg.norm(tri_n, axis=1); tri_n /= np.maximum(2 * tri_area[:, None], 1e-12)
# vertex normals (smooth), world
vn = np.zeros_like(Vw)
for k in range(3):
    np.add.at(vn, tri_v[:, k], tri_n * tri_area[:, None])
vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)

eyeL = MW[:3, :3] @ np.array(rig.data.bones["left_eye"].head_local) + MW[:3, 3]
eyeR = MW[:3, :3] @ np.array(rig.data.bones["right_eye"].head_local) + MW[:3, 3]
eye_mid = (eyeL + eyeR) / 2
head_centre = np.array([eye_mid[0], Vw[:, 1].mean() + 0.0, eye_mid[2] + 0.02])
head_centre[1] = eye_mid[1] + 0.085                      # skull centre ~8.5 cm behind the eyes
FWD = np.array([0.0, -1.0, 0.0]); UP = np.array([0.0, 0.0, 1.0])


def sample(tri_idx, count, weight=None):
    w = tri_area[tri_idx] * (1.0 if weight is None else weight)
    pick = rng.choice(tri_idx, size=count, p=w / w.sum())
    r1, r2 = rng.random(count), rng.random(count)
    s = np.sqrt(r1); b = np.stack([1 - s, s * (1 - r2), s * r2], 1)
    P = (b[:, :, None] * Vw[tri_v[pick]]).sum(1)
    N = (b[:, :, None] * vn[tri_v[pick]]).sum(1); N /= np.linalg.norm(N, axis=1, keepdims=True)
    UV = (b[:, :, None] * tri_uv[pick]).sum(1)
    return P, N, UV


def tris_where(vertex_mask, all_corners=False):
    m = vertex_mask[tri_v]
    return np.nonzero(m.all(1) if all_corners else m.any(1))[0]


def curves_object(name, pos, radius_root, radius_tip, material, surface_uv=None):
    n_curves, n_pts = pos.shape[:2]
    cu = bpy.data.hair_curves.new(name)
    cu.add_curves([n_pts] * n_curves)
    cu.position_data.foreach_set("vector", pos.reshape(-1).astype(np.float32))
    rad = np.tile(np.linspace(radius_root, radius_tip, n_pts), n_curves).astype(np.float32)
    ra = cu.attributes.get("radius") or cu.attributes.new("radius", "FLOAT", "POINT")
    ra.data.foreach_set("value", rad)
    cu.materials.append(material)
    o = bpy.data.objects.new(name, cu); sc.collection.objects.link(o)
    if surface_uv is not None:
        cu.surface = ob
        cu.surface_uv_map = "UDIM"
        at = cu.attributes.get("surface_uv_coordinate") or cu.attributes.new("surface_uv_coordinate", "FLOAT2", "CURVE")
        at.data.foreach_set("vector", surface_uv.reshape(-1).astype(np.float32))
        attach(o)
    return o


def attach(o):
    """Geometry-nodes 'Deform Curves on Surface' so the strands ride GNM's shape keys and rig."""
    ng = bpy.data.node_groups.get("GNM_deform_curves")
    if ng is None:
        ng = bpy.data.node_groups.new("GNM_deform_curves", "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        gin = ng.nodes.new("NodeGroupInput"); gout = ng.nodes.new("NodeGroupOutput")
        d = ng.nodes.new("GeometryNodeDeformCurvesOnSurface")
        ng.links.new(gin.outputs[0], d.inputs[0]); ng.links.new(d.outputs[0], gout.inputs[0])
    m = o.modifiers.new("DeformOnGNM", "NODES"); m.node_group = ng


ob.add_rest_position_attribute = True        # Deform Curves on Surface reads the rest position

# GNM lid-margin rotation about the eye centre, measured from GNM itself (lookdev report, D): linear in
# the controls, radius change <= 0.4 mm. Degrees per unit of shape-key value:
HINGE = {"upper": {"blink": -24.7, "lid_follow": 7.47}, "lower": {"blink": 3.4, "lid_follow": 1.6}}


def lid_hinge(o, cL, cR):
    """Lashes rotate rigidly about their eye centre (world X axis) with the lid: angle driven from the
    blink / lid_follow shape-key values with GNM's measured coefficients. (Deform Curves on Surface only
    translated them: the margin triangles barely rotate, so closed-lid lashes pointed up.)"""
    ng = bpy.data.node_groups.new("GNM_lash_hinge", "GeometryNodeTree")
    io = ng.interface
    io.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for n in ("ang_upper_L", "ang_lower_L", "ang_upper_R", "ang_lower_R"):
        io.new_socket(n, in_out="INPUT", socket_type="NodeSocketFloat")
    io.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    gin = N.new("NodeGroupInput"); gout = N.new("NodeGroupOutput")
    grp = N.new("GeometryNodeInputNamedAttribute"); grp.data_type = "INT"; grp.inputs["Name"].default_value = "lash_group"
    ang = None
    for k, n in enumerate(("ang_upper_L", "ang_lower_L", "ang_upper_R", "ang_lower_R")):
        eq = N.new("FunctionNodeCompare"); eq.data_type = "INT"; eq.operation = "EQUAL"
        L.new(grp.outputs["Attribute"], eq.inputs[0]); eq.inputs[1].default_value = k   # Blender 5: A, B only
        mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
        L.new(eq.outputs[0], mul.inputs[0]); L.new(gin.outputs[n], mul.inputs[1])
        if ang is None:
            ang = mul.outputs[0]
        else:
            add = N.new("ShaderNodeMath"); add.operation = "ADD"; L.new(ang, add.inputs[0]); L.new(mul.outputs[0], add.inputs[1]); ang = add.outputs[0]
    right = N.new("FunctionNodeCompare"); right.data_type = "INT"; right.operation = "GREATER_EQUAL"
    L.new(grp.outputs["Attribute"], right.inputs[0]); right.inputs[1].default_value = 2
    mix = N.new("GeometryNodeSwitch"); mix.input_type = "VECTOR"
    L.new(right.outputs[0], mix.inputs["Switch"]); mix.inputs["False"].default_value = tuple(cL); mix.inputs["True"].default_value = tuple(cR)
    pos = N.new("GeometryNodeInputPosition")
    rot = N.new("ShaderNodeVectorRotate"); rot.rotation_type = "X_AXIS"
    L.new(pos.outputs[0], rot.inputs["Vector"]); L.new(mix.outputs[0], rot.inputs["Center"])
    neg = N.new("ShaderNodeMath"); neg.operation = "MULTIPLY"; L.new(ang, neg.inputs[0]); neg.inputs[1].default_value = -math.pi / 180.0
    L.new(neg.outputs[0], rot.inputs["Angle"])     # GNM 'up' (+Y_gnm) is -rotation about world +X
    sp = N.new("GeometryNodeSetPosition"); L.new(gin.outputs[0], sp.inputs["Geometry"]); L.new(rot.outputs[0], sp.inputs["Position"])
    L.new(sp.outputs[0], gout.inputs[0])
    m = o.modifiers.new("LidHinge", "NODES"); m.node_group = ng
    key = ob.data.shape_keys
    for n in ("ang_upper_L", "ang_lower_L", "ang_upper_R", "ang_lower_R"):
        sock = next(it for it in ng.interface.items_tree if getattr(it, "in_out", "") == "INPUT" and it.name == n)
        lid = "upper" if "upper" in n else "lower"; LR = n[-1]
        # Blender 5.x: modifier inputs live at modifiers[...].properties.inputs.<Socket>.value (on the object)
        fc = o.driver_add(f'modifiers["{m.name}"].properties.inputs.{sock.identifier}.value'); drv = fc.driver; drv.type = "SCRIPTED"
        for var_name, ctrl in (("b", f"blink_{LR}"), ("f", f"lid_follow_{LR}")):
            v = drv.variables.new(); v.name = var_name; v.type = "SINGLE_PROP"
            v.targets[0].id_type = "KEY"; v.targets[0].id = key; v.targets[0].data_path = f'key_blocks["{ctrl}"].value'
        drv.expression = f"{HINGE[lid]['blink']}*b + {HINGE[lid]['lid_follow']}*f"

# ======================================================================== hair
skin = vmask("skin"); face = vmask("hockey_mask"); ears = vmask("ears")
scalp_v = skin & ~face & ~ears & (Vw[:, 2] > eye_mid[2] - 0.035)
scalp_t = tris_where(scalp_v, all_corners=True)
P, N, UVh = sample(scalp_t, 78000)
keep = ~hair_strands.below_hairline(P, eye_mid, head_centre)
# soft hairline: fade density over the last 6 mm above the production hairline height
h0 = eye_mid[2] + 0.070
front = P[:, 1] < head_centre[1] - 0.035
fade = np.clip((P[:, 2] - h0) / 0.006, 0, 1)
keep &= ~front | (rng.random(len(P)) < np.where(np.abs(P[:, 0]) < 0.05, fade, 1.0))
# no hair below the ear tops at the sides/back (short crop), soft
keep &= P[:, 2] > eye_mid[2] - 0.03 + 0.01 * rng.random(len(P))
P, N = P[keep][:60000], N[keep][:60000]
pos, _ = hair_strands.grow(P, N, head_centre, rng, points=8)
hair = curves_object("GNM_Hair", pos, 0.000045, 0.000012, hair_strands.hair_material())
print("HAIR", len(P), "strands")

# ======================================================================== brows
brow_mat = hair_strands.hair_material(melanin=1.0, redness=0.03); brow_mat.name = "GNM_Brow"
brow_pos, brow_uv = [], []
for side, sgn in (("left", 1.0), ("right", -1.0)):
    reg = vmask(f"{side}_brow_region")
    t_idx = tris_where(reg, all_corners=False)
    P, N, UV = sample(t_idx, 9000)
    lat = sgn * (P[:, 0] - eye_mid[0])                         # 0 at midline, + laterally
    x0, x1 = np.percentile(lat, 3), np.percentile(lat, 97)
    t = np.clip((lat - x0) / (x1 - x0), 0, 1)                 # 0 medial -> 1 lateral
    # brow centre line: smooth running median height along t
    bins = np.linspace(0, 1, 13); cl = np.interp(t, (bins[:-1] + bins[1:]) / 2,
          [np.median(P[(t >= bins[i]) & (t < bins[i + 1]), 2]) if ((t >= bins[i]) & (t < bins[i + 1])).any() else np.nan for i in range(12)])
    cl = np.where(np.isnan(cl), np.nanmedian(cl), cl)
    half = 0.0035 - 0.0013 * t                                 # half thickness 3.5 -> 2.2 mm (iter7: thin, drawn-looking)
    prof = np.exp(-((P[:, 2] - cl) / half) ** 4) * np.clip(t / 0.08, 0, 1) * np.clip((1 - t) / 0.12, 0, 1)
    acc = rng.random(len(P)) < prof
    P, N, UV, t = P[acc][:1100], N[acc][:1100], UV[acc][:1100], t[acc][:1100]
    lat_dir = np.array([sgn, 0.0, 0.0])
    d = lat_dir[None] * (0.55 + 0.45 * t[:, None]) + UP[None] * (0.75 - 0.95 * t[:, None])   # iter3: medial hairs stood up
    d -= (d * N).sum(1, keepdims=True) * N                     # into the skin's tangent plane
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    d += rng.normal(0, 0.12, d.shape); d -= (d * N).sum(1, keepdims=True) * N; d /= np.linalg.norm(d, axis=1, keepdims=True)
    L = rng.uniform(0.006, 0.009, len(P))
    k = np.linspace(0, 1, 5)[None, :, None]
    lift = np.sin(math.radians(8)) * L[:, None, None] * np.sin(np.pi * k * 0.8)    # leaves, then settles
    pts = P[:, None] + d[:, None] * (L[:, None, None] * k) + N[:, None] * lift
    brow_pos.append(pts); brow_uv.append(UV)
    print("BROW", side, len(P))
brows = curves_object("GNM_Brows", np.concatenate(brow_pos), 0.000035, 0.00001, brow_mat, np.concatenate(brow_uv))

# ======================================================================== lashes
lash_mat = hair_strands.hair_material(melanin=1.0, redness=0.05); lash_mat.name = "GNM_Lash"
# GNM's skin continues into the socket lining, so the lid margin is not a mesh boundary. Seen from
# the front, the margin is the innermost ring of skin around the opening: per 5 deg around the gaze
# axis, the outward-facing skin vertex in front of the eye nearest the axis in the frontal plane.
# (iter4: "closest to the eyeball sphere" picked skin folds above the lid -> floating lashes.)
vert_uv = {}
for p in me.polygons:
    if mi[p.index] == 0:
        for v, l in zip(p.vertices, p.loop_indices):
            vert_uv.setdefault(v, tuple(uvl[l].uv))
lash_pos, lash_uv, lash_group = [], [], []
for side, centre in (("left", eyeL), ("right", eyeR)):
    cand = np.nonzero(skin & vmask(f"{side}_orbital_region"))[0]
    front = (Vw[cand, 1] < centre[1] - 0.006) & (vn[cand, 1] < -0.2)          # in front, facing the camera side
    cand = cand[front]
    rel = Vw[cand] - centre
    phi = np.arctan2(rel[:, 2], rel[:, 0]); rho = np.hypot(rel[:, 0], rel[:, 2])
    ring = []
    for b0 in np.linspace(-np.pi, np.pi, 73)[:-1]:
        inb = (phi >= b0) & (phi < b0 + 2 * np.pi / 72)
        if inb.any():
            ring.append(int(cand[inb][np.argmin(rho[inb])]))
    edges = [(ring[i], ring[(i + 1) % len(ring)], {ring[i]: vert_uv[ring[i]], ring[(i + 1) % len(ring)]: vert_uv[ring[(i + 1) % len(ring)]]})
             for i in range(len(ring)) if np.linalg.norm(Vw[ring[i]] - Vw[ring[(i + 1) % len(ring)]]) < 0.006]
    print("LID_RING", side, len(ring), "vertices,", len(edges), "segments")
    # sample roots uniformly along the rim, split by height relative to the eye centre
    seg = np.array([np.linalg.norm(Vw[a] - Vw[b]) for a, b, _ in edges])
    for upper, count, (lc, le) in ((True, 150, (0.0065, 0.0040)), (False, 80, (0.0028, 0.0017))):   # iter5-7: too long
        sel = [i for i, (a, b, _) in enumerate(edges) if (((Vw[a] + Vw[b]) / 2)[2] > centre[2]) == upper]
        w = seg[sel] / seg[sel].sum()
        pick = rng.choice(sel, size=count, p=w); u = rng.random(count)
        P = np.array([Vw[edges[i][0]] * (1 - s) + Vw[edges[i][1]] * s for i, s in zip(pick, u)])
        UV = np.array([np.array(edges[i][2][edges[i][0]]) * (1 - s) + np.array(edges[i][2][edges[i][1]]) * s for i, s in zip(pick, u)])
        Nn = np.array([vn[edges[i][0]] * (1 - s) + vn[edges[i][1]] * s for i, s in zip(pick, u)]); Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
        lateral = np.abs(P[:, 0] - centre[0]) / 0.014
        L = (lc - (lc - le) * np.clip(lateral, 0, 1) ** 2) * rng.uniform(0.85, 1.1, count)
        out_dir = (P - centre); out_dir[:, 2] = 0; out_dir /= np.linalg.norm(out_dir, axis=1, keepdims=True)
        # upper lashes leave the lid ~40 deg above horizontal and curl up; lower ones point down-forward
        # iter5: 0.6 up read as vertical bristles from the front; lashes leave the lid mostly forward
        base = 0.85 * FWD[None] + 0.20 * out_dir + (0.20 if upper else -0.25) * UP[None]   # iter7: bristly from the front
        base += rng.normal(0, 0.10, base.shape)
        base /= np.linalg.norm(base, axis=1, keepdims=True)
        curl = math.radians(35 if upper else 15) * (1 if upper else -1)
        pts = [P]
        cur = P.copy(); dirv = base.copy()
        for k in range(1, 5):
            ang = curl / 4
            axis = np.cross(dirv, UP[None]); axis /= np.maximum(np.linalg.norm(axis, axis=1, keepdims=True), 1e-9)
            # rotate dir toward +UP (upper) or -UP (lower) by ang
            # cross(axis, dir) points toward +UP (perpendicular to dir); positive ang curls up, negative down
            dirv = dirv * math.cos(ang) + np.cross(axis, dirv) * math.sin(ang)
            dirv /= np.linalg.norm(dirv, axis=1, keepdims=True)
            cur = cur + dirv * (L[:, None] / 4); pts.append(cur.copy())
        lash_pos.append(np.stack(pts, 1)); lash_uv.append(UV)
        lash_group.append(np.full(count, (0 if upper else 1) + (0 if side == 'left' else 2), np.int32))
        print("LASHES", side, "upper" if upper else "lower", count)

lashes = curves_object("GNM_Lashes", np.concatenate(lash_pos), 0.00005, 0.00001, lash_mat, None)
lg = lashes.data.attributes.new("lash_group", "INT", "CURVE"); lg.data.foreach_set("value", np.concatenate(lash_group))
lid_hinge(lashes, eyeL, eyeR)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
print("SAVED", out_blend)
