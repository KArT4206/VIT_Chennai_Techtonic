"""Build the Track 1 scene on the 3D Scan Store Free HD Head (one-time licence for this publication only).

    blender -b scene.blend --factory-startup -P tools/build_scene_scan.py -- <scan_original.blend> <out.blend>

Starts from the production scene (calibrated EyeCam, lights, world, FixationTarget, render settings and the
`eye_*` scene properties) and replaces the MakeHuman character with the vendor's original scan: head with
its 8K maps, scanned eyeballs and corneal lenses, tear film, brows, lashes, teeth and tongue.

The scan is converted from centimetres to metres and moved so its eye midpoint lands exactly on the scene's
`eye_midpoint`; the camera and target therefore stay at their calibrated 40 / 35 cm. A new armature provides
the contract `wrapper/eyes.py` expects, with no change to the wrapper:
  * bones eye.L / eye.R with heads at the fitted eyeball centres (L = subject's left = +X); each eyeball
    and its lens is parented to its bone, so it rotates about its true centre;
  * lid bones orbicularis03/04.L/R (non-deforming: the scan has no lid rig; the lids stay at rest);
  * objects EyeL.Iris / EyeR.Iris (empties on the eye bones, local +Z = optical axis) carrying
    pupil_local, eye_dims {cornea_centre_z, cornea_r} and cornea_ior, fitted to the scanned geometry.
"""
import math
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
# Empirical calibration (Phase 2N.7R): the eyeballs are smoothed by a Subdivision modifier at render time, so the
# painted pupil renders slightly inside / off the raw-mesh point sampled below. Fitted by rendering an unoccluded
# emission mask of the painted pupil at all 10 sequence poses + reset and matching it to the wrapper's 2D point:
# depth -2.0 mm and offset (-0.123, +0.308) mm (world X, Z at rest) leave 0.14 px mean / 0.28 px max residual.
PUPIL_DEPTH_ADJ = float(__import__("os").environ.get("PUPIL_DEPTH_ADJ_MM", "-2.0")) / 1000
PUPIL_OFFSET = [float(x) / 1000 for x in __import__("os").environ.get("PUPIL_OFFSET_MM", "-0.123,0.308").split(",")]
CORNEA_IOR = 1.376

sc = bpy.context.scene
mid = Vector(sc["eye_midpoint"])

# ---- 1. remove the MakeHuman character (keep camera, lights, target, world) ----
keep_types = {"CAMERA", "LIGHT"}
keep_names = {"FixationTarget"}
for o in list(bpy.data.objects):
    if o.type not in keep_types and o.name not in keep_names:
        bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.curves, bpy.data.materials, bpy.data.images):
    for d in list(coll):
        if d.users == 0:
            coll.remove(d)

# ---- 2. append the vendor scan objects ----
NAMES = ["Head", "Realtime Eyeball Left", "Realtime Eyeball Right", "Lens Left", "Lens Right", "Eye Wet", "Brows", "Lashes", "Teeth", "Tongue"]
with bpy.data.libraries.load(src, link=False) as (data_from, data_to):
    data_to.objects = [n for n in data_from.objects if n in NAMES]
coll = bpy.data.collections.new("Scan")
sc.collection.children.link(coll)
obs = {}
for o in data_to.objects:
    coll.objects.link(o)
    o.hide_render = False; o.hide_viewport = False
    o.data = o.data.copy()
    obs[o.name] = o
bpy.context.view_layer.update()

def world_verts(o):
    M = np.array(o.matrix_world)
    v = np.array([v.co[:] for v in o.data.vertices])
    return (np.c_[v, np.ones(len(v))] @ M.T)[:, :3]

PUPIL_UV = (0.5015, 0.4945)

def uv_to_world(o, uv):
    """World point on mesh o whose UV is uv (barycentric inside the containing triangle)."""
    me = o.data; me.calc_loop_triangles(); ul = me.uv_layers.active.data
    M = o.matrix_world; q = np.array(uv)
    for t in me.loop_triangles:
        a, b, c = (np.array(ul[i].uv[:]) for i in t.loops)
        m = np.array([b - a, c - a]).T
        if abs(np.linalg.det(m)) < 1e-14:
            continue
        l1, l2 = np.linalg.solve(m, q - a)
        if l1 >= -1e-6 and l2 >= -1e-6 and l1 + l2 <= 1 + 1e-6:
            p = [M @ me.vertices[i].co for i in t.vertices]
            w = (1 - l1 - l2) * p[0] + l1 * p[1] + l2 * p[2]
            return np.array(w[:])
    raise RuntimeError(f"UV {uv} not found on {o.name}")

def pupil_from_texture(o, centre, n_sub=12, dark=0.05):
    """3D centroid of the eyeball surface whose painted colour is pupil-dark (front hemisphere only).
    Samples every triangle on an n_sub barycentric grid and looks the texel up with UV wrap."""
    img = next(nd.image for nd in o.material_slots[0].material.node_tree.nodes if nd.type == "TEX_IMAGE" and "Diffuse" in nd.image.name)
    w, h = img.size
    lum = np.array(img.pixels[:]).reshape(h, w, 4)[:, :, :3].mean(2)
    me = o.data; me.calc_loop_triangles(); ul = me.uv_layers.active.data; M = o.matrix_world
    co = np.array([(M @ v.co)[:] for v in me.vertices])
    fwd = np.array([0.0, -1.0, 0.0])
    g = [(i / n_sub, j / n_sub) for i in range(n_sub + 1) for j in range(n_sub + 1 - i)]
    pts = []
    for t in me.loop_triangles:
        P = co[list(t.vertices)]
        if ((P.mean(0) - centre) @ fwd) <= 0:
            continue
        U = np.array([ul[i].uv[:] for i in t.loops])
        for a, b in g:
            uv = (1 - a - b) * U[0] + a * U[1] + b * U[2]
            x = int((uv[0] % 1.0) * w) % w; y = int((uv[1] % 1.0) * h) % h
            if lum[y, x] < dark:
                pts.append((1 - a - b) * P[0] + a * P[1] + b * P[2])
    pts = np.array(pts)
    print(f"  pupil samples on {o.name}: {len(pts)}")
    return pts.mean(0)

def fit_sphere(p):
    A = np.c_[2 * p, np.ones(len(p))]
    b = (p ** 2).sum(1)
    c, *_ = np.linalg.lstsq(A, b, rcond=None)
    centre = c[:3]
    return centre, math.sqrt(c[3] + centre @ centre)

# ---- 3. cm -> m and align the eye midpoint ----
ball = {s: world_verts(obs[f"Realtime Eyeball {n}"]) for s, n in (("L", "Left"), ("R", "Right"))}
cen_cm = {s: fit_sphere(ball[s])[0] for s in "LR"}
mid_cm = (cen_cm["L"] + cen_cm["R"]) / 2
S = 0.01
T = Matrix.Translation(mid) @ Matrix.Scale(S, 4) @ Matrix.Translation(Vector(-mid_cm))
for o in obs.values():
    o.data.transform(T @ o.matrix_world)
    o.matrix_world = Matrix.Identity(4)
    o.data.update()
bpy.context.view_layer.update()

# ---- 3b. the vendor's shading distances are in centimetres: scale them to metres too ----
def scale_input(nt, node, name, f):
    sock = node.inputs.get(name)
    if sock is None:
        return
    if sock.is_linked:
        link = sock.links[0]
        mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = f
        nt.links.new(link.from_socket, mul.inputs[0]); nt.links.new(mul.outputs[0], sock)
    else:
        sock.default_value = sock.default_value * f
done = set()
for o in obs.values():
    for m in o.data.materials:
        if not m or m.name in done or not m.use_nodes:
            continue
        done.add(m.name)
        nt = m.node_tree
        for n in list(nt.nodes):
            if n.type == "BSDF_PRINCIPLED":
                scale_input(nt, n, "Subsurface Scale", S)
            elif n.type == "DISPLACEMENT":
                scale_input(nt, n, "Scale", S)
            elif n.type == "BUMP":
                scale_input(nt, n, "Distance", S)
print("SCALED materials:", sorted(done))
# lashes share the vendor's brow material, which renders them pale under the studio key light: give them a
# dark hair material of their own
lm = obs["Lashes"].material_slots[0].material.copy(); lm.name = "Lashes_dark"   # keeps the vendor's alpha-masked strands
nt = lm.node_tree
p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
bc = p.inputs["Base Color"]
if bc.is_linked:
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = "RGBA"; mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0; mul.inputs[7].default_value = (0.08, 0.07, 0.065, 1.0)
    nt.links.new(bc.links[0].from_socket, mul.inputs[6]); nt.links.new(mul.outputs[2], bc)
else:
    bc.default_value = (0.012, 0.009, 0.008, 1.0)
p.inputs["Roughness"].default_value = 0.6
if p.inputs.get("Specular IOR Level") is not None and not p.inputs["Specular IOR Level"].is_linked:
    p.inputs["Specular IOR Level"].default_value = 0.15
def set_all_materials(o, mat):
    o.data.materials.clear(); o.data.materials.append(mat)
    for slot in o.material_slots:
        slot.link = "DATA"
    for slot in o.material_slots:
        slot.link = "OBJECT"; slot.material = mat; slot.link = "DATA"
set_all_materials(obs["Lashes"], lm)
# corneal lens: clean refractive glass (the vendor lens material shows a grey disc under studio light)
# (a clear Fresnel coat: transparent + glossy. The lens lies ~0.1 mm over the painted iris, so refraction there
#  moves the pupil far below a pixel, and a transmissive shell would block the light reaching the eyeball)
cm = bpy.data.materials.new("Cornea_coat"); cm.use_nodes = True; nt = cm.node_tree; nt.nodes.clear()
o_ = nt.nodes.new("ShaderNodeOutputMaterial"); mix = nt.nodes.new("ShaderNodeMixShader")
tr = nt.nodes.new("ShaderNodeBsdfTransparent"); gl = nt.nodes.new("ShaderNodeBsdfGlossy"); gl.inputs["Roughness"].default_value = 0.02
fr = nt.nodes.new("ShaderNodeFresnel"); fr.inputs["IOR"].default_value = CORNEA_IOR
nt.links.new(fr.outputs[0], mix.inputs[0]); nt.links.new(tr.outputs[0], mix.inputs[1]); nt.links.new(gl.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], o_.inputs["Surface"])
try: cm.blend_method = "HASHED"
except Exception: pass
# large studio lights are kept for the skin but hidden from reflections; the small EyeLight gives the catchlight
for ln in ("KeyLight", "FillLight", "RimLight"):
    lo = bpy.data.objects.get(ln)
    if lo is not None:
        lo.visible_glossy = False
for n in ("Lens Left", "Lens Right"):
    set_all_materials(obs[n], cm)
fl = bpy.data.objects.get("FillLight")
if fl is not None:
    fl.data.energy *= float(__import__("os").environ.get("SCAN_FILL_GAIN", "2.5"))   # softer shadow side for this skin
sc.view_settings.exposure = float(__import__("os").environ.get("SCAN_EXPOSURE", "-0.8"))

# ---- 4. measure eyes in metres ----
eye = {}
for s, n in (("L", "Left"), ("R", "Right")):
    pb = world_verts(obs[f"Realtime Eyeball {n}"])
    centre, r_ball = fit_sphere(pb)
    lens = world_verts(obs[f"Lens {n}"])
    fwd = np.array([0.0, -1.0, 0.0])                       # the scan looks along -Y
    dist = (lens - centre) @ fwd
    cap = lens[dist > np.percentile(dist, 85)]             # front corneal cap of the lens
    c_cen, c_r = fit_sphere(cap)
    # the painted pupil is the dark centre of the eyeball texture (UV ~0.5015, 0.4945); map that UV point onto
    # the scanned eyeball to get the true optical axis (the scan's eyes point slightly outwards, not along -Y)
    pupil_w = pupil_from_texture(obs[f"Realtime Eyeball {n}"], centre)
    axis = (pupil_w - centre); depth = float(np.linalg.norm(axis)); axis = axis / depth
    c_cen, c_r = fit_sphere(lens[((lens - centre) @ axis) > np.percentile((lens - centre) @ axis, 85)])
    pupil_depth = depth + PUPIL_DEPTH_ADJ
    eye[s] = dict(centre=Vector(centre), r=r_ball, cornea_centre=Vector(c_cen), cornea_r=c_r, pupil_depth=pupil_depth, axis=Vector(axis))
    print(f"EYE {s}: centre {np.round(centre, 5)} r {r_ball*1000:.2f} mm, cornea r {c_r*1000:.2f} mm at "
          f"{(np.array(c_cen) - centre) @ fwd * 1000:.2f} mm ahead, pupil depth {pupil_depth*1000:.2f} mm")

# ---- 5. armature with the wrapper's bones ----
arm = bpy.data.armatures.new("Track1.rig")
rig = bpy.data.objects.new("Track1.rig", arm)
coll.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for s in "LR":
    c = eye[s]["centre"]
    b = arm.edit_bones.new(f"eye.{s}")
    b.head = c; b.tail = c + Vector((0, -0.02, 0)); b.roll = 0.0; b.use_deform = False
    for nm, dz in ((f"orbicularis03.{s}", 0.012), (f"orbicularis04.{s}", -0.012)):
        lb = arm.edit_bones.new(nm)
        lb.head = c + Vector((0, 0, dz)); lb.tail = lb.head + Vector((0, -0.01, 0)); lb.use_deform = False
bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.update()

def parent_to_bone(o, bone):
    mw = o.matrix_world.copy()
    o.parent = rig; o.parent_type = "BONE"; o.parent_bone = bone
    bpy.context.view_layer.update()
    o.matrix_world = mw

for s, n in (("L", "Left"), ("R", "Right")):
    parent_to_bone(obs[f"Realtime Eyeball {n}"], f"eye.{s}")
    parent_to_bone(obs[f"Lens {n}"], f"eye.{s}")
    e = eye[s]
    iris = bpy.data.objects.new(f"Eye{s}.Iris", None)
    coll.objects.link(iris)
    rot = Vector((0, 0, 1)).rotation_difference(e["axis"]).to_matrix().to_4x4()     # local +Z -> true optical axis
    iris.matrix_world = Matrix.Translation(e["centre"]) @ rot
    parent_to_bone(iris, f"eye.{s}")
    cz = (e["cornea_centre"] - e["centre"]).dot(e["axis"])
    off_local = rot.to_3x3().inverted() @ Vector((PUPIL_OFFSET[0], 0.0, PUPIL_OFFSET[1]))
    iris["pupil_local"] = [off_local.x, off_local.y, e["pupil_depth"] + off_local.z]
    iris["eye_dims"] = {"cornea_centre_z": cz, "cornea_r": e["cornea_r"]}
    iris["cornea_ior"] = CORNEA_IOR

sc["eye_center_L"] = list(eye["L"]["centre"]); sc["eye_center_R"] = list(eye["R"]["centre"])
sc["eye_radius_m"] = (eye["L"]["r"] + eye["R"]["r"]) / 2
sc["character"] = "3D Scan Store Free HD Head (one-time licence for Samsung PRISM Hackathon 2026 Track 1)"
TEX_MAX = int(__import__("os").environ.get("TEX_MAX", "4096"))      # keeps the submission ZIP a practical size
for img in bpy.data.images:
    if img.size[0] > TEX_MAX or img.size[1] > TEX_MAX:
        f = TEX_MAX / max(img.size[0], img.size[1])
        old = tuple(img.size); img.scale(int(img.size[0] * f), int(img.size[1] * f))
        print(f"TEX {img.name}: {old} -> {tuple(img.size)}")
        tmp = __import__("os").path.join(__import__("tempfile").gettempdir(), f"scan_tex_{img.name.replace(' ', '_')}.jpg")
        cs = img.colorspace_settings.name
        img.file_format = "JPEG"
        img.save(filepath=tmp, quality=95)          # raw pixels, no view transform
        img.filepath = tmp; img.source = "FILE"; img.reload(); img.colorspace_settings.name = cs
        img.pack()
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("SAVED", out)
