"""Final-round silent video for Team Techtonic: built only from real renders and committed result files.

    python3 research/demo/source/build_video.py <work_dir> <out_dir> [--preview SECONDS ...] [--fps 30]

<work_dir> is the clean-run folder (SyntheticEyes-Track1-research-work/clean_run_2026-11-23). Every number shown is
read from AUDIT/results at build time and checked against the figures agreed for the video (CHECK below); the
build stops if any differs. Imagery: the shipped 10-frame renders, the research scene views, ablation/dataset/
dynamics/benchmark renders and detector overlays. Diagrams that are not measured outputs carry the label
"SCHEMATIC". No speech; the soundtrack is synthesised in music.py (instrumental, no vocals).
Writes <out_dir>/final_round_silent.mp4 (H.264, 1920x1080, 30 fps), thumbnail.png, scene_timeline.csv,
asset_manifest.json; --preview renders single PNG frames instead.
"""
import csv, hashlib, json, math, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RES = os.path.join(REPO, "AUDIT", "results"); SCENE = os.path.join(REPO, "demo", "final_hair", "demo_assets")
a = sys.argv[1:]; WK, OUT = a[0], a[1]
FPS = int(a[a.index("--fps") + 1]) if "--fps" in a else 30
PREVIEW = [float(x) for x in a[a.index("--preview") + 1:]] if "--preview" in a else None
W, H = 1920, 1080
USED = {}


def src(path):
    """Register a source file for the asset manifest and return its path."""
    if path not in USED:
        USED[path] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return path


def J(rel):
    return json.load(open(src(os.path.join(RES, rel))))


# ------------------------------------------------------------------ numbers, read from result files
comp = J("compliance.json"); dfit = J("ws1_depth/depth_fit.json"); probe = J("ws1_depth/depth_probe_extended.json")
det = {k: J(f) for k, f in (("released frames", "release_metrics.json"), ("full scene", "full_roi_metrics.json"),
                            ("clean condition", "no_lids_lens_roi_metrics.json"), ("40-sample dataset", "ws6_dataset_v1/dataset_roi_metrics.json"))}
m1 = J("ws6_dataset_v1/manifest.json"); cov = J("ws4_dataset/coverage.json")["coverage"]; integ2 = J("ws4_dataset/integrity.json")
dyn = J("ws5_dynamics/dynamics_render_check.json"); dval = J("ws5_dynamics/dynamics_validation.json")
bench = J("ws6_performance/bench_compare.json"); band = J("ws6_performance/band_audit.json"); levels = J("research_pupil_levels.json")
unc = J("ws3_masks/unclassified_audit.json")["summary"]
legacy = open(src(os.path.join(RES, "verify_py_release_bundle.txt"))).read().splitlines()
N = dict(
    comp_pass=comp["passed"], comp_total=comp["passed"] + comp["failed"],
    anat_L=probe["reset_pose"]["L"]["wrapper_pupil_depth_mm"], anat_R=probe["reset_pose"]["R"]["wrapper_pupil_depth_mm"],
    paint_L=probe["reset_pose"]["L"]["painted_surface_depth_along_axis_mm"], paint_R=probe["reset_pose"]["R"]["painted_surface_depth_along_axis_mm"],
    fit_L=dfit["conditions"]["no_lids_lens"]["L"]["best_depth_mm"], fit_R=dfit["conditions"]["no_lids_lens"]["R"]["best_depth_mm"],
    ci_L=dfit["conditions"]["no_lids_lens"]["L"]["bootstrap_depth_mm"], ci_R=dfit["conditions"]["no_lids_lens"]["R"]["bootstrap_depth_mm"],
    ho_fit_L=dfit["conditions"]["no_lids_lens"]["L"]["heldout_fitted_depth_model"]["rmse_px"], ho_fit_R=dfit["conditions"]["no_lids_lens"]["R"]["heldout_fitted_depth_model"]["rmse_px"],
    ho_gt_L=dfit["conditions"]["no_lids_lens"]["L"]["heldout_wrapper_gt_no_offset"]["rmse_px"], ho_gt_R=dfit["conditions"]["no_lids_lens"]["R"]["heldout_wrapper_gt_no_offset"]["rmse_px"],
    n_heldout=dfit["conditions"]["no_lids_lens"]["L"]["n_heldout"],
    det={k: v["success_rate"] for k, v in det.items()},
    v1=(len(m1["samples"]), m1["config"]["n"], len(m1["failures"])), v2=(cov["n_samples"], cov["planned"], cov["failures"]), kinds=cov["kinds"],
    sac_L=dyn["saccade"]["image_left"]["measured_duration_5_95_ms"], sac_R=dyn["saccade"]["image_right"]["measured_duration_5_95_ms"],
    sac_cmd=dyn["saccade"]["image_left"]["commanded_duration_5_95_ms"], sac_dt=dyn["saccade"]["image_left"]["frame_interval_ms"],
    glitch=dyn["saccade"]["image_right"]["max_residual_px"], pur_lag=dyn["pursuit"]["image_left"]["measured_lag_ms"],
    pur_res=dyn["pursuit"]["image_left"]["lag_resolution_ms"], pur_gain=(dyn["pursuit"]["image_left"]["measured_gain_vs_target"], dyn["pursuit"]["image_right"]["measured_gain_vs_target"]),
    verg=dyn["vergence"]["converges"], ver_dx=(dyn["vergence"]["image_left"]["dx_first_to_last_px"], dyn["vergence"]["image_right"]["dx_first_to_last_px"]),
    pers_speed=bench["configs"]["persistent"]["speedup_sequence_vs_original"], pers_max=band["configs"]["persistent"][0]["band_interior_max"],
    roi_in=band["configs"]["band"][0]["band_interior_max"], roi_edge=band["configs"]["band"][0]["band_edge_frame_max"],
    roi_accept=bench["configs"]["band"]["accept"], pers_accept=bench["configs"]["persistent"]["accept"],
    legacy_pass=sum(l.startswith("PASS ") for l in legacy), legacy_fail=sum(l.startswith("FAIL ") for l in legacy),
    unc=unc["unclassified_fraction_range"])
CHECK = [  # (value read from file, figure agreed for the video, tolerance for display rounding)
    (N["comp_pass"], 40, 0), (N["comp_total"], 40, 0), (N["anat_L"], 14.19, .01), (N["anat_R"], 14.29, .01), (N["paint_L"], 16.28, .01), (N["paint_R"], 16.35, .01),
    (N["fit_L"], 16.10, 1e-9), (N["fit_R"], 16.15, 1e-9), (N["ho_fit_L"], .116, 1e-9), (N["ho_fit_R"], .136, 1e-9), (N["ho_gt_L"], 3.14, .005), (N["ho_gt_R"], 3.15, .005),
    (N["n_heldout"], 14, 0), (N["det"]["released frames"], .90, .005), (N["det"]["full scene"], .68, .005), (N["det"]["clean condition"], 1.0, 1e-9),
    (N["det"]["40-sample dataset"], .75, 1e-9), (N["v1"][0], 40, 0), (N["v2"][0], 22, 0), (N["kinds"]["static"], 12, 0), (N["kinds"]["pursuit"], 5, 0), (N["kinds"]["saccade"], 5, 0),
    (N["sac_L"], 33.9, .05), (N["sac_R"], 37.1, .05), (N["sac_cmd"], 36.7, .05), (N["pur_lag"], 100, 0), (N["pur_res"], 33.3, .05), (N["glitch"], 8.09, .005),
    (N["pers_speed"], 1.12, .005), (N["pers_max"], 1, 0), (N["roi_in"], 37, 0), (N["roi_edge"], 181, 0), (N["legacy_pass"], 51, 0), (N["legacy_fail"], 20, 0)]
bad = [(v, e) for v, e, t in CHECK if abs(v - e) > t]
assert not bad, f"result files disagree with the agreed video figures: {bad}"
assert N["v1"][2] == 0 and N["v2"][2] == 0 and integ2["ok"] and N["verg"] and not N["roi_accept"] and N["pers_accept"]

# ------------------------------------------------------------------ style
FONT = "/System/Library/Fonts/Avenir Next.ttc"; MONO = "/System/Library/Fonts/SFNSMono.ttf"
_fc = {}
def F(size, w="Medium"):
    k = (size, w)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(MONO, size) if w == "Mono" else ImageFont.truetype(FONT, size, index={"Bold": 0, "Demi": 2, "Medium": 5, "Regular": 7, "Heavy": 8, "Light": 10}[w])
    return _fc[k]
BG = (11, 13, 17); PANEL = (20, 26, 36); GRID = (30, 38, 50); WHITE = (240, 243, 247); GREY = (150, 160, 172); CYAN = (64, 200, 235)
BLUE = (70, 130, 240); AMBER = (240, 170, 60); GREEN = (90, 210, 130); RED = (235, 90, 80)


def ease(x):
    x = max(0.0, min(1.0, x)); return x * x * (3 - 2 * x)


def ramp(t, t0, d=0.5):
    return ease((t - t0) / d)


def fade(t, start, end, d=0.4):
    return min(ramp(t, start, d), 1 - ramp(t, end - d, d))


class Canvas:
    def __init__(self, base=None):
        self.im = base.copy() if base is not None else Image.new("RGBA", (W, H), BG + (255,))
        self.ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.ov)

    def flush(self):
        self.im = Image.alpha_composite(self.im, self.ov); self.ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.ov)

    def text(self, xy, s, size, color=WHITE, alpha=1.0, w="Medium", anchor="la", spacing=6):
        if alpha <= 0: return
        self.d.multiline_text(xy, s, font=F(size, w), fill=color + (int(255 * alpha),), anchor=anchor, spacing=spacing)

    def rect(self, box, fill=None, outline=None, alpha=1.0, width=2, r=10):
        if alpha <= 0: return
        self.d.rounded_rectangle(box, radius=r, fill=fill + (int(255 * alpha * (0.92 if fill == PANEL else 1)),) if fill else None,
                                 outline=outline + (int(255 * alpha),) if outline else None, width=width)

    def line(self, pts, color, alpha=1.0, width=2):
        if alpha > 0: self.d.line(pts, fill=color + (int(255 * alpha),), width=width)

    def circle(self, c, r, color, alpha=1.0, width=3, fill=False):
        if alpha <= 0: return
        box = (c[0] - r, c[1] - r, c[0] + r, c[1] + r)
        if fill: self.d.ellipse(box, fill=color + (int(255 * alpha),))
        else: self.d.ellipse(box, outline=color + (int(255 * alpha),), width=width)

    def paste(self, img, xy, alpha=1.0):
        if alpha <= 0: return
        self.flush(); t = img.convert("RGBA")
        if alpha < 1: t.putalpha(t.getchannel("A").point(lambda v: int(v * alpha)))
        self.im.alpha_composite(t, (int(xy[0]), int(xy[1])))


def background(t):
    """Charcoal field with a fine technical grid and calibration ticks (static, decorative)."""
    c = Canvas(); g = c.d
    for x in range(0, W, 80): g.line([(x, 0), (x, H)], fill=GRID + (70,), width=1)
    for y in range(0, H, 80): g.line([(0, y), (W, y)], fill=GRID + (70,), width=1)
    for x in range(40, W, 40): g.line([(x, H - 18), (x, H - (26 if x % 200 == 0 else 22))], fill=GREY + (60,), width=1)
    c.flush(); return c


BGC = background(0).im


def label(c, x, y, s, alpha, color=CYAN):
    c.text((x, y), s, 22, color, alpha, "Demi")


def title(c, t, s, sub=None, y=70, t0=0.0):
    al = ramp(t, t0, .5); c.text((96, y + (1 - al) * 16), s, 56, WHITE, al, "Bold")
    c.line([(96, y + 78), (96 + 120 * al, y + 78)], CYAN, al, 4)
    if sub: c.text((96, y + 96), sub, 28, GREY, ramp(t, t0 + .3, .5), "Regular")


def footer(c, s, alpha=1.0, color=GREY):
    c.text((96, H - 66), s, 22, color, alpha, "Regular")


_img = {}
def IMG(path):
    if path not in _img: _img[path] = Image.open(src(path)).convert("RGB")
    return _img[path]


def kenburns(img, box0, box1, size, k):
    """Crop interpolated between two boxes (image coords) and resized to `size`: a camera push on real footage."""
    k = ease(k); b = [box0[i] + (box1[i] - box0[i]) * k for i in range(4)]
    return img.resize(size, Image.BICUBIC, box=tuple(b))


def eyecrop(path, box=(200, 410, 824, 610)):
    return IMG(path).crop(box)


PK = os.path.join(WK, "pkg"); META = json.load(open(src(os.path.join(PK, "metadata.json"))))
RING = [os.path.join(PK, f["file"]) for f in META["frames"]]

# ------------------------------------------------------------------ scenes
def s1_hook(t):  # 0-7  real eye, gaze moving round the ring, tracking markers, push in
    c = Canvas(BGC); k = t / 7.0
    idx = int((t * 3.2)) % 10; f = META["frames"][idx]; im = IMG(RING[idx])
    b0, b1 = (150, 300, 874, 707), (560, 418, 868, 591)
    pic = kenburns(im, b0, b1, (1920, 1080), min(1, t / 5.0)); pic = Image.blend(pic, Image.new("RGB", pic.size, BG), 0.12)
    c.paste(pic, (0, 0))
    b = [b0[i] + (b1[i] - b0[i]) * ease(min(1, t / 5.0)) for i in range(4)]; sx = 1920 / (b[2] - b[0]); sy = 1080 / (b[3] - b[1])
    for s in "LR":  # markers at the wrapper's ground-truth pupil centre for this frame (metadata.json)
        x, y = f[f"pupil_center_2D_{s}"]; X, Y = (x - b[0]) * sx, (y - b[1]) * sy
        if 0 < X < W and 0 < Y < H:
            r = 12 + 2.2 * sx; c.circle((X, Y), r, CYAN, .95, 3)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)): c.line([(X + dx * (r + 6), Y + dy * (r + 6)), (X + dx * (r + 30), Y + dy * (r + 30))], CYAN, .95, 3)
            c.text((X + r + 36, Y - r - 34), f"GT ({x:.1f}, {y:.1f}) px", 22, CYAN, .95, "Mono")
    c.text((96, 84), f"frame {idx}  ·  h = {f['input']['h']:+.2f}  v = {f['input']['v']:+.2f}", 22, GREY, 1, "Mono")
    c.rect((0, 0, W, H), fill=BG, alpha=0.0)
    a1 = fade(t, 0.6, 4.3); c.rect((0, 820, W, 940), fill=BG, alpha=.6 * a1, r=0)
    c.text((W / 2, 880), "SYNTHETIC GAZE.  REAL GEOMETRY.  MEASURED RESULTS.", 54, WHITE, a1, "Bold", "mm")
    a2 = ramp(t, 4.5, .6)
    if a2 > 0:
        c.rect((0, 0, W, H), fill=BG, alpha=0.55 * a2)
        c.text((W / 2, 440), "TEAM TECHTONIC", 96, WHITE, a2, "Heavy", "mm"); c.text((W / 2, 530), "VIT CHENNAI", 38, CYAN, a2, "Demi", "mm")
        c.text((W / 2, 590), "Samsung PRISM XR Hackathon 2026  ·  Track 01", 30, GREY, a2, "Regular", "mm")
    footer(c, "Real renders from the shipped scene; markers = wrapper ground-truth pupil centres (metadata.json)", .8)
    c.flush(); return c.im


def s2_problem(t):  # 7-17
    c = Canvas(BGC); title(c, t, "THE CHALLENGE")
    c.text((96, 200), "Reliable gaze data needs accurate eye geometry,\ncontrolled movement and trustworthy ground truth.", 40, WHITE, ramp(t, .5), "Demi", spacing=10)
    pic = IMG(os.path.join(SCENE, "scene", "eyes_cutaway.png")); pic = pic.resize((960, 540), Image.BICUBIC, box=(240, 0, 1920, 945))
    c.paste(pic, (864, 330), ramp(t, .8, .8)); c.rect((864, 330, 1824, 870), outline=GRID, alpha=ramp(t, .8))
    label(c, 880, 880, "research render of the shipped scene · gaze lines to the fixation target", ramp(t, 1.2))
    items = [("EYE ARTICULATION", "each eyeball rotates about its own centre"), ("CALIBRATED CAMERA", "known K and [R|t], locked at 40 cm"),
             ("GROUND-TRUTH ANNOTATION", "2-D pupil centre per eye, per frame")]
    for i, (h, s) in enumerate(items):
        al = ramp(t, 1.6 + i * 0.7); y = 370 + i * 150
        c.rect((96, y, 790, y + 120), fill=PANEL, outline=GRID, alpha=al); c.text((130, y + 22), f"{i + 1}", 44, CYAN, al, "Heavy")
        c.text((200, y + 24), h, 30, WHITE, al, "Bold"); c.text((200, y + 66), s, 24, GREY, al, "Regular")
    c.text((96, 940), "Synthetic data must be more than a pupil sliding across a flat image.", 30, AMBER, ramp(t, 4.5), "Demi")
    c.flush(); return c.im


def s3_system(t):  # 17-31
    c = Canvas(BGC); title(c, t, "OUR SYSTEM", "A textured, rigged face in Blender with a Python gaze controller")
    pic = IMG(os.path.join(SCENE, "scene", "overview.png")).resize((880, 495), Image.BICUBIC)
    c.paste(pic, (96, 250), ramp(t, .4, .7)); c.rect((96, 250, 976, 745), outline=GRID, alpha=ramp(t, .4))
    label(c, 112, 756, "side view of the real scene: camera (blue), fixation target (green), eye centres", ramp(t, .8))
    names = [("00_reset", "reset"), ("01_left", "move(-1, 0)"), ("03_up", "move(0, 1)"), ("02_right", "move(1, 0)"), ("04_down", "move(0, -1)")]
    code_al = fade(t, 9.5, 14.2)
    for i, (n, lab) in enumerate(names):
        al = ramp(t, 1.2 + i * 0.35) * (1 - code_al); cr = eyecrop(os.path.join(SCENE, n + ".png"), (560, 430, 860, 590)).resize((300, 160), Image.BICUBIC)
        x, y = 1040 + (i % 2) * 330, 250 + (i // 2) * 200
        if i == 4: x, y = 1040 + 165, 650
        c.paste(cr, (x, y), al); c.rect((x, y, x + 300, y + 160), outline=CYAN if i == 0 else GRID, alpha=al)
        c.text((x + 8, y + 164), "eyes." + lab, 20, CYAN, al, "Mono")
    flow = ["Blender scene", "Eye rig", "Gaze controller", "Camera render", "Ground-truth metadata"]
    for i, s in enumerate(flow):
        al = ramp(t, 5.5 + i * 0.6); x = 96 + i * 352
        c.rect((x, 860, x + 300, 940), fill=PANEL, outline=CYAN, alpha=al); c.text((x + 150, 900), s, 26, WHITE, al, "Demi", "mm")
        if i < 4: c.line([(x + 304, 900), (x + 346, 900)], CYAN, ramp(t, 5.8 + i * .6)); c.line([(x + 334, 890), (x + 346, 900), (x + 334, 910)], CYAN, ramp(t, 5.8 + i * .6))
    al = fade(t, 9.5, 14.2); c.rect((1040, 250, 1824, 820), fill=PANEL, outline=GRID, alpha=al)
    c.text((1080, 300), "import eyes\n\neyes.move(h, v)     # h, v in [-1, +1]\neyes.reset()\neyes.render('frame.png')\n\n# both eyeballs rotate about their\n# own centres (bone pivots), lids follow", 28, WHITE, al, "Mono", spacing=12)
    footer(c, "Footage: wrapper call renders (demo/final_hair/demo_assets) · flow diagram: SCHEMATIC", .8)
    c.flush(); return c.im


def s4_calibration(t):  # 31-43
    c = Canvas(BGC); title(c, t, "CALIBRATION AND COMPLIANCE", "Ten clockwise gaze positions  ·  θk = 2πk/10, starting at the top")
    cx, cy, R = 560, 610, 300
    for k in range(10):
        al = ramp(t, .6 + k * .22); th = 2 * math.pi * k / 10; x, y = cx + R * math.sin(th), cy - R * math.cos(th)
        cr = eyecrop(RING[k], (590, 440, 840, 580)).resize((180, 101), Image.BICUBIC)
        c.paste(cr, (x - 90, y - 50), al); c.rect((x - 90, y - 50, x + 90, y + 51), outline=CYAN if k == int(t * 2) % 10 else GRID, alpha=al)
        c.text((x, y + 70), f"k={k}", 18, GREY, al, "Mono", "mm")
    for k in range(10):
        a0 = 2 * math.pi * k / 10 + .25; a1 = a0 + 2 * math.pi / 10 - .5; al = ramp(t, 3.0)
        c.d.arc((cx - 150, cy - 150, cx + 150, cy + 150), math.degrees(a0) - 90, math.degrees(a1) - 90, fill=CYAN + (int(200 * al),), width=3)
    c.text((cx, cy), "clockwise", 22, CYAN, ramp(t, 3.0), "Demi", "mm")
    specs = [("35 cm", "fixation distance"), ("40 cm", "camera distance"), ("1024 × 1024", "PNG output"), ("10", "clockwise gaze positions")]
    for i, (v, l) in enumerate(specs):
        al = ramp(t, 2.0 + i * .5); y = 260 + i * 120
        c.text((1060, y), v, 60, WHITE, al, "Heavy"); c.text((1060, y + 72), l, 24, GREY, al, "Regular")
    al = ramp(t, 5.0); c.rect((1040, 760, 1830, 890), fill=PANEL, outline=GREEN, alpha=al)
    c.text((1070, 778), f"{N['comp_pass']}/{N['comp_total']}  RESEARCH COMPLIANCE CHECKS PASSED", 32, GREEN, al, "Bold")
    c.text((1070, 830), "new deterministic suite: geometry, projection, pivots, inputs, reset", 22, GREY, al, "Regular")
    c.text((1040, 910), f"Legacy tools/verify.py (unmodified, separate tool): {N['legacy_pass']} PASS / {N['legacy_fail']} FAIL records", 22, AMBER, ramp(t, 6.0), "Demi")
    footer(c, "compliance.json · verify_py_release_bundle.txt · renders: the 10 shipped frames", .8)
    c.flush(); return c.im


DISC_F = levels["frames"][5]; DISC_IMG = os.path.join(PK, META["frames"][5]["file"])


def s5_discovery(t):  # 43-66 (23 s)
    c = Canvas(BGC); title(c, t, "DISCOVERING THE PUPIL ALIGNMENT ERROR", "Frame 5 (h = 0, v = -1), eye on the image right")
    e = DISC_F["L"]; A_ = e["A"]["apparent_2D_analytic_px"]; B_ = e["B"]["painted_pupil_2D_px"]; C_ = e["C"]["detected_2D_px"]
    box = (A_[0] - 48, A_[1] - 36, A_[0] + 48, A_[1] + 36); S = 760 / 96
    zoom = IMG(DISC_IMG).resize((760, 570), Image.LANCZOS, box=box); c.paste(zoom, (96, 250)); c.rect((96, 250, 856, 820), outline=GRID)
    P = lambda p: (96 + (p[0] - box[0]) * S, 250 + (p[1] - box[1]) * S)
    sep = ramp(t, 1.0, 1.2)
    pa, pb, pc = P(A_), P(B_), P(C_)
    c.circle(pa, 16, RED, ramp(t, .6), 4); c.line([(pa[0] - 26, pa[1]), (pa[0] + 26, pa[1])], RED, ramp(t, .6), 3); c.line([(pa[0], pa[1] - 26), (pa[0], pa[1] + 26)], RED, ramp(t, .6), 3)
    if sep > 0:
        pbx = (pa[0] + (pb[0] - pa[0]) * sep, pa[1] + (pb[1] - pa[1]) * sep)
        c.circle(pbx, 16, GREEN, sep, 4); c.line([pa, pbx], WHITE, sep, 3)
        c.circle(pc, 9, CYAN, ramp(t, 2.4), 0, fill=True)
    dpx = math.dist(A_, B_)
    c.text((96, 836), "red   A  official ground truth (anatomical pupil, analytic cornea)", 22, RED, ramp(t, .6), "Demi")
    c.text((96, 866), "green B  pupil painted on the rendered eye (mesh + texture, no fit)", 22, GREEN, ramp(t, 1.0), "Demi")
    c.text((96, 896), "cyan  C  independent image detector (prediction)", 22, CYAN, ramp(t, 2.4), "Demi")
    c.text((96, 940), f"|A − B| = {dpx:.2f} px in this frame (one rendered frame, not an average)", 24, WHITE, ramp(t, 1.8), "Bold")
    ph1 = fade(t, 3.0, 11.0, .25); ph2 = fade(t, 11.0, 17.0, .25); ph3 = ramp(t, 17.0, .3)
    x0 = 930
    if ph1 > 0:
        c.text((x0, 270), "ANATOMICAL REFERENCE", 28, RED, ph1, "Bold"); c.text((x0, 312), "depth of the pupil from the eye centre", 22, GREY, ph1, "Regular")
        c.text((x0, 350), f"Left  {N['anat_L']:.2f} mm\nRight {N['anat_R']:.2f} mm", 46, WHITE, ph1, "Heavy", spacing=8)
        c.text((x0, 500), "PAINTED EYE ASSET", 28, GREEN, ramp(t, 4.5) * ph1, "Bold"); c.text((x0, 542), "measured on the mesh under the painted pupil", 22, GREY, ramp(t, 4.5) * ph1, "Regular")
        c.text((x0, 580), f"{N['paint_L']:.2f} – {N['paint_R']:.2f} mm", 46, WHITE, ramp(t, 4.5) * ph1, "Heavy")
        c.text((x0, 690), "The anatomical ground truth and the\ntextured pupil do not align.", 32, AMBER, ramp(t, 6.5) * ph1, "Demi", spacing=8)
    if ph2 > 0:
        c.text((x0, 270), "EFFECTIVE FITTED DEPTH", 28, CYAN, ph2, "Bold")
        c.text((x0, 320), f"LEFT   {N['fit_L']:.2f} mm\nRIGHT  {N['fit_R']:.2f} mm", 60, WHITE, ph2, "Heavy", spacing=10)
        c.text((x0, 480), f"95% bootstrap CI  {N['ci_L']['p2_5']:.2f}–{N['ci_L']['p97_5']:.2f}  ·  {N['ci_R']['p2_5']:.2f}–{N['ci_R']['p97_5']:.2f} mm", 24, GREY, ph2, "Regular")
        c.rect((x0, 540, 1830, 610), outline=AMBER, alpha=ph2); c.text((x0 + 20, 556), "EFFECTIVE FITTED PARAMETERS — NOT ANATOMICAL MEASUREMENTS", 24, AMBER, ph2, "Bold")
        c.text((x0, 650), "fit: 11 gaze poses per eye · clean condition (lids and\nlens mesh hidden) · this asset and this detector only", 22, GREY, ph2, "Regular", spacing=6)
    if ph3 > 0:
        c.text((x0, 270), f"{N['n_heldout']} HELD-OUT GAZE POSITIONS", 30, WHITE, ph3, "Bold")
        c.text((x0, 312), "never used for fitting · independent evaluation", 22, GREY, ph3, "Regular")
        # dot map of the held-out inputs (ids 20..33) vs fit inputs
        hx, hy = 1700, 380
        for k, v in dfit["conditions"]["no_lids_lens"]["L"]["heldout_pose_inputs"].items():
            c.circle((hx + v[0] * 70, hy - v[1] * 70), 6, AMBER, ph3, 0, fill=True)
        for f in META["frames"]:
            c.circle((hx + f["input"]["h"] * 70, hy - f["input"]["v"] * 70), 5, CYAN, ph3, 2)
        c.circle((hx - 70, hy + 102), 6, AMBER, ph3, 0, fill=True); c.text((hx - 58, hy + 90), "held-out", 18, GREY, ph3, "Regular")
        c.circle((hx + 30, hy + 102), 5, CYAN, ph3, 2); c.text((hx + 42, hy + 90), "fit", 18, GREY, ph3, "Regular")
        rows = [("Left", N["ho_fit_L"], N["ho_gt_L"]), ("Right", N["ho_fit_R"], N["ho_gt_R"])]
        c.text((x0, 480), "held-out RMSE (px)", 22, GREY, ph3, "Demi")
        for i, (eye, fv, gv) in enumerate(rows):
            y = 520 + i * 150; sc = 210   # px of bar per pixel of error (same scale for every bar)
            c.text((x0, y), eye, 28, WHITE, ph3, "Bold")
            c.rect((x0 + 110, y + 4, x0 + 110 + max(4, fv * sc * ramp(t, 17.5, 1)), y + 40), fill=CYAN, alpha=ph3, r=4); c.text((x0 + 120 + fv * sc, y + 6), f"{fv:.3f} fitted model", 24, CYAN, ph3, "Demi")
            c.rect((x0 + 110, y + 52, x0 + 110 + gv * sc * ramp(t, 17.5, 1), y + 88), fill=RED, alpha=ph3, r=4); c.text((x0 + 120 + gv * sc, y + 54), f"{gv:.2f} official GT", 24, RED, ph3, "Demi")
        c.text((x0, 840), "Applies to this asset and detector; not to other eyes or human subjects.", 22, AMBER, ph3, "Demi")
    footer(c, "research_pupil_levels.json · ws1_depth/depth_probe_extended.json · ws1_depth/depth_fit.json", .8)
    c.flush(); return c.im


OVL = IMG(os.path.join(RES, "full_roi_overlays.png"))


def s6_detector(t):  # 66-78
    c = Canvas(BGC); title(c, t, "INDEPENDENT DETECTOR VALIDATION", "Image-only pupil detector, frozen · successes and failures shown")
    tiles = OVL.crop((0, 0, 1536, 576)).resize((960, 360), Image.BICUBIC); c.paste(tiles, (96, 260), ramp(t, .4))
    c.rect((96, 260, 1056, 620), outline=GRID, alpha=ramp(t, .4))
    label(c, 96, 630, "actual overlays, full scene: green = ground truth, red = detection; orange label = failed (> 5 px)", ramp(t, .8))
    tiles2 = OVL.crop((0, 576, 1536, 768)).resize((960, 120), Image.BICUBIC); c.paste(tiles2, (96, 680), ramp(t, 1.2))
    x0 = 1150; c.text((x0, 262), "within 5 px of ground truth", 24, GREY, ramp(t, .6), "Demi")
    for i, (k, v) in enumerate(N["det"].items()):
        al = ramp(t, 1.0 + i * .5); y = 310 + i * 130; Lb = 560 * v * ramp(t, 1.0 + i * .5, 1.0)
        c.text((x0, y), k.upper(), 24, WHITE, al, "Demi"); c.rect((x0, y + 40, x0 + 560, y + 84), fill=GRID, alpha=al, r=4)
        c.rect((x0, y + 40, x0 + max(Lb, 4), y + 84), fill=CYAN, alpha=al, r=4); c.text((x0 + 580, y + 38), f"{v:.0%}", 40, WHITE, al, "Heavy")
    c.text((96, 850), "Detection percentages are condition-specific; missed detections are retained in reporting.", 26, AMBER, ramp(t, 4.0), "Demi")
    footer(c, "release / full_roi / no_lids_lens_roi _metrics.json · ws6_dataset_v1/dataset_roi_metrics.json · full_roi_overlays.png", .8)
    c.flush(); return c.im


DS1 = [os.path.join(WK, "dataset", "images", f) for f in sorted(os.listdir(os.path.join(WK, "dataset", "images")))]
DS2D = sorted(f for f in os.listdir(os.path.join(WK, "ds2", "degraded")) if f.endswith(".png"))


def s7_dataset(t):  # 78-91
    c = Canvas(BGC); title(c, t, "SYNTHETIC DATASET GENERATION", "Config-driven, seeded, resumable; every file hashed in a manifest")
    for i in range(24):
        al = ramp(t, .3 + i * .07, .4); x, y = 96 + (i % 6) * 152, 250 + (i // 6) * 112
        cr = eyecrop(DS1[i], (230, 420, 794, 610)).resize((144, 48 * 2 + 4), Image.BICUBIC); c.paste(cr, (x, y), al)
    label(c, 96, 706, f"dataset v1 renders (first 24 of {N['v1'][0]}): random gaze, iris colour and lighting", ramp(t, 1.5))
    for j, f in enumerate(DS2D[:4]):
        al = ramp(t, 6.0 + j * .3); sp = json.load(open(src(os.path.join(WK, "ds2", "degraded", f[:-4] + ".degrade.json"))))
        cr = eyecrop(os.path.join(WK, "ds2", "degraded", f), (230, 420, 794, 610)).resize((216, 73), Image.BICUBIC); x = 96 + j * 232
        c.paste(cr, (x, 760), al); c.text((x, 840), " + ".join(o["op"] for o in sp["spec"]), 20, CYAN, al, "Mono")
    x0 = 1080
    c.text((x0, 260), f"DATASET V1 — {N['v1'][0]}/{N['v1'][1]} SAMPLES", 34, WHITE, ramp(t, 1.0), "Bold")
    c.text((x0, 330), f"DATASET V2 PILOT — {N['v2'][0]}/{N['v2'][1]} SAMPLES", 34, WHITE, ramp(t, 2.0), "Bold")
    c.text((x0, 384), f"{N['kinds']['static']} static  ·  {N['kinds']['pursuit']} smooth-pursuit  ·  {N['kinds']['saccade']} saccade", 26, GREY, ramp(t, 2.4), "Regular")
    var = ["camera variations", "eyelid occlusion", "noise", "JPEG compression", "motion blur", "defocus"]
    for i, v in enumerate(var):
        al = ramp(t, 3.2 + i * .3); c.text((x0 + (i % 2) * 360, 450 + (i // 2) * 46), "• " + v, 26, WHITE, al, "Regular")
    c.text((x0, 620), "ZERO GENERATION FAILURES", 36, GREEN, ramp(t, 5.5), "Heavy")
    c.text((x0, 668), "INTEGRITY CHECKS PASSED", 36, GREEN, ramp(t, 6.0), "Heavy")
    c.text((x0, 740), "Generation success is not detector accuracy.", 26, AMBER, ramp(t, 7.0), "Demi")
    c.text((x0, 780), f"Semantic masks: provisional ({N['unc'][0]:.1%} pixels unclassified).", 24, AMBER, ramp(t, 7.5), "Regular")
    footer(c, "ws6_dataset_v1/manifest.json + integrity.txt · ws4_dataset/coverage.json + integrity.json · ws3_masks/unclassified_audit.json", .8)
    c.flush(); return c.im


DYN = json.load(open(src(os.path.join(WK, "dynamics", "dynamics.json"))))


def dynframe(name, t, dur):
    fr = DYN[name]["frames"]; i = min(len(fr) - 1, int(t / dur * len(fr))); return os.path.join(WK, "dynamics", fr[i]["file"]), i, len(fr)


def s8_dynamics(t):  # 91-102
    c = Canvas(BGC); title(c, t, "DYNAMIC EYE MOVEMENT", "Rendered frames, measured by the independent detector (simulation, not human data)")
    panels = [("SACCADE", "saccade", 2.5), ("SMOOTH PURSUIT", "pursuit", 4.0), ("VERGENCE", "vergence", 3.0), ("FIXATION", "fixation", 2.5)]
    for i, (lab, n, dur) in enumerate(panels):
        x, y = 96 + (i % 2) * 560, 250 + (i // 2) * 300; al = ramp(t, .3 + i * .3)
        p, k, nf = dynframe(n, (t - .5) % (dur + .8), dur)
        cr = eyecrop(p, (230, 430, 794, 600)).resize((520, 157), Image.BICUBIC); c.paste(cr, (x, y + 40), al)
        c.rect((x, y + 40, x + 520, y + 197), outline=GRID, alpha=al); c.text((x, y), lab, 26, WHITE, al, "Bold"); c.text((x + 520, y + 6), f"frame {k + 1}/{nf}", 18, GREY, al, "Mono", "ra")
    x0 = 1260
    c.text((x0, 255), "SACCADE  (5–95 % duration)", 26, CYAN, ramp(t, 1.0), "Bold")
    c.text((x0, 298), f"image-left eye   {N['sac_L']:.1f} ms\nimage-right eye  {N['sac_R']:.1f} ms\ncommanded        {N['sac_cmd']:.1f} ms", 28, WHITE, ramp(t, 1.2), "Mono", spacing=8)
    c.text((x0, 420), f"frame interval {N['sac_dt']:.2f} ms", 22, GREY, ramp(t, 1.4), "Regular")
    c.text((x0, 480), "SMOOTH PURSUIT", 26, CYAN, ramp(t, 2.5), "Bold")
    c.text((x0, 522), f"lag  ≈ {N['pur_lag']:.0f} ms  (resolution {N['pur_res']:.1f} ms)\ngain ≈ {N['pur_gain'][0]:.2f} / {N['pur_gain'][1]:.2f}", 28, WHITE, ramp(t, 2.7), "Mono", spacing=8)
    c.text((x0, 630), "VERGENCE", 26, CYAN, ramp(t, 4.0), "Bold")
    c.text((x0, 672), f"both eyes move inward: {N['ver_dx'][0]:+.1f} / {N['ver_dx'][1]:+.1f} px", 26, WHITE, ramp(t, 4.2), "Regular")
    c.text((x0, 740), f"Kept in the data: one {N['glitch']:.2f} px detector glitch\nin the image-right saccade.", 24, AMBER, ramp(t, 5.0), "Demi", spacing=6)
    c.text((x0, 820), "Blink: closure profile only, not rendered.", 24, AMBER, ramp(t, 5.5), "Regular")
    footer(c, "ws5_dynamics/dynamics_render_check.json · renders: clean_run dynamics/ (dynamics.json)", .8)
    c.flush(); return c.im


def s9_perf(t):  # 102-111
    c = Canvas(BGC); title(c, t, "PERFORMANCE ENGINEERING", "Every optimisation must reproduce the full render")
    o, p = bench["configs"]["original"], bench["configs"]["persistent"]
    c.rect((96, 250, 900, 820), fill=PANEL, outline=GREEN, alpha=ramp(t, .3))
    c.text((130, 280), "PERSISTENT SCENE DATA", 32, WHITE, ramp(t, .4), "Bold"); c.text((130, 330), "PASSED", 30, GREEN, ramp(t, .6), "Heavy")
    c.text((130, 400), f"{N['pers_speed']:.2f}× FASTER", 72, WHITE, ramp(t, 1.0), "Heavy")
    sc = 560 / o["sequence_s"]
    for i, (lab, v, col) in enumerate((("full render", o["sequence_s"], GREY), ("persistent", p["sequence_s"], GREEN))):
        y = 530 + i * 80; c.text((130, y), lab, 22, GREY, ramp(t, 1.4), "Regular")
        c.rect((300, y, 300 + v * sc * ramp(t, 1.4, 1), y + 36), fill=col, alpha=ramp(t, 1.4), r=4); c.text((310 + v * sc, y + 2), f"{v:.1f} s", 24, WHITE, ramp(t, 1.4), "Demi")
    c.text((130, 700), f"6-pose sequence, 128 spp · pixels within {N['pers_max']}/255", 22, GREY, ramp(t, 2.0), "Regular")
    al = ramp(t, 3.0)
    c.rect((960, 250, 1824, 820), fill=PANEL, outline=AMBER, alpha=al)
    c.text((994, 280), "ROI (EYE-REGION) RENDERING", 32, WHITE, al, "Bold"); c.text((994, 330), "NOT ADOPTED", 30, AMBER, al, "Heavy")
    for i, s in enumerate([f"difference up to {N['roi_in']}/255 inside the region", f"difference up to {N['roi_edge']}/255 at its edges", "fails the equivalence test", "its faster timing is not claimed"]):
        c.text((994, 420 + i * 60), "• " + s, 28, WHITE, ramp(t, 3.4 + i * .4), "Regular")
    footer(c, "ws6_performance/bench_compare.json · ws6_performance/band_audit.json", .8)
    c.flush(); return c.im


def s10_end(t):  # 111-115
    c = Canvas(BGC); im = IMG(os.path.join(SCENE, "scene", "overview.png"))
    pic = kenburns(im, (900, 120, 1500, 457), (0, 0, 1920, 1080), (1920, 1080), t / 3.2); pic = Image.blend(pic, Image.new("RGB", pic.size, BG), .45)
    c.paste(pic, (0, 0))
    c.text((W / 2, 400), "FROM SYNTHETIC EYE RENDERING", 50, WHITE, ramp(t, .2), "Bold", "mm")
    c.text((W / 2, 470), "TO SCIENTIFICALLY VALIDATED GAZE GENERATION", 50, CYAN, ramp(t, .6), "Bold", "mm")
    c.text((W / 2, 610), "TEAM TECHTONIC  ·  VIT CHENNAI", 40, WHITE, ramp(t, 1.2), "Heavy", "mm")
    c.text((W / 2, 666), "Samsung PRISM XR Hackathon 2026  ·  Track 01 — XR Perception Group", 26, GREY, ramp(t, 1.4), "Regular", "mm")
    c.rect((0, 0, W, H), fill=BG, alpha=ramp(t, 3.4, .6))
    c.flush(); return c.im


SCENES = [("1 Hook", 7, s1_hook), ("2 The challenge", 10, s2_problem), ("3 Our system", 14, s3_system), ("4 Calibration and compliance", 12, s4_calibration),
          ("5 Pupil alignment discovery", 23, s5_discovery), ("6 Detector validation", 12, s6_detector), ("7 Dataset generation", 13, s7_dataset),
          ("8 Dynamic eye movement", 11, s8_dynamics), ("9 Performance engineering", 9, s9_perf), ("10 Final message", 4, s10_end)]
TOTAL = sum(d for _, d, _ in SCENES)


def frame_at(T):
    t0 = 0
    for i, (name, d, fn) in enumerate(SCENES):
        if T < t0 + d or i == len(SCENES) - 1:
            im = fn(T - t0)
            if i > 0 and T - t0 < .35:    # short motivated crossfade from the previous scene
                pn, pd, pf = SCENES[i - 1]; im = Image.blend(pf(pd - 1e-3).convert("RGB"), im.convert("RGB"), ease((T - t0) / .35))
            return im.convert("RGB")
        t0 += d


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    if PREVIEW:
        for T in PREVIEW: frame_at(T).save(os.path.join(OUT, f"preview_{T:06.2f}.png"))
        print("previews written"); sys.exit(0)
    nfr = int(TOTAL * FPS); silent = os.path.join(OUT, "video_noaudio.mp4")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent], stdin=subprocess.PIPE)
    for i in range(nfr):
        ff.stdin.write(frame_at(i / FPS).tobytes())
        if i % 300 == 0: print(f"frame {i}/{nfr}", flush=True)
    ff.stdin.close(); assert ff.wait() == 0
    frame_at(57.0).save(os.path.join(OUT, "thumbnail.png"))
    with open(os.path.join(OUT, "scene_timeline.csv"), "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["scene", "start_s", "end_s", "duration_s"]); t0 = 0
        for n, d, _ in SCENES: w.writerow([n, t0, t0 + d, d]); t0 += d
    json.dump(dict(numbers_shown=N, checks=[dict(value=v, agreed=e, tol=t_) for v, e, t_ in CHECK],
                   sources=[dict(path=os.path.relpath(p, REPO) if p.startswith(REPO) else p, sha256=h) for p, h in sorted(USED.items())]),
              open(os.path.join(OUT, "asset_manifest.json"), "w"), indent=1, default=str)
    print("VIDEO_FRAMES_DONE", nfr, TOTAL)
