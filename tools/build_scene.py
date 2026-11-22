"""Build the Track 1 scene from scratch (development tool, needs the MPFB add-on).

Run inside Blender:
    Blender -b -P tools/build_scene.py -- --out scene.blend

The submitted scene.blend is the output of this script, so evaluators never need MPFB.
Scene conventions (metres, Blender world frame):
    +Z up, the face looks along -Y, the subject's left eye is at +X.
    The eye midpoint is the midpoint of the two fitted eyeball centres.
    Camera:   locked 0.40 m in front of the eye midpoint, looking at it (+Y).
    Fixation: empty "FixationTarget" 0.35 m in front of the eye midpoint.
"""

import math
import sys

import bpy
import numpy as np
from mathutils import Vector

CAMERA_DISTANCE_M = 0.40
FIXATION_DISTANCE_M = 0.35
RESOLUTION_PX = 1024
FOCAL_LENGTH_MM = 96.0       # 36 mm sensor -> 0.15 m wide field at 0.40 m: whole face width, pupil shifts ~1.6x larger than 60 mm
SENSOR_WIDTH_MM = 36.0

HUMAN_INFO = {
    "rig": "default",
    "eyes": "high-poly/high-poly.mhclo",
    "eyebrows": "eyebrow009/eyebrow009.mhclo",
    "eyelashes": "eyelashes01/eyelashes01.mhclo",
    "hair": "short04/short04.mhclo",
    "skin_mhmat": "young_caucasian_male/young_caucasian_male.mhmat",
    "skin_material_type": "ENHANCED_SSS",
    "eyes_material_type": "MAKESKIN",
    "alternative_materials": {},
}

# An original adult male face: fully male, a slightly heavier build and a fuller, rounder face.
# These are generic shape adjustments, not measurements of any real person.
PHENOTYPE = {"gender": 1.0, "age": 0.5, "muscle": 0.56, "weight": 0.55}
FACE_TARGETS = {
    "head-round": 0.20, "head-fat-incr": 0.12, "chin-width-incr": 0.25,
    "l-cheek-volume-incr": 0.12, "r-cheek-volume-incr": 0.12,
    "forehead-scale-vert-decr": 0.30, "measure-neck-circ-incr": 0.30,
    "nose-volume-incr": 0.20, "nose-point-width-incr": 0.25, "mouth-lowerlip-volume-incr": 0.20,
}


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def create_human():
    import addon_utils
    # With -b -P the script can run before extensions register; MPFB needs its package set up.
    addon_utils.enable("bl_ext.user_default.mpfb", default_set=True)
    from bl_ext.user_default.mpfb.services import HumanService
    info = HumanService._create_default_human_info_dict()
    info.update(HUMAN_INFO)
    info["phenotype"].update(PHENOTYPE)
    info["targets"] = [{"target": k, "value": v} for k, v in FACE_TARGETS.items()]
    settings = HumanService.get_default_deserialization_settings()
    settings["subdiv_levels"] = 1
    HumanService.deserialize_from_dict(info, settings)
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    eyes = next(o for o in bpy.data.objects if o.type == "MESH" and "high-poly" in o.name)
    return rig, eyes


def fit_sphere(points):
    """Least-squares sphere fit, iterated on the outer shell so the iris disc and cornea are ignored."""
    def solve(p):
        a = np.c_[2 * p, np.ones(len(p))]
        x = np.linalg.lstsq(a, (p ** 2).sum(1), rcond=None)[0]
        c = x[:3]
        return c, math.sqrt(x[3] + c @ c)

    centre, radius = solve(points)
    for _ in range(4):
        d = np.linalg.norm(points - centre, axis=1)
        shell = np.abs(d - np.median(d[d > np.percentile(d, 40)])) < 0.0015
        centre, radius = solve(points[shell])
    return Vector(centre), radius


def eyeball_centres(eyes):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = eyes.evaluated_get(dg)
    mesh = ev.to_mesh()
    pts = np.array([tuple(ev.matrix_world @ v.co) for v in mesh.vertices])
    ev.to_mesh_clear()
    left, r_l = fit_sphere(pts[pts[:, 0] > 0])
    right, r_r = fit_sphere(pts[pts[:, 0] < 0])
    return left, right, r_l, r_r


def install_anatomical_eyes(rig, mpfb_eyes, body, radius_m):
    """Swap MPFB's painted eye for the anatomical eye in tools/eye_model.py (sclera, recessed iris
    with a real pupil opening, refractive cornea) plus a wet tear line along each lid margin."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import eye_model
    bpy.data.objects.remove(mpfb_eyes, do_unlink=True)
    built = {}
    for side in "LR":
        bone = rig.data.bones[f"eye.{side}"]
        centre = rig.matrix_world @ bone.head_local
        axis = (rig.matrix_world.to_3x3() @ bone.matrix_local.to_3x3()).col[1]
        parts = eye_model.build_eye(side, centre, axis, radius_m, rig, bone.name)
        parts["TearLine"] = eye_model.build_tear_line(side, body, centre, axis, radius_m, rig)
        built[side] = parts
    return built


def setup_hair_material(hair):
    """Give the hair cards their strand normal map and remove the shell-wide specular.

    MPFB ships short02_normal.png but leaves it unconnected, so the cards shade as one smooth
    shell. With the default specular, the rim light grazing the crown then turns the top of the
    head into a white sheet (measured: it disappears with specular 0, not with the rim's own
    specular factor reduced).
    """
    import os
    mat = hair.active_material
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    diffuse = next(n.image for n in nt.nodes if n.type == "TEX_IMAGE")
    normal_path = os.path.join(os.path.dirname(bpy.path.abspath(diffuse.filepath)),
                               diffuse.name.replace("_diffuse", "_normal"))
    if os.path.exists(normal_path):
        img = bpy.data.images.load(normal_path, check_existing=True)
        img.colorspace_settings.name = "Non-Color"
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nmap = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(tex.outputs["Color"], nmap.inputs["Color"])
        nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.85     # matte, dry hair (no slicked-back gloss)
    bsdf.inputs["Specular IOR Level"].default_value = 0.0


SKIN_SETTINGS = {
    # MPFB's defaults (pore scale 2500, strength 0.2) are too fine and faint to show at 1024 px,
    # which leaves the skin looking airbrushed.
    "Pore scale": 1400.0,
    "Pore strength": 0.5,
    "SSS strength": 0.22,          # higher made shadowed lids glow orange
    "Roughness": 0.5,
}


# Adult skin colouring by zone (tools/skin_detail.py): redness on nose, cheeks and ears, a
# blue-grey beard shadow with stubble, oily sheen on nose and forehead, darker under the eyes.
FACE_ZONES = {"beard_strength": 0.5, "redness": 0.45, "sheen": 0.2, "under_eye": 0.3, "warmth": 1.0}


def setup_skin_material(body, eye_l, eye_r):
    group = next(n for n in body.active_material.node_tree.nodes if n.type == "GROUP")
    for name, value in SKIN_SETTINGS.items():
        group.inputs[name].default_value = value
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import skin_detail
    zones = skin_detail.compute_face_zones(body, eye_l, eye_r)
    skin_detail.store_rest_positions(body)
    skin_detail.add_skin_detail(body.active_material, body, bump_strength=0.6, mottling=0.2)
    # young-adult expression lines: faint forehead lines, nasolabial folds, under-eye creases
    skin_detail.add_wrinkles(body.active_material, eye_l, eye_r, zones["nose_tip"], zones["lip_top"])
    skin_detail.add_face_zones(body.active_material, **FACE_ZONES)


def bind_lashes_to_lids(lashes, body):
    """Give every lash vertex the skin weights of the eyelid surface it grows from.

    MPFB weights some lashes mostly to `head` while the lid skin under them follows the lid bones,
    so lashes detach from the lid when the lids follow vertical gaze. Transferring all weights from
    the nearest body surface makes lashes deform exactly like the lid margin.
    """
    mod = lashes.modifiers.new("LidWeights", "DATA_TRANSFER")
    mod.object = body
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    mod.layers_vgroup_select_src = "ALL"
    mod.layers_vgroup_select_dst = "NAME"
    with bpy.context.temp_override(object=lashes, active_object=lashes):
        while lashes.modifiers.find("LidWeights") > 0:     # must run before the armature deforms
            bpy.ops.object.modifier_move_up(modifier="LidWeights")
        bpy.ops.object.datalayout_transfer(modifier="LidWeights")
        bpy.ops.object.modifier_apply(modifier="LidWeights")


def add_camera(midpoint):
    cam_data = bpy.data.cameras.new("EyeCam")
    cam_data.lens = FOCAL_LENGTH_MM
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = SENSOR_WIDTH_MM
    cam_data.clip_start = 0.01
    cam = bpy.data.objects.new("EyeCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = midpoint + Vector((0.0, -CAMERA_DISTANCE_M, 0.0))
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)   # looks along +Y, up is +Z
    cam.lock_location = (True, True, True)
    cam.lock_rotation = (True, True, True)
    bpy.context.scene.camera = cam
    return cam


def add_fixation_target(midpoint):
    target = bpy.data.objects.new("FixationTarget", None)
    target.empty_display_type = "SPHERE"
    target.empty_display_size = 0.005
    target.location = midpoint + Vector((0.0, -FIXATION_DISTANCE_M, 0.0))
    target["rest_location"] = tuple(target.location)
    bpy.context.scene.collection.objects.link(target)
    return target


def add_lighting(midpoint, eye_parts=None):
    """Constant studio lighting: soft key, fill and rim area lights plus a dim neutral world."""
    def area(name, offset, power, size):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = power
        data.shape = "DISK"          # round catchlights in the cornea, like a real softbox
        data.size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = midpoint + Vector(offset)
        direction = midpoint - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    # Small sources at the same power are brighter per area, so the corneal catchlights are small
    # crisp white points (as from a real softbox) instead of large dull grey discs.
    # Steeper placements were tried to keep catchlights off the pupil, but they shade the iris
    # almost as dark as the pupil; this placement gave the best pupil/iris contrast.
    # Low-key portrait lighting (azimuth, elevation in degrees, distance m): a side key that
    # models the face, a weak fill (~11:1), a rim for separation, and a dark background.
    def polar(az, el, d):
        a, e = math.radians(az), math.radians(el)
        return (d * math.sin(a) * math.cos(e), -d * math.cos(a) * math.cos(e), d * math.sin(e))

    area("KeyLight", polar(40, 30, 0.65), 18.0, 0.5)
    area("FillLight", polar(-50, 0, 0.6), 3.0, 0.6)
    area("RimLight", polar(150, 35, 0.6), 12.0, 0.4)

    # Eye light: a small softbox seen only in the corneas (light linking), the way portrait and
    # film lighting adds a catchlight without changing the face. The key and fill are excluded
    # from the corneas so each eye shows one crisp catchlight instead of flat grey discs.
    if eye_parts:
        corneas = bpy.data.collections.new("Corneas")
        for parts in eye_parts.values():
            corneas.objects.link(parts["Cornea"])
        wet = bpy.data.collections.new("EyeLightReceivers")
        for parts in eye_parts.values():
            wet.objects.link(parts["Cornea"])
            wet.objects.link(parts["TearLine"])
        data = bpy.data.lights.new("EyeLight", "AREA")
        data.shape = "RECTANGLE"
        data.size, data.size_y = 0.08, 0.12
        data.energy = 135.0                   # same radiance as a 0.12 x 0.18 m box at 60 W
        data.diffuse_factor = 0.0
        obj = bpy.data.objects.new("EyeLight", data)
        obj.visible_camera = False
        bpy.context.scene.collection.objects.link(obj)
        # 60 deg to the side, 12 deg up, 0.55 m away: the catchlight lands on the iris at about
        # 2 o'clock, clear of the pupil at every gaze in the sequence (measured with
        # tools/verify.py's detector; higher placements hide it under the upper lid).
        az, el = math.radians(60.0), math.radians(12.0)
        obj.location = midpoint + 0.55 * Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el),
                                                 math.sin(el)))
        obj.rotation_euler = (midpoint - obj.location).to_track_quat("-Z", "Y").to_euler()
        obj.light_linking.receiver_collection = wet
        for name in ("KeyLight", "FillLight"):
            bpy.data.objects[name].light_linking.receiver_collection = corneas
        for item in corneas.collection_objects:
            item.light_linking.link_state = "EXCLUDE"

    world = bpy.data.worlds.new("NeutralWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.10, 0.10, 0.11, 1.0)
    bg.inputs[1].default_value = 0.10
    # Camera-only backdrop: dark teal-grey, so dark hair keeps a readable silhouette (on black it
    # vanished and the head read as bald). Lighting still comes from the neutral world above.
    nt = world.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    backdrop = nt.nodes.new("ShaderNodeBackground")
    backdrop.inputs[0].default_value = (0.035, 0.075, 0.075, 1.0)
    is_cam = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(is_cam.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(backdrop.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    bpy.context.scene.world = world


def configure_render():
    scene = bpy.context.scene
    try:
        scene.render.engine = "CYCLES"
    except TypeError as err:
        raise SystemExit(f"Cycles unavailable: {err}")
    # 512 samples. No glossy filter: the refractive cornea needs sharp paths, or the catchlight
    # smears into a grey blob; the single linked eye light keeps it noise-free.
    scene.cycles.samples = 512
    scene.cycles.blur_glossy = 0.0
    scene.cycles.use_denoising = True
    scene.cycles.seed = 0                      # deterministic noise pattern
    scene.render.resolution_x = RESOLUTION_PX
    scene.render.resolution_y = RESOLUTION_PX
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    # Punchy keeps skin chroma that the other AgX looks wash out (measured against a reference
    # portrait photo: cheek colour, texture, contrast and stubble, see README).
    scene.view_settings.look = "AgX - Punchy"
    scene.view_settings.exposure = 0.2
    scene.unit_settings.system = "METRIC"


def build():
    clear_scene()
    rig, eyes = create_human()
    body = next(o for o in bpy.data.objects if o.type == "MESH" and o.name == "Human")
    for lashes in [o for o in bpy.data.objects if o.type == "MESH" and "eyelashes" in o.name]:
        bind_lashes_to_lids(lashes, body)
    for hair in [o for o in bpy.data.objects if o.type == "MESH" and HUMAN_INFO["hair"].split("/")[0] in o.name]:
        setup_hair_material(hair)
    left, right, r_l, r_r = eyeball_centres(eyes)
    setup_skin_material(body, left, right)
    midpoint = (left + right) / 2
    add_camera(midpoint)
    add_fixation_target(midpoint)
    eye_parts = install_anatomical_eyes(rig, eyes, body, (r_l + r_r) / 2)
    import hair_strands                      # tools/ is on sys.path (install_anatomical_eyes)
    cap = next(o for o in bpy.data.objects if o.type == "MESH" and HUMAN_INFO["hair"].split("/")[0] in o.name)
    hair_strands.build_hair(body, cap, midpoint + Vector((0.0, 0.07, 0.04)), midpoint)
    add_lighting(midpoint, eye_parts)
    configure_render()

    scene = bpy.context.scene
    scene["eye_center_L"] = tuple(left)
    scene["eye_center_R"] = tuple(right)
    scene["eye_midpoint"] = tuple(midpoint)
    scene["eye_radius_m"] = (r_l + r_r) / 2
    print(f"eye centres L={tuple(round(v, 4) for v in left)} R={tuple(round(v, 4) for v in right)} "
          f"radius_mm={(r_l + r_r) * 500:.2f}")
    return rig, eyes


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build()
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
        bpy.ops.file.pack_all()          # textures travel inside the .blend; no MPFB needed to render
        bpy.ops.wm.save_as_mainfile(filepath=bpy.path.abspath(out))
        print("saved", out)


if __name__ == "__main__":
    main()
