"""Deterministic eye-gaze controller and renderer for the Track 1 scene.

Usage (from the bundle root):
    blender -b scene.blend -P wrapper/eyes.py                          # 10 clockwise renders + metadata.json
    blender -b scene.blend -P wrapper/eyes.py -- --move 1 0 --out out  # one render looking right
    blender -b scene.blend -P wrapper/eyes.py -- --reset --out out     # one render looking at the centre

Inside Blender's Python console (with scene.blend open):
    import sys; sys.path.append("<bundle>/wrapper"); import eyes
    eyes.move(0.5, -0.3); eyes.render("frame.png"); eyes.reset()

Conventions
    Inputs h, v are normalised to [-1, +1] and clamped.
    h > 0 moves the pupils towards the RIGHT of the rendered image, v > 0 moves them UP.
    (h, v) maps to a fixation target on the plane 35 cm in front of the eye midpoint,
    displaced by (h, v) * 5 cm. Each eyeball rotates about its own centre to look at it,
    so the eyes converge naturally. Rotations are the shortest arc from the primary gaze
    direction (Listing's law), so the eyes never twist about their gaze axis.
    World frame: Blender world, metres, +Z up, the face looks along -Y.
"""

import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector
from bpy_extras.object_utils import world_to_camera_view

FIXATION_DISTANCE_M = 0.35
MOTION_BOUND_M = 0.05
SEQUENCE_FRAMES = 10
EYE_BONES = {"L": "eye.L", "R": "eye.R"}
# Lid-gaze coupling: in real eyes the upper lid follows vertical gaze closely and the lower lid
# partly, so the lid margin stays near the top of the iris instead of covering the pupil.
UPPER_LID_BONES = {"L": "orbicularis03.L", "R": "orbicularis03.R"}
LOWER_LID_BONES = {"L": "orbicularis04.L", "R": "orbicularis04.R"}
UPPER_LID_GAIN = 1.1
# Upper-lid rest offset (deg, + lowers). With the fuller adult face the lid already rests over the
# top of the iris; lifting it 2 deg and letting it follow upward gaze fully (gain 1.1) keeps the
# pupil uncovered at every gaze (measured: worst detector error 1.29 px on the 10-frame ring).
UPPER_LID_REST_DEG = -2.0
LOWER_LID_GAIN = 0.35
TARGET_NAME = "FixationTarget"

_state = {}


# --------------------------------------------------------------------------- scene lookup

def _rig():
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE" and "eye.L" in o.data.bones]
    if len(rigs) != 1:
        raise RuntimeError(f"expected one armature with eye bones, found {len(rigs)}")
    return rigs[0]


def _clear_eye_pose():
    rig = _rig()
    for side in EYE_BONES:
        for name in (EYE_BONES[side], UPPER_LID_BONES[side], LOWER_LID_BONES[side]):
            pb = rig.pose.bones[name]
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = Quaternion()
            pb.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()


def _eye_centre(side):
    """Rotation pivot of an eye in world space (the eye bone head, i.e. the eyeball centre)."""
    rig = _rig()
    return rig.matrix_world @ rig.data.bones[EYE_BONES[side]].head_local


def _iris(side):
    obs = [o for o in bpy.data.objects if o.name == f"Eye{side}.Iris"]
    if len(obs) != 1:
        raise RuntimeError(f"expected one object Eye{side}.Iris, found {len(obs)}")
    return obs[0]


def mesh_pupils():
    """World positions of both anatomical pupil centres (centre of the pupil opening in the iris)."""
    bpy.context.view_layer.update()
    return {side: _iris(side).matrix_world @ Vector(_iris(side)["pupil_local"]) for side in EYE_BONES}


def _calibrate():
    """Measure each eye's primary gaze axis (centre -> painted pupil) in the rest pose."""
    if _state.get("calibrated"):
        return
    _clear_eye_pose()
    pupils = mesh_pupils()
    for side in EYE_BONES:
        offset = pupils[side] - _eye_centre(side)
        _state[f"axis_{side}"] = offset.normalized()
        _state[f"pupil_depth_{side}"] = offset.length

    scene = bpy.context.scene
    if "eye_midpoint" in scene:
        _state["midpoint"] = Vector(scene["eye_midpoint"])
    else:
        _state["midpoint"] = (_eye_centre("L") + _eye_centre("R")) / 2
    _state["calibrated"] = True
    _state["h"], _state["v"] = 0.0, 0.0


# --------------------------------------------------------------------------- gaze

def _clamp(x, name):
    try:
        x = float(x)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {x!r}") from None
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite, got {x!r}")
    return max(-1.0, min(1.0, x))


def target_point(h, v):
    """Fixation target for normalised input (h, v), in world space."""
    mid = _state["midpoint"]
    return mid + Vector((h * MOTION_BOUND_M, -FIXATION_DISTANCE_M, v * MOTION_BOUND_M))


def _world_rotation(side, target):
    """Shortest-arc rotation taking the primary gaze axis to the direction of the target."""
    desired = (target - _eye_centre(side)).normalized()
    return _state[f"axis_{side}"].rotation_difference(desired)


def _set_bone_world_rotation(bone_name, q_world):
    """Pose a bone so it is rotated by q_world (world frame) about its head, relative to rest."""
    rig = _rig()
    pb = rig.pose.bones[bone_name]
    rest = (rig.matrix_world @ pb.bone.matrix_local).to_3x3().normalized()
    basis = rest.inverted() @ q_world.to_matrix() @ rest
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = basis.to_quaternion()


def _elevation(side, target):
    """Vertical gaze angle (radians, up positive) relative to looking at the centre target."""
    d = (target - _eye_centre(side)).normalized()
    d0 = (target_point(0.0, 0.0) - _eye_centre(side)).normalized()
    return math.asin(max(-1.0, min(1.0, d.z))) - math.asin(max(-1.0, min(1.0, d0.z)))


def lid_rotations(side, target):
    """World rotations of the upper and lower lid for the current gaze (about the world X axis)."""
    e = _elevation(side, target)
    x = Vector((1.0, 0.0, 0.0))          # rotating about -X lifts, about +X lowers
    rest = math.radians(UPPER_LID_REST_DEG)
    return Quaternion(x, rest - UPPER_LID_GAIN * e), Quaternion(x, -LOWER_LID_GAIN * e)


def move(h, v):
    """Point both eyes at the target for normalised input (h, v) in [-1, 1]; the lids follow."""
    _calibrate()
    h, v = _clamp(h, "h"), _clamp(v, "v")
    target = target_point(h, v)
    for side in EYE_BONES:
        _set_bone_world_rotation(EYE_BONES[side], _world_rotation(side, target))
        upper, lower = lid_rotations(side, target)
        _set_bone_world_rotation(UPPER_LID_BONES[side], upper)
        _set_bone_world_rotation(LOWER_LID_BONES[side], lower)
    obj = bpy.data.objects.get(TARGET_NAME)
    if obj is not None:
        obj.location = target
    bpy.context.view_layer.update()
    _state["h"], _state["v"] = h, v
    return state()


def reset():
    """Return both eyes to the centre fixation point (35 cm straight ahead)."""
    return move(0.0, 0.0)


# --------------------------------------------------------------------------- measurement

def _pupil_world(side):
    q = _world_rotation(side, target_point(_state["h"], _state["v"]))
    return _eye_centre(side) + q @ (_state[f"axis_{side}"] * _state[f"pupil_depth_{side}"])


def camera_matrices():
    """OpenCV-convention intrinsics K (3x3) and world-to-camera extrinsics [R|t] (3x4)."""
    scene = bpy.context.scene
    cam = scene.camera
    w = scene.render.resolution_x * scene.render.resolution_percentage / 100
    hgt = scene.render.resolution_y * scene.render.resolution_percentage / 100
    sensor = cam.data.sensor_width if cam.data.sensor_fit != "VERTICAL" else cam.data.sensor_height
    f_px = cam.data.lens / sensor * max(w, hgt)
    k = [[f_px, 0.0, w / 2], [0.0, f_px, hgt / 2], [0.0, 0.0, 1.0]]
    # Blender camera looks down -Z with +Y up; OpenCV looks down +Z with +Y down.
    flip = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
    r_wc = cam.matrix_world.to_3x3().normalized().transposed()
    r = flip @ r_wc
    t = -(r @ cam.matrix_world.translation)
    rt = [list(r[i]) + [t[i]] for i in range(3)]
    return k, rt


def _cornea(side):
    """Corneal sphere (centre, radius) in world space and its refractive index, for the current pose."""
    iris = _iris(side)
    d = iris["eye_dims"]
    centre = iris.matrix_world @ Vector((0.0, 0.0, d["cornea_centre_z"]))
    return centre, d["cornea_r"], iris["cornea_ior"]


def _refract(d, n, eta):
    """Snell refraction of unit direction d at a surface with unit normal n facing the incoming ray."""
    cos_i = -n.dot(d)
    k = 1.0 - eta * eta * (1.0 - cos_i * cos_i)
    return (eta * d + (eta * cos_i - math.sqrt(k)) * n).normalized()


def _trace_to_iris(origin, direction, side, pupil, axis):
    """Follow a camera ray through the cornea; return where it meets the iris plane (or None)."""
    c, r, ior = _cornea(side)
    oc = origin - c
    b = oc.dot(direction)
    disc = b * b - (oc.dot(oc) - r * r)
    if disc < 0:
        return None, None
    hit = origin + direction * (-b - math.sqrt(disc))
    inside = _refract(direction, (hit - c).normalized(), 1.0 / ior)
    denom = inside.dot(axis)
    if abs(denom) < 1e-9:
        return None, None
    return hit + inside * ((pupil - hit).dot(axis) / denom), hit


def apparent_pupil(side, pupil):
    """Pixel where the pupil centre is SEEN: the camera ray that, refracted by the cornea, lands on it.

    A real cornea magnifies and shifts the pupil (the 'entrance pupil'); the rendered image shows
    that, so the 2D ground truth must too. Solved with Newton's method on the pixel coordinates.
    Returns (pixel [u, v], 3D point where that ray crosses the corneal surface).
    """
    scene = bpy.context.scene
    k, rt = camera_matrices()
    kinv = Matrix(k).inverted()
    r_wc = Matrix([row[:3] for row in rt])
    origin = scene.camera.matrix_world.translation
    axis = (_iris(side).matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
    ex = axis.orthogonal().normalized()
    ey = axis.cross(ex)

    def residual(u, v):
        d = (r_wc.transposed() @ (kinv @ Vector((u, v, 1.0)))).normalized()
        x, hit = _trace_to_iris(origin, d, side, pupil, axis)
        if x is None:
            raise RuntimeError("camera ray missed the cornea while solving the apparent pupil")
        e = x - pupil
        return Vector((e.dot(ex), e.dot(ey))), hit

    u, v = _project(pupil)
    for _ in range(30):
        f, hit = residual(u, v)
        if f.length < 1e-7:
            break
        h = 0.05                      # px; finite-difference step well above float32 noise
        fu, _ = residual(u + h, v)
        fv, _ = residual(u, v + h)
        jac = Matrix((((fu - f).x / h, (fv - f).x / h), ((fu - f).y / h, (fv - f).y / h)))
        step = jac.inverted() @ f
        u, v = u - step.x, v - step.y
    f, hit = residual(u, v)
    # mathutils is single precision (~0.1 um at 1.5 m); 1 um is ~0.004 px here.
    if f.length > 1e-6:
        raise RuntimeError(f"apparent pupil did not converge ({f.length * 1000:.4f} mm)")
    return [u, v], hit


def _project(p):
    scene = bpy.context.scene
    ndc = world_to_camera_view(scene, scene.camera, p)
    return [ndc.x * scene.render.resolution_x, (1.0 - ndc.y) * scene.render.resolution_y]


def _euler_deg(q):
    return [round(math.degrees(a), 4) for a in q.to_euler("XYZ")]


def state():
    """Current gaze state: inputs, world rotations and 2D pupil centres (pixels, origin top-left)."""
    target = target_point(_state["h"], _state["v"])
    out = {"input": {"h": round(_state["h"], 6), "v": round(_state["v"], 6)},
           "fixation_target": [round(c, 6) for c in target]}
    for side in EYE_BONES:
        q = _world_rotation(side, target)
        out[f"eye_rotation_{side}"] = _euler_deg(q)
        out[f"eye_rotation_quat_{side}"] = [round(c, 6) for c in q]
        pupil = _pupil_world(side)
        seen, on_cornea = apparent_pupil(side, pupil)
        out[f"pupil_center_2D_{side}"] = [round(c, 3) for c in seen]
        out[f"pupil_center_3D_{side}"] = [round(c, 6) for c in pupil]
        out[f"pupil_center_cornea_3D_{side}"] = [round(c, 7) for c in on_cornea]
        out[f"pupil_center_2D_unrefracted_{side}"] = [round(c, 3) for c in _project(pupil)]
    return out


# --------------------------------------------------------------------------- rendering

def use_best_device():
    """Render on a GPU when one is available (Metal, OptiX, CUDA, HIP, oneAPI), else on the CPU."""
    scene = bpy.context.scene
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return "CPU"
    for backend in ("METAL", "OPTIX", "CUDA", "HIP", "ONEAPI"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = "GPU"
            return backend
    scene.cycles.device = "CPU"
    return "CPU"


def render(path):
    """Render the current gaze to a PNG at `path` and return the gaze state."""
    _calibrate()
    scene = bpy.context.scene
    scene.render.filepath = os.path.abspath(path)
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return state()


def sequence_inputs(n=SEQUENCE_FRAMES):
    """Clockwise sampling theta_k = 2*pi*k/n, h = sin(theta), v = cos(theta), starting at the top."""
    for k in range(n):
        theta = 2.0 * math.pi * k / n
        yield k, theta, math.sin(theta), math.cos(theta)


def render_sequence(out_dir):
    """Render the 10 clockwise frames to <out_dir>/renders and write <out_dir>/metadata.json."""
    _calibrate()
    renders = os.path.join(out_dir, "renders")
    os.makedirs(renders, exist_ok=True)
    k_mat, rt = camera_matrices()
    records = []
    for k, theta, h, v in sequence_inputs():
        move(h, v)
        name = f"frame_{k:02d}.png"
        s = render(os.path.join(renders, name))
        rec = {"frame": k, "file": f"renders/{name}", "theta": round(theta, 6)}
        rec.update(s)
        rec["camera_matrix"] = k_mat
        rec["camera_extrinsic_world_to_cam"] = rt
        records.append(rec)
        print(f"[eyes] frame {k}: h={h:+.3f} v={v:+.3f} -> {name}", flush=True)
    reset()
    meta = {
        "conventions": {
            "inputs": "h, v normalised to [-1, 1]; h>0 pupils to image right, v>0 pupils up",
            "sampling": "theta_k = 2*pi*k/10, h = sin(theta_k), v = cos(theta_k), k = 0..9, clockwise from top",
            "eye_rotation": "world-frame rotation from primary gaze, Euler XYZ degrees (quaternion w,x,y,z also given)",
            "pupil_center_2D": "pixels, origin top-left, x right, y down, 1024x1024 image",
            "camera_matrix": "OpenCV intrinsics K; camera_extrinsic_world_to_cam is [R|t], world metres",
            "world_frame": "Blender world, metres, +Z up, face looks along -Y",
        },
        "fixation_distance_m": FIXATION_DISTANCE_M,
        "motion_bound_m": MOTION_BOUND_M,
        "camera_distance_m": round((bpy.context.scene.camera.location - _state["midpoint"]).length, 6),
        "eye_midpoint": [round(c, 6) for c in _state["midpoint"]],
        "frames": records,
    }
    with open(os.path.join(out_dir, "metadata.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    return meta


# --------------------------------------------------------------------------- command line

def _main(argv):
    import argparse
    parser = argparse.ArgumentParser(prog="eyes.py")
    parser.add_argument("--out", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        help="output folder (default: the bundle root)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--move", nargs=2, type=float, metavar=("H", "V"), help="render one gaze")
    group.add_argument("--reset", action="store_true", help="render the centre gaze")
    parser.add_argument("--samples", type=int, help="override Cycles samples (default: scene setting)")
    parser.add_argument("--cpu", action="store_true", help="force CPU rendering")
    args = parser.parse_args(argv)

    print("[eyes] render device:", "CPU" if args.cpu else use_best_device(), flush=True)
    if args.samples:
        bpy.context.scene.cycles.samples = args.samples
    os.makedirs(args.out, exist_ok=True)
    if args.move or args.reset:
        h, v = args.move if args.move else (0.0, 0.0)
        move(h, v)
        name = "reset" if args.reset else f"move_h{h:+.2f}_v{v:+.2f}"
        s = render(os.path.join(args.out, name + ".png"))
        with open(os.path.join(args.out, name + ".json"), "w") as fh:
            json.dump(s, fh, indent=2)
        print(json.dumps(s, indent=2))
    else:
        render_sequence(args.out)


if __name__ == "__main__":
    _main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
