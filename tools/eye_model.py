"""Anatomical eye for the Track 1 head: sclera, recessed iris with a real pupil opening, and a
refractive corneal dome. Replaces MPFB's painted eye (about 500 faces, texture on a sphere).

Built in an eye-local frame: origin at the eyeball centre, local +Z along the rest gaze axis.
Every part is parented to the eye bone, so it rotates exactly as the bone does.

Dimensions are real adult anatomy scaled to the MPFB eyeball radius (it fits the lids), so the
proportions (cornea curvature, anterior chamber depth, iris and pupil size) are lifelike:
    eyeball radius 12.0 mm, cornea radius of curvature 7.8 mm, corneal (limbus) radius 5.85 mm,
    anterior chamber depth 3.6 mm, iris radius 6.0 mm, pupil radius 1.8 mm.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

REAL_EYE_RADIUS_MM = 12.0
CORNEA_CURVATURE_MM = 7.8
LIMBUS_RADIUS_MM = 5.85
CHAMBER_DEPTH_MM = 3.6
IRIS_RADIUS_MM = 6.0
PUPIL_RADIUS_MM = 1.8
KERATOMETRIC_IOR = 1.3375      # single-surface equivalent of cornea + aqueous humour


def dimensions(radius_m):
    """All eye-local distances in metres for an eyeball of the given radius."""
    # The anterior eye (cornea, iris, pupil) keeps true adult size. Scaling it up with MPFB's
    # oversized 15 mm eyeball made the visible iris ~60 % of the eye opening instead of ~40 %.
    mm = lambda v: v / 1000.0
    r_l = mm(LIMBUS_RADIUS_MM)
    rc = mm(CORNEA_CURVATURE_MM)
    z_limbus = math.sqrt(radius_m ** 2 - r_l ** 2)
    cornea_centre = z_limbus - math.sqrt(rc ** 2 - r_l ** 2)
    apex = cornea_centre + rc
    return {
        "radius": radius_m,
        "limbus_r": r_l,
        "limbus_z": z_limbus,
        "cornea_r": rc,
        "cornea_centre_z": cornea_centre,
        "apex_z": apex,
        "iris_z": apex - mm(CHAMBER_DEPTH_MM),
        "iris_r": mm(IRIS_RADIUS_MM),
        "pupil_r": mm(PUPIL_RADIUS_MM),
    }


def eye_frame(centre, axis):
    """World matrix of the eye-local frame: origin at centre, +Z along axis, +Y roughly world up."""
    z = Vector(axis).normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = centre
    return m


# ---------------------------------------------------------------- geometry

def _sclera(d, segs=128, rings=96):
    """Sphere with an opening at the limbus (the cornea covers it)."""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=d["radius"])
    cut = d["limbus_z"] - 0.0002      # tiny overlap under the cornea edge, no gap at the limbus
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > cut], context="FACES")
    return bm


def _cornea(d, segs=128, rings=48):
    """Spherical cap (radius of curvature cornea_r) from the apex down to the limbus."""
    bm = bmesh.new()
    rc, zc = d["cornea_r"], d["cornea_centre_z"]
    theta_max = math.asin(d["limbus_r"] / rc) + 0.01
    apex = bm.verts.new((0, 0, zc + rc))
    prev = None
    for i in range(1, rings + 1):
        t = theta_max * i / rings
        ring = [bm.verts.new((rc * math.sin(t) * math.cos(a), rc * math.sin(t) * math.sin(a), zc + rc * math.cos(t)))
                for a in (2 * math.pi * j / segs for j in range(segs))]
        for j in range(segs):
            if prev is None:
                bm.faces.new((apex, ring[j], ring[(j + 1) % segs]))
            else:
                bm.faces.new((prev[j], ring[j], ring[(j + 1) % segs], prev[(j + 1) % segs]))
        prev = ring
    return bm


def _iris(d, segs=192, rings=40):
    """Annulus from pupil edge to iris root, slightly domed forward like a real iris (lens push)."""
    bm = bmesh.new()
    rp, ri, z0 = d["pupil_r"], d["iris_r"], d["iris_z"]
    dome = 0.08 * (ri - rp)
    prev = None
    for i in range(rings + 1):
        u = i / rings
        r = rp + (ri - rp) * u
        z = z0 + dome * math.sin(math.pi * (1 - u) * 0.5)    # highest at the pupil margin
        ring = [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in (2 * math.pi * j / segs for j in range(segs))]
        if prev:
            for j in range(segs):
                bm.faces.new((prev[j], ring[j], ring[(j + 1) % segs], prev[(j + 1) % segs]))
        prev = ring
    return bm


def _pupil_back(d, segs=64):
    """Dark disc just behind the pupil opening (lens and retina are not lit from the camera)."""
    bm = bmesh.new()
    z = d["iris_z"] - 0.0015 * d["radius"] / 0.015
    r = d["pupil_r"] * 1.6
    vs = [bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for a in (2 * math.pi * j / segs for j in range(segs))]
    bm.faces.new(vs)
    return bm


# ---------------------------------------------------------------- materials

def _nodes(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    return mat, nt, out


def _polar(nt, scale_r):
    """Object coords -> (radius normalised by scale_r, angle in [0,1))."""
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    vlen = nt.nodes.new("ShaderNodeVectorMath"); vlen.operation = "LENGTH"
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], comb.inputs["X"]); nt.links.new(sep.outputs["Y"], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], vlen.inputs[0])
    r = nt.nodes.new("ShaderNodeMath"); r.operation = "DIVIDE"; r.inputs[1].default_value = scale_r
    nt.links.new(vlen.outputs["Value"], r.inputs[0])
    ang = nt.nodes.new("ShaderNodeMath"); ang.operation = "ARCTAN2"
    nt.links.new(sep.outputs["Y"], ang.inputs[0]); nt.links.new(sep.outputs["X"], ang.inputs[1])
    a01 = nt.nodes.new("ShaderNodeMath"); a01.operation = "MULTIPLY_ADD"
    a01.inputs[1].default_value = 1 / (2 * math.pi); a01.inputs[2].default_value = 0.5
    nt.links.new(ang.outputs[0], a01.inputs[0])
    return r.outputs[0], a01.outputs[0], tc


def _math(nt, op, a, b=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath"); n.operation = op; n.use_clamp = clamp
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _ramp(nt, fac, stops):
    n = nt.nodes.new("ShaderNodeValToRGB")
    els = n.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0]
    for pos, col in stops[1:]:
        e = els.new(pos); e.color = col
    nt.links.new(fac, n.inputs["Fac"])
    return n.outputs["Color"]


def iris_material(d, base=(0.20, 0.085, 0.03), seed=0.0):
    """Procedural iris: radial stroma fibres, crypts, collarette, darker pupillary ruff and limbal ring."""
    mat, nt, out = _nodes("Iris")
    span = d["iris_r"] - d["pupil_r"]
    r, a, tc = _polar(nt, 1.0)
    u = _math(nt, "DIVIDE", _math(nt, "SUBTRACT", r, d["pupil_r"]), span)       # 0 at pupil, 1 at root

    # radial fibres: noise stretched hard along the radius
    fib_co = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", a, 180.0), fib_co.inputs["X"])
    nt.links.new(_math(nt, "MULTIPLY", u, 3.0), fib_co.inputs["Y"])
    fib_co.inputs["Z"].default_value = seed
    fib = nt.nodes.new("ShaderNodeTexNoise"); fib.inputs["Scale"].default_value = 1.0
    fib.inputs["Detail"].default_value = 8.0; fib.inputs["Roughness"].default_value = 0.6
    nt.links.new(fib_co.outputs[0], fib.inputs["Vector"])
    fibres = _ramp(nt, fib.outputs["Fac"], [(0.35, (0, 0, 0, 1)), (0.65, (1, 1, 1, 1))])

    # crypts: dark lacunae between the collarette and the root
    cr_co = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(_math(nt, "MULTIPLY", a, 40.0), cr_co.inputs["X"])
    nt.links.new(_math(nt, "MULTIPLY", u, 6.0), cr_co.inputs["Y"])
    cr_co.inputs["Z"].default_value = seed + 3.1
    vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.feature = "F1"; vor.inputs["Scale"].default_value = 1.0
    nt.links.new(cr_co.outputs[0], vor.inputs["Vector"])
    crypts = _ramp(nt, vor.outputs["Distance"], [(0.0, (0, 0, 0, 1)), (0.25, (1, 1, 1, 1))])

    # radial colour structure: ruff (dark) | pupillary zone (warm) | collarette (light) | ciliary | limbal ring (dark)
    # Dark, low-saturation brown: real irises read far darker than their "colour name".
    zones = _ramp(nt, u, [
        (0.00, (0.010, 0.007, 0.005, 1)),
        (0.04, (0.070, 0.036, 0.016, 1)),     # warm brown: more red, less grey-green
        (0.25, (0.105, 0.055, 0.024, 1)),
        (0.38, (0.060, 0.032, 0.016, 1)),
        (0.80, (0.050, 0.028, 0.016, 1)),
        (0.90, (0.026, 0.024, 0.022, 1)),
        (1.00, (0.045, 0.045, 0.047, 1)),     # soft grey limbal haze, no hard outline
    ])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    fibres = _ramp(nt, fib.outputs["Fac"], [(0.3, (0.35, 0.35, 0.35, 1)), (0.7, (1.6, 1.6, 1.6, 1))])
    nt.links.new(zones, mix.inputs[6]); nt.links.new(fibres, mix.inputs[7])
    mix2 = nt.nodes.new("ShaderNodeMix"); mix2.data_type = "RGBA"; mix2.blend_type = "MULTIPLY"
    mix2.inputs["Factor"].default_value = 0.6
    nt.links.new(mix.outputs[2], mix2.inputs[6]); nt.links.new(crypts, mix2.inputs[7])

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Roughness"].default_value = 0.8
    # The iris sits in aqueous humour of almost the same index, so it has essentially no specular
    # of its own; any sheen here shows as a grey veil through the cornea.
    bsdf.inputs["Specular IOR Level"].default_value = 0.0
    nt.links.new(mix2.outputs[2], bsdf.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0002
    h = _math(nt, "ADD", fib.outputs["Fac"], _math(nt, "MULTIPLY", vor.outputs["Distance"], 0.5))
    nt.links.new(h, bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def sclera_material(d):
    """Off-white sclera with subsurface, conjunctival veins toward the corners, and a wet coat."""
    mat, nt, out = _nodes("Sclera")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Object"], sep.inputs[0])
    # 0 at the limbus, 1 at the equator: veins and yellowing grow toward the periphery
    periph = _math(nt, "SUBTRACT", 1.0, _math(nt, "DIVIDE", sep.outputs["Z"], d["limbus_z"]), clamp=True)
    periph = _math(nt, "POWER", _math(nt, "MULTIPLY", periph, 1.6), 1.3, clamp=True)

    vein = nt.nodes.new("ShaderNodeTexNoise"); vein.inputs["Scale"].default_value = 260.0
    vein.inputs["Detail"].default_value = 6.0; vein.inputs["Distortion"].default_value = 0.6
    nt.links.new(tc.outputs["Object"], vein.inputs["Vector"])
    # thin branching lines: where noise is close to 0.5
    line = _math(nt, "ABSOLUTE", _math(nt, "SUBTRACT", vein.outputs["Fac"], 0.5))
    line = _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", line, 28.0), clamp=True)
    vmask = _math(nt, "MULTIPLY", line, periph)

    # Real sclera is not paper white: warm grey-white, yellower and pinker toward the canthi.
    base = _ramp(nt, periph, [(0.0, (0.46, 0.43, 0.41, 1)), (1.0, (0.42, 0.31, 0.28, 1))])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"
    nt.links.new(_math(nt, "MULTIPLY", vmask, 0.8), mix.inputs["Factor"])
    nt.links.new(base, mix.inputs[6]); mix.inputs[7].default_value = (0.55, 0.09, 0.07, 1)

    # Lid shadow: the lids hug the eyeball, so the sclera darkens toward them. Ambient occlusion
    # within 3 mm reproduces that contact shading.
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion"); ao.samples = 16
    ao.inputs["Distance"].default_value = 0.003
    ao_curve = _math(nt, "POWER", ao.outputs["AO"], 1.8)
    shade = nt.nodes.new("ShaderNodeMix"); shade.data_type = "RGBA"; shade.blend_type = "MULTIPLY"
    shade.inputs["Factor"].default_value = 1.0
    nt.links.new(mix.outputs[2], shade.inputs[6])
    aoc = nt.nodes.new("ShaderNodeCombineXYZ")
    for k in "XYZ":
        nt.links.new(ao_curve, aoc.inputs[k])
    nt.links.new(aoc.outputs[0], shade.inputs[7])

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(shade.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.35
    bsdf.inputs["Subsurface Weight"].default_value = 0.4
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.25)
    bsdf.inputs["Subsurface Scale"].default_value = 0.002
    bsdf.inputs["Coat Weight"].default_value = 1.0          # tear film
    bsdf.inputs["Coat Roughness"].default_value = 0.04
    bsdf.inputs["Coat IOR"].default_value = 1.336
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def cornea_material():
    """Refractive cornea for camera rays; transparent for shadow rays so the iris is lit without
    caustic noise (standard production trick: physically refracted view, unshadowed iris)."""
    mat, nt, out = _nodes("Cornea")
    glass = nt.nodes.new("ShaderNodeBsdfGlass"); glass.inputs["IOR"].default_value = KERATOMETRIC_IOR
    glass.inputs["Roughness"].default_value = 0.0
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs["Fac"])
    nt.links.new(glass.outputs[0], mix.inputs[1]); nt.links.new(clear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def dark_material():
    mat, nt, out = _nodes("PupilDark")
    bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse"); bsdf.inputs["Color"].default_value = (0.003, 0.002, 0.002, 1)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


# ---------------------------------------------------------------- tear meniscus

def lid_margin_loop(body, centre, frame, radius_m, n=160, clearance=0.001):
    """Closed loop where the lid skin meets the eyeball, found by ray casting the evaluated body.

    For each angle phi around the gaze axis, walk outward over the eyeball (polar angle theta) and
    stop at the first direction whose outward ray hits skin within `clearance` of the eyeball.
    """
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(body, dg)
    rot = frame.to_3x3()
    pts = []
    for i in range(n):
        phi = 2 * math.pi * i / n
        found, best = None, None
        for step in range(2, 170):
            th = math.radians(step * 0.5)
            d = rot @ Vector((math.sin(th) * math.cos(phi), math.sin(th) * math.sin(phi), math.cos(th)))
            hit, _, _, _ = bvh.ray_cast(centre + d * (radius_m + 0.006), -d, 0.006 - 0.0001)
            if hit is None:
                continue
            gap = (hit - centre).length - radius_m
            if gap < clearance:
                found = centre + d * (radius_m + 0.00015)
                break
            if best is None or gap < best[0]:
                best = (gap, centre + d * (radius_m + 0.00015))
        if found is None:
            if best is None:
                raise RuntimeError(f"no lid skin over the eye at phi={math.degrees(phi):.0f} deg")
            found = best[1]                   # corner: take the closest skin contact
        pts.append((found, phi))
    return pts


def water_material():
    mat, nt, out = _nodes("TearFilm")
    glass = nt.nodes.new("ShaderNodeBsdfGlass"); glass.inputs["IOR"].default_value = 1.336
    glass.inputs["Roughness"].default_value = 0.03
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs["Fac"])
    nt.links.new(glass.outputs[0], mix.inputs[1]); nt.links.new(clear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def build_tear_line(side, body, centre, axis, radius_m, rig, tube_r=0.00028, segs=8):
    """Thin water tube along the lid margin. Points above the gaze axis follow the upper lid bone,
    points below the lower lid bone, blending to the head at the corners, so it rides the lids."""
    frame = eye_frame(centre, axis)
    loop = lid_margin_loop(body, centre, frame, radius_m)
    me = bpy.data.meshes.new(f"Eye{side}.TearLine")
    bm = bmesh.new()
    rings = []
    n = len(loop)
    for i, (p, phi) in enumerate(loop):
        t = (loop[(i + 1) % n][0] - loop[i - 1][0]).normalized()
        nrm = (p - centre).normalized()
        b = t.cross(nrm).normalized()
        rings.append([bm.verts.new(p + tube_r * (math.cos(a) * nrm + math.sin(a) * b))
                      for a in (2 * math.pi * k / segs for k in range(segs))])
    for i in range(n):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            bm.faces.new((r0[k], r1[k], r1[(k + 1) % segs], r0[(k + 1) % segs]))
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(water_material())
    ob = bpy.data.objects.new(me.name, me)
    bpy.context.scene.collection.objects.link(ob)
    up, low = f"orbicularis03.{side}", f"orbicularis04.{side}"
    groups = {name: ob.vertex_groups.new(name=name) for name in (up, low, "head")}
    for i, (_, phi) in enumerate(loop):
        s = math.sin(phi)                         # +1 top of the eye, -1 bottom (frame y is up)
        w = min(1.0, abs(s) * 1.6)               # corners (canthi) stay with the head
        lid = up if s > 0 else low
        idx = list(range(i * segs, (i + 1) * segs))
        groups[lid].add(idx, w, "REPLACE")
        groups["head"].add(idx, 1.0 - w, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    return ob


# ---------------------------------------------------------------- assembly

def build_eye(side, centre, axis, radius_m, rig, bone_name, collection=None):
    d = dimensions(radius_m)
    frame = eye_frame(centre, axis)
    mats = {"Sclera": sclera_material(d), "Iris": iris_material(d), "Cornea": cornea_material(),
            "PupilDark": dark_material()}
    parts = {"Sclera": _sclera(d), "Iris": _iris(d), "Cornea": _cornea(d), "PupilDark": _pupil_back(d)}
    coll = collection or bpy.context.scene.collection
    objs = {}
    for name, bm in parts.items():
        me = bpy.data.meshes.new(f"Eye{side}.{name}")
        bm.to_mesh(me); bm.free()
        for p in me.polygons:
            p.use_smooth = True
        me.materials.append(mats[name])
        ob = bpy.data.objects.new(f"Eye{side}.{name}", me)
        coll.objects.link(ob)
        ob.matrix_world = frame
        # bone parent, keeping the world transform
        ob.parent = rig
        ob.parent_type = "BONE"
        ob.parent_bone = bone_name
        objs[name] = ob
    bpy.context.view_layer.update()
    for ob in objs.values():                 # re-pin world transform after parenting
        ob.matrix_world = frame
    objs["Iris"]["pupil_local"] = (0.0, 0.0, d["iris_z"] + 0.08 * (d["iris_r"] - d["pupil_r"]))
    objs["Iris"]["eye_dims"] = d
    objs["Iris"]["cornea_ior"] = KERATOMETRIC_IOR
    return objs
