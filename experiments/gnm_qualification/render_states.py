"""Render named GNM states (exact vertex arrays) as labelled eye-region previews.

    blender -b --factory-startup gnm_head_test.blend --python render_states.py -- build/states_preview.npz OUTDIR

The armature modifier is disabled here because the vertex arrays already include GNM's own
joint rotations (computed by GNM, not by Blender).
"""

import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gnm_look  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
data = np.load(a[0])
out = a[1]
os.makedirs(out, exist_ok=True)
scene = bpy.context.scene
print("RENDER_DEVICE", gnm_look.metal(scene, 64))
ob = bpy.data.objects["GNM_Head"]
for mod in ob.modifiers:
    mod.show_render = mod.show_viewport = mod.type != "ARMATURE"
gnm_look.materials(ob)
rig = bpy.data.objects["GNM_Rig"]
mid = ob.matrix_world @ ((rig.data.bones["left_eye"].head_local + rig.data.bones["right_eye"].head_local) / 2)
gnm_look.lights(scene, mid)
cam = gnm_look.camera(scene, mid + Vector((0, -0.40, -0.004)), mid + Vector((0, 0, 0.004)), 105)
for i, name in enumerate(data["names"]):
    ob.data.vertices.foreach_set("co", data["vertices"][i].reshape(-1))
    ob.data.update()
    gnm_look.label(scene, cam, str(name))
    scene.render.filepath = os.path.join(out, f"{i:02d}.png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", i, name)
