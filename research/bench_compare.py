"""WS6: compare speed configurations against 'original' (pure Python).

    python3 research/bench_compare.py <bench_dir> <roi_reset.png> <out_json>

Per configuration: timing summary from bench.json; per pose, inside the eye band: max/mean absolute pixel
difference vs original (0-255), wrapper ground truth identical (exact JSON equality), independent-detector
coordinate difference vs original; repeatability = reset vs reset_again within the same configuration.
Acceptance (adopt): ground truth identical, detector coordinate difference <= 0.25 px on every pupil, and
eye-band pixel difference no larger than the original's own repeat-to-repeat difference + 2/255 (mean).
"""
import json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P
bd, roi_png, out = sys.argv[1:4]
ref = P.detect(Image.open(roi_png).convert("RGB")); ROI = [(int(d["centre"][0]) - 90, int(d["centre"][1]) - 90, int(d["centre"][0]) + 90, int(d["centre"][1]) + 90) for d in ref]
B = {c: json.load(open(os.path.join(bd, c, "bench.json"))) for c in ("original", "band", "persistent", "combined") if os.path.exists(os.path.join(bd, c, "bench.json"))}
box = next((b["band_px"] for b in B.values() if b["band_px"]), None)
def img(c, p): return np.asarray(Image.open(os.path.join(bd, c, p + ".png")).convert("RGB")).astype(float)
def crop(a): x0, y0, x1, y1 = box; return a[y0:y1, x0:x1]
def det(c, p): return sorted([d["centre"] for d in P.detect(Image.open(os.path.join(bd, c, p + ".png")).convert("RGB"), roi=ROI)])
res = {}
orig_rep = float(np.abs(crop(img("original", "reset")) - crop(img("original", "reset_again"))).mean())
for c, b in B.items():
    r = {k: b[k] for k in ("init_s", "sequence_s", "first_frame_s", "mean_later_frame_s", "cpu_utilisation", "peak_rss_mb", "samples", "device", "band_px", "persistent")}
    r["speedup_sequence_vs_original"] = round(B["original"]["sequence_s"] / b["sequence_s"], 3)
    poses = []
    for fr, fo in zip(b["frames"], B["original"]["frames"]):
        p = fr["pose"]; diff = np.abs(crop(img(c, p)) - crop(img("original", p)))
        dc = [float(np.linalg.norm(np.array(x) - np.array(y))) for x, y in zip(det(c, p), det("original", p))]
        poses.append(dict(pose=p, gt_identical=fr["state"] == fo["state"], band_max_abs_diff=round(float(diff.max()), 2), band_mean_abs_diff=round(float(diff.mean()), 4),
                          detector_coord_diff_px=[round(x, 4) for x in dc]))
    r["poses"] = poses
    r["repeat_mean_abs_diff_band"] = round(float(np.abs(crop(img(c, "reset")) - crop(img(c, "reset_again"))).mean()), 4)
    r["accept"] = all(q["gt_identical"] for q in poses) and all(max(q["detector_coord_diff_px"] or [0]) <= 0.25 for q in poses) and \
        all(q["band_mean_abs_diff"] <= orig_rep + 2 for q in poses)
    res[c] = r
json.dump(dict(eye_band_px=box, original_repeat_mean_abs_diff_band=round(orig_rep, 4), configs=res), open(out, "w"), indent=1)
for c, r in res.items():
    print(c, r["sequence_s"], "s  speedup", r["speedup_sequence_vs_original"], "accept", r["accept"], [q["detector_coord_diff_px"] for q in r["poses"]])
