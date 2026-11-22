"""PRIVATE: export the scan-based GNM head as a web GLB for a local-only Studio preview.

    blender -b --factory-startup --disable-autoexec ../3dscanstore/build/phase2f/gnm_scan_2e.blend \
        --python export_web_glb.py -- ../3dscanstore/build/web/gnm_scan_private.glb

Licence: 3D Scan Store Free HD Head, personal use + the user's stated one-time permission
(3dscanstore/LICENCE_RECORD.md). The output stays in the git-ignored build/web/ folder. The source
.blend is never saved.

* GNM_Head (17,821 vertices, GNM topology, 12 expression shape keys) with GNM_Rig (neck, head,
  left_eye, right_eye; eye bones at the scan eyeball centres).
* Skin: glTF material with the vendor's 8K Face_Albedo as base colour (the user's request).
* Eyes: the Phase 2F scan eye maps (tiles 1002/1004; REPEAT wrapping maps the tile UVs onto them).
* Corneas: clear transmissive material. Teeth / tongue: plain colours (vendor maps use other UVs).
* Brows and lashes: the vendor strand meshes evaluated at rest (no UVs; dark flat material).
* Transform: the vendor scene's x100 cm scale removed, so the GLB is in metres, upright, face +Z.
"""
import os
import sys

import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree
from mathutils.interpolate import poly_3d_calc

out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
os.makedirs(os.path.dirname(out), exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "..", "3dscanstore", "extracted", "Textures")
BUILD = os.path.join(HERE, "..", "3dscanstore", "build", "phase2f")

gh = bpy.data.objects["GNM_Head"]; rig = bpy.data.objects["GNM_Rig"]
bpy.context.view_layer.update()
V2W = rig.matrix_basis.copy()                       # rig has no parent; head is parented to the rig
loc, rot, scl = V2W.decompose()
NEW = rot.to_matrix().to_4x4()                      # same orientation, metres, at the origin
FIX = NEW @ V2W.inverted()


def mat(name, color, rough=0.5, image=None, transmission=0.0, colorspace="sRGB", alpha=1.0):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (*color, 1); p.inputs["Roughness"].default_value = rough
    if transmission:
        p.inputs["Transmission Weight"].default_value = transmission; p.inputs["IOR"].default_value = 1.376
    if image:
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(image, check_existing=True)
        t.image.colorspace_settings.name = colorspace; t.extension = "REPEAT"
        nt.links.new(t.outputs["Color"], p.inputs["Base Color"])
    return m


slots = [m.name if m else None for m in gh.data.materials]
print("SLOTS", slots)
skin = mat("Skin", (1, 1, 1), 0.55, os.path.join(TEX, "JPG", "Face", "Face_Albedo.jpg"))
eyeL = mat("Eye_L", (1, 1, 1), 0.35, os.path.join(BUILD, "scan_eye_albedo_2e.1002.png"))
eyeR = mat("Eye_R", (1, 1, 1), 0.35, os.path.join(BUILD, "scan_eye_albedo_2e.1004.png"))
cornea = mat("Cornea", (1, 1, 1), 0.0, transmission=1.0)
teeth = mat("Teeth", (0.86, 0.82, 0.74), 0.35)
tongue = mat("Tongue", (0.62, 0.30, 0.30), 0.45)
new = [skin, eyeL, cornea, eyeR, cornea, teeth, tongue]
for i, m in enumerate(new[: len(gh.data.materials)]):
    gh.data.materials[i] = m

# web UV: the UDIM layer is the render UV; make it the active/exported layer
for u in gh.data.uv_layers:
    u.active_render = u.name == "UDIM"
gh.data.uv_layers.active = gh.data.uv_layers["UDIM"]

# drop subdivision (glTF exports the deforming base cage; shape keys survive only without it)
for md in list(gh.modifiers):
    if md.type == "SUBSURF":
        gh.modifiers.remove(md)

# head shape keys in world space (rig at rest), used to drive the brow and lash strands
rig.data.pose_position = "REST"
bpy.context.view_layer.update()
HW = gh.matrix_world.copy(); HW3 = HW.to_3x3()
kb = gh.data.shape_keys.key_blocks
basis = kb[0]
head_w = [HW @ v.co for v in basis.data]
KEYS = [k.name for k in kb[1:]]
head_d = {n: [HW3 @ (kb[n].data[i].co - basis.data[i].co) for i in range(len(basis.data))] for n in KEYS}
polys = [list(p.vertices) for p in gh.data.polygons]
bvh = BVHTree.FromPolygons(head_w, polys)


def strand_deltas(world_pts, edges):
    """Each strand (connected piece) moves rigidly with the skin point nearest its root."""
    n = len(world_pts); parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    best = {}
    for i, p in enumerate(world_pts):
        loc, _, fi, dist = bvh.find_nearest(p)
        r = find(i)
        if fi is not None and (r not in best or dist < best[r][0]):
            best[r] = (dist, loc, fi)
    island = {}
    for r, (_, loc, fi) in best.items():
        vids = polys[fi]
        w = poly_3d_calc([head_w[v] for v in vids], loc)
        island[r] = {k: sum((head_d[k][v] * wi for v, wi in zip(vids, w)), head_d[k][0] * 0) for k in KEYS}
    return [island.get(find(i)) for i in range(n)]


# brows / lashes: bake their current (rest) shape into plain meshes in the new frame
keep = [rig, gh]
dg = bpy.context.evaluated_depsgraph_get()
for nm, col in (("Brows", (0.09, 0.06, 0.045)), ("Lashes", (0.03, 0.025, 0.02))):
    o = bpy.data.objects.get(nm)
    if not o:
        continue
    # subdivision on the strand meshes multiplies them to >2M vertices; export the base strands
    for md in o.modifiers:
        if md.type == "SUBSURF":
            md.show_viewport = md.show_render = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    wpts = [o.matrix_world @ v.co for v in me.vertices]
    deltas = strand_deltas(wpts, [tuple(e.vertices) for e in me.edges])
    me.transform(FIX @ o.matrix_world)
    F3 = FIX.to_3x3()
    me.materials.clear(); me.materials.append(mat(nm, col, 0.6))
    ob = bpy.data.objects.new(nm + "_web", me); bpy.context.scene.collection.objects.link(ob)
    ob.shape_key_add(name="Basis")
    moved = 0
    for k in KEYS:
        sk = ob.shape_key_add(name=k, from_mix=False)
        for i, d in enumerate(deltas):
            if d is not None:
                sk.data[i].co = me.vertices[i].co + F3 @ d[k]
        moved = max(moved, max((d[k].length for d in deltas if d is not None), default=0))
    print("STRAND KEYS", nm, len(me.vertices), "max world delta", round(moved, 4))
    keep.append(ob)

# move rig (and the parented head) into metres at the origin
rig.matrix_world = NEW
bpy.context.view_layer.update()

for o in bpy.data.objects:
    o.select_set(o in keep)
bpy.context.view_layer.objects.active = gh
for k in gh.data.shape_keys.key_blocks:
    k.value = 0.0
rig.data.pose_position = "REST"

bpy.ops.export_scene.gltf(
    filepath=out, export_format="GLB", use_selection=True, export_yup=True,
    export_texcoords=True, export_normals=True, export_tangents=False,
    export_materials="EXPORT", export_image_format="AUTO",
    export_morph=True, export_morph_normal=True, export_skins=True, export_animations=False,
    export_apply=False,
)
print("EXPORTED", out, os.path.getsize(out))
