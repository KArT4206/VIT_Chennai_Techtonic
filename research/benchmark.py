"""Stage 7: render benchmark + robustness, inside Blender, on an unmodified bundle.

    blender -b --factory-startup <bundle>/scene.blend -P research/benchmark.py -- <out_dir> [--cpu] [--samples N] [--repeats 3]

Measures: scene-ready time (process start -> script start is reported by the caller), per-frame render time for
the reset pose repeated R times, peak RSS of the Blender process, device, and repeat-to-repeat pixel difference
(same machine, same device). Also checks extreme valid inputs (corners), reset after every direction, and that an
invalid input leaves the previous pose untouched.
"""
import json, os, resource, sys, time
import bpy
a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]; cpu = "--cpu" in a
samples = int(a[a.index("--samples") + 1]) if "--samples" in a else None
reps = int(a[a.index("--repeats") + 1]) if "--repeats" in a else 3
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402
import numpy as np
sc = bpy.context.scene
dev = "CPU" if cpu else eyes.use_best_device()
if cpu: sc.cycles.device = "CPU"
if samples: sc.cycles.samples = samples
os.makedirs(out, exist_ok=True); res = dict(device=dev, samples=sc.cycles.samples, blender=bpy.app.version_string, threads=sc.render.threads)
def load(p):
    im = bpy.data.images.load(p); px = np.array(im.pixels[:], dtype=np.float32); bpy.data.images.remove(im); return px
times = []; imgs = []
for r in range(reps):
    eyes.reset(); t = time.time(); eyes.render(os.path.join(out, f"rep_{r}.png")); times.append(time.time() - t)
    imgs.append(load(os.path.join(out, f"rep_{r}.png")))
res["reset_render_s"] = [round(x, 2) for x in times]
res["repeat_max_abs_diff_255"] = [round(float(np.abs(imgs[0] - x).max() * 255), 3) for x in imgs[1:]]
res["repeat_mean_abs_diff_255"] = [round(float(np.abs(imgs[0] - x).mean() * 255), 5) for x in imgs[1:]]
# robustness
rb = {}
for h, v in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
    s = eyes.move(h, v); rb[f"corner_{h}_{v}"] = s["pupil_center_2D_L"] + s["pupil_center_2D_R"]
eyes.reset(); base = eyes.state()
same = True
for h, v in ((-1, 0), (1, 0), (0, 1), (0, -1)):
    eyes.move(h, v); eyes.reset(); same &= eyes.state() == base
rb["reset_after_each_direction_identical"] = same
eyes.move(0.2, 0.2); before = eyes.state()
try:
    eyes.move(float("nan"), 0)
except ValueError:
    pass
rb["invalid_input_leaves_pose_unchanged"] = eyes.state() == before
res["robustness"] = rb
res["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1)   # macOS reports bytes
json.dump(res, open(os.path.join(out, "benchmark.json"), "w"), indent=1)
print("BENCH", json.dumps(res), flush=True)
