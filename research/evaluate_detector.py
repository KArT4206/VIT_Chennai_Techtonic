"""Compare the independent image detector (research/pupil_detector.py) with geometry ground truth.

    python3 research/evaluate_detector.py [--roi-from reset.png] <name> <out_dir> <source> [<source> ...]

A source is one of
  * a bundle folder with metadata.json (uses frames[*].file / pupil_center_2D_*),
  * an ablation folder with frame_NN.png + state_NN.json,
  * a dataset_engine folder with manifest.json.
The detector sees only the PNG. Ground truth is matched to detections afterwards by eye (L/R by image x).
Writes <out_dir>/<name>_metrics.json, <name>_per_pupil.csv and <name>_overlays.png (every pupil, failures kept).
Metrics (pixels, Euclidean unless stated): n, success rate, per-axis MAE, mean, RMSE, median, P95, max,
and error by confidence bin.
"""
import csv, glob, hashlib, json, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

FAIL_PX = 5.0      # a detection farther than this from ground truth counts as a failed detection


def items(src):
    if os.path.exists(os.path.join(src, "metadata.json")):
        for f in json.load(open(os.path.join(src, "metadata.json")))["frames"]:
            yield os.path.join(src, f["file"]), f, f"frame{f['frame']:02d}"
    elif os.path.exists(os.path.join(src, "manifest.json")):
        for stem, e in sorted(json.load(open(os.path.join(src, "manifest.json")))["samples"].items()):
            yield os.path.join(src, e["image"]), json.load(open(os.path.join(src, e["annotation"]))), stem
    else:
        for p in sorted(glob.glob(os.path.join(src, "frame_*.png"))):
            yield p, json.load(open(p.replace("frame_", "state_").replace(".png", ".json"))), os.path.basename(p)[:-4]


ROI = None   # set with --roi-from <reset.png>: boxes of +-ROI_HALF px around the detector's own reset detection
ROI_HALF = 90


def main(name, out, srcs):
    os.makedirs(out, exist_ok=True); rows = []; tiles = []
    for src in srcs:
        for img_path, gt, tag in items(src):
            im = Image.open(img_path).convert("RGB"); det = P.detect(im, ROI)
            for s in "LR":
                g = np.array(gt[f"pupil_center_2D_{s}"])
                d = min(det, key=lambda d: abs(d["centre"][0] - g[0])) if det else None
                c = np.array(d["centre"]) if d else np.array([np.nan, np.nan])
                e = float(np.linalg.norm(c - g)) if d else float("nan")
                ok = d is not None and d["status"] != "fail" and e <= FAIL_PX
                rows.append(dict(source=os.path.basename(os.path.normpath(src)), item=tag, eye=s, h=gt["input"]["h"], v=gt["input"]["v"],
                                 gt_x=g[0], gt_y=g[1], det_x=c[0], det_y=c[1], err_px=e, dx=c[0] - g[0], dy=c[1] - g[1],
                                 status=d["status"] if d else "none", confidence=d.get("confidence", 0) if d else 0, success=ok))
                x0, y0 = int(g[0]) - 32, int(g[1]) - 32
                t = im.crop((x0, y0, x0 + 64, y0 + 64)).resize((192, 192), Image.NEAREST); dr = ImageDraw.Draw(t)
                for p_, col in ((g, "lime"), (c, "red")):
                    if np.isfinite(p_).all():
                        X, Y = (p_[0] - x0) * 3, (p_[1] - y0) * 3; dr.ellipse((X - 4, Y - 4, X + 4, Y + 4), outline=col, width=2)
                if d and np.isfinite(c).all():
                    X, Y, R = (c[0] - x0) * 3, (c[1] - y0) * 3, d["radius"] * 3; dr.ellipse((X - R, Y - R, X + R, Y + R), outline="red")
                dr.rectangle((0, 0, 191, 14), fill="black"); dr.text((2, 1), f"{tag[-10:]} {s} {e:.2f}px {'OK' if ok else 'FAIL'}", fill="white" if ok else "orange")
                tiles.append(t)
    E = np.array([r["err_px"] for r in rows]); okm = np.array([r["success"] for r in rows]); Es = E[okm]
    dx = np.array([r["dx"] for r in rows])[okm]; dy = np.array([r["dy"] for r in rows])[okm]
    conf = np.array([r["confidence"] for r in rows])
    bins = [(0, .35), (.35, .5), (.5, 1.01)]
    m = dict(name=name, sources=srcs, n_pupils=len(rows), n_success=int(okm.sum()), success_rate=round(float(okm.mean()), 4), fail_threshold_px=FAIL_PX,
             on_successful=dict(mae_x=round(float(np.mean(np.abs(dx))), 3), mae_y=round(float(np.mean(np.abs(dy))), 3),
                                mean_bias_x=round(float(dx.mean()), 3), mean_bias_y=round(float(dy.mean()), 3),
                                mean_euclid=round(float(Es.mean()), 3), rmse=round(float(np.sqrt(np.mean(Es ** 2))), 3),
                                median=round(float(np.median(Es)), 3), p95=round(float(np.percentile(Es, 95)), 3), max=round(float(Es.max()), 3)) if len(Es) else None,
             all_pupils_max_err=round(float(np.nanmax(E)), 3) if np.isfinite(E).any() else None,
             by_confidence=[dict(bin=b, n=int(((conf >= b[0]) & (conf < b[1])).sum()),
                                 median_err=round(float(np.nanmedian(E[(conf >= b[0]) & (conf < b[1])])), 3) if ((conf >= b[0]) & (conf < b[1])).any() else None) for b in bins],
             detector=dict(dark_levels=list(P.DARK_LEVELS), bright=P.BRIGHT_T, rays=P.N_RAYS,
                           sha256=hashlib.sha256(open(P.__file__, 'rb').read()).hexdigest()),
             roi=ROI, n_missed_or_failed=len(rows) - int(okm.sum()))
    json.dump(m, open(os.path.join(out, f"{name}_metrics.json"), "w"), indent=1)
    with open(os.path.join(out, f"{name}_per_pupil.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    cols = 8; sheet = Image.new("RGB", (cols * 192, ((len(tiles) + cols - 1) // cols) * 192), "black")
    for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * 192, (i // cols) * 192))
    sheet.save(os.path.join(out, f"{name}_overlays.png"))
    print(json.dumps(m, indent=1))


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--roi-from" in a:
        i = a.index("--roi-from"); ref = P.detect(Image.open(a[i + 1]).convert("RGB")); del a[i:i + 2]
        ROI = [(int(d["centre"][0]) - ROI_HALF, int(d["centre"][1]) - ROI_HALF, int(d["centre"][0]) + ROI_HALF, int(d["centre"][1]) + ROI_HALF) for d in ref]
        print("ROI from reference detection:", ROI)
    main(a[0], a[1], a[2:])
