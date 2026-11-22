"""WS6: benchmark research/speed.py against the original renderer (one configuration per Blender process).

    BENCH_T0=$(python3 -c 'import time;print(time.time())') blender -b --factory-startup <bundle>/scene.blend \
        -P research/bench_speed.py -- <out_dir> <config> [--samples 128]
    config: original | band | persistent | combined

Renders reset, left, right, up, down, then reset again (repeatability), all through the wrapper. Records:
init_s (process start -> script start, needs BENCH_T0), per-frame wall time, sequence total, CPU time / wall
(process CPU utilisation; GPU utilisation is not observable without root on macOS), peak RSS, and the wrapper state
per frame. research/bench_compare.py compares configurations (pixel difference in the eye band, coordinate error).
"""
import json, os, resource, sys, time
t_script = time.time()
import bpy
a = sys.argv[sys.argv.index("--") + 1:]
out, cfg = a[0], a[1]
samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 128
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402
sc = bpy.context.scene
dev = eyes.use_best_device(); sc.cycles.samples = samples
band = None
if cfg in ("band", "combined"):
    import speed; band = speed.eye_band()
sc.render.use_persistent_data = cfg in ("persistent", "combined")
d = os.path.join(out, cfg); os.makedirs(d, exist_ok=True)
POSES = [("reset", 0, 0), ("left", -1, 0), ("right", 1, 0), ("up", 0, 1), ("down", 0, -1), ("reset_again", 0, 0)]
rows = []; c0 = os.times(); t0 = time.time()
for name, h, v in POSES:
    eyes.move(h, v); t = time.time(); st = eyes.render(os.path.join(d, name + ".png")); rows.append(dict(pose=name, render_s=round(time.time() - t, 3), state=st))
    print("BENCHF", cfg, name, rows[-1]["render_s"], flush=True)
t1 = time.time(); c1 = os.times()
cpu = (c1.user - c0.user) + (c1.system - c0.system) + (c1.children_user - c0.children_user)
t_start = float(os.environ["BENCH_T0"]) if "BENCH_T0" in os.environ else None
res = dict(config=cfg, device=dev, samples=samples, blender=bpy.app.version_string, band_px=band, persistent=sc.render.use_persistent_data,
           init_s=round(t_script - t_start, 2) if t_start else None, sequence_s=round(t1 - t0, 2),
           first_frame_s=rows[0]["render_s"], mean_later_frame_s=round(sum(r["render_s"] for r in rows[1:]) / (len(rows) - 1), 3),
           cpu_utilisation=round(cpu / (t1 - t0), 3), peak_rss_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, 1),
           gpu_utilisation="not measured (needs root powermetrics on macOS)", frames=rows)
json.dump(res, open(os.path.join(d, "bench.json"), "w"), indent=1)
print("BENCH_DONE", json.dumps({k: v for k, v in res.items() if k != "frames"}), flush=True)
