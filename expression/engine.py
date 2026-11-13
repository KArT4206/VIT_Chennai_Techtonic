"""Blender side of the expression system: poses the rig from motion.py samples and keys Actions.

It reuses wrapper/eyes.py for every eye rotation (same calibrated primary axes, same shortest-arc
rotation about each eyeball's own centre, same lid gains), so the evaluator API and its geometry are
unchanged. Nothing here edits scene.blend on disk.

Controls used (all verified by rendering):
    eye.L / eye.R                    eyeball rotation about the eye centre (bone head = centre)
    orbicularis03.L/R                upper lid, rotates about the eye centre; +world-X rotation closes
    orbicularis04.L/R                lower lid, same pivot
    oculi01.L/R                      brow: moves the eyebrow mesh and the brow skin together
"""

import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "wrapper"))
sys.path.insert(0, _HERE)
import eyes      # noqa: E402  (the evaluator wrapper)
import motion    # noqa: E402

# Lid angles (deg, world X, + closes) that fully close the eye at any tested gaze without the
# lashes crossing: measured 24-32 deg closed cleanly, 20 deg left a slit at down-gaze, 40+ deg
# pushed the lashes through the lower lid.
UPPER_CLOSED_DEG = 27.0
LOWER_CLOSED_DEG = -2.5
BROW_BONES = {"L": "oculi01.L", "R": "oculi01.R"}
DOWN_KNEE_DEG = 8.0
DOWN_GAIN_BEYOND = 0.55

ACTION_NAMES = {
    "left": "Competition_Look_Left",
    "right": "Competition_Look_Right",
    "generate": "Competition_Natural_Eye_Expression",
}
X = Vector((1.0, 0.0, 0.0))


def target_for(yaw_deg, pitch_deg, dist_m):
    """World fixation point for a cyclopean gaze direction from the eye midpoint."""
    eyes._calibrate()
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    d = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
    return eyes._state["midpoint"] + d * dist_m


def _lid_angles(side, target, blink):
    """Upper/lower lid world angles (deg): eyes.py's gaze-following lids, blended to closed."""
    e = eyes._elevation(side, target)
    e_deg = math.degrees(e)
    # Identical to eyes.py inside its +-8 deg calibration range. Below -8 deg the upper lid follows
    # at a lower gain: with 1.1 it nearly shut the eye at -18 deg (rendered), real lids keep the
    # pupil visible in down-gaze.
    if e_deg < -DOWN_KNEE_DEG:
        follow = eyes.UPPER_LID_GAIN * -DOWN_KNEE_DEG + DOWN_GAIN_BEYOND * (e_deg + DOWN_KNEE_DEG)
    else:
        follow = eyes.UPPER_LID_GAIN * e_deg
    upper = eyes.UPPER_LID_REST_DEG - follow
    lower = -math.degrees(eyes.LOWER_LID_GAIN * e)
    upper += (UPPER_CLOSED_DEG - upper) * blink
    lower += (LOWER_CLOSED_DEG - lower) * blink
    return upper, lower


def _set_brow(side, dz_mm):
    rig = eyes._rig()
    pb = rig.pose.bones[BROW_BONES[side]]
    rest = (rig.matrix_world @ pb.bone.matrix_local).to_3x3().normalized()
    pb.location = rest.inverted() @ Vector((0.0, 0.0, dz_mm / 1000.0))


def apply(sample):
    """Pose the rig for one motion sample. Returns the target point."""
    target = target_for(sample["yaw_deg"], sample["pitch_deg"], sample["dist_m"])
    for side in eyes.EYE_BONES:
        eyes._set_bone_world_rotation(eyes.EYE_BONES[side], eyes._world_rotation(side, target))
        up, lo = _lid_angles(side, target, sample["blink"])
        eyes._set_bone_world_rotation(eyes.UPPER_LID_BONES[side], Quaternion(X, math.radians(up)))
        eyes._set_bone_world_rotation(eyes.LOWER_LID_BONES[side], Quaternion(X, math.radians(lo)))
        _set_brow(side, sample[f"brow_{side}_mm"])
    obj = bpy.data.objects.get(eyes.TARGET_NAME)
    if obj is not None:
        obj.location = target
    bpy.context.view_layer.update()
    return target


def _bones():
    names = []
    for side in "LR":
        names += [eyes.EYE_BONES[side], eyes.UPPER_LID_BONES[side], eyes.LOWER_LID_BONES[side], BROW_BONES[side]]
    return names


def bake_action(name, samples, frame_start=1):
    """Key every frame of `samples` into a new Action on the rig (rotation + brow location)."""
    rig = eyes._rig()
    eyes._calibrate()
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    if rig.animation_data is None:
        rig.animation_data_create()
    rig.animation_data.action = None
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    rig.animation_data.action = action
    prev = {}
    for s in samples:
        f = frame_start + s["frame"]
        apply(s)
        for bn in _bones():
            pb = rig.pose.bones[bn]
            q = pb.rotation_quaternion.copy()
            if bn in prev and prev[bn].dot(q) < 0:       # keep quaternion keys on one hemisphere
                q.negate()
                pb.rotation_quaternion = q
            prev[bn] = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if bn in BROW_BONES.values():
                pb.keyframe_insert("location", frame=f)
    for fc in _fcurves(action):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"                   # samples are dense; no Bezier overshoot
    return action


def _fcurves(action):
    """F-curves of an action (Blender 4.4+ layered actions, or the legacy list)."""
    if hasattr(action, "fcurves") and len(getattr(action, "fcurves", [])):
        return list(action.fcurves)
    out = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                out += list(bag.fcurves)
    return out


def prepare_render(samples=None, persistent=True):
    scene = bpy.context.scene
    device = eyes.use_best_device()
    if samples:
        scene.cycles.samples = samples
    scene.render.use_persistent_data = persistent
    scene.render.fps = motion.FPS
    scene.render.image_settings.file_format = "PNG"
    return device
