"""Strand hair for the Track 1 head: a short textured crop grown as real curves on the scalp.

MPFB's hair is a textured shell, which reads as a helmet. Real short hair is tens of thousands of
strands with volume on top, shorter sides, clumps and stray hairs. This grows such strands:

  scalp   body skin under the MPFB hair cap (ray cast along the skin normal hits the cap)
  roots   area-weighted random points on the scalp (seeded, so builds are reproducible)
  shape   length and combing depend on where a root sits: long (~3.5 cm) on top, swept forward
          and lifted for volume; short (~1.2 cm) on the sides and back, lying down
  detail  per-strand jitter and clumping toward shared clump tips
  shading Cycles Principled Hair BSDF (melanin model), dark brown, per-strand colour variation

The MPFB cap stays underneath, darkened, as the dense base layer the strands grow out of.
"""

import math

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SEED = 7


def below_hairline(p, eye_mid, head_centre, height=0.070, half_width=0.050):
    """True for points on the front of the head below the hairline (forehead and temples)."""
    return (p[..., 1] < head_centre[1] - 0.035) & (np.abs(p[..., 0]) < half_width) & \
        (p[..., 2] < eye_mid[2] + height)


def fade_cap(cap, eye_mid, head_centre, height=None, soft=0.006):
    """Fade the cap out below the hairline with a soft alpha ramp (a real hairline thins out
    over a few millimetres; cutting the mesh left jagged spikes)."""
    import inspect
    if height is None:
        height = inspect.signature(below_hairline).parameters["height"].default
    half = inspect.signature(below_hairline).parameters["half_width"].default
    nt = cap.active_material.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])

    def m(op, a, b=None, clamp=False):
        n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    front = m("DIVIDE", m("SUBTRACT", head_centre[1] - 0.035, sep.outputs["Y"]), 0.01, clamp=True)
    inside = m("DIVIDE", m("SUBTRACT", half, m("ABSOLUTE", sep.outputs["X"])), 0.01, clamp=True)
    below = m("DIVIDE", m("SUBTRACT", eye_mid[2] + height, sep.outputs["Z"]), soft, clamp=True)
    keep = m("SUBTRACT", 1.0, m("MULTIPLY", m("MULTIPLY", front, inside), below), clamp=True)
    src = next((l.from_socket for l in nt.links if l.to_socket == bsdf.inputs["Alpha"]), None)
    alpha = m("MULTIPLY", src if src is not None else 1.0, keep)
    nt.links.new(alpha, bsdf.inputs["Alpha"])


def scalp_faces(body, cap, max_gap=0.025):
    """Evaluated body triangles whose outward normal ray meets the hair cap within max_gap."""
    dg = bpy.context.evaluated_depsgraph_get()
    cap_bvh = BVHTree.FromObject(cap, dg)
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    mw = ev.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    tris = []
    for t in me.loop_triangles:
        c = mw @ t.center
        n = (nm @ t.normal).normalized()
        if c.z < 1.45:
            continue
        hit = cap_bvh.ray_cast(c + n * 0.0005, n, max_gap)[0]
        if hit is None:
            continue
        a, b, d = (mw @ me.vertices[i].co for i in t.vertices)
        tris.append((np.array(a), np.array(b), np.array(d), np.array(n)))
    ev.to_mesh_clear()
    return tris


def sample_roots(tris, count, rng):
    a = np.array([t[0] for t in tris]); b = np.array([t[1] for t in tris]); c = np.array([t[2] for t in tris])
    n = np.array([t[3] for t in tris])
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    idx = rng.choice(len(tris), size=count, p=area / area.sum())
    u, v = rng.random(count), rng.random(count)
    flip = u + v > 1
    u[flip], v[flip] = 1 - u[flip], 1 - v[flip]
    pts = a[idx] + u[:, None] * (b[idx] - a[idx]) + v[:, None] * (c[idx] - a[idx])
    return pts, n[idx], area.sum()


def grow(roots, normals, head_centre, rng, points=8, top_len=0.030, side_len=0.008,
         lift=0.3, clumps=900):
    """Polyline strands (N, points, 3) for a short textured crop."""
    nrm = normals / np.linalg.norm(normals, axis=1, keepdims=True)
    up = np.clip(nrm[:, 2], 0, 1)                       # 1 on the crown, 0 on the sides
    front = np.clip(-(roots[:, 1] - head_centre[1]) / 0.08, 0, 1)
    length = side_len + (top_len - side_len) * up ** 1.5
    length *= 1 + 0.25 * rng.standard_normal(len(roots)).clip(-2, 2)

    # comb direction: top swept forward and slightly to the part side, sides down and back
    comb = np.zeros_like(roots)
    comb[:, 1] = 0.6 * up + 0.6 * (1 - up)               # back on top (+Y) and on the sides
    comb[:, 2] = -1.0 * (1 - up)                          # down on the sides
    # sideways sweep blends smoothly across the centre line (a hard sign() flip made a parting)
    comb[:, 0] = (0.15 * up + 0.2 * (1 - up)) * np.tanh(roots[:, 0] / 0.02)
    tang = comb - (comb * nrm).sum(1, keepdims=True) * nrm
    tang /= np.linalg.norm(tang, axis=1, keepdims=True) + 1e-9

    # per-strand jitter: rotate the tangent about the normal by a random angle
    ang = rng.normal(0, math.radians(10), len(roots))
    bit = np.cross(nrm, tang)
    tang = tang * np.cos(ang)[:, None] + bit * np.sin(ang)[:, None]

    t = np.linspace(0, 1, points)[None, :, None]
    lift_s = (lift * (0.15 + 1.0 * up ** 2) * (1 + 0.6 * front))[:, None, None]   # sides lie flat
    L = length[:, None, None]
    pos = (roots[:, None, :]
           + nrm[:, None, :] * L * lift_s * (1 - (1 - t) ** 2)
           + tang[:, None, :] * L * t
           + np.array([0, 0, -1.0])[None, None, :] * L * 0.25 * t ** 2)

    # clumping: strands near each other share a clump and their tips lean together
    centres = rng.choice(len(roots), size=min(clumps, len(roots)), replace=False)
    return pos, centres


def _clump(pos, roots, centres, pull):
    """Pull each strand's outer part toward its nearest clump centre strand (brute force, chunked)."""
    cr = roots[centres]
    out = pos.copy()
    t = np.linspace(0, 1, pos.shape[1])[None, :, None] ** 1.5
    for s in range(0, len(roots), 4000):
        d = ((roots[s:s + 4000, None, :] - cr[None, :, :]) ** 2).sum(-1)
        k = d.argmin(1)
        target = pos[centres[k]] - roots[centres[k]][:, None, :] + roots[s:s + 4000, None, :]
        out[s:s + 4000] = pos[s:s + 4000] + (target - pos[s:s + 4000]) * pull * t
    return out


def hair_material(melanin=1.0, redness=0.15):
    mat = bpy.data.materials.get("HairStrands") or bpy.data.materials.new("HairStrands")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    hb = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    hb.parametrization = "MELANIN"
    hb.inputs["Melanin"].default_value = melanin
    hb.inputs["Melanin Redness"].default_value = redness
    hb.inputs["Roughness"].default_value = 0.5         # dry, matte black hair (0.3 read grey)
    hb.inputs["Radial Roughness"].default_value = 0.35
    hb.inputs["Coat"].default_value = 0.0
    hb.inputs["Random Color"].default_value = 0.12
    hb.inputs["Random Roughness"].default_value = 0.15
    nt.links.new(hb.outputs[0], out.inputs["Surface"])
    return mat


def darken_cap(cap, factor=0.3):
    """The cap stays as the dense base layer under the strands: darker and fully matte."""
    nt = cap.active_material.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = next(l.from_socket for l in nt.links if l.to_socket == bsdf.inputs["Base Color"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mul.inputs[6])
    mul.inputs[7].default_value = (factor, factor, factor, 1.0)
    nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 1.0


def build_hair(body, cap, head_centre, eye_mid, count=60000, points=8, radius=0.00004, **kw):
    rng = np.random.default_rng(SEED)
    fade_cap(cap, eye_mid, head_centre)
    tris = scalp_faces(body, cap)
    roots, normals, area = sample_roots(tris, int(count * 1.15), rng)
    keep = ~below_hairline(roots, np.array(eye_mid), np.array(head_centre))
    roots, normals = roots[keep][:count], normals[keep][:count]
    count = len(roots)
    pos, centres = grow(roots, normals, np.array(head_centre), rng, points=points,
                        **{k: v for k, v in kw.items() if k != "clump_pull"})
    pos = _clump(pos, roots, centres, kw.get("clump_pull", 0.6))

    curves = bpy.data.hair_curves.new("HairStrands")
    curves.add_curves([points] * count)
    curves.position_data.foreach_set("vector", pos.reshape(-1).astype(np.float32))
    rad = curves.attributes.get("radius") or curves.attributes.new("radius", "FLOAT", "POINT")
    taper = np.linspace(1.0, 0.35, points)
    rad.data.foreach_set("value", np.tile(taper * radius, count).astype(np.float32))
    curves.materials.append(hair_material())
    ob = bpy.data.objects.new("HairStrands", curves)
    bpy.context.scene.collection.objects.link(ob)
    darken_cap(cap)
    return ob, {"scalp_tris": len(tris), "scalp_area_cm2": area * 1e4, "strands": count}
