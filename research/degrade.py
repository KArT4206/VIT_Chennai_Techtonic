"""WS2: reproducible camera/sensor degradation of clean renders. Clean images and labels are never modified.

    python3 research/degrade.py apply <src_png> <label_json> <out_dir> <spec_json_or_inline>
    python3 research/degrade.py sweep <bundle_dir> <out_dir> [--seed 7]        (all ops x levels on the 10 frames)
    python3 research/degrade.py selftest

A spec is a list of ops applied in order, each {"op": name, ...params}; one integer seed drives every random op.
Ops (all photometric or centred-kernel, so geometry-derived labels stay valid by construction):
  noise     Poisson-Gaussian sensor model: full_well_e (photons at value 1.0), read_noise_e, (shot + read noise)
  motion    linear motion blur: length_px, angle_deg  (centred, symmetric kernel -> no centroid shift)
  defocus   uniform disc (pillbox) blur: radius_px
  exposure  stops (x 2**stops in linear light, sRGB re-encoded, clipped)
  glint     extra corneal reflection: n, radius_px, strength, placed by seed inside a box (box_px, given or derived)
  jpeg      compression: quality 1..95
  eyelid    2-D occluder band: frac (0..1 of eye-box height) lowered from the top, skin colour sampled above the box
  illum     smooth illumination gradient: strength (0..1), angle_deg
Output: <out_dir>/<stem>.png, <stem>.label.json (byte copy of the input label) and <stem>.degrade.json
(spec, seed, sha256 of source, label and output, library versions).
"""
import hashlib, io, json, math, os, shutil, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage, signal


def srgb_to_lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def _kernel_motion(L, ang):
    n = int(math.ceil(L)) | 1; k = np.zeros((n, n)); c = n // 2
    for t in np.linspace(-L / 2, L / 2, 4 * n):
        x, y = c + t * math.cos(math.radians(ang)), c - t * math.sin(math.radians(ang))
        k[int(round(y)), int(round(x))] += 1
    return k / k.sum()


def _kernel_disc(r):
    n = int(math.ceil(r)) * 2 + 1; c = n // 2; yy, xx = np.mgrid[:n, :n]
    k = ((xx - c) ** 2 + (yy - c) ** 2 <= r * r).astype(float); return k / k.sum()


def _conv(a, k):
    return np.stack([signal.fftconvolve(a[..., i], k, mode="same") for i in range(3)], -1)


def apply_ops(img, spec, seed, eye_box=None):
    """img float RGB 0..1 (sRGB). eye_box (x0,y0,x1,y1) bounds glint/eyelid ops; required for those ops."""
    rng = np.random.default_rng(seed); a = img.copy(); log = []
    for op in spec:
        o = op["op"]
        if o == "noise":
            lin = srgb_to_lin(a); fw = op.get("full_well_e", 2000.0); rn = op.get("read_noise_e", 3.0)
            e = rng.poisson(np.clip(lin, 0, 1) * fw) + rng.normal(0, rn, lin.shape)
            a = lin_to_srgb(e / fw)
        elif o == "motion":
            a = _conv(a, _kernel_motion(op["length_px"], op.get("angle_deg", 0.0)))
        elif o == "defocus":
            a = _conv(a, _kernel_disc(op["radius_px"]))
        elif o == "exposure":
            a = lin_to_srgb(srgb_to_lin(a) * 2 ** op["stops"])
        elif o == "illum":
            h, w = a.shape[:2]; yy, xx = np.mgrid[:h, :w]; ang = math.radians(op.get("angle_deg", 90))
            g = ((xx - w / 2) * math.cos(ang) - (yy - h / 2) * math.sin(ang)) / (max(h, w) / 2)
            a = lin_to_srgb(srgb_to_lin(a) * (1 + op["strength"] * g)[..., None])
        elif o == "glint":
            x0, y0, x1, y1 = op.get("box_px") or eye_box; lin = srgb_to_lin(a); yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]; pos = []
            for _ in range(op.get("n", 1)):
                cx, cy = rng.uniform(x0, x1), rng.uniform(y0, y1); pos.append([round(cx, 2), round(cy, 2)])
                lin = lin + op.get("strength", 3.0) * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * op.get("radius_px", 2.0) ** 2))[..., None]
            a = lin_to_srgb(lin); log.append(dict(op="glint", positions=pos))
        elif o == "eyelid":
            x0, y0, x1, y1 = [int(v) for v in (op.get("box_px") or eye_box)]
            skin = a[max(0, y0 - 25):max(1, y0 - 5), x0:x1].reshape(-1, 3).mean(0)
            yb = y0 + int(round(op["frac"] * (y1 - y0)))
            a[y0:yb, x0:x1] = skin
            # soft lower edge (2 px) so the occluder is not a hard synthetic step
            for d, w_ in ((0, .66), (1, .33)):
                if yb + d < a.shape[0]: a[yb + d, x0:x1] = w_ * skin + (1 - w_) * a[yb + d, x0:x1]
        elif o == "jpeg":
            buf = io.BytesIO(); Image.fromarray((np.clip(a, 0, 1) * 255 + .5).astype(np.uint8)).save(buf, "JPEG", quality=int(op["quality"]))
            a = np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB")).astype(float) / 255
        else:
            raise ValueError(f"unknown op {o}")
    return np.clip(a, 0, 1), log


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def eye_boxes(label, half=45):
    return [(int(label[f"pupil_center_2D_{s}"][0]) - half, int(label[f"pupil_center_2D_{s}"][1]) - half,
             int(label[f"pupil_center_2D_{s}"][0]) + half, int(label[f"pupil_center_2D_{s}"][1]) + half) for s in "LR"]


def apply_file(src, label_path, out_dir, spec, seed, stem=None):
    """Writes degraded image + byte-copied label + provenance. Occluder/glint boxes come from the label's eye
    positions: this places the disturbance at the eye, which is the point of the test; labels are not altered."""
    os.makedirs(out_dir, exist_ok=True); stem = stem or os.path.splitext(os.path.basename(src))[0]
    label = json.load(open(label_path))
    img = np.asarray(Image.open(src).convert("RGB")).astype(float) / 255
    logs = []
    if any(o["op"] in ("glint", "eyelid") for o in spec):
        for i, box in enumerate(eye_boxes(label)):
            per = [dict(o, box_px=box) if o["op"] in ("glint", "eyelid") else o for o in spec]
            sub = [o for o in per if o["op"] in ("glint", "eyelid")]
            img, lg = apply_ops(img, sub, seed * 1000 + i); logs += lg
        spec_rest = [o for o in spec if o["op"] not in ("glint", "eyelid")]
    else:
        spec_rest = spec
    img, lg = apply_ops(img, spec_rest, seed); logs += lg
    outp = os.path.join(out_dir, stem + ".png"); Image.fromarray((img * 255 + .5).astype(np.uint8)).save(outp)
    lab_out = os.path.join(out_dir, stem + ".label.json"); shutil.copyfile(label_path, lab_out)
    import scipy, PIL
    prov = dict(source=os.path.abspath(src), source_sha256=sha(src), label_source=os.path.abspath(label_path), label_sha256=sha(label_path),
                label_copy_sha256=sha(lab_out), output_sha256=sha(outp), spec=spec, seed=seed, events=logs,
                versions=dict(numpy=np.__version__, scipy=scipy.__version__, pillow=PIL.__version__))
    json.dump(prov, open(os.path.join(out_dir, stem + ".degrade.json"), "w"), indent=1)
    return outp, prov


LEVELS = dict(noise=[dict(full_well_e=w) for w in (4000, 1000, 250, 60)], motion=[dict(length_px=l, angle_deg=0) for l in (3, 7, 15, 25)],
              defocus=[dict(radius_px=r) for r in (1, 2, 4, 6)], exposure=[dict(stops=s) for s in (-2, -1, 1, 2)],
              glint=[dict(n=n, radius_px=2.5, strength=4) for n in (1, 2, 3, 4)], jpeg=[dict(quality=q) for q in (80, 50, 25, 10)],
              eyelid=[dict(frac=f) for f in (0.2, 0.35, 0.5, 0.6)], illum=[dict(strength=s, angle_deg=90) for s in (0.2, 0.4, 0.6, 0.8)])


def sweep(bundle, out, seed=7):
    meta = json.load(open(os.path.join(bundle, "metadata.json")))
    tmp_lab = os.path.join(out, "_labels"); os.makedirs(tmp_lab, exist_ok=True)
    n = 0
    for f in meta["frames"]:
        lp = os.path.join(tmp_lab, f"frame_{f['frame']:02d}.json"); json.dump(f, open(lp, "w"), indent=1)
        for op, levels in LEVELS.items():
            for li, p in enumerate(levels):
                apply_file(os.path.join(bundle, f["file"]), lp, os.path.join(out, op, f"L{li}"), [dict(op=op, **p)], seed + f["frame"], f"frame_{f['frame']:02d}"); n += 1
    print("SWEEP", n, "images")


def selftest():
    ok = True
    def ck(n, c, v):
        nonlocal ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + f"{n}: {v}")
    rng = np.random.default_rng(0); img = rng.uniform(.2, .8, (64, 64, 3))
    a1, _ = apply_ops(img, [dict(op="noise", full_well_e=500)], 5); a2, _ = apply_ops(img, [dict(op="noise", full_well_e=500)], 5)
    ck("same seed -> identical output", np.array_equal(a1, a2), "ok")
    a3, _ = apply_ops(img, [dict(op="noise", full_well_e=500)], 6); ck("different seed -> different output", not np.array_equal(a1, a3), "ok")
    disc = np.zeros((101, 101, 3)) + .8; yy, xx = np.mgrid[:101, :101]; disc[(xx - 50.0) ** 2 + (yy - 50.0) ** 2 < 15 ** 2] = .05
    def cen(a):
        m = a.mean(2) < .4; ys, xs = np.nonzero(m); return xs.mean(), ys.mean()
    for spec in ([dict(op="motion", length_px=9, angle_deg=30)], [dict(op="defocus", radius_px=4)], [dict(op="exposure", stops=1)]):
        b, _ = apply_ops(disc, spec, 1); c = cen(b); ck(f"{spec[0]['op']} keeps disc centroid at (50,50)", math.dist(c, (50, 50)) < 0.05, [round(c[0], 3), round(c[1], 3)])
    ck("motion kernel sums to 1", abs(_kernel_motion(9, 30).sum() - 1) < 1e-12, "ok")
    b, _ = apply_ops(disc, [dict(op="exposure", stops=0)], 1); ck("exposure 0 stops is identity (<1e-12)", np.abs(b - disc).max() < 1e-9, float(np.abs(b - disc).max()))
    return ok


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "selftest":
        sys.exit(0 if selftest() else 1)
    if a[0] == "sweep":
        sweep(a[1], a[2], int(a[a.index("--seed") + 1]) if "--seed" in a else 7)
    if a[0] == "apply":
        spec = json.load(open(a[4])) if os.path.exists(a[4]) else json.loads(a[4])
        print(apply_file(a[1], a[2], a[3], spec, int(a[5]) if len(a) > 5 else 0)[0])
