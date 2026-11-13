"""Read-only export of the production MakeHuman head for GNM fitting (never saves scene.blend).

    blender -b --factory-startup ../../scene.blend --python export_mh.py -- build/mh_head.npz

Exports, in GNM's frame (Y up, face +Z: gnm = (x, z, -y) of Blender world coordinates):
- evaluated Human mesh at rest pose (armature + subdivision; helper geometry masked), head only
  (z > neck cut), its triangles and the eye bone centres and gaze axes.
"""

import sys

import bpy
import numpy as np


def to_gnm(P):
    P = np.asarray(P, dtype=np.float64)
    return np.stack([P[:, 0], P[:, 2], -P[:, 1]], axis=1)


out = sys.argv[sys.argv.index("--") + 1]
h = bpy.data.objects["Human"]
rig = bpy.data.objects["Human.rig"]
for pb in rig.pose.bones:
    pb.location = (0, 0, 0)
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = (1, 0, 0, 0)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
me = h.evaluated_get(dg).to_mesh()
me.calc_loop_triangles()
co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co)
co = (np.array(h.matrix_world) @ np.c_[co.reshape(-1, 3), np.ones(len(me.vertices))].T).T[:, :3]
tris = np.empty(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tris)
tris = tris.reshape(-1, 3)
eye = {}
for s, b in (("left", "eye.L"), ("right", "eye.R")):
    bone = rig.data.bones[b]
    eye[s] = (np.array(rig.matrix_world @ bone.head_local), np.array(rig.matrix_world @ bone.tail_local))
neck_z = eye["left"][0][2] - 0.30                  # head and neck (GNM's neck reaches ~0.24 m below the eyes)
keep_v = co[:, 2] > neck_z
keep_t = keep_v[tris].all(1)
idx = np.nonzero(keep_v)[0]
remap = -np.ones(len(co), np.int64); remap[idx] = np.arange(len(idx))
np.savez(out, vertices=to_gnm(co[idx]), triangles=remap[tris[keep_t]],
         eye_left=to_gnm([eye["left"][0]])[0], eye_right=to_gnm([eye["right"][0]])[0],
         eye_left_tail=to_gnm([eye["left"][1]])[0], eye_right_tail=to_gnm([eye["right"][1]])[0])
print("EXPORTED", out, len(idx), "verts", int(keep_t.sum()), "tris")
h.evaluated_get(dg).to_mesh_clear()
