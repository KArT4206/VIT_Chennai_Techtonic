"""Three-input expression renderer and Timeline-scene builder (slides deliverable).

    blender -b scene.blend -P expression/run.py -- --input left     --out OUT
    blender -b scene.blend -P expression/run.py -- --input right    --out OUT
    blender -b scene.blend -P expression/run.py -- --input generate --out OUT
    blender -b scene.blend -P expression/run.py -- --build-scene OUT/expression_scene.blend

--input renders the expression's frames to OUT/<input>_frames/, writes OUT/<input>_motion.json
(per-frame gaze, blink and brow channels plus the rendered eye rotations) and encodes
OUT/<input>.mp4 with ffmpeg (H.264, constant 24 fps). "left" means the SUBJECT'S left, which is
the image's right (world +X), matching eyes.py's h > 0.

--build-scene keys all three expressions as Actions on the rig, makes the natural expression the
active one with the scene's frame range set to it, and saves a NEW .blend. scene.blend is never
saved over. Open the new file and press Space to play the Timeline.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine   # noqa: E402
import motion   # noqa: E402
import eyes     # noqa: E402


def _ffmpeg():
    for c in (shutil.which("ffmpeg"), "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("ffmpeg not found")


def render_input(name, out, samples=None, frame_limit=None, resume=False):
    seq = motion.INPUTS[name]()
    frames = seq.frames()
    if frame_limit:
        frames = frames[:frame_limit]
    device = engine.prepare_render(samples)
    print(f"[expr] {name}: {len(frames)} frames, device {device}, samples {bpy.context.scene.cycles.samples}", flush=True)
    fdir = os.path.join(out, f"{name}_frames")
    os.makedirs(fdir, exist_ok=True)
    scene = bpy.context.scene
    engine.bake_action(engine.ACTION_NAMES[name], frames)
    scene.frame_start, scene.frame_end = 1, len(frames)
    records, t0 = [], time.time()
    for s in frames:
        scene.frame_set(1 + s["frame"])            # the Action drives the pose, as in the Timeline
        rec = dict(s)
        for side in "LR":
            q = eyes._rig().pose.bones[eyes.EYE_BONES[side]].rotation_quaternion
            rec[f"eye_bone_quat_{side}"] = [round(c, 6) for c in q]
        records.append(rec)
        scene.render.filepath = os.path.join(fdir, f"{s['frame']:04d}.png")
        if resume and os.path.exists(scene.render.filepath):
            continue                                # deterministic: an existing frame is identical
        bpy.ops.render.render(write_still=True)
        print(f"[expr] frame {s['frame'] + 1}/{len(frames)}  {time.time() - t0:.1f}s", flush=True)
    render_s = time.time() - t0
    with open(os.path.join(out, f"{name}_motion.json"), "w") as fh:
        json.dump({"input": name, "fps": motion.FPS, "action": engine.ACTION_NAMES[name],
                   "conventions": {"yaw_deg": "+ = subject's left = image right (world +X)",
                                   "pitch_deg": "+ = up (includes Bell's dip during blinks)",
                                   "blink": "0 open (lids follow gaze) .. 1 fully closed",
                                   "brow_mm": "+ = raised, world Z"},
                   "frames": records}, fh, indent=1)
    t1 = time.time()
    mp4 = os.path.join(out, f"{name}.mp4")
    subprocess.run([_ffmpeg(), "-y", "-loglevel", "error", "-framerate", str(motion.FPS),
                    "-i", os.path.join(fdir, "%04d.png"), "-c:v", "libx264", "-preset", "slow",
                    "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(motion.FPS), "-movflags", "+faststart", mp4],
                   check=True)
    print(f"[expr] {name}: render {render_s:.1f}s ({render_s / len(frames):.2f}s/frame), "
          f"encode {time.time() - t1:.1f}s -> {mp4}", flush=True)


def build_scene(path):
    if os.path.abspath(path) == os.path.abspath(bpy.data.filepath):
        raise RuntimeError("refusing to overwrite the opened scene; give a new path")
    for name in ("left", "right", "generate"):
        engine.bake_action(engine.ACTION_NAMES[name], motion.INPUTS[name]().frames())
    scene = bpy.context.scene
    main = bpy.data.actions[engine.ACTION_NAMES["generate"]]
    eyes._rig().animation_data.action = main
    n = len(motion.generate().frames())
    scene.frame_start, scene.frame_end = 1, n
    scene.render.fps = motion.FPS
    scene.frame_set(1)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(path), copy=True, compress=True)
    print(f"[expr] saved {path}: active action {main.name}, frames 1-{n} @ {motion.FPS} fps", flush=True)


def main(argv):
    ap = argparse.ArgumentParser(prog="run.py")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--input", choices=sorted(motion.INPUTS))
    g.add_argument("--build-scene", metavar="BLEND")
    ap.add_argument("--out", default="expression_out")
    ap.add_argument("--samples", type=int, help="Cycles samples (default: scene's 512)")
    ap.add_argument("--frames", type=int, help="render only the first N frames (testing)")
    ap.add_argument("--resume", action="store_true", help="skip frames already rendered in OUT")
    a = ap.parse_args(argv)
    if a.build_scene:
        build_scene(a.build_scene)
    else:
        os.makedirs(a.out, exist_ok=True)
        render_input(a.input, a.out, a.samples, a.frames, a.resume)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
