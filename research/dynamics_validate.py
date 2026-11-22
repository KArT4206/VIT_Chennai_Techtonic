"""WS5: quantitative validation of research/dynamics.py profiles (simulated behaviour, NOT human data).

    python3 research/dynamics_validate.py <out_dir> [--ipd_mm 59.404]

Converts each profile to per-eye rotation angles with the scene geometry (eye pivots IPD apart, targets on the
35 cm plane or at the vergence depth), then reports angular position, velocity and acceleration (central
differences), target-following error, vergence geometry and timing; plots go to <out_dir>/*.png, numbers to
<out_dir>/dynamics_validation.json. Each check states the published reference it is compared with; the
reference values are representative literature figures, quoted as ranges, and are not a fitted human dataset.
"""
import json, math, os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynamics as D

a = sys.argv[1:]; out = a[0]; os.makedirs(out, exist_ok=True)
IPD = (float(a[a.index("--ipd_mm") + 1]) if "--ipd_mm" in a else 59.404) / 1000

REFS = {
 "saccade_duration": "Carpenter (1988), Movements of the Eyes: D ~ 21 ms + 2.2 ms/deg (approx., 5-50 deg)",
 "saccade_peak_velocity": "Bahill, Clark & Stark (1975) main sequence; peak velocity rises with amplitude and saturates "
                          "around 400-600 deg/s; ~300-450 deg/s for 10-20 deg saccades is typical of reported means",
 "pursuit": "Lisberger, Morris & Tychsen (1987): pursuit latency ~100-150 ms; steady-state gain ~0.9-1.0 for slow (<~0.5 Hz) targets",
 "vergence": "geometry: each eye aims at the same 3-D point; vergence angle = 2*atan((IPD/2)/d) for a midline target",
 "blink": "Blink duration typically ~100-400 ms with the closing phase faster than the opening phase (e.g. VanderWerf et al. 2003)",
 "fixation": "Drift during fixation is a slow random walk of the order of minutes of arc (e.g. Rolfs 2009 review); microsaccades are not modelled",
}


def angles(h, v, depth):
    """Per-eye (azimuth, elevation) in deg for a target at (h*5cm, v*5cm) on a plane `depth` m ahead of the midpoint."""
    tx, tz = h * D.BOUND_M, v * D.BOUND_M; res = {}
    for s, ex in (("L", IPD / 2), ("R", -IPD / 2)):
        dx = tx - ex; res[s] = (math.degrees(math.atan2(dx, depth)), math.degrees(math.atan2(tz, math.hypot(dx, depth))))
    return res


def series(frames, key_t="t"):
    t = np.array([f[key_t] for f in frames]); A = {s: np.array([angles(max(-1, min(1, f["h"])), max(-1, min(1, f["v"])), f["depth_m"])[s] for f in frames]) for s in "LR"}
    return t, A


def deriv(t, x):
    v = np.gradient(x, t, axis=0); return v, np.gradient(v, t, axis=0)


R = dict(references=REFS, ipd_m=IPD)
# --- saccades: main sequence over amplitudes reachable in the +-1 plane
amps, durs, pv, pa = [], [], [], []
for h1 in np.linspace(0.1, 1.0, 10):
    s = D.saccade(-h1, 0, h1, 0, fps=2000); t, A = series(s["frames"])
    az = A["L"][:, 0]; v, acc = deriv(t, az)
    amps.append(abs(az[-1] - az[0])); durs.append(s["duration_s"] * 1000); pv.append(np.abs(v).max()); pa.append(np.abs(acc).max())
amps, durs, pv, pa = map(np.array, (amps, durs, pv, pa))
ref_lo, ref_hi = 300 + 0 * amps, 600 + 0 * amps
R["saccade"] = dict(amplitude_deg=amps.round(3).tolist(), duration_ms=durs.round(2).tolist(), peak_velocity_dps=pv.round(1).tolist(),
                    peak_accel_dps2=pa.round(0).tolist(), duration_formula_ms="21 + 2.2*A (model input, matches reference by construction)",
                    peak_velocity_over_duration_ratio=round(float(np.mean(pv * durs / 1000 / amps)), 4),
                    min_jerk_theory_ratio=1.875,
                    in_typical_range_10_20deg=[bool(300 <= p <= 600) for a_, p in zip(amps, pv) if 10 <= a_ <= 20],
                    note="peak velocity = 1.875*A/D for a minimum-jerk profile; compare with the reference range, not a fitted human dataset")
s = D.saccade(-1, 0.3, 1, -0.3, fps=2000); t, A = series(s["frames"])
v, acc = deriv(t, A["L"]); vR, _ = deriv(t, A["R"])
R["saccade"]["example"] = dict(amplitude_cyclopean_deg=round(s["amplitude_deg"], 3), duration_ms=round(s["duration_s"] * 1000, 2),
                              peak_speed_L_dps=round(float(np.linalg.norm(v, axis=1).max()), 1), peak_speed_R_dps=round(float(np.linalg.norm(vR, axis=1).max()), 1),
                              conjugacy_max_LR_speed_diff_dps=round(float(np.abs(np.linalg.norm(v, axis=1) - np.linalg.norm(vR, axis=1)).max()), 2))
fig, ax = plt.subplots(1, 3, figsize=(14, 3.8))
ax[0].plot(t * 1000, A["L"][:, 0], label="L azimuth"); ax[0].plot(t * 1000, A["R"][:, 0], "--", label="R azimuth"); ax[0].set_xlabel("ms"); ax[0].set_ylabel("deg"); ax[0].set_title("saccade position"); ax[0].legend()
ax[1].plot(t * 1000, np.linalg.norm(v, axis=1), label="speed"); ax2 = ax[1].twinx(); ax2.plot(t * 1000, np.linalg.norm(acc, axis=1) / 1000, "r", alpha=.5); ax2.set_ylabel("accel (10^3 deg/s^2)", color="r")
ax[1].set_xlabel("ms"); ax[1].set_ylabel("deg/s"); ax[1].set_title("speed and acceleration (L)")
ax[2].plot(amps, pv, "o-", label="model (min-jerk)"); ax[2].fill_between(amps, ref_lo, ref_hi, color="grey", alpha=.25, label="typical human means (ref range)")
ax[2].set_xlabel("amplitude (deg)"); ax[2].set_ylabel("peak velocity (deg/s)"); ax[2].set_title("main sequence"); ax[2].legend(fontsize=8)
for x in ax: x.grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(out, "saccade.png"), dpi=120); plt.close(fig)

# --- pursuit
p = D.pursuit(fps=500, dur=5.0); t, A = series(p["frames"])
tgt = np.array([angles(f["target_h"], 0, D.FIX_M)["L"][0] for f in p["frames"]])
eye = A["L"][:, 0]; ss = t > 1.0
err = eye - tgt
lags = np.arange(0, 0.3, 0.002); xc = [np.corrcoef(eye[ss], np.interp(t[ss] - L, t, tgt))[0, 1] for L in lags]
best = float(lags[int(np.argmax(xc))])
gain = float(np.std(eye[ss]) / np.std(tgt[ss]))
R["pursuit"] = dict(freq_hz=0.4, target_amp_deg=round(float(np.abs(tgt).max()), 3), measured_gain=round(gain, 4), measured_latency_s=round(best, 3),
                    rms_following_error_deg=round(float(np.sqrt(np.mean(err[ss] ** 2))), 4), max_following_error_deg=round(float(np.abs(err[ss]).max()), 4),
                    gain_in_reference_range=0.9 <= gain <= 1.0, latency_in_reference_range=0.1 <= best <= 0.15)
fig, ax = plt.subplots(figsize=(8, 3.5)); ax.plot(t, tgt, label="target"); ax.plot(t, eye, label="eye L"); ax.plot(t, err, label="eye - target")
ax.set_xlabel("s"); ax.set_ylabel("azimuth (deg)"); ax.set_title(f"smooth pursuit: gain {gain:.3f}, latency {best*1000:.0f} ms"); ax.legend(); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(out, "pursuit.png"), dpi=120); plt.close(fig)

# --- vergence: exact geometry check
vg = D.vergence(fps=500); t, A = series(vg["frames"])
depth = np.array([f["depth_m"] for f in vg["frames"]]); verg = A["R"][:, 0] - A["L"][:, 0]
theory = np.degrees(2 * np.arctan(IPD / 2 / depth))
vv, _ = deriv(t, verg)
R["vergence"] = dict(depth_m=[round(float(depth[0]), 3), round(float(depth[-1]), 3)], vergence_deg=[round(float(verg[0]), 4), round(float(verg[-1]), 4)],
                     max_abs_error_vs_geometry_deg=float(np.abs(verg - theory).max()), peak_vergence_velocity_dps=round(float(np.abs(vv).max()), 2),
                     symmetric_eyes_max_deg=float(np.abs(A["L"][:, 0] + A["R"][:, 0]).max()))
fig, ax = plt.subplots(figsize=(6, 3.5)); ax.plot(t, verg, label="model"); ax.plot(t, theory, "--", label="2·atan(IPD/2d)"); ax.set_xlabel("s"); ax.set_ylabel("vergence (deg)")
ax.set_title("vergence 35 -> 20 cm"); ax.legend(); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(os.path.join(out, "vergence.png"), dpi=120); plt.close(fig)

# --- fixation drift
fx = D.fixation(dur=2.0, fps=500, seed=3); t, A = series(fx["frames"]); dev = A["L"] - A["L"][0]
R["fixation"] = dict(rms_deviation_arcmin=round(float(np.sqrt((dev ** 2).sum(1).mean()) * 60), 3), max_deviation_arcmin=round(float(np.sqrt((dev ** 2).sum(1)).max() * 60), 3),
                     reproducible_with_seed=D.fixation(seed=3) == D.fixation(seed=3))
fig, ax = plt.subplots(figsize=(4.2, 4)); ax.plot(dev[:, 0] * 60, dev[:, 1] * 60, lw=.8); ax.set_xlabel("arcmin"); ax.set_ylabel("arcmin"); ax.set_title("fixation drift (L)"); ax.set_aspect("equal"); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(out, "fixation.png"), dpi=120); plt.close(fig)

# --- blink
b = D.blink(fps=1000); t = np.array([f["t"] for f in b["frames"]]); c = np.array([f["closure"] for f in b["frames"]])
tc = t[np.argmax(c >= 0.999)]; to = t[len(c) - 1 - np.argmax(c[::-1] >= 0.999)]
R["blink"] = dict(total_ms=round(float(t[-1] * 1000), 1), closing_ms=round(float(tc * 1000), 1), opening_ms=round(float((t[-1] - to) * 1000), 1),
                  closing_faster_than_opening=bool(tc < t[-1] - to), within_reference_duration=bool(0.1 <= t[-1] <= 0.4),
                  rendered=False, note="closure curve only; lid bones are not driven to full closure (see KNOWN_LIMITATIONS)")
fig, ax = plt.subplots(figsize=(6, 3)); ax.plot(t * 1000, c); ax.set_xlabel("ms"); ax.set_ylabel("closure"); ax.set_title("blink profile"); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(out, "blink.png"), dpi=120); plt.close(fig)

json.dump(R, open(os.path.join(out, "dynamics_validation.json"), "w"), indent=1, default=float)
print(json.dumps({k: v for k, v in R.items() if k not in ("references",)}, indent=1, default=float)[:3000])
