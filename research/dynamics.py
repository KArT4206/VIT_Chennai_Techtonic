"""Stage 5 (experimental): temporal eye-movement profiles. Separate from the official 10-frame sequence.

Pure-Python trajectory generators (no Blender needed) plus an optional Blender renderer:

    python3 research/dynamics.py --selftest
    blender -b --factory-startup <bundle>/scene.blend -P research/dynamics.py -- --render <out_dir> [--fps 30] [--samples 16]   (saccades always at 240 fps)

Units: time s, angles deg, targets in the wrapper's normalised (h, v) plane at 35 cm, vergence in metres.
Models
  saccade  : minimum-jerk position profile; duration from the main-sequence fit D = 21 ms + 2.2 ms/deg
             (Carpenter 1988, used widely as a first-order model; NOT validated against human data here).
  pursuit  : target moving sinusoidally; eye follows with a fixed latency (default 100 ms) and gain (0.95).
  vergence : fixation target moving in depth; each eye aims at the same 3-D point (exact geometry).
  fixation : constant target with optional micro-drift (seeded random walk, default 0.05 deg rms).
  blink    : lid closure 0..1 with 100 ms close / 150 ms open (cosine ramps); reported only, see limitations.
"""
import json, math, os, random, sys

FIX_M, BOUND_M = 0.35, 0.05


def amp_deg(h0, v0, h1, v1):
    """Gaze amplitude (deg, cyclopean) between two normalised inputs on the 35 cm plane."""
    a = (h0 * BOUND_M, v0 * BOUND_M, FIX_M); b = (h1 * BOUND_M, v1 * BOUND_M, FIX_M)
    dot = sum(x * y for x, y in zip(a, b)) / (math.dist((0, 0, 0), a) * math.dist((0, 0, 0), b))
    return math.degrees(math.acos(max(-1, min(1, dot))))


def min_jerk(s):
    return 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5


def saccade(h0, v0, h1, v1, fps=1000, t_pre=0.02, t_post=0.03):
    A = amp_deg(h0, v0, h1, v1); D = 0.021 + 0.0022 * A
    n = int(round((t_pre + D + t_post) * fps)) + 1; out = []
    for i in range(n):
        t = i / fps; s = min(1, max(0, (t - t_pre) / D)); m = min_jerk(s)
        out.append(dict(t=round(t, 6), h=h0 + (h1 - h0) * m, v=v0 + (v1 - v0) * m, depth_m=FIX_M))
    return dict(kind="saccade", amplitude_deg=A, duration_s=D, frames=out)


def pursuit(amp=0.8, freq=0.4, dur=2.5, fps=60, latency=0.1, gain=0.95):
    out = []
    for i in range(int(dur * fps) + 1):
        t = i / fps; te = max(0.0, t - latency)
        out.append(dict(t=round(t, 6), target_h=amp * math.sin(2 * math.pi * freq * t), h=gain * amp * math.sin(2 * math.pi * freq * te), v=0.0, depth_m=FIX_M))
    return dict(kind="pursuit", frames=out)


def vergence(d0=0.35, d1=0.20, dur=0.6, fps=60):
    out = []
    for i in range(int(dur * fps) + 1):
        s = min_jerk(min(1, i / (dur * fps)))
        out.append(dict(t=round(i / fps, 6), h=0.0, v=0.0, depth_m=d0 + (d1 - d0) * s))
    return dict(kind="vergence", frames=out)


def fixation(dur=1.0, fps=60, drift_deg=0.05, seed=0):
    r = random.Random(seed); h = v = 0.0; out = []
    k = math.degrees(math.atan(BOUND_M / FIX_M))      # deg per unit input
    for i in range(int(dur * fps) + 1):
        h += r.gauss(0, drift_deg / k / math.sqrt(fps)); v += r.gauss(0, drift_deg / k / math.sqrt(fps))
        h *= 0.98; v *= 0.98
        out.append(dict(t=round(i / fps, 6), h=h, v=v, depth_m=FIX_M))
    return dict(kind="fixation", seed=seed, frames=out)


def blink(fps=60, close=0.1, hold=0.05, open_=0.15):
    out = []; T = close + hold + open_
    for i in range(int(T * fps) + 1):
        t = i / fps
        c = 0.5 - 0.5 * math.cos(math.pi * t / close) if t < close else 1.0 if t < close + hold else 0.5 + 0.5 * math.cos(math.pi * (t - close - hold) / open_)
        out.append(dict(t=round(t, 6), h=0.0, v=0.0, depth_m=FIX_M, closure=round(c, 4)))
    return dict(kind="blink", frames=out)


def selftest():
    res = []
    def ck(n, ok, val): res.append((n, ok, val)); print(("PASS " if ok else "FAIL ") + f"{n}: {val}")
    s = saccade(-1, 0, 1, 0); f = s["frames"]
    ck("saccade starts/ends exactly at endpoints", abs(f[0]["h"] + 1) < 1e-12 and abs(f[-1]["h"] - 1) < 1e-12, (f[0]["h"], f[-1]["h"]))
    ck("saccade monotonic", all(b["h"] >= a["h"] - 1e-12 for a, b in zip(f, f[1:])), "ok")
    k = math.degrees(math.atan(BOUND_M / FIX_M)); vel = [(b["h"] - a["h"]) * k * 1000 for a, b in zip(f, f[1:])]
    ck("saccade duration follows main sequence (ms)", abs(s["duration_s"] - (0.021 + 0.0022 * s["amplitude_deg"])) < 1e-12, round(s["duration_s"] * 1000, 2))
    ck("saccade peak velocity plausible (deg/s, 100-700 for 5-20 deg)", 100 < max(vel) < 700, round(max(vel), 1))
    ck("min-jerk velocity zero at start and end", vel[0] < 1e-6 and vel[-1] < 1e-6, (vel[0], vel[-1]))
    p = pursuit()["frames"]; lag = p[int(0.1 * 60)]
    ck("pursuit lags target by latency (h at t=latency is 0)", abs(p[6]["h"]) < 1e-12, p[6]["h"])
    ck("pursuit gain <= 1", max(abs(x["h"]) for x in p) <= max(abs(x["target_h"]) for x in p) + 1e-12, "ok")
    vg = vergence()["frames"]
    ck("vergence depth monotonic 0.35 -> 0.20 m", vg[0]["depth_m"] == 0.35 and abs(vg[-1]["depth_m"] - 0.2) < 1e-12 and all(b["depth_m"] <= a["depth_m"] for a, b in zip(vg, vg[1:])), "ok")
    fx1, fx2 = fixation(seed=3), fixation(seed=3)
    ck("fixation drift reproducible with seed", fx1 == fx2, "ok")
    ck("fixation drift stays within 0.05 input units", max(max(abs(x["h"]), abs(x["v"])) for x in fx1["frames"]) < 0.05, round(max(abs(x["h"]) for x in fx1["frames"]), 4))
    b = blink()["frames"]
    ck("blink closes fully and reopens", max(x["closure"] for x in b) == 1.0 and b[0]["closure"] == 0 and b[-1]["closure"] < 1e-6, "ok")
    return all(r[1] for r in res), res


def render(out, fps=60, samples=16):
    """Render each profile through the wrapper's own bones. Vergence uses arbitrary-depth targets via
    the wrapper's internal _world_rotation (same Listing's-law maths as move())."""
    import bpy
    from mathutils import Vector
    sys.dont_write_bytecode = True
    sys.path.append(bpy.path.abspath("//wrapper")); import eyes
    eyes.use_best_device(); bpy.context.scene.cycles.samples = samples
    eyes.reset(); mid = eyes._state["midpoint"]
    profs = dict(saccade=saccade(-1, 0.3, 1, -0.3, fps=240), pursuit=pursuit(fps=fps, dur=1.0), vergence=vergence(fps=fps), fixation=fixation(fps=fps, dur=0.5))
    log = {}
    for name, pr in profs.items():
        d = os.path.join(out, name); os.makedirs(d, exist_ok=True); rec = []
        for i, fr in enumerate(pr["frames"]):
            h, v = max(-1, min(1, fr["h"])), max(-1, min(1, fr["v"]))
            eyes.move(h, v)
            if fr["depth_m"] != FIX_M:
                tgt = mid + Vector((h * BOUND_M, -fr["depth_m"], v * BOUND_M))
                for side in "LR":
                    eyes._set_bone_world_rotation(eyes.EYE_BONES[side], eyes._world_rotation(side, tgt))
                bpy.context.view_layer.update()
            path = os.path.join(d, f"{i:04d}.png")
            if not os.path.exists(path):
                bpy.context.scene.render.filepath = path; bpy.ops.render.render(write_still=True)
            rec.append(dict(fr, file=os.path.relpath(path, out)))
        log[name] = dict({k: v for k, v in pr.items() if k != "frames"}, frames=rec)
        print("DYN", name, len(rec), flush=True)
    eyes.reset()
    json.dump(log, open(os.path.join(out, "dynamics.json"), "w"), indent=1)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if "--render" in a:
        render(a[a.index("--render") + 1], int(a[a.index("--fps") + 1]) if "--fps" in a else 60,
               int(a[a.index("--samples") + 1]) if "--samples" in a else 16)
    else:
        ok, _ = selftest(); sys.exit(0 if ok else 1)
