"""Compute named GNM states (exact GNM vertex positions) for previews and tests.

    PYTHONPATH=vendor/GNM env/bin/python gnm_states.py build/gnm_controls.npz build/states_preview.npz

Gaze uses GNM's own eye joints: with identity joint orientations the axis-angle vector of an eye
joint is a world-frame rotation about that eye's centre (verified, error 5.6e-17). GNM frame:
Y up, face looks +Z, subject's left = +X. Looking toward (yaw, pitch) is the rotation taking +Z to
d = (sin yaw cos pitch, sin pitch, cos yaw cos pitch); each eye aims at its own target point, so
the eyes converge.
"""

import sys

import numpy as np

import gnm_expr as gx

FIX_DIST = 0.35   # m from the eye midpoint (Track 1 fixation distance)


def aim_rotvec(eye_centre, target, primary):
    """Axis-angle (shortest arc) taking the eye's primary axis to the direction of target."""
    d = target - eye_centre
    d /= np.linalg.norm(d)
    a = primary / np.linalg.norm(primary)
    axis = np.cross(a, d)
    s = np.linalg.norm(axis)
    if s < 1e-12:
        return np.zeros(3)
    return axis / s * np.arctan2(s, float(a @ d))


def gaze_rotations(m, yaw_deg, pitch_deg, dist=FIX_DIST):
    """Rotations array (J,3) aiming both eyes at a point dist from the eye midpoint in direction (yaw, pitch)."""
    R = np.zeros((m.g.num_joints, 3))
    mid = (m.eye["left"]["centre"] + m.eye["right"]["centre"]) / 2
    y, p = np.radians(yaw_deg), np.radians(pitch_deg)
    target = mid + dist * np.array([np.sin(y) * np.cos(p), np.sin(p), np.cos(y) * np.cos(p)])
    for side in ("left", "right"):
        c = m.eye[side]["centre"]
        pu = m.V0[m.mask["pupils"] & m.mask[f"{side}_eye"]].mean(0)
        R[m.joints.index(f"{side}_eye")] = aim_rotvec(c, target, pu - c)
    return R, target


def neutral_rotations(m):
    """Neutral = both eyes fixating the centre target at 35 cm (converged), not the raw rest pose."""
    return gaze_rotations(m, 0.0, 0.0)[0]


def expression(ctrl, **w):
    e = np.zeros(383)
    for k, v in w.items():
        e = e + v * ctrl[k]
    return e


def preview_states(m, C):
    both = lambda n, w: {f"{n}_left": w, f"{n}_right": w}
    S = [
        ("neutral", {}, (0, 0)),
        ("left eye closed (blink_left 1.0)", {"blink_left": 1.0}, (0, 0)),
        ("right eye closed (blink_right 1.0)", {"blink_right": 1.0}, (0, 0)),
        ("both closed (blink 1.0)", both("blink", 1.0), (0, 0)),
        ("partial closure (blink 0.5)", both("blink", 0.5), (0, 0)),
        ("squint (semantic, eye blocks)", both("squint", 1.0), (0, 0)),
        ("surprise (semantic, eye blocks)", both("surprise", 1.0), (0, 0)),
        ("raised upper lids (lid_follow +8)", both("lid_follow", 8.0), (0, 0)),
        ("lowered upper lids (lid_follow -8)", both("lid_follow", -8.0), (0, 0)),
        ("upward gaze 12 deg + lids follow", both("lid_follow", 12.0), (0, 12)),
        ("downward gaze 12 deg + lids follow", both("lid_follow", -12.0), (0, -12)),
        ("brow raise 3 mm (brow_raise 6.5)", both("brow_raise", 6.5), (0, 0)),
    ]
    names, Vs = [], []
    for label, w, (yaw, pitch) in S:
        R, _ = gaze_rotations(m, yaw, pitch)
        Vs.append(m.vertices(expression(C, **w), R))
        names.append(label)
    return names, np.stack(Vs).astype(np.float32)


if __name__ == "__main__":
    m = gx.Model()
    C = dict(np.load(sys.argv[1]))
    names, V = preview_states(m, C)
    np.savez(sys.argv[2], names=np.array(names), vertices=V)
    for n, v in zip(names, V):
        print(f"{n:40s} apL {m.aperture(v, 'left').min():6.2f}/{m.aperture(v, 'left').mean():5.2f}  apR {m.aperture(v, 'right').min():6.2f}/{m.aperture(v, 'right').mean():5.2f}")
