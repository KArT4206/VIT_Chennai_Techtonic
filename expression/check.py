"""Acceptance checks for the expression system. Does not import or change tools/verify.py.

    blender -b <expression_scene.blend> -P expression/check.py -- <dir with videos and *_motion.json>

Checks: Timeline actions exist and are keyed; the main action is active and covers the frame range;
blink completion; brow animation; lid/eyeball clipping on every frame of every action (geometry);
determinism of the motion model; the evaluator API still poses identically; video duration, frame
count, constant frame rate and resolution (ffprobe); rendered frames continuous (no gaps or
duplicate file indices). Exit code 0 only if all pass.
"""

import json
import math
import os
import shutil
import subprocess
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import engine   # noqa: E402
import motion   # noqa: E402
import eyes     # noqa: E402

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg, flush=True)
    if not ok:
        FAILS.append(msg)


def lid_vertex_sets():
    h = bpy.data.objects["Human"]
    vg = {g.name: g.index for g in h.vertex_groups}
    body = vg[h.modifiers["Hide helpers"].vertex_group]
    out = {}
    for side in "LR":
        idx = {vg[eyes.UPPER_LID_BONES[side]], vg[eyes.LOWER_LID_BONES[side]]}
        out[side] = [v.index for v in h.data.vertices
                     if any(g.group in idx and g.weight > 0.05 for g in v.groups)
                     and any(g.group == body for g in v.groups)]
    return out


def sclera_radius(side):
    o = bpy.data.objects[f"Eye{side}.Sclera"]
    c = eyes._eye_centre(side)
    return max(((o.matrix_world @ v.co) - c).length for v in o.data.vertices)


def _depths(h, lids, rmax):
    """Per lid vertex: how far (m) it is inside the eye volume (eyeball sphere U corneal sphere); <=0 = outside."""
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = h.evaluated_get(dg).to_mesh()
    out = {}
    for side in "LR":
        c = eyes._eye_centre(side)
        cc, cr, _ = eyes._cornea(side)
        for i in lids[side]:
            p = h.matrix_world @ mesh.vertices[i].co
            out[(side, i)] = max(rmax[side] - (p - c).length, cr - (p - cc).length)
    h.evaluated_get(dg).to_mesh_clear()
    return out


def clipping_scan(action_name, lids):
    """Compare every frame against the evaluator's own reset pose.

    The base mesh already tucks some inner-lid (conjunctival) vertices behind the eyeball at rest:
    measured ~35 per eye, up to 2.95 mm deep, identical in eyes.py's reset/up/down/left poses.
    A visible contact is a vertex OUTSIDE the eye volume at rest that enters it. The lids have no
    corrective shapes, so even eyes.py's validated +-8 deg poses produce some (up to ~0.45 mm);
    those poses are the reference the expressions must not exceed.
    Returns (vertices with new contact, worst new depth mm, evaluator reference mm, hidden extra mm).
    """
    rig = eyes._rig()
    h = bpy.data.objects["Human"]
    saved = [(m, m.show_viewport) for m in h.modifiers if m.type in ("SUBSURF", "MASK")]
    for m, _ in saved:
        m.show_viewport = False
    rmax = {s: sclera_radius(s) for s in "LR"}
    rig.animation_data.action = None
    eyes._clear_eye_pose()
    for b in engine.BROW_BONES.values():
        rig.pose.bones[b].location = (0.0, 0.0, 0.0)
    eyes.reset()
    rest = _depths(h, lids, rmax)
    # Reference: eyes.py's own validated evaluator poses (the 5-direction check), same metric.
    ref_depth = 0.0
    for hv in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        eyes.move(*hv)
        ref_depth = max([ref_depth] + [d for k, d in _depths(h, lids, rmax).items() if rest[k] <= 0.0])
    eyes.reset()
    rig.animation_data.action = bpy.data.actions[action_name]
    new_pen, worst_extra, worst_new = set(), 0.0, 0.0
    fr = action_frames(action_name)
    for f in range(fr[0], fr[1] + 1):
        bpy.context.scene.frame_set(f)
        for k, d in _depths(h, lids, rmax).items():
            if rest[k] <= 0.0 and d > 0.0:
                new_pen.add(k)
                worst_new = max(worst_new, d)
            if rest[k] > 0.0:
                worst_extra = max(worst_extra, d - rest[k])
    for m, v in saved:
        m.show_viewport = v
    return len(new_pen), worst_new * 1000, ref_depth * 1000, worst_extra * 1000


def action_frames(name):
    a = bpy.data.actions[name]
    return int(a.frame_range[0]), int(a.frame_range[1])


def ffprobe(path):
    exe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    r = subprocess.run([exe, "-v", "error", "-select_streams", "v:0", "-count_frames", "-show_entries",
                        "stream=width,height,r_frame_rate,avg_frame_rate,nb_read_frames,codec_name,pix_fmt:format=duration",
                        "-of", "json", path], capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    st = d["streams"][0]
    pts = subprocess.run([exe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                          "-of", "csv=p=0", path], capture_output=True, text=True, check=True).stdout.split()
    return st, float(d["format"]["duration"]), sorted(float(x) for x in pts if x)


def main(video_dir):
    scene = bpy.context.scene
    rig = eyes._rig()

    # --- Timeline actions
    names = list(engine.ACTION_NAMES.values())
    for n in names:
        a = bpy.data.actions.get(n)
        check(a is not None, f"action {n} exists")
        if a is None:
            continue
        fcs = engine._fcurves(a)
        paths = {fc.data_path for fc in fcs}
        want = {f'pose.bones["{b}"].rotation_quaternion' for b in engine._bones()} | \
               {f'pose.bones["{b}"].location' for b in engine.BROW_BONES.values()}
        check(want <= paths, f"{n}: keyed eye, upper lid, lower lid and brow channels ({len(fcs)} f-curves)")
        nkeys = min(len(fc.keyframe_points) for fc in fcs)
        check(nkeys >= 100, f"{n}: every channel keyed per frame ({nkeys} keys minimum)")
    main_action = rig.animation_data.action if rig.animation_data else None
    check(main_action is not None and main_action.name == engine.ACTION_NAMES["generate"],
          f"active action is {engine.ACTION_NAMES['generate']}")
    n_gen = len(motion.generate().frames())
    check((scene.frame_start, scene.frame_end) == (1, n_gen), f"Timeline frame range 1-{n_gen} ({scene.frame_start}-{scene.frame_end})")
    check(scene.render.fps == motion.FPS, f"scene fps {scene.render.fps}")

    # --- blink completion and brow motion, read back from the keyed action
    eyes._calibrate()
    for key, name in engine.ACTION_NAMES.items():
        rig.animation_data.action = bpy.data.actions[name]
        f0, f1 = action_frames(name)
        up_angles, brow_z = [], []
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            m = (rig.matrix_world @ rig.pose.bones["orbicularis03.L"].matrix).to_3x3()
            rest = (rig.matrix_world @ rig.pose.bones["orbicularis03.L"].bone.matrix_local).to_3x3()
            q = (m @ rest.inverted()).to_quaternion()
            up_angles.append(math.degrees(q.angle) * (1 if q.axis.x >= 0 else -1))
            brow_z.append((rig.matrix_world @ rig.pose.bones["oculi01.L"].head).z * 1000)
        closed = [a for a in up_angles if a > engine.UPPER_CLOSED_DEG - 0.5]
        check(len(closed) >= 1, f"{key}: blink reaches full closure (max upper-lid {max(up_angles):.1f} deg, "
                                f"closed {engine.UPPER_CLOSED_DEG})")
        check(abs(up_angles[0] - eyes.UPPER_LID_REST_DEG) < 1.5 and abs(up_angles[-1] - eyes.UPPER_LID_REST_DEG) < 1.5,
              f"{key}: starts and ends with open lids ({up_angles[0]:.2f}, {up_angles[-1]:.2f} deg)")
        span = max(brow_z) - min(brow_z)
        check(0.3 < span < 5.0, f"{key}: brows move subtly ({span:.2f} mm range)")
        jumps = max(abs(up_angles[i + 1] - up_angles[i]) for i in range(len(up_angles) - 1))
        # Fastest physical lid motion = the blink's closing phase: smoothstep peaks at 1.5x its mean
        # speed, i.e. 1.5 * (closed - open) / (75 ms * fps). Anything faster would be a pop.
        travel = engine.UPPER_CLOSED_DEG - (eyes.UPPER_LID_REST_DEG - 12.0)   # from the highest lid pose
        limit = 1.5 * travel / (0.075 * motion.FPS)
        check(jumps <= limit, f"{key}: lid never moves faster than a blink closes ({jumps:.1f} <= {limit:.1f} deg/frame)")

    # --- clipping
    lids = lid_vertex_sets()
    for key, name in engine.ACTION_NAMES.items():
        n_new, worst_new, ref, extra = clipping_scan(name, lids)
        check(worst_new <= ref + 0.01,
              f"{key}: lid/cornea contact no deeper than in eyes.py's own 5-direction poses "
              f"({worst_new:.2f} mm over {n_new} vertices; evaluator poses {ref:.2f} mm)")
        # Inner-lid lining already inside the opaque eyeball at rest stays hidden behind the sclera
        # however deep it goes, so it is reported, not gated.
        print(f"INFO {key}: hidden inner-lid lining moves up to {extra:.2f} mm deeper than at rest")
    rig.animation_data.action = main_action

    # --- determinism
    for key, fn in motion.INPUTS.items():
        check(fn().frames() == fn().frames(), f"{key}: motion model is deterministic")

    # --- videos
    for key in motion.INPUTS:
        mp4 = os.path.join(video_dir, f"{key}.mp4")
        if not os.path.exists(mp4):
            check(False, f"{key}.mp4 exists")
            continue
        st, dur, pts = ffprobe(mp4)
        n = len(motion.INPUTS[key]().frames())
        check(dur <= 15.0, f"{key}.mp4: duration {dur:.3f} s <= 15 s")
        check(int(st["nb_read_frames"]) == n, f"{key}.mp4: {st['nb_read_frames']} frames == {n} motion frames")
        check(st["r_frame_rate"] == st["avg_frame_rate"] == f"{motion.FPS}/1", f"{key}.mp4: constant {st['r_frame_rate']} fps")
        steps = {round(pts[i + 1] - pts[i], 4) for i in range(len(pts) - 1)}
        check(len(steps) == 1, f"{key}.mp4: uniform frame spacing {sorted(steps)}")
        check((st["width"], st["height"]) == (1024, 1024), f"{key}.mp4: 1024x1024 ({st['codec_name']}, {st['pix_fmt']})")
        fdir = os.path.join(video_dir, f"{key}_frames")
        files = sorted(os.listdir(fdir))
        check(files == [f"{i:04d}.png" for i in range(n)], f"{key}: rendered frames 0000..{n - 1:04d} with no gaps")
        rec = json.load(open(os.path.join(video_dir, f"{key}_motion.json")))
        check([ {k: v for k, v in r.items() if not k.startswith("eye_bone")} for r in rec["frames"]] ==
              motion.INPUTS[key]().frames(), f"{key}: rendered motion matches a fresh run of the model")

    print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' CHECK(S) FAILED'}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else ".")
    sys.exit(1 if FAILS else 0)
