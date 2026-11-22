"""Attribute the detector-vs-ground-truth offset to a cause, from real renders only.

    python3 research/analyze_bias.py <probe_dir> <ablation_dir> <roi_reset.png> <out_json>

Per pose and eye it compares, against the metadata point (GT):
  M  centroid of the painted-pupil mask (probe/mask)           -> tests the GT definition
  Dm detector on the mask image                                -> tests the detector's circle fit on a clean disc
  Da detector on the unlit albedo render (probe/albedo)        -> detector on texture, no shading
  Ds detector on the lit render, lids and lens hidden          -> adds shading
  Dl detector on the lit render, lids hidden, lens present     -> adds corneal refraction
  Df detector on the full scene                                -> adds lids
Each step's mean (dx, dy) shift says how much that factor contributes. Same detector settings and ROI throughout.
"""
import json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

probe, abl, roi_img, out = sys.argv[1:5]
ref = P.detect(Image.open(roi_img).convert("RGB"))
H = 60
ROI = [(int(d["centre"][0]) - H, int(d["centre"][1]) - H, int(d["centre"][0]) + H, int(d["centre"][1]) + H) for d in ref]


def det(path):
    return P.detect(Image.open(path).convert("RGB"), roi=ROI)


def pick(ds, g):
    return min(ds, key=lambda d: abs(d["centre"][0] - g[0])) if ds else None


rows = []
conds = dict(Dm=os.path.join(probe, "mask"), Da=os.path.join(probe, "albedo"), Ds=os.path.join(abl, "no_lids_lens"),
             Dl=os.path.join(abl, "no_lids"), Df=os.path.join(abl, "full"))
for k in range(11):
    st = json.load(open(os.path.join(probe, "mask", f"state_{k:02d}.json")))
    mask = np.asarray(Image.open(os.path.join(probe, "mask", f"frame_{k:02d}.png")).convert("L")).astype(float)
    dets = {c: det(os.path.join(p, f"frame_{k:02d}.png")) for c, p in conds.items()}
    for s in "LR":
        g = np.array(st[f"pupil_center_2D_{s}"]); x0, y0 = int(g[0]) - 50, int(g[1]) - 50
        w = mask[y0:y0 + 100, x0:x0 + 100]; ys, xs = np.nonzero(w > 128)
        wt = w[ys, xs]
        M = np.array([x0 + 0.5 + (xs * wt).sum() / wt.sum(), y0 + 0.5 + (ys * wt).sum() / wt.sum()])
        r = dict(pose=k, eye=s, h=st["input"]["h"], v=st["input"]["v"], gt=g.round(3).tolist(),
                 M=(M - g).round(3).tolist(), mask_r_eq=round(float(np.sqrt(len(xs) / np.pi)), 2))
        for c, ds in dets.items():
            d = pick(ds, g)
            ok = d is not None and d["status"] != "fail" and np.linalg.norm(np.array(d["centre"]) - g) < 20
            r[c] = (np.array(d["centre"]) - g).round(3).tolist() if ok else None
            r[c + "_r"] = round(d["radius"], 2) if ok else None
        rows.append(r)


def stats(key):
    v = np.array([r[key] for r in rows if r[key] is not None])
    return dict(n=int(len(v)), mean_dx=round(float(v[:, 0].mean()), 3), mean_dy=round(float(v[:, 1].mean()), 3),
                mean_euclid=round(float(np.linalg.norm(v, axis=1).mean()), 3), max_euclid=round(float(np.linalg.norm(v, axis=1).max()), 3))


summary = {k: stats(k) for k in ("M", "Dm", "Da", "Ds", "Dl", "Df")}
# linear model of the offset vs gaze for each condition: d = a + b*h (x), a + b*v (y)
for k in ("Da", "Ds", "Df"):
    v = [(r["h"], r["v"], *r[k]) for r in rows if r[k] is not None]
    A = np.array(v)
    bx = np.polyfit(A[:, 0], A[:, 2], 1); by = np.polyfit(A[:, 1], A[:, 3], 1)
    summary[k]["fit_dx_vs_h"] = dict(slope=round(float(bx[0]), 3), intercept=round(float(bx[1]), 3))
    summary[k]["fit_dy_vs_v"] = dict(slope=round(float(by[0]), 3), intercept=round(float(by[1]), 3))
summary["radius_px"] = {k: round(float(np.mean([r[k] for r in rows if r[k] is not None])), 2) for k in ("mask_r_eq", "Dm_r", "Da_r", "Ds_r")}
json.dump(dict(roi=ROI, summary=summary, rows=rows), open(out, "w"), indent=1)
print(json.dumps(summary, indent=1))
