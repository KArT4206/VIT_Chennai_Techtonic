"""WS6 audit of the eye-band (border) render vs the full-frame render (pure Python, read-only).

    python3 research/bench_band_audit.py <bench_dir> <out_json>

Per pose and for band and combined: (1) ROI coordinate reconstruction - the band PNG is still 1024x1024 and the wrapper
ground truth in bench.json is identical to the original's (so no coordinate transform is needed); (2) pixel differences
vs original inside the band, split into the band interior (inset 2 px) and the band's outer 2-px frame; (3) the same
for 'persistent' as a control. Values are 0-255 per channel, max over RGB.
"""
import json, os, sys
import numpy as np
from PIL import Image
bd, out = sys.argv[1:3]
B = {c: json.load(open(os.path.join(bd, c, "bench.json"))) for c in ("original", "band", "persistent", "combined")}
x0, y0, x1, y1 = next(b["band_px"] for b in B.values() if b["band_px"])
res = dict(band_px=[x0, y0, x1, y1], configs={})
for c in ("band", "combined", "persistent"):
    rows = []
    for ro, rc in zip(B["original"]["frames"] if "frames" in B["original"] else B["original"]["rows"], B[c]["frames"] if "frames" in B[c] else B[c]["rows"]):
        o = np.asarray(Image.open(os.path.join(bd, "original", ro["pose"] + ".png")).convert("RGB")).astype(int)
        b = np.asarray(Image.open(os.path.join(bd, c, rc["pose"] + ".png")).convert("RGB")).astype(int)
        d = np.abs(o - b).max(2); band = d[y0:y1, x0:x1]; inner = d[y0 + 2:y1 - 2, x0 + 2:x1 - 2]
        frame = np.ones_like(band, bool); frame[2:-2, 2:-2] = False
        rows.append(dict(pose=rc["pose"], image_size=list(b.shape[1::-1]), gt_identical_to_original=rc["state"] == ro["state"],
                         band_interior_max=int(inner.max()), band_interior_mean=round(float(inner.mean()), 4), band_interior_p99=float(np.percentile(inner, 99)),
                         band_edge_frame_max=int(band[frame].max()), band_edge_frame_mean=round(float(band[frame].mean()), 3),
                         outside_band_mean=round(float(np.concatenate([d[:y0].ravel(), d[y1:].ravel()]).mean()), 3)))
    res["configs"][c] = rows
json.dump(res, open(out, "w"), indent=1); print(json.dumps({c: rows[0] for c, rows in res["configs"].items()}, indent=1))
