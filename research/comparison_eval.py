"""WS8 evaluation of comparison_render.py output (pure Python).

    python3 research/comparison_eval.py <cmp_dir> <roi_reset.png> <out_dir>

Per pose and eye, inside a 120x120 px box around the anatomical ground-truth pupil:
  * mean / P95 absolute pixel difference (0-255) of sphere and planar vs anatomical (appearance difference),
  * independent-detector pupil centre and radius per model and the centre's distance from the anatomical GT,
  * planar model's translation (mm) and solve residual.
Writes comparison_metrics.json and comparison_sheet.png (rows = poses, columns = anatomical | sphere | planar |
|planar - anatomical| x4).
"""
import glob, json, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P
cd, roi_png, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
ref = P.detect(Image.open(roi_png).convert("RGB")); ROI = [(int(d["centre"][0]) - 90, int(d["centre"][1]) - 90, int(d["centre"][0]) + 90, int(d["centre"][1]) + 90) for d in ref]
poses = [os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(cd, "anatomical", "*.json")))]
M = ("anatomical", "sphere", "planar"); rows = []; tiles = []
for name in poses:
    st = json.load(open(os.path.join(cd, "anatomical", name + ".json")))["state"]
    pl = json.load(open(os.path.join(cd, "planar", name + ".json")))["planar"]
    im = {m: np.asarray(Image.open(os.path.join(cd, m, name + ".png")).convert("RGB")).astype(float) for m in M}
    det = {m: P.detect(Image.fromarray(im[m].astype(np.uint8)), roi=ROI) for m in M}
    for s in "LR":
        g = np.array(st[f"pupil_center_2D_{s}"]); x0, y0 = int(g[0]) - 60, int(g[1]) - 60
        crop = {m: im[m][y0:y0 + 120, x0:x0 + 120] for m in M}
        r = dict(pose=name, eye=s, input=st["input"], gt=g.tolist(), planar_translation_mm=pl[s]["translation_mm"], planar_residual_px=pl[s]["residual_px"])
        for m in ("sphere", "planar"):
            d = np.abs(crop[m] - crop["anatomical"]); r[f"{m}_vs_anatomical_mean_abs"] = round(float(d.mean()), 3); r[f"{m}_vs_anatomical_p95_abs"] = round(float(np.percentile(d, 95)), 3)
        for m in M:
            dd = min(det[m], key=lambda d: abs(d["centre"][0] - g[0])) if det[m] else None
            r[f"{m}_detector"] = dict(centre=dd["centre"], radius=round(dd["radius"], 3), status=dd["status"], err_vs_gt_px=round(float(np.linalg.norm(np.array(dd["centre"]) - g)), 3)) if dd else None
        rows.append(r)
        if s == "L":
            row = [crop[m] for m in M] + [np.clip(np.abs(crop["planar"] - crop["anatomical"]) * 4, 0, 255)]
            tiles.append((name, row))
def agg(k):
    v = np.array([r[k] for r in rows]); return dict(mean=round(float(v.mean()), 3), max=round(float(v.max()), 3))
summ = dict(cmp_dir=cd, n=len(rows), sphere_vs_anatomical_mean_abs=agg("sphere_vs_anatomical_mean_abs"), planar_vs_anatomical_mean_abs=agg("planar_vs_anatomical_mean_abs"),
            planar_translation_mm=agg("planar_translation_mm"), planar_residual_px=agg("planar_residual_px"),
            detector_err_vs_gt={m: agg_m for m, agg_m in ((m, dict(mean=round(float(np.mean([r[f"{m}_detector"]["err_vs_gt_px"] for r in rows if r[f"{m}_detector"]])), 3))) for m in M)},
            detector_radius={m: round(float(np.mean([r[f"{m}_detector"]["radius"] for r in rows if r[f"{m}_detector"]])), 3) for m in M}, rows=rows)
json.dump(summ, open(os.path.join(out, "comparison_metrics.json"), "w"), indent=1)
sheet = Image.new("RGB", (4 * 240, len(tiles) * 240 + 20), "black"); d = ImageDraw.Draw(sheet)
for j, t in enumerate(("anatomical", "sphere (no cornea)", "planar (translated)", "|planar-anat| x4")): d.text((j * 240 + 4, 4), t, fill="white")
for i, (name, row) in enumerate(tiles):
    for j, c in enumerate(row): sheet.paste(Image.fromarray(c.astype(np.uint8)).resize((240, 240)), (j * 240, 20 + i * 240))
    d.text((4, 24 + i * 240), name, fill="yellow")
sheet.save(os.path.join(out, "comparison_sheet.png"))
print(json.dumps({k: v for k, v in summ.items() if k != "rows"}, indent=1))
