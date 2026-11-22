"""WS3 post-processing, validation and metrics for research/masks.py output (pure Python).

    python3 research/masks_eval.py <masks_dir> <photoreal_dir_or_bundle> <out_dir> [--roi-from reset.png]

Writes per pose: <out_dir>/labels/frame_NN_index.png (0 bg,1 pupil,2 iris,3 sclera,4 eyelid,5 lashes,6 other skin,
7 other), <out_dir>/labels/frame_NN_<class>.png binary masks (incl. cornea), frame_NN_landmarks.json
(GT pupil centres, mask centroids, visible boundary points, visible fraction), and <out_dir>/masks_metrics.json.
Metrics: landmark error (mask centroid vs GT, refracted and unrefracted), pupil visible fraction, IoU/Dice of the
independent detector's circle vs the visible pupil mask, IoU/Dice of refracted vs unrefracted pupil masks.
Validation: 1024x1024, unclassified-pixel fraction, both pupils present, pupil adjacent to iris, cornea covers pupil.
"""
import glob, json, os, sys
import numpy as np
from PIL import Image
from scipy import ndimage
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

PAL = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [1, 0, 1], [0, 1, 1]], float)
NAMES = ["bg", "pupil", "iris", "sclera", "skin", "lashes", "other"]
a = sys.argv[1:]; roi_png = None
if "--roi-from" in a:
    i = a.index("--roi-from"); roi_png = a[i + 1]; del a[i:i + 2]
md, photo, out = a[:3]; os.makedirs(os.path.join(out, "labels"), exist_ok=True)
ROI = None
if roi_png:
    ref = P.detect(Image.open(roi_png).convert("RGB")); ROI = [(int(d["centre"][0]) - 90, int(d["centre"][1]) - 90, int(d["centre"][0]) + 90, int(d["centre"][1]) + 90) for d in ref]


def classify(path):
    x = np.asarray(Image.open(path).convert("RGB")).astype(float) / 255
    d = ((x[:, :, None, :] - PAL[None, None]) ** 2).sum(-1)
    idx = d.argmin(-1); unk = d.min(-1) > 0.35 ** 2
    return idx, unk


def iou_dice(m1, m2):
    i = (m1 & m2).sum(); u = (m1 | m2).sum(); s = m1.sum() + m2.sum()
    return (float(i / u) if u else None, float(2 * i / s) if s else None)


def photo_path(k):
    for c in (os.path.join(photo, "renders", f"frame_{k:02d}.png"), os.path.join(photo, f"frame_{k:02d}.png")):
        if os.path.exists(c):
            return c


rows = []; problems = []
for sp in sorted(glob.glob(os.path.join(md, "state_*.json"))):
    k = int(sp[-7:-5]); st = json.load(open(sp)); f = f"frame_{k:02d}"
    ir, unk_r = classify(os.path.join(md, "classes_refr", f + ".png"))
    iu, _ = classify(os.path.join(md, "classes_unrefr", f + ".png"))
    ipu, _ = classify(os.path.join(md, "pupil_unoccluded", f + ".png"))
    cor = np.asarray(Image.open(os.path.join(md, "cornea", f + ".png")).convert("L")) > 127
    if ir.shape != (1024, 1024): problems.append(f"{f}: shape {ir.shape}")
    eye = np.isin(ir, [1, 2, 3])
    # eyelid = skin pixels within 20 px of the visible eyeball, per eye; remaining skin = other skin
    near = ndimage.binary_dilation(eye, iterations=20)
    index = ir.copy(); index[(ir == 4) & ~near] = 6; index[(ir == 6)] = 7
    index[(ir == 4) & near] = 4
    Image.fromarray(index.astype(np.uint8)).save(os.path.join(out, "labels", f + "_index.png"))
    for cid, nm in ((1, "pupil"), (2, "iris"), (3, "sclera"), (4, "eyelid"), (5, "lashes")):
        Image.fromarray(((index == cid) * 255).astype(np.uint8)).save(os.path.join(out, "labels", f"{f}_{nm}.png"))
    Image.fromarray((cor * 255).astype(np.uint8)).save(os.path.join(out, "labels", f"{f}_cornea.png"))
    photo_img = photo_path(k); det = P.detect(Image.open(photo_img).convert("RGB"), roi=ROI) if photo_img else []
    lab, n = ndimage.label(ir == 1); lu, _ = ndimage.label(iu == 1); lpu, _ = ndimage.label(ipu == 1)
    lm = dict(frame=k, input=st["input"])
    for s in "LR":
        g = np.array(st[f"pupil_center_2D_{s}"]); gu = np.array(st[f"pupil_center_2D_unrefracted_{s}"])
        def comp(L):
            ids = [i for i in range(1, L.max() + 1)]
            if not ids: return None
            cs = [(np.array(ndimage.center_of_mass(L == i))[::-1], i) for i in ids]
            c, i = min(cs, key=lambda t: np.linalg.norm(t[0] - g)); return (L == i) if np.linalg.norm(c - g) < 40 else None
        vis, unr, full = comp(lab), comp(lu), comp(lpu)
        rec = dict(eye=s, gt_apparent=g.tolist(), gt_unrefracted=gu.tolist())
        if full is not None:
            c = np.array(ndimage.center_of_mass(full))[::-1]; rec["unoccluded_refr_centroid"] = c.tolist(); rec["err_unoccluded_refr_vs_gt_apparent_px"] = float(np.linalg.norm(c - g))
            rec["err_unoccluded_refr_vs_gt_unrefracted_px"] = float(np.linalg.norm(c - gu)); rec["unoccluded_area_px"] = int(full.sum())
        else:
            problems.append(f"{f} {s}: no unoccluded pupil")
        if vis is not None:
            c = np.array(ndimage.center_of_mass(vis))[::-1]; rec["visible_refr_centroid"] = c.tolist(); rec["err_visible_refr_vs_gt_apparent_px"] = float(np.linalg.norm(c - g))
            rec["visible_fraction"] = float(vis.sum() / full.sum()) if full is not None else None
            edge = vis & ~ndimage.binary_erosion(vis)
            ys, xs = np.nonzero(edge); rec["visible_boundary_px"] = [[int(x), int(y)] for x, y in zip(xs, ys)]
            ring = ndimage.binary_dilation(vis, iterations=1) & ~vis
            rec["pupil_ring_iris_fraction"] = float((ir[ring] == 2).mean())
            if rec["pupil_ring_iris_fraction"] < 0.3: problems.append(f"{f} {s}: pupil not surrounded by iris ({rec['pupil_ring_iris_fraction']:.2f})")
            rec["cornea_covers_pupil_fraction"] = float(cor[vis].mean())
            if unr is not None:
                rec["iou_refr_vs_unrefr"], rec["dice_refr_vs_unrefr"] = iou_dice(vis, unr)
                cu = np.array(ndimage.center_of_mass(unr))[::-1]; rec["err_visible_unrefr_vs_gt_unrefracted_px"] = float(np.linalg.norm(cu - gu))
            if det:
                d = min(det, key=lambda d: abs(d["centre"][0] - g[0])); yy, xx = np.mgrid[:1024, :1024]
                circ = (xx + .5 - d["centre"][0]) ** 2 + (yy + .5 - d["centre"][1]) ** 2 <= d["radius"] ** 2
                rec["iou_detector_vs_visible"], rec["dice_detector_vs_visible"] = iou_dice(circ, vis)
                rec["iou_detector_vs_unoccluded"], rec["dice_detector_vs_unoccluded"] = iou_dice(circ, full) if full is not None else (None, None)
                rec["detector_centre"] = d["centre"]; rec["detector_radius"] = d["radius"]; rec["detector_status"] = d["status"]
                if full is not None:
                    rec["err_detector_vs_unoccluded_centroid_px"] = float(np.linalg.norm(np.array(d["centre"]) - np.array(rec["unoccluded_refr_centroid"])))
        else:
            problems.append(f"{f} {s}: pupil fully occluded")
        lm[s] = rec
    lm["unclassified_fraction"] = float(unk_r.mean())
    if lm["unclassified_fraction"] > 0.001: problems.append(f"{f}: unclassified {lm['unclassified_fraction']:.4f}")
    lm["class_pixels"] = {NAMES[i] if i < 7 else "x": int((ir == i).sum()) for i in range(7)}
    json.dump(lm, open(os.path.join(out, "labels", f + "_landmarks.json"), "w"), indent=1); rows.append(lm)


def stat(key):
    v = np.array([r[s][key] for r in rows for s in "LR" if r[s].get(key) is not None], float)
    return dict(n=len(v), mean=round(float(v.mean()), 4), median=round(float(np.median(v)), 4), p95=round(float(np.percentile(v, 95)), 4), max=round(float(v.max()), 4), min=round(float(v.min()), 4)) if len(v) else None


def vec(key, ref):
    v = np.array([np.array(r[s][key]) - np.array(r[s][ref]) for r in rows for s in "LR" if r[s].get(key) is not None])
    return dict(mean_dx=round(float(v[:, 0].mean()), 4), mean_dy=round(float(v[:, 1].mean()), 4)) if len(v) else None


summ = dict(masks_dir=md, n_poses=len(rows), validation_problems=problems, validation_ok=not problems,
            landmark=dict(unoccluded_refracted_centroid_vs_gt_apparent=stat("err_unoccluded_refr_vs_gt_apparent_px"),
                          unoccluded_refracted_centroid_vs_gt_unrefracted=stat("err_unoccluded_refr_vs_gt_unrefracted_px"),
                          visible_refracted_centroid_vs_gt_apparent=stat("err_visible_refr_vs_gt_apparent_px"),
                          visible_unrefracted_centroid_vs_gt_unrefracted=stat("err_visible_unrefr_vs_gt_unrefracted_px"),
                          detector_vs_unoccluded_mask_centroid=stat("err_detector_vs_unoccluded_centroid_px"),
                          bias_unoccluded_refr_minus_gt_apparent=vec("unoccluded_refr_centroid", "gt_apparent"),
                          bias_detector_minus_unoccluded_centroid=vec("detector_centre", "unoccluded_refr_centroid")),
            segmentation=dict(iou_detector_vs_visible=stat("iou_detector_vs_visible"), dice_detector_vs_visible=stat("dice_detector_vs_visible"),
                              iou_detector_vs_unoccluded=stat("iou_detector_vs_unoccluded"), iou_refr_vs_unrefr=stat("iou_refr_vs_unrefr"),
                              dice_refr_vs_unrefr=stat("dice_refr_vs_unrefr")),
            visibility=dict(visible_fraction=stat("visible_fraction"), cornea_covers_pupil=stat("cornea_covers_pupil_fraction"), pupil_ring_iris_fraction=stat("pupil_ring_iris_fraction")),
            unclassified_fraction_max=max(r["unclassified_fraction"] for r in rows))
json.dump(summ, open(os.path.join(out, "masks_metrics.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in summ.items() if k != "validation_problems"}, indent=1)); print("PROBLEMS", problems[:10])
