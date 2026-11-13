"""Shared Blender look for GNM previews: materials from GNM's own groups, lights, camera helpers.

Preview materials (not photorealism): skin clay, sclera / iris / pupil from GNM's scleras, irises
and pupils vertex groups (colour attribute), glass corneas (tiles 1003/1005), teeth, tongue.
"""

import bpy
from mathutils import Vector


def metal(scene, samples=96):
    scene.render.engine = "CYCLES"
    p = bpy.context.preferences.addons["cycles"].preferences
    dev = "CPU"
    try:
        p.compute_device_type = "METAL"
        p.get_devices()
        for d in p.devices:
            d.use = d.type == "METAL"
        if any(d.type == "METAL" for d in p.devices):
            scene.cycles.device = "GPU"
            dev = "METAL"
    except TypeError:
        pass
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    return dev


def group_colours(ob):
    me = ob.data
    attr = me.color_attributes.get("gnm_parts") or me.color_attributes.new("gnm_parts", "FLOAT_COLOR", "POINT")
    gi = {g.name: g.index for g in ob.vertex_groups}
    cols = {"gnm_pupils": (0.01, 0.01, 0.01, 1), "gnm_irises": (0.32, 0.18, 0.08, 1), "gnm_scleras": (0.82, 0.8, 0.76, 1)}
    order = ["gnm_scleras", "gnm_irises", "gnm_pupils"]
    data = [(0.6, 0.6, 0.6, 1)] * len(me.vertices)
    for v in me.vertices:
        gs = {g.group for g in v.groups}
        for n in order:
            if gi[n] in gs:
                data[v.index] = cols[n]
    for i, c in enumerate(data):
        attr.data[i].color = c
    return attr.name


def materials(ob):
    attr = group_colours(ob)
    mats = ob.data.materials
    def principled(m):
        m.use_nodes = True
        return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    for i, m in enumerate(mats):
        nt = m.node_tree if m.use_nodes else None
        b = principled(m)
        for n in [n for n in m.node_tree.nodes if n.type in ("TEX_IMAGE", "UVMAP", "ATTRIBUTE")]:
            m.node_tree.nodes.remove(n)
        tile = 1001 + i
        if tile == 1001:
            b.inputs["Base Color"].default_value = (0.72, 0.56, 0.48, 1)
            b.inputs["Roughness"].default_value = 0.5
        elif tile in (1002, 1004):
            a = m.node_tree.nodes.new("ShaderNodeAttribute")
            a.attribute_name = attr
            m.node_tree.links.new(a.outputs["Color"], b.inputs["Base Color"])
            b.inputs["Roughness"].default_value = 0.35
        elif tile in (1003, 1005):
            b.inputs["Base Color"].default_value = (1, 1, 1, 1)
            b.inputs["Transmission Weight"].default_value = 1.0
            b.inputs["Roughness"].default_value = 0.0
            b.inputs["IOR"].default_value = 1.376
        elif tile == 1006:
            b.inputs["Base Color"].default_value = (0.85, 0.82, 0.75, 1)
        else:
            b.inputs["Base Color"].default_value = (0.6, 0.25, 0.25, 1)


def lights(scene, mid, key=9, fill=3.5, rim=4):
    w = bpy.data.worlds.new("W")
    scene.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.18, 0.2, 0.22, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    for name, off, e in (("Key", (0.35, -0.45, 0.25), key), ("Fill", (-0.4, -0.4, 0.05), fill), ("Rim", (0, 0.45, 0.3), rim)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size = e, 0.25
        lo = bpy.data.objects.new(name, ld)
        lo.location = mid + Vector(off)
        lo.rotation_euler = (mid - lo.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(lo)


def camera(scene, pos, target, lens):
    cd = bpy.data.cameras.get("Cam") or bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", cd)
    if cam.name not in scene.collection.objects:
        scene.collection.objects.link(cam)
    cam.location = pos
    cam.rotation_euler = (target - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    scene.camera = cam
    return cam


def label(scene, cam, text):
    cu = bpy.data.curves.get("Label") or bpy.data.curves.new("Label", "FONT")
    ob = bpy.data.objects.get("Label") or bpy.data.objects.new("Label", cu)
    if ob.name not in scene.collection.objects:
        scene.collection.objects.link(ob)
        mat = bpy.data.materials.new("LabelMat")
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            if n.type == "BSDF_PRINCIPLED":
                nt.nodes.remove(n)
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1)    # dark text: readable on pale skin
        em.inputs["Strength"].default_value = 1
        nt.links.new(em.outputs[0], next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL").inputs[0])
        cu.materials.append(mat)
        ob.parent = cam
        ob.visible_shadow = False
    cu.body = text.replace("_", " ")          # the default font has no underscore glyph
    cu.size = 0.0016 * cam.data.lens / 50.0 * 0.12 / 0.06 / 4.0
    cu.align_x = "CENTER"
    # camera space, 12 cm in front (beyond the 10 cm clip start), ~78 % of the way to the bottom edge
    half_h = 0.12 * 18.0 / cam.data.lens
    ob.location = (0, -0.78 * half_h, -0.12)
