"""Independent check of a Track 1 bundle: layout, sequence, metadata maths and rendered pupils.

    python3 tools/verify.py <bundle_dir>            (needs numpy and pillow)

It never imports eyes.py. Pupils are found in the rendered pixels and compared against the
metadata, and the camera matrices are checked by reprojecting the 3D pupil centres.
Exit code 0 only if every check passes.
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image

FAILS = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def largest_component(mask):
    """Largest 4-connected region of a boolean mask."""
    labels = np.zeros(mask.shape, int)
    best_size, best_label = 0, 0
    for label, (y, x) in enumerate(zip(*np.nonzero(mask)), start=1):
        if labels[y, x]:
            continue
        labels[y, x] = label
        stack, size = [(y, x)], 0
        while stack:
            cy, cx = stack.pop()
            size += 1
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = label
                    stack.append((ny, nx))
        if size > best_size:
            best_size, best_label = size, label
    return labels == best_label


def detect_pupil(img, guess, win=22, bright=110):
    """Pupil centre from a circle fitted to the pupil/iris edge in a window around the guess.

    Corneal catchlights often cover part of the pupil, which biases an area centroid. Edge pixels
    that border a bright catchlight are therefore dropped, and the circle is fitted to the
    remaining pupil-iris boundary only (algebraic least squares).

    The dark mask is the largest connected region below a threshold set 6 % of the way from the
    darkest pixels to the window median. A fixed darkest-N-% cut breaks on a flat black pupil
    (ties give a random speckle of pixels) and picks up lashes, so it was replaced. Measured on
    five lighting setups: every pupil within 1.22 px for any fraction from 5 % to 8 %.
    """
    x0, y0 = int(round(guess[0])) - win, int(round(guess[1])) - win
    lum = img[y0:y0 + 2 * win, x0:x0 + 2 * win].mean(2)
    lo = np.percentile(lum, 1)
    mask = largest_component(lum < lo + 0.06 * (np.median(lum) - lo))
    pad = np.pad(mask, 1)
    inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    edge = mask & ~inner
    lp = np.pad(lum, 1, mode="edge")
    near_bright = np.zeros_like(mask)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            near_bright |= lp[1 + dy:lp.shape[0] - 1 + dy, 1 + dx:lp.shape[1] - 1 + dx] > bright
    ys, xs = np.nonzero(edge & ~near_bright)
    xs, ys = xs + 0.5, ys + 0.5
    a = np.c_[2 * xs, 2 * ys, np.ones(len(xs))]
    cx, cy, _ = np.linalg.lstsq(a, xs ** 2 + ys ** 2, rcond=None)[0]
    return np.array([cx + x0, cy + y0])


def main(root):
    meta_path = os.path.join(root, "metadata.json")
    for rel in ("scene.blend", "wrapper/eyes.py", "renders", "metadata.json", "README.md"):
        check(os.path.exists(os.path.join(root, rel)), f"bundle contains {rel}")
    if not os.path.exists(meta_path):
        return
    meta = json.load(open(meta_path))
    frames = meta["frames"]
    check(len(frames) == 10, f"10 frames in metadata (got {len(frames)})")
    check(abs(meta["camera_distance_m"] - 0.40) < 1e-4, f"camera 0.40 m from eye midpoint ({meta['camera_distance_m']})")
    check(abs(meta["fixation_distance_m"] - 0.35) < 1e-9, "fixation distance 0.35 m")

    detected = []
    for k, f in enumerate(frames):
        theta = 2 * math.pi * k / 10
        ok_seq = (f["frame"] == k and abs(f["theta"] - theta) < 1e-5
                  and abs(f["input"]["h"] - math.sin(theta)) < 1e-5 and abs(f["input"]["v"] - math.cos(theta)) < 1e-5)
        check(ok_seq, f"frame {k}: theta={f['theta']:.4f} h=sin, v=cos")
        img_path = os.path.join(root, f["file"])
        im = Image.open(img_path)
        check(im.size == (1024, 1024) and im.format == "PNG", f"frame {k}: 1024x1024 PNG")
        img = np.asarray(im.convert("RGB")).astype(float)

        k_mat = np.array(f["camera_matrix"])
        rt = np.array(f["camera_extrinsic_world_to_cam"])
        for side in "LR":
            # The pupil is seen through the refracting cornea, so the visible 2D pupil lies on the
            # straight camera ray through the corneal point it is seen at, not the anatomical centre.
            seen_at = f.get(f"pupil_center_cornea_3D_{side}", f[f"pupil_center_3D_{side}"])
            p = rt @ np.r_[seen_at, 1.0]
            uv = (k_mat @ p)[:2] / p[2]
            err = np.linalg.norm(uv - f[f"pupil_center_2D_{side}"])
            check(err < 0.05, f"frame {k} {side}: K[R|t] reprojects the seen pupil to 2D (err {err:.4f} px)")
            found = detect_pupil(img, f[f"pupil_center_2D_{side}"])
            d = np.linalg.norm(found - f[f"pupil_center_2D_{side}"])
            check(d < 2.5, f"frame {k} {side}: rendered pupil at metadata 2D point (off by {d:.2f} px)")
            detected.append((k, side, found))

    # Direction: rendered pupil displacement must follow (h, -v) in image space for every frame.
    by_side = {s: np.array([d for (_, side, d) in detected if side == s]) for s in "LR"}
    hv = np.array([[f["input"]["h"], -f["input"]["v"]] for f in frames])
    for s in "LR":
        disp = by_side[s] - by_side[s].mean(0)      # ring centre ~ straight-ahead gaze
        cos = (disp * hv).sum(1) / (np.linalg.norm(disp, axis=1) * np.linalg.norm(hv, axis=1))
        check(cos.min() > 0.9, f"eye {s}: every frame's rendered pupil moves in the commanded direction "
                               f"(min cosine {cos.min():.3f}, shift {np.linalg.norm(disp, axis=1).mean():.1f} px)")
    clockwise = all(np.cross(np.r_[hv[i], 0], np.r_[hv[(i + 1) % 10], 0])[2] > 0 for i in range(10))
    check(clockwise and frames[0]["input"]["v"] > 0.99, "sequence starts at top and runs clockwise on screen")

    directions = os.path.join(root, "directions")
    if os.path.isdir(directions):
        check_directions(directions)

    print(f"\n{'ALL CHECKS PASSED' if not FAILS else str(len(FAILS)) + ' CHECK(S) FAILED'}")


DIRECTIONS = {"left": (-1.0, 0.0), "right": (1.0, 0.0), "up": (0.0, 1.0), "down": (0.0, -1.0)}


def check_directions(folder, min_shift_px=4.0):
    """The spec's 5-direction check on renders made with --move / --reset:
    each direction must move both rendered pupils the right way vs reset, and reset must be centred."""
    def load(stem):
        state = json.load(open(os.path.join(folder, stem + ".json")))
        img = np.asarray(Image.open(os.path.join(folder, stem + ".png")).convert("RGB")).astype(float)
        return {s: detect_pupil(img, state[f"pupil_center_2D_{s}"]) for s in "LR"}, state

    centre, centre_state = load("reset")
    check(centre_state["input"] == {"h": 0.0, "v": 0.0}, "reset: input is (0, 0)")
    for name, (h, v) in DIRECTIONS.items():
        found, _ = load(f"move_h{h:+.2f}_v{v:+.2f}")
        want = np.array([h, -v])                       # image y points down
        for s in "LR":
            d = found[s] - centre[s]
            along = float(d @ want)
            across = float(abs(d @ np.array([want[1], -want[0]])))
            check(along >= min_shift_px and across < along / 3,
                  f"direction {name} {s}: rendered pupil moves {along:.1f} px the right way "
                  f"({across:.1f} px sideways)")
    for s in "LR":
        mid = np.mean([load(f"move_h{h:+.2f}_v{v:+.2f}")[0][s] for h, v in DIRECTIONS.values()], axis=0)
        off = np.linalg.norm(centre[s] - mid)
        check(off < 1.5, f"reset {s}: centre pupil sits between left/right/up/down ({off:.2f} px off)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
    sys.exit(1 if FAILS else 0)
