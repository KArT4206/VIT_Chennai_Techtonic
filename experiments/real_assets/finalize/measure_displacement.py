"""Phase 2E: measure the vendor 16-bit displacement map before using it.

    blender -b --factory-startup --disable-autoexec ../3dscanstore/build/gnm_scan.blend --python measure_displacement.py -- OUT.json

* bit depth, value range, background value, distribution inside the UV island
* UV alignment: island mask of the displacement vs the GNM 1001 UV layout (rasterised)
* physical scale: least-squares fit of the displacement gradient to the vendor tangent-space normal map
  slopes (high-pass, several crops), metres per unit value; sign of the fit gives the direction convention
  and the normal map's green-channel convention
* frequency split: how much of the displacement is low-frequency shape vs pore-scale detail, and how strongly
  its pore-scale gradient correlates with the normal map (double counting)
"""
import json
import os
import sys

import bpy
import numpy as np
import OpenImageIO as oiio

out = sys.argv[sys.argv.index("--") + 1]
X = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "3dscanstore", "extracted", "Textures")
D = oiio.ImageBuf(os.path.join(X, "Displacement", "Face_Displacement.tif"))
spec = D.spec(); d = D.get_pixels(oiio.FLOAT)[..., 0]
N = oiio.ImageBuf(os.path.join(X, "TGA", "Face", "Face_Normal.tga")).get_pixels(oiio.FLOAT)[..., :3]
H, W = d.shape
R = dict(width=W, height=H, channels=spec.nchannels, format=str(spec.format), bits=spec.get_int_attribute("oiio:BitsPerSample"),
         min=float(d.min()), max=float(d.max()))
bg = float(d[0, 0])
# GNM tile-1001 island mask rasterised from the mesh UVs (coarse: polygon fill by bbox of triangles at 1/8 res)
me = bpy.data.objects["GNM_Head"].data
uv = np.empty(len(me.loops) * 2, np.float32); me.uv_layers["UDIM"].data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
ls = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("loop_start", ls)
s = 8; mask = np.zeros((H // s, W // s), bool)
yy, xx = np.mgrid[0:H // s, 0:W // s]; P = np.stack([(xx + 0.5) / (W // s), 1 - (yy + 0.5) / (H // s)], -1)
for f in np.where(mi == 0)[0]:
    q = uv[ls[f]:ls[f] + 4]
    for tri in ((0, 1, 2), (0, 2, 3)):
        a, b, c = q[list(tri)]
        x0, x1 = int(min(a[0], b[0], c[0]) * (W // s)), int(max(a[0], b[0], c[0]) * (W // s)) + 1
        y0, y1 = int((1 - max(a[1], b[1], c[1])) * (H // s)), int((1 - min(a[1], b[1], c[1])) * (H // s)) + 1
        p = P[max(y0, 0):y1, max(x0, 0):x1]
        v0, v1, v2 = c - a, b - a, p - a
        d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
        d20, d21 = v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01 + 1e-20
        u_ = (d11 * d20 - d01 * d21) / den; v_ = (d00 * d21 - d01 * d20) / den
        mask[max(y0, 0):y1, max(x0, 0):x1] |= (u_ >= -1e-3) & (v_ >= -1e-3) & (u_ + v_ <= 1 + 1e-3)
dsm = d[s // 2::s, s // 2::s][:mask.shape[0], :mask.shape[1]]
diff_bg = np.abs(dsm - bg) > 1e-4
R["background_value"] = bg
R["uv_alignment"] = dict(island_texels_gnm=int(mask.sum()), disp_nonbackground_in_island=float(diff_bg[mask].mean()),
                         disp_nonbackground_outside_island=float(diff_bg[~mask].mean()))
inside = np.repeat(np.repeat(mask, s, 0), s, 1)[:H, :W]
di = d[inside]
R["inside_percentiles"] = {str(k): float(v) for k, v in zip((0.1, 1, 5, 25, 50, 75, 95, 99, 99.9), np.percentile(di, (0.1, 1, 5, 25, 50, 75, 95, 99, 99.9)))}
R["inside_mean"] = float(di.mean())

# world metres per texel (GNM basis = scan positions, metres)
V = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3)
lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv)
aw = au = 0.0
for f in np.where(mi == 0)[0]:
    idx = lv[ls[f]:ls[f] + 4]; q = uv[ls[f]:ls[f] + 4]; p = V[idx]
    aw += 0.5 * np.linalg.norm(np.cross(p[2] - p[0], p[3] - p[1]))
    au += 0.5 * abs(np.cross(q[2] - q[0], q[3] - q[1]))
m_per_texel = np.sqrt(aw / au) / W
R["metres_per_texel_mean"] = float(m_per_texel)


def blur(a, sig):
    k = np.fft.fftfreq(a.shape[0])[:, None] ** 2 + np.fft.fftfreq(a.shape[1])[None, :] ** 2
    return np.real(np.fft.ifft2(np.fft.fft2(a) * np.exp(-2 * np.pi ** 2 * sig ** 2 * k)))


fits = []
for cy, cx in ((0.45, 0.30), (0.45, 0.70), (0.60, 0.50), (0.35, 0.50), (0.70, 0.35), (0.70, 0.65)):
    y0, x0 = int(cy * H) - 512, int(cx * W) - 512
    m = inside[y0:y0 + 1024, x0:x0 + 1024]
    if m.mean() < 0.98:
        continue
    h = d[y0:y0 + 1024, x0:x0 + 1024].astype(np.float64)
    n = N[y0:y0 + 1024, x0:x0 + 1024].astype(np.float64) * 2 - 1
    hp = h - blur(h, 8)                       # pore-scale band (< ~8 texels)
    su = -n[..., 0] / n[..., 2]; sv = -n[..., 1] / n[..., 2]
    su = su - blur(su, 8); sv = sv - blur(sv, 8)
    gx = np.gradient(hp, axis=1) / m_per_texel          # d(value)/d(metre) along +u
    gy = -np.gradient(hp, axis=0) / m_per_texel         # +v is image-up
    ku = (gx * su).sum() / (gx * gx).sum(); kv = (gy * sv).sum() / (gy * gy).sum()
    cu = np.corrcoef(gx.ravel(), su.ravel())[0, 1]; cv = np.corrcoef(gy.ravel(), sv.ravel())[0, 1]
    lo = blur(h, 32)
    fits.append(dict(crop=[cy, cx], scale_u_m=float(ku), scale_v_m=float(kv), corr_u=float(cu), corr_v=float(cv),
                     std_highpass=float(hp.std()), std_lowpass=float((lo - lo.mean()).std())))
R["normal_fit"] = fits
json.dump(R, open(out, "w"), indent=1)
print(json.dumps(R, indent=1))
