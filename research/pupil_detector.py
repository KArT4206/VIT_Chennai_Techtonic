"""Independent image-based pupil detector (numpy + scipy + pillow only).

It never reads metadata, ground truth or the scene: input is the RGB image alone.

    detect(img) -> list of up to 2 dicts {centre:[x,y], radius, confidence, inliers, rays, status}
                   sorted image-left first.

Method
  1. Candidate blobs: pixels darker than each level in DARK_LEVELS (luminance 0-255) -> holes filled -> connected
     components; keep components of plausible pupil area and roundness.
  2. Pair selection: the two most pupil-like blobs that lie side by side (|dy| small, dx in range).
  3. Sub-pixel refinement: 180 rays from the blob centroid; on each ray find the first sub-pixel
     crossing of the half level between pupil and iris luminance. Rays that touch a bright
     catchlight (> BRIGHT_T) before the crossing are discarded. A circle is fitted to the edge
     points with RANSAC + algebraic least squares, so eyelid/lash occlusion becomes outliers.
  Coordinates: pixel (i, j) has its centre at (i + 0.5, j + 0.5), origin top-left (same as the wrapper ground truth);
     internal sampling uses array indices, so +0.5 is added to every returned centre.
  4. Confidence = inlier fraction x exp(-rms residual), and status 'ok' | 'low_confidence' | 'fail'.
"""
import numpy as np
from scipy import ndimage

DARK_LEVELS = (12, 16, 20, 25, 30, 40, 55)
BRIGHT_T = 150.0
AREA = (150, 6000)
N_RAYS = 180


def _lum(img):
    a = np.asarray(img, dtype=float)
    return a[..., :3].mean(2) if a.ndim == 3 else a


def _blobs(lum, t):
    mask = ndimage.binary_fill_holes(lum < t)
    mask = ndimage.binary_opening(mask, iterations=2)
    lab, n = ndimage.label(mask)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        comp = lab[sl] == i
        area = int(comp.sum())
        if not AREA[0] <= area <= AREA[1]:
            continue
        h, w = comp.shape
        r_eq = np.sqrt(area / np.pi)
        fill = area / (np.pi * (max(h, w) / 2) ** 2)          # 1.0 for a perfect disc
        aspect = min(h, w) / max(h, w)
        if aspect < 0.6 or fill < 0.6:
            continue
        cy, cx = ndimage.center_of_mass(comp)
        out.append(dict(c=np.array([cx + sl[1].start, cy + sl[0].start]), r=r_eq, score=fill * aspect, area=area, t=t))
    return out


def _pair(blobs):
    best, best_s = None, -1
    for i in range(len(blobs)):
        for j in range(i + 1, len(blobs)):
            a, b = blobs[i], blobs[j]
            dx, dy = abs(a["c"][0] - b["c"][0]), abs(a["c"][1] - b["c"][1])
            rr = min(a["r"], b["r"]) / max(a["r"], b["r"])
            if dy > 0.5 * dx or not (6 * a["r"] < dx < 40 * a["r"]) or rr < 0.7:
                continue
            s = a["score"] * b["score"] * rr
            if s > best_s:
                best, best_s = (a, b), s
    if best is None:
        return [], -1.0
    return list(best), best_s


def _fit_circle(x, y):
    a = np.c_[2 * x, 2 * y, np.ones(len(x))]
    cx, cy, c = np.linalg.lstsq(a, x ** 2 + y ** 2, rcond=None)[0]
    return cx, cy, np.sqrt(max(c + cx ** 2 + cy ** 2, 0))


def refine(lum, c0, r0, rng=None):
    rng = rng or np.random.default_rng(0)
    inner = ndimage.map_coordinates(lum, [[c0[1]], [c0[0]]], order=1)[0]
    pupil_level = np.percentile(lum[int(c0[1] - r0 / 2):int(c0[1] + r0 / 2) + 1, int(c0[0] - r0 / 2):int(c0[0] + r0 / 2) + 1], 20)
    ring = []
    pts = []
    ts = np.linspace(0, 2 * r0 * 1.0 + 6, 400)
    for ang in np.linspace(0, 2 * np.pi, N_RAYS, endpoint=False):
        d = np.array([np.cos(ang), np.sin(ang)])
        xy = c0[:, None] + d[:, None] * ts
        prof = ndimage.map_coordinates(lum, [xy[1], xy[0]], order=1)
        ring.append(prof[(ts > 1.4 * r0) & (ts < 1.9 * r0)])
        pts.append((d, prof))
    iris_level = np.median(np.concatenate(ring))
    half = pupil_level + 0.5 * (iris_level - pupil_level)
    ex, ey = [], []
    for d, prof in pts:
        idx = np.nonzero(prof > half)[0]
        if len(idx) == 0 or idx[0] == 0:
            continue
        k = idx[0]
        if prof[:k + 1].max() > BRIGHT_T or (k + 1 < len(prof) and prof[k + 1] > BRIGHT_T):
            continue                                    # catchlight on this ray
        t = ts[k - 1] + (half - prof[k - 1]) / (prof[k] - prof[k - 1]) * (ts[k] - ts[k - 1])
        ex.append(c0[0] + d[0] * t); ey.append(c0[1] + d[1] * t)
    ex, ey = np.array(ex), np.array(ey)
    if len(ex) < 12:
        return None
    best = None
    for _ in range(300):
        s = rng.choice(len(ex), 3, replace=False)
        try:
            cx, cy, r = _fit_circle(ex[s], ey[s])
        except np.linalg.LinAlgError:
            continue
        if not 0.5 * r0 < r < 1.6 * r0:
            continue
        inl = np.abs(np.hypot(ex - cx, ey - cy) - r) < 0.75
        if best is None or inl.sum() > best.sum():
            best = inl
    if best is None or best.sum() < 12:
        return None
    cx, cy, r = _fit_circle(ex[best], ey[best])
    res = np.hypot(ex[best] - cx, ey[best] - cy) - r
    rms = float(np.sqrt(np.mean(res ** 2)))
    conf = float(best.sum() / N_RAYS * np.exp(-rms))
    return dict(centre=[float(cx) + 0.5, float(cy) + 0.5], radius=float(r), confidence=round(conf, 4), inliers=int(best.sum()),
                rays=int(len(ex)), rms_px=round(rms, 4), status="ok" if conf >= 0.35 else "low_confidence")


def detect(img, roi=None):
    """roi: optional list of (x0, y0, x1, y1) search boxes, one per eye. This is a fixed scene-level prior
    (for example from the detector's own detection on a reset frame), never per-frame ground truth."""
    lum = _lum(img)
    if roi:
        out = []
        for x0, y0, x1, y1 in roi:
            sub = lum[y0:y1, x0:x1]
            bl = [b for t in DARK_LEVELS for b in _blobs(sub, t)]
            if not bl:
                continue
            b = max(bl, key=lambda b: b["score"])
            c = b["c"] + np.array([x0, y0])
            r = refine(lum, c, b["r"])
            out.append(r if r else dict(centre=[float(c[0]) + 0.5, float(c[1]) + 0.5], radius=float(b["r"]), confidence=0.0, status="fail"))
        return sorted(out, key=lambda d: d["centre"][0])
    # adaptive threshold: try several dark levels, keep the most disc-like side-by-side pair
    best, best_s = [], -1
    for t in DARK_LEVELS:
        pair, sc = _pair(_blobs(lum, t))
        if sc > best_s:
            best, best_s = pair, sc
    if not best:      # no side-by-side pair at any level: fall back to the single most disc-like blob
        singles = [b for t in DARK_LEVELS for b in _blobs(lum, t)]
        best = sorted(singles, key=lambda b: -b["score"])[:1]
    cands = best
    out = []
    for b in cands:
        r = refine(lum, b["c"], b["r"])
        out.append(r if r else dict(centre=[float(b["c"][0]) + 0.5, float(b["c"][1]) + 0.5], radius=float(b["r"]),
                                     confidence=0.0, status="fail"))
    return sorted(out, key=lambda d: d["centre"][0])
