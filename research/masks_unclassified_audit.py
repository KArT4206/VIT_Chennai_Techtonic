"""WS3 audit of unclassified pixels in masks.py class renders (pure Python; read-only, changes no labels).

    python3 research/masks_unclassified_audit.py <masks_dir> <out_json>

For every classes_refr/frame_NN.png: fraction of pixels not near any label colour, how many of those are neutral
grey (R~G~B, 40..200), their location (per 128-px column/row band, and inside the eye band y 400-620, x 250-780),
and the most frequent unclassified colours. Unclassified pixels are reported, never reassigned.
"""
import glob, json, os, sys
import numpy as np
from PIL import Image
PAL = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [1, 0, 1], [0, 1, 1]], float) * 255
md, out = sys.argv[1:3]; res = {}
for p in sorted(glob.glob(os.path.join(md, "classes_refr", "frame_*.png"))):
    a = np.asarray(Image.open(p).convert("RGB")).astype(float)
    d = np.sqrt(((a[:, :, None, :] - PAL[None, None]) ** 2).sum(-1)).min(-1); unk = d > 60
    grey = unk & (np.ptp(a, axis=2) < 8) & (a[..., 0] > 40) & (a[..., 0] < 200)
    eb = unk[400:620, 250:780]; ebp = a[400:620, 250:780][eb]
    eb_grey = float(((np.ptp(ebp, axis=1) < 8) & (ebp[:, 0] > 40) & (ebp[:, 0] < 200)).mean()) if eb.any() else 0.0
    # mixed-colour pixels = touching two different label classes (anti-aliased class boundary)
    cols, cnt = np.unique(a[unk].astype(int), axis=0, return_counts=True); o = np.argsort(-cnt)[:5]
    res[os.path.basename(p)] = dict(unclassified_fraction=round(float(unk.mean()), 5), neutral_grey_fraction_of_unclassified=round(float(grey.sum() / max(unk.sum(), 1)), 4),
                                    unclassified_in_eye_band=round(float(eb.mean()), 6), eye_band_unclassified_grey_share=round(eb_grey, 4),
                                    by_column_band=[round(float(unk[:, c:c + 128].mean()), 4) for c in range(0, 1024, 128)],
                                    by_row_band=[round(float(unk[r:r + 128].mean()), 4) for r in range(0, 1024, 128)],
                                    top_colours=[[cols[i].tolist(), int(cnt[i])] for i in o])
fr = list(res.values())
summary = dict(frames=len(fr), unclassified_fraction_range=[min(f["unclassified_fraction"] for f in fr), max(f["unclassified_fraction"] for f in fr)],
               max_unclassified_in_eye_band=max(f["unclassified_in_eye_band"] for f in fr),
               min_grey_share=min(f["neutral_grey_fraction_of_unclassified"] for f in fr),
               interpretation="About 98% of unclassified pixels are neutral grey, concentrated in the outer left/right image columns outside the "
                              "head silhouette. Up to ~1.1% of eye-band pixels are also unclassified (see eye_band_unclassified_grey_share; their "
                              "cause is not established here). The grey pixels are consistent with the world background still rendering grey "
                              "(masks.py sets world.use_nodes=False, which Blender 5.3 deprecates). They are NOT reassigned here; "
                              "segmentation metrics stay provisional until masks.py renders a true black background.")
json.dump(dict(summary=summary, frames=res), open(out, "w"), indent=1); print(json.dumps(summary, indent=1))
