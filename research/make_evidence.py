"""Stage 9: jury-facing figures from real outputs (no simulated data).

    python3 research/make_evidence.py <bundle_dir> <results_dir> <out_dir>

Reads <bundle_dir>/metadata.json + renders, <results_dir>/model_comparison.json and the detector CSVs written by
evaluate_detector.py (<results_dir>/*_per_pupil.csv). Writes:
  trajectory.png       ground-truth 2D pupil path of the 10 clockwise frames, both eyes, with detector points
  model_comparison.png planar vs sphere vs anatomical pupil position over gaze angle (extended sweep)
  error_by_frame.png   detector - ground truth per frame (dx, dy), per ablation condition
  contact_sheet.png    the 10 released frames, eye band crop, labelled with (h, v)
"""
import csv, glob, json, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

b, res, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
meta = json.load(open(os.path.join(b, "metadata.json")))
C = dict(L="#d9480f", R="#1c7ed6")

fig, axs = plt.subplots(1, 2, figsize=(10, 4.6))
det = {}
p = os.path.join(res, "release_per_pupil.csv")
if os.path.exists(p):
    for r in csv.DictReader(open(p)):
        det.setdefault(r["eye"], []).append((float(r["det_x"]), float(r["det_y"])))
for ax, s in zip(axs, "LR"):
    xs = [f[f"pupil_center_2D_{s}"][0] for f in meta["frames"]]; ys = [f[f"pupil_center_2D_{s}"][1] for f in meta["frames"]]
    ax.plot(xs + xs[:1], ys + ys[:1], "-o", color=C[s], label="ground truth (metadata)")
    for k, (x, y) in enumerate(zip(xs, ys)):
        ax.annotate(str(k), (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)
    if s in det:
        ax.plot(*zip(*det[s]), "x", color="black", label="independent detector")
    ax.set_aspect("equal"); ax.invert_yaxis(); ax.set_title(f"eye {s}: pupil centre, 10 clockwise frames"); ax.set_xlabel("x (px)"); ax.set_ylabel("y (px, down)")
    ax.legend(fontsize=8); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(os.path.join(out, "trajectory.png"), dpi=130); plt.close(fig)

cmp = json.load(open(os.path.join(res, "model_comparison.json")))
ext = cmp["extended_sweep_left_eye"]
fig, ax = plt.subplots(figsize=(6.5, 4.2))
g = [e["gaze_deg"] for e in ext]
ax.plot(g, [e["planar_minus_anatomic_px"] for e in ext], "-o", label="planar translation vs anatomical")
ax.plot(g, [e["sphere_minus_anatomic_px"] for e in ext], "-s", label="rigid sphere (no cornea) vs anatomical")
ax.axvspan(0, 8.1, color="grey", alpha=.15, label="Track 1 range (±5 cm at 35 cm)")
ax.set_xlabel("horizontal gaze angle (deg)"); ax.set_ylabel("pupil-centre difference (px)"); ax.set_title("Pupil centre: model differences, left eye")
ax.legend(fontsize=8); ax.grid(alpha=.3); fig.tight_layout(); fig.savefig(os.path.join(out, "model_comparison.png"), dpi=130); plt.close(fig)

conds = sorted(glob.glob(os.path.join(res, "*_roi_per_pupil.csv")))
if conds:
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    for path in conds:
        name = os.path.basename(path).replace("_roi_per_pupil.csv", "")
        rows = [r for r in csv.DictReader(open(path)) if r["success"] == "True"]
        lab = [f"{r['item'][-2:]}{r['eye']}" for r in rows]
        axs[0].plot(range(len(rows)), [float(r["dx"]) for r in rows], "o-", ms=3, label=name)
        axs[1].plot(range(len(rows)), [float(r["dy"]) for r in rows], "o-", ms=3, label=name)
    for ax, t in zip(axs, ("dx = detected - truth (px)", "dy = detected - truth (px, + is down)")):
        ax.axhline(0, color="k", lw=.8); ax.set_title(t); ax.set_xlabel("pupil (frame order, L/R)"); ax.grid(alpha=.3); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(os.path.join(out, "error_by_condition.png"), dpi=130); plt.close(fig)

tiles = []
for f in meta["frames"]:
    im = Image.open(os.path.join(b, f["file"])).convert("RGB").crop((232, 420, 792, 600))
    d = ImageDraw.Draw(im); d.rectangle((0, 0, 230, 16), fill="black")
    d.text((3, 2), f"frame {f['frame']}  h={f['input']['h']:+.2f} v={f['input']['v']:+.2f}", fill="white"); tiles.append(im)
sheet = Image.new("RGB", (560 * 2, 180 * 5), "black")
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % 2) * 560, (i // 2) * 180))
sheet.save(os.path.join(out, "contact_sheet_eyes.png"))
print("evidence written to", out)
