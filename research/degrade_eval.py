"""WS2 evaluation: detector robustness and label invariance over a degrade.py sweep.

    python3 research/degrade_eval.py <sweep_dir> <roi_reset_png> <out_json> [<clean_bundle_dir>]

For every op/level: detector success rate (<= 5 px), mean / median / P95 / max Euclidean error vs the label,
and the shift of the detection relative to the detector's own result on the clean image (isolates the effect of
the degradation from the clean-image bias). Label invariance: each copied label's SHA-256 equals its source's
and the 2D pupil values equal the clean metadata exactly.
"""
import glob, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

sweep, roi_png, out = sys.argv[1:4]; clean = sys.argv[4] if len(sys.argv) > 4 else None
ref = P.detect(Image.open(roi_png).convert("RGB")); H = 90
ROI = [(int(d["centre"][0]) - H, int(d["centre"][1]) - H, int(d["centre"][0]) + H, int(d["centre"][1]) + H) for d in ref]
cache = {}
def det(path):
    return P.detect(Image.open(path).convert("RGB"), roi=ROI)
def match(ds, g):
    return min(ds, key=lambda d: abs(d["centre"][0] - g[0])) if ds else None
res = {}; inv_bad = []
meta = json.load(open(os.path.join(clean, "metadata.json"))) if clean else None
for op in sorted(d for d in os.listdir(sweep) if not d.startswith("_")):
    for lv in sorted(os.listdir(os.path.join(sweep, op))):
        E, S, ok = [], [], []
        for pj in sorted(glob.glob(os.path.join(sweep, op, lv, "*.degrade.json"))):
            prov = json.load(open(pj)); lab = json.load(open(pj.replace(".degrade.json", ".label.json")))
            if prov["label_sha256"] != prov["label_copy_sha256"]: inv_bad.append(pj)
            if meta and lab["pupil_center_2D_L"] != meta["frames"][lab["frame"]]["pupil_center_2D_L"]: inv_bad.append(pj + " (values)")
            src = prov["source"]
            if src not in cache: cache[src] = det(src)
            dd = det(pj.replace(".degrade.json", ".png"))
            for s in "LR":
                g = np.array(lab[f"pupil_center_2D_{s}"]); d = match(dd, g); c0 = match(cache[src], g)
                if d is None or d["status"] == "fail":
                    ok.append(False); continue
                e = float(np.linalg.norm(np.array(d["centre"]) - g)); E.append(e); ok.append(e <= 5)
                if c0 and c0["status"] != "fail": S.append(float(np.linalg.norm(np.array(d["centre"]) - np.array(c0["centre"]))))
        E = np.array(E); spec = json.load(open(glob.glob(os.path.join(sweep, op, lv, "*.degrade.json"))[0]))["spec"][0]
        res.setdefault(op, []).append(dict(level=lv, params={k: v for k, v in spec.items() if k not in ("op", "box_px")}, n_pupils=len(ok),
              success_rate=round(float(np.mean(ok)), 4), mean_err=round(float(E.mean()), 3) if len(E) else None,
              median_err=round(float(np.median(E)), 3) if len(E) else None, p95_err=round(float(np.percentile(E, 95)), 3) if len(E) else None,
              max_err=round(float(E.max()), 3) if len(E) else None, mean_shift_vs_clean_detection=round(float(np.mean(S)), 3) if S else None))
summary = dict(sweep=sweep, roi_reference=roi_png, label_invariance_violations=inv_bad, label_invariance_ok=not inv_bad, results=res)
json.dump(summary, open(out, "w"), indent=1)
for op, rows in res.items():
    print(op, [(r["params"], r["success_rate"], r["median_err"], r["mean_shift_vs_clean_detection"]) for r in rows])
print("LABEL INVARIANCE", "OK" if not inv_bad else inv_bad[:3])
