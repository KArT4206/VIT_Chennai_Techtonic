"""Blender side of the GNM expression prototype (hybrid: armature eye joints + exact shape keys).

Object space of GNM_Head and GNM_Rig is GNM's own frame (metres, Y up, face +Z, subject's left +X);
the objects carry a +90 deg X rotation so the head stands up in Blender. Therefore:
- shape keys store GNM offsets in GNM coordinates directly (exact; GNM expressions are linear and
  applied before skinning, the same order as Blender's shape keys -> armature);
- an eye rotation computed in GNM's frame (axis-angle about the eye centre, verified to be a
  world-frame rotation in GNM) is set on the pose bone as  basis = Rbone^-1 * Q * Rbone, with Rbone the
  bone's rest orientation in armature (= GNM) space.

Gaze is driven by the unchanged Phase 1B motion model (expression/motion.py): yaw + = subject's left
(+X), pitch + = up (+Y). Each eye aims at its own point FIX_DIST from the eye midpoint, so the eyes
converge. lid_follow keys follow the eye's elevation (value = degrees / 10), blink keys follow the
blink channel (Bell's dip is already in the pitch), brow keys follow brow_mm (value = mm / 2).
"""

import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "expression"))
import motion  # noqa: E402  (Phase 1B motion model, unchanged)

FIX_DIST = 0.35
ACTION_RIG = "Competition_GNM_Natural_Eye_Expression"
ACTION_KEYS = "Competition_GNM_Natural_Eye_Expression_ShapeKeys"


class GNMRig:
    def __init__(self, keys_npz):
        self.ob = bpy.data.objects["GNM_Head"]
        self.rig = bpy.data.objects["GNM_Rig"]
        d = np.load(keys_npz)
        self.d = d
        self.key_names = [str(k) for k in d["key_names"]]
        J = d["joints"]; names = [str(n) for n in d["joint_names"]]
        self.centre = {s: Vector(J[names.index(f"{s}_eye")].tolist()) for s in ("left", "right")}
        self.mid = (self.centre["left"] + self.centre["right"]) / 2
        V0 = np.empty(len(self.ob.data.vertices) * 3, np.float32)
        self.ob.data.vertices.foreach_get("co", V0)
        V0 = V0.reshape(-1, 3)
        gi = self.ob.vertex_groups
        def centroid(group):
            idx = gi[group].index
            pts = [V0[v.index] for v in self.ob.data.vertices if any(g.group == idx for g in v.groups)]
            return Vector(np.mean(pts, axis=0).tolist())
        self.primary = {}
        for s in ("left", "right"):
            pu_idx = [v.index for v in self.ob.data.vertices
                      if any(g.group == gi["gnm_pupils"].index for g in v.groups)
                      and any(g.group == gi[f"gnm_{s}_eye"].index for g in v.groups)]
            pu = Vector(V0[pu_idx].mean(0).tolist())
            self.primary[s] = (pu - self.centre[s]).normalized()

    # ---------------------------------------------------------------- shape keys
    def ensure_keys(self):
        me = self.ob.data
        if me.shape_keys is None:
            self.ob.shape_key_add(name="Basis", from_mix=False)
        basis = np.empty(len(me.vertices) * 3, np.float32)
        me.shape_keys.key_blocks["Basis"].data.foreach_get("co", basis)
        for name, off in zip(self.key_names, self.d["key_offsets"]):
            kb = me.shape_keys.key_blocks.get(name) or self.ob.shape_key_add(name=name, from_mix=False)
            kb.data.foreach_set("co", basis + off.reshape(-1))
            kb.slider_min, kb.slider_max = (-1.5, 1.5) if name.startswith("lid_follow") else (0.0, 2.0)
        return me.shape_keys

    def set_keys(self, **w):
        kbs = self.ob.data.shape_keys.key_blocks
        for n in self.key_names:
            kbs[n].value = float(w.get(n, 0.0))

    # ---------------------------------------------------------------- gaze
    def target(self, yaw, pitch, dist=FIX_DIST):
        y, p = math.radians(yaw), math.radians(pitch)
        return self.mid + dist * Vector((math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)))

    def eye_rotation(self, side, target):
        d = (target - self.centre[side]).normalized()
        return self.primary[side].rotation_difference(d)            # GNM-frame quaternion

    def set_eye_quat(self, side, q):
        pb = self.rig.pose.bones[f"{side}_eye"]
        r = pb.bone.matrix_local.to_3x3()
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (r.inverted() @ q.to_matrix() @ r).to_quaternion()

    def set_eye_rotvec(self, side, rv):
        v = Vector(rv.tolist())
        q = Quaternion(v.normalized(), v.length) if v.length > 1e-12 else Quaternion()
        self.set_eye_quat(side, q)

    def elevation(self, side, target):
        d = (target - self.centre[side]).normalized()
        d0 = (self.target(0, 0) - self.centre[side]).normalized()
        return math.degrees(math.asin(max(-1, min(1, d.y))) - math.asin(max(-1, min(1, d0.y))))

    # ---------------------------------------------------------------- motion sample -> pose
    def apply(self, s, dist=FIX_DIST):
        t = self.target(s["yaw_deg"], s["pitch_deg"], dist)
        w = {}
        for side, L in (("left", "L"), ("right", "R")):
            self.set_eye_quat(side, self.eye_rotation(side, t))
            w[f"lid_follow_{L}"] = self.elevation(side, t) / 10.0 * (1.0 - s["blink"])
            w[f"blink_{L}"] = s["blink"]
            w[f"brow_raise_{L}"] = s[f"brow_{L}_mm"] / 2.0
        self.set_keys(**w)
        bpy.context.view_layer.update()
        return w

    def bake(self, samples, frame_start=1):
        """Key every frame: eye bone quaternions on the rig, key values on the Key datablock."""
        key = self.ensure_keys()
        for idb, name in ((self.rig, ACTION_RIG), (key, ACTION_KEYS)):
            old = bpy.data.actions.get(name)
            if old:
                bpy.data.actions.remove(old)
            if idb.animation_data is None:
                idb.animation_data_create()
            act = bpy.data.actions.new(name)
            act.use_fake_user = True
            idb.animation_data.action = act
        prev = {}
        for s in samples:
            f = frame_start + s["frame"]
            self.apply(s)
            for side in ("left", "right"):
                pb = self.rig.pose.bones[f"{side}_eye"]
                q = pb.rotation_quaternion.copy()
                if side in prev and prev[side].dot(q) < 0:
                    q.negate(); pb.rotation_quaternion = q
                prev[side] = q
                pb.keyframe_insert("rotation_quaternion", frame=f)
            for n in self.key_names:
                key.key_blocks[n].keyframe_insert("value", frame=f)
        for idb in (self.rig, key):
            for fc in fcurves(idb.animation_data.action):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        return bpy.data.actions[ACTION_RIG], bpy.data.actions[ACTION_KEYS]

    # ---------------------------------------------------------------- verification against GNM
    def evaluated_vertices(self):
        dg = bpy.context.evaluated_depsgraph_get()
        me = self.ob.evaluated_get(dg).to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float64); me.vertices.foreach_get("co", co)
        self.ob.evaluated_get(dg).to_mesh_clear()
        return co.reshape(-1, 3)

    def verify_against_gnm(self):
        """Pose with the reference key weights and GNM's own eye rotation vectors; compare to GNM."""
        saved = [(m, m.show_viewport) for m in self.ob.modifiers if m.type != "ARMATURE"]
        for m, _ in saved:
            m.show_viewport = False
        errs = []
        for i in range(len(self.d["ref_vertices"])):
            self.set_keys(**{n: float(v) for n, v in zip(self.key_names, self.d["ref_weights"][i])})
            names = [str(n) for n in self.d["joint_names"]]
            for side in ("left", "right"):
                self.set_eye_rotvec(side, self.d["ref_rotvecs"][i][names.index(f"{side}_eye")])
            bpy.context.view_layer.update()
            errs.append(float(np.abs(self.evaluated_vertices() - self.d["ref_vertices"][i]).max()))
        for m, v in saved:
            m.show_viewport = v
        self.set_keys()
        for side in ("left", "right"):
            self.set_eye_quat(side, Quaternion())
        return errs


def fcurves(action):
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out
