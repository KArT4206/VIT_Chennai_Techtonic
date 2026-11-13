"""Procedural skin micro-detail layered onto MPFB's skin shader.

MPFB's skin is a 2K colour map plus one noise bump. Real skin at portrait distance shows:
  pores ~0.5-0.7 mm apart (recessed cells), a cross-hatched pattern of fine creases ~0.3 mm,
  blotchy redness and melanin variation, and roughness that varies with the pores.
All coordinates are the mesh's undeformed (Generated) coordinates scaled back to metres, so the
detail is glued to the skin and does not swim when the lids or other bones deform it.
"""

import bpy

PORE_SPACING_M = 0.0006
CREASE_SPACING_M = 0.0003


def _n(nt, kind, **inputs):
    node = nt.nodes.new(kind)
    for k, v in inputs.items():
        if isinstance(v, bpy.types.NodeSocket):
            nt.links.new(v, node.inputs[k])
        else:
            node.inputs[k].default_value = v
    return node


def _math(nt, op, a, b=None, clamp=False):
    node = nt.nodes.new("ShaderNodeMath")
    node.operation = op
    node.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            node.inputs[i].default_value = v
        else:
            nt.links.new(v, node.inputs[i])
    return node.outputs[0]


def add_skin_detail(material, body, bump_strength=0.35, mottling=0.18):
    """Insert the micro-detail between MPFB's skin group and the material output."""
    nt = material.node_tree
    group = next(n for n in nt.nodes if n.type == "GROUP")
    bsdf = next(n for n in group.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    g = group.node_tree

    # metric coordinates on the undeformed mesh
    tc = g.nodes.new("ShaderNodeTexCoord")
    dims = _bbox_size(body)
    metric = _n(g, "ShaderNodeVectorMath", Vector=tc.outputs["Generated"])
    metric.operation = "MULTIPLY"
    metric.inputs[1].default_value = dims
    co = metric.outputs[0]

    # pores: cellular dimples
    pores = _n(g, "ShaderNodeTexVoronoi", Vector=co, Scale=1.0 / PORE_SPACING_M, Randomness=0.9)
    pores.feature = "F1"
    pore_h = _math(g, "POWER", _math(g, "MULTIPLY", pores.outputs["Distance"], 2.2, clamp=True), 0.6)

    # cross-hatched creases: two sets of fine lines at +/-40 degrees (anisotropic noise)
    def creases(angle_deg, seed):
        rot = _n(g, "ShaderNodeVectorRotate", Vector=co)
        rot.rotation_type = "Y_AXIS"
        rot.inputs["Angle"].default_value = angle_deg * 3.14159265 / 180
        sc = _n(g, "ShaderNodeVectorMath", Vector=rot.outputs[0])
        sc.operation = "MULTIPLY"
        sc.inputs[1].default_value = (1.0 / CREASE_SPACING_M, 1.0 / (CREASE_SPACING_M * 8),
                                      1.0 / (CREASE_SPACING_M * 8))
        nz = g.nodes.new("ShaderNodeTexNoise")
        nz.noise_dimensions = "4D"
        g.links.new(sc.outputs[0], nz.inputs["Vector"])
        nz.inputs["Scale"].default_value = 1.0
        nz.inputs["Detail"].default_value = 2.0
        nz.inputs["W"].default_value = seed
        line = _math(g, "ABSOLUTE", _math(g, "SUBTRACT", nz.outputs["Fac"], 0.5))
        return _math(g, "MULTIPLY", line, 2.0, clamp=True)

    crease_h = _math(g, "MINIMUM", creases(40, 1.3), creases(-40, 7.1))

    height = _math(g, "ADD", _math(g, "MULTIPLY", pore_h, 0.65), _math(g, "MULTIPLY", crease_h, 0.35))

    bump = _n(g, "ShaderNodeBump", Strength=bump_strength, Distance=0.00012, Height=height)
    old_normal = next((l.from_socket for l in g.links if l.to_socket == bsdf.inputs["Normal"]), None)
    if old_normal is not None:
        g.links.new(old_normal, bump.inputs["Normal"])
    g.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    # roughness: pores and creases hold less oil, so they are rougher
    old_rough = next((l.from_socket for l in g.links if l.to_socket == bsdf.inputs["Roughness"]), None)
    base_rough = old_rough if old_rough is not None else bsdf.inputs["Roughness"].default_value
    rough = _math(g, "ADD", base_rough, _math(g, "MULTIPLY", _math(g, "SUBTRACT", 1.0, height), 0.12))
    g.links.new(rough, bsdf.inputs["Roughness"])

    # colour: low-frequency redness blotches and small melanin spots
    old_col = next(l.from_socket for l in g.links if l.to_socket == bsdf.inputs["Base Color"])
    blotch = _n(g, "ShaderNodeTexNoise", Vector=co, Scale=1.0 / 0.012, Detail=3.0, Roughness=0.55)
    red = _n(g, "ShaderNodeMix", Factor=_math(g, "MULTIPLY", _math(g, "SUBTRACT", blotch.outputs["Fac"], 0.45, clamp=True), mottling * 2.5))
    red.data_type = "RGBA"
    red.blend_type = "MULTIPLY"
    g.links.new(old_col, red.inputs[6])
    red.inputs[7].default_value = (1.0, 0.72, 0.68, 1.0)

    spots = _n(g, "ShaderNodeTexVoronoi", Vector=co, Scale=1.0 / 0.004, Randomness=1.0)
    spots.feature = "F1"
    spot_mask = _math(g, "SUBTRACT", 1.0, _math(g, "MULTIPLY", spots.outputs["Distance"], 9.0), clamp=True)
    cell = _n(g, "ShaderNodeSeparateColor", Color=spots.outputs["Color"])     # random per cell
    spot_mask = _math(g, "MULTIPLY", _math(g, "GREATER_THAN", cell.outputs[0], 0.88), spot_mask)
    mel = _n(g, "ShaderNodeMix", Factor=_math(g, "MULTIPLY", spot_mask, mottling * 0.9))
    mel.data_type = "RGBA"
    mel.blend_type = "MULTIPLY"
    g.links.new(red.outputs[2], mel.inputs[6])
    mel.inputs[7].default_value = (0.70, 0.55, 0.45, 1.0)
    g.links.new(mel.outputs[2], bsdf.inputs["Base Color"])
    return group


ZONE_ATTR = "skin_zones"      # R redness, G beard shadow, B sheen, A under-eye darkening


def _gauss(d, r):
    import math
    return math.exp(-0.5 * (d / r) ** 2)


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def shaped_positions(body):
    """Vertex positions with MPFB's shape keys (phenotype and face targets) applied but before the
    armature, mask and subdivision modifiers, so there is one position per base-mesh vertex.
    Raw v.co is the unshaped Basis: wrong as soon as the phenotype differs from the default."""
    from mathutils import Vector
    saved = [(m, m.show_viewport) for m in body.modifiers]
    for m, _ in saved:
        m.show_viewport = False
    try:
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        ev = body.evaluated_get(dg)
        me = ev.to_mesh()
        if len(me.vertices) != len(body.data.vertices):
            raise RuntimeError("shaped mesh vertex count differs from the base mesh")
        pos = [Vector(v.co) for v in me.vertices]
        ev.to_mesh_clear()
    finally:
        for m, state in saved:
            m.show_viewport = state
    return pos


def compute_face_zones(body, eye_l, eye_r):
    """Per-vertex skin zone masks from anatomy, stored as a colour attribute on the base mesh.

    Rest-pose positions (the body object is at the origin, unscaled) plus MPFB's own vertex groups
    (lips, ears, jaw) place each zone; distances are in metres.
    """
    from mathutils import Vector
    me = body.data
    gi = {g.name: g.index for g in body.vertex_groups}

    def weights(name):
        w = [0.0] * len(me.vertices)
        idx = gi.get(name)
        if idx is None:
            return w
        for v in me.vertices:
            for g in v.groups:
                if g.group == idx:
                    w[v.index] = g.weight
        return w

    lips, ears, jaw = weights("lips"), weights("ears"), weights("jaw")
    pos = shaped_positions(body)
    mid = (eye_l + eye_r) / 2
    face = [p for p in pos if abs(p.x) < 0.006 and mid.z - 0.07 < p.z < mid.z - 0.01]
    nose_tip = min(face, key=lambda p: p.y).copy()
    lip_vs = [p for p, w in zip(pos, lips) if w > 0.5]
    lip_top = max(c.z for c in lip_vs) if lip_vs else nose_tip.z - 0.025
    nose_base = nose_tip.z - 0.012
    cheeks = [Vector((s * (abs(eye_l.x) + 0.012), mid.y - 0.005, mid.z - 0.030)) for s in (1, -1)]
    under = [e + Vector((0, -0.010, -0.014)) for e in (eye_l, eye_r)]
    forehead = mid + Vector((0, -0.012, 0.050))

    attr = me.color_attributes.get(ZONE_ATTR) or me.color_attributes.new(ZONE_ATTR, "FLOAT_COLOR", "POINT")
    for v in me.vertices:
        c = pos[v.index]
        front = c.y < mid.y + 0.02 and c.z > mid.z - 0.16
        red = max(_gauss((c - nose_tip).length, 0.010),
                  0.5 * max(_gauss((c - k).length, 0.014) for k in cheeks),
                  0.7 * ears[v.index]) if front or ears[v.index] > 0 else 0.0
        # smooth upper-lip band: between the lip top and the nose base, fading toward the sides
        band = _smooth((c.z - lip_top) / 0.003) * _smooth((nose_base - c.z) / 0.003)
        moustache = band * _gauss(c.x, 0.016) if c.y < mid.y else 0.0
        beard = max(jaw[v.index], moustache) * (1.0 - lips[v.index]) * (1.0 if c.y < mid.y + 0.035 else 0.0)
        sheen = max(_gauss((c - nose_tip).length, 0.014), 0.5 * _gauss((c - forehead).length, 0.018)) if front else 0.0
        dark = max(_gauss((c - u).length, 0.009) for u in under) if front else 0.0
        attr.data[v.index].color = (red, beard, sheen, dark)
    return {"nose_tip": tuple(nose_tip), "lip_top": lip_top}


def add_face_zones(material, beard_strength=0.22, redness=0.35, sheen=0.18, under_eye=0.25, warmth=0.0):
    """Shade the zone masks: redness, blue-grey beard shadow with stubble, oily sheen, under-eye."""
    group = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    g = group.node_tree
    bsdf = next(n for n in g.nodes if n.type == "BSDF_PRINCIPLED")
    attr = g.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = ZONE_ATTR
    sep = _n(g, "ShaderNodeSeparateColor", Color=attr.outputs["Color"])
    zr, zb, zs, za = sep.outputs[0], sep.outputs[1], sep.outputs[2], attr.outputs["Alpha"]

    col = next(l.from_socket for l in g.links if l.to_socket == bsdf.inputs["Base Color"])

    def tint(src, fac, colour):
        m = _n(g, "ShaderNodeMix", Factor=fac)
        m.data_type = "RGBA"
        m.blend_type = "MULTIPLY"
        g.links.new(src, m.inputs[6])
        m.inputs[7].default_value = (*colour, 1.0)
        return m.outputs[2]

    # overall warmth: real skin carries far more red/yellow than MPFB's pale base colour
    col = tint(col, warmth, (1.0, 0.72, 0.50))
    col = tint(col, _math(g, "MULTIPLY", zr, redness), (0.96, 0.74, 0.76))
    col = tint(col, _math(g, "MULTIPLY", za, under_eye), (0.78, 0.66, 0.70))
    # stubble: dense dark dots inside the beard zone, over a soft blue-grey shadow
    tc = g.nodes.new("ShaderNodeTexCoord")
    dots = _n(g, "ShaderNodeTexVoronoi", Vector=tc.outputs["UV"], Scale=900.0, Randomness=1.0)
    dots.feature = "F1"
    dot = _math(g, "SUBTRACT", 1.0, _math(g, "MULTIPLY", dots.outputs["Distance"], 3.5), clamp=True)
    col = tint(col, _math(g, "MULTIPLY", zb, beard_strength), (0.72, 0.74, 0.78))
    col = tint(col, _math(g, "MULTIPLY", _math(g, "MULTIPLY", zb, dot), beard_strength * 1.6), (0.35, 0.30, 0.28))
    g.links.new(col, bsdf.inputs["Base Color"])

    rough = next((l.from_socket for l in g.links if l.to_socket == bsdf.inputs["Roughness"]), None)
    base = rough if rough is not None else bsdf.inputs["Roughness"].default_value
    g.links.new(_math(g, "SUBTRACT", base, _math(g, "MULTIPLY", zs, sheen)), bsdf.inputs["Roughness"])
    return attr


def _bbox_size(obj):
    from mathutils import Vector
    xs = [v.co for v in obj.data.vertices]
    lo = Vector((min(v.x for v in xs), min(v.y for v in xs), min(v.z for v in xs)))
    hi = Vector((max(v.x for v in xs), max(v.y for v in xs), max(v.z for v in xs)))
    return hi - lo


# ------------------------------------------------------------------ expression lines

REST_ATTR = "rest_co"


def store_rest_positions(body):
    """Rest-pose position per vertex, so creases are drawn per pixel and stay put under the lids'
    deformation (a per-vertex mask would be far too coarse: vertices are 3-5 mm apart)."""
    me = body.data
    attr = me.attributes.get(REST_ATTR) or me.attributes.new(REST_ATTR, "FLOAT_VECTOR", "POINT")
    attr.data.foreach_set("vector", [c for p in shaped_positions(body) for c in p])


def add_wrinkles(material, eye_l, eye_r, nose_tip, lip_top, depth=0.00045, strength=1.0, forehead_weight=0.4):
    """Forehead lines, nasolabial folds and under-eye creases as bump relief (metres)."""
    import math
    group = next(n for n in material.node_tree.nodes if n.type == "GROUP")
    g = group.node_tree
    bsdf = next(n for n in g.nodes if n.type == "BSDF_PRINCIPLED")
    attr = g.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = REST_ATTR
    sep = _n(g, "ShaderNodeSeparateXYZ", Vector=attr.outputs["Vector"])
    X, Y, Z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]
    M = lambda op, a, b=None, clamp=False: _math(g, op, a, b, clamp)

    def gauss(d, sigma):                      # exp(-(d/sigma)^2)
        return M("EXPONENT", M("MULTIPLY", M("POWER", M("DIVIDE", d, sigma), 2.0), -1.0))

    front = M("LESS_THAN", Y, nose_tip[1] + 0.065)
    mid_z = (eye_l.z + eye_r.z) / 2
    ax = M("ABSOLUTE", X)

    # forehead: three wavy horizontal lines, fading toward the temples
    fade_x = M("SUBTRACT", 1.0, M("POWER", M("DIVIDE", ax, 0.045), 2.0), clamp=True)
    forehead = None
    for i, dz in enumerate((0.040, 0.050, 0.060)):
        wave = M("MULTIPLY", M("SINE", M("ADD", M("MULTIPLY", X, 110.0), 1.7 * i)), 0.0012)
        line = gauss(M("SUBTRACT", Z, M("ADD", mid_z + dz, wave)), 0.0007)
        line = M("MULTIPLY", line, 0.8 - 0.15 * i)
        forehead = line if forehead is None else M("ADD", forehead, line)
    forehead = M("MULTIPLY", M("MULTIPLY", forehead, fade_x), forehead_weight)

    # nasolabial folds: segment from the nose wing down to beside the mouth corner (x-z plane)
    ax0, az0 = 0.019, nose_tip[2] - 0.008
    ax1, az1 = 0.031, lip_top - 0.016
    vx, vz = ax1 - ax0, az1 - az0
    ln2 = vx * vx + vz * vz
    tpar = M("DIVIDE", M("ADD", M("MULTIPLY", M("SUBTRACT", ax, ax0), vx),
                         M("MULTIPLY", M("SUBTRACT", Z, az0), vz)), ln2, clamp=True)
    px = M("ADD", ax0, M("MULTIPLY", tpar, vx))
    pz = M("ADD", az0, M("MULTIPLY", tpar, vz))
    dist = M("SQRT", M("ADD", M("POWER", M("SUBTRACT", ax, px), 2.0), M("POWER", M("SUBTRACT", Z, pz), 2.0)))
    fold_fade = M("SINE", M("MULTIPLY", tpar, math.pi))          # strongest mid-fold
    nasolabial = M("MULTIPLY", gauss(dist, 0.0016), M("ADD", 0.35, M("MULTIPLY", fold_fade, 0.65)))

    # under-eye creases: a shallow arc below each lower lid
    under = None
    for e in (eye_l, eye_r):
        dx = M("SUBTRACT", X, e.x)
        arc_z = M("ADD", e.z - 0.0165, M("MULTIPLY", M("POWER", dx, 2.0), 7.0))
        inside = M("SUBTRACT", 1.0, M("POWER", M("DIVIDE", dx, 0.015), 2.0), clamp=True)
        c = M("MULTIPLY", gauss(M("SUBTRACT", Z, arc_z), 0.0008), inside)
        under = c if under is None else M("ADD", under, c)
    under = M("MULTIPLY", under, 0.6)

    crease = M("MULTIPLY", M("ADD", M("ADD", forehead, nasolabial), under), M("MULTIPLY", front, strength))
    height = M("MULTIPLY", crease, -1.0)                           # creases are grooves
    bump = _n(g, "ShaderNodeBump", Strength=1.0, Distance=depth, Height=height)
    prev = next((l.from_socket for l in g.links if l.to_socket == bsdf.inputs["Normal"]), None)
    if prev is not None:
        g.links.new(prev, bump.inputs["Normal"])
    g.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return bump
