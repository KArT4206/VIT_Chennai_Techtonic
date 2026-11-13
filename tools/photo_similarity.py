"""How close is a render to a real reference portrait? (needs numpy and pillow)

    python3 tools/photo_similarity.py <render.png> <render_state.json> <photo.jpg> <photo_pupils>

  render_state.json   the wrapper's JSON for that render (gives the 2D pupil centres)
  photo_pupils        "xL,yL,xR,yR" pupil centres in the photo, in its own pixels

Everything is measured in units of eye spacing (inter-pupil distance), so faces of different size
and shape are compared at the same anatomical spots and the same skin scale:
  cheek colour (CIE Lab dE), skin micro-texture, face contrast, stubble speckle (chin / cheek).
"""

import json
import sys

import numpy as np
from PIL import Image, ImageFilter


def lab(rgb):
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


# anatomical sample spots, (x, y) in inter-pupil units from the pupil midpoint (y down)
CHEEK = (-0.62, 0.95)      # under the image-left eye, mid cheek
CHIN = (0.0, 1.65)        # on the chin, above its lower edge (both chins end ~1.85 IPD below the eyes)
FACE = (-0.95, -0.6, 0.95, 1.8)
IPD_PX = 150               # both images are resampled so the eyes are this far apart


def measure(img, pl, pr):
    pl, pr = np.array(pl, float), np.array(pr, float)
    k = IPD_PX / np.linalg.norm(pr - pl)
    im = img.convert("RGB").resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
    mid = (pl + pr) / 2 * k
    at = lambda u: (mid + np.array(u) * IPD_PX).astype(int)
    a = np.asarray(im).astype(float)
    g = np.asarray(im.convert("L")).astype(float)
    blur = np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(3))).astype(float)
    h = 10

    def patch(arr, p):
        x, y = at(p)
        return arr[y - h:y + h, x - h:x + h]

    col = lab(patch(a, CHEEK).reshape(-1, 3)).mean(0)
    tex = (patch(g, CHEEK) - patch(blur, CHEEK)).std()
    x0, y0 = at(FACE[:2]); x1, y1 = at(FACE[2:])
    contrast = g[y0:y1, x0:x1].std()
    # stubble reads as dark speckle: fine-detail energy on the chin relative to the cheek
    # (a brightness ratio depended on how each photo happened to light the chin)
    stubble = (patch(g, CHIN) - patch(blur, CHIN)).std() / max(tex, 1e-6)
    return col, tex, contrast, stubble


def main(render, state_path, photo, photo_pupils):
    st = json.load(open(state_path))
    o = measure(Image.open(render), st["pupil_center_2D_R"], st["pupil_center_2D_L"])   # image-left first
    xl, yl, xr, yr = (float(v) for v in photo_pupils.split(","))
    r = measure(Image.open(photo), (xl, yl), (xr, yr))
    de = float(np.linalg.norm(o[0] - r[0]))
    print(f"cheek colour Lab ours {o[0].round(1)} photo {r[0].round(1)}  dE={de:.1f}")
    print(f"micro-texture     ours {o[1]:.2f} photo {r[1]:.2f}  ratio={o[1] / r[1]:.2f}")
    print(f"face contrast     ours {o[2]:.1f} photo {r[2]:.1f}  ratio={o[2] / r[2]:.2f}")
    print(f"stubble speckle   ours {o[3]:.2f} photo {r[3]:.2f}  (chin / cheek fine detail)")
    score = lambda x: max(0.0, 1 - abs(np.log(x)))
    parts = {"colour": max(0.0, 1 - de / 30), "texture": score(o[1] / r[1]),
             "contrast": score(o[2] / r[2]), "stubble": score(o[3] / r[3])}
    print({k: round(v, 2) for k, v in parts.items()}, f"overall {100 * np.mean(list(parts.values())):.0f}%")


if __name__ == "__main__":
    main(*sys.argv[1:5])
