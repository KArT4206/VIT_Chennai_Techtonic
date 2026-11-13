"""Render the 3D Scan Store Free HD Head exactly as the vendor authored it (original geometry, maps,
materials, HDRI and light), on the Apple M5 Metal GPU.

    blender -b --factory-startup --disable-autoexec "extracted/Blender/Blender Scene.blend" \
        --python scan_render_original.py -- OUT_DIR SAMPLES COPY_BLEND

Only render settings change (device, samples 4096 -> SAMPLES, resolution) and cameras are ADDED for
the requested views; the vendor's file is never saved (a copy is written to COPY_BLEND).
Auto-run scripts are disabled when opening the vendor file.
"""

import os
import sys
import time

import bpy
from mathutils import Vector

out, spp, copy_blend = sys.argv[sys.argv.index("--") + 1:]
spp = int(spp); os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
p = bpy.context.preferences.addons["cycles"].preferences
p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
sc.cycles.samples = spp
print("VENDOR_SETTINGS view", sc.view_settings.view_transform, "| samples (vendor 4096) ->", spp)


def world_bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


eyeL = sum(world_bbox(bpy.data.objects["Lens Left"]), Vector()) / 2
eyeR = sum(world_bbox(bpy.data.objects["Lens Right"]), Vector()) / 2
mid = (eyeL + eyeR) / 2
hmin, hmax = world_bbox(bpy.data.objects["Head"])
print("GEOM eye L", tuple(round(c, 2) for c in eyeL), "R", tuple(round(c, 2) for c in eyeR),
      "IPD (scene units, cm)", round((eyeL - eyeR).length, 2), "head bbox", tuple(round(c, 1) for c in hmin), tuple(round(c, 1) for c in hmax))
times = {}


def shot(name, cam, rx, ry):
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = rx, ry, 100
    sc.render.filepath = os.path.join(out, name)
    t = time.time(); bpy.ops.render.render(write_still=True); times[name] = round(time.time() - t, 1)
    print("RENDERED", name, times[name], "s", flush=True)


def add_cam(name, pos, target, lens, dof_target=None, fstop=8.0):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 1.0
    co = bpy.data.objects.new(name, cd); sc.collection.objects.link(co)
    co.location = pos; co.rotation_euler = (target - pos).to_track_quat("-Z", "Y").to_euler()
    if dof_target is not None:
        cd.dof.use_dof = True; cd.dof.focus_distance = (dof_target - pos).length; cd.dof.aperture_fstop = fstop
    return co


fwd = Vector((0, -1, 0)); right = Vector((1, 0, 0)); up = Vector((0, 0, 1))
face_c = mid - up * 3.0
cams = {
    "scan_face_front.png": (add_cam("V_front", mid + fwd * 60 - up * 2, face_c, 70, mid), 1024, 1024),
    "scan_three_quarter.png": (add_cam("V_34", mid + fwd * 46 - right * 36 + up * 2, face_c, 70, mid), 1024, 1024),
    "scan_eyes_closeup.png": (add_cam("V_eyes", mid + fwd * 32, mid, 100, mid, 16), 1024, 1024),
    "scan_skin_closeup.png": (add_cam("V_skin", mid + fwd * 20 - right * 3 - up * 4, mid - up * 4.5 - right * 1.2, 100,
                                      mid - up * 4.5 - right * 1.2 + fwd * 6, 16), 2048, 2048),
    "scan_brows_lashes.png": (add_cam("V_brow", mid + fwd * 16 + right * 6 + up * 1.5, eyeL + up * 1.0, 100, eyeL + up * 1.0 + fwd * 1.5, 16), 1024, 1024),
}
for name, (cam, rx, ry) in cams.items():
    shot(name, cam, rx, ry)
shot("vendor_full_shot.png", bpy.data.objects["Full Shot"], 1400, 608)
shot("vendor_eyes_shot.png", bpy.data.objects["Eyes Shot"], 1400, 608)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(copy_blend), copy=True, relative_remap=True)
print("SAVED_COPY", copy_blend, times)
