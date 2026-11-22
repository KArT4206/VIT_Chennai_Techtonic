"""Images for the final-round presentation, cut from real renders and committed result files only (pure Python).

    python3 research/demo/source/deck_assets.py <clean_run_work_dir> <out_dir>

Writes PNGs plus deck_numbers.json (every number the deck shows, read from AUDIT/results).
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RES = os.path.join(REPO, "AUDIT", "results"); SC = os.path.join(REPO, "demo", "final_hair", "demo_assets")
WK, OUT = sys.argv[1:3]; os.makedirs(OUT, exist_ok=True)
J = lambda f: json.load(open(os.path.join(RES, f)))
PK = os.path.join(WK, "pkg"); META = json.load(open(os.path.join(PK, "metadata.json")))
F = lambda s: ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", s)
eye = lambda p, b=(200, 410, 824, 610): Image.open(p).convert("RGB").crop(b)
# 1 hero: both eyes, frame 0
eye(os.path.join(PK, "renders", "frame_00.png"), (150, 330, 874, 690)).resize((1448, 720), Image.LANCZOS).save(os.path.join(OUT, "hero_eyes.png"))
# 2 scene views
for n in ("overview", "eyes_cutaway"):
    Image.open(os.path.join(SC, "scene", n + ".png")).convert("RGB").save(os.path.join(OUT, f"scene_{n}.png"))
# 3 five directions strip
names = [("04_down", "move(0,-1)"), ("01_left", "move(-1,0)"), ("00_reset", "reset()"), ("02_right", "move(1,0)"), ("03_up", "move(0,1)")]
S = Image.new("RGB", (5 * 420, 260), (11, 13, 17)); d = ImageDraw.Draw(S)
for i, (n, lab) in enumerate(names):
    S.paste(eye(os.path.join(SC, n + ".png"), (540, 425, 880, 595)).resize((400, 200), Image.LANCZOS), (i * 420 + 10, 10)); d.text((i * 420 + 12, 220), "eyes." + lab, font=F(26), fill=(64, 200, 235))
S.save(os.path.join(OUT, "directions.png"))
# 4 ten-frame ring grid (2 x 5)
G = Image.new("RGB", (5 * 360, 2 * 210), (11, 13, 17)); d = ImageDraw.Draw(G)
for k, f in enumerate(META["frames"]):
    x, y = (k % 5) * 360, (k // 5) * 210
    G.paste(eye(os.path.join(PK, f["file"]), (560, 430, 870, 590)).resize((350, 180), Image.LANCZOS), (x + 5, y + 5)); d.text((x + 10, y + 184), f"k={k}  h={f['input']['h']:+.2f} v={f['input']['v']:+.2f}", font=F(18), fill=(150, 160, 172))
G.save(os.path.join(OUT, "ring.png"))
# 5 discovery zoom, frame 5, image-right eye, with A/B/C points from research_pupil_levels.json
L = J("research_pupil_levels.json")["frames"][5]["L"]; A, B, C = L["A"]["apparent_2D_analytic_px"], L["B"]["painted_pupil_2D_px"], L["C"]["detected_2D_px"]
bx = (A[0] - 48, A[1] - 36, A[0] + 48, A[1] + 36); s = 900 / 96
Z = Image.open(os.path.join(PK, META["frames"][5]["file"])).convert("RGB").resize((900, 675), Image.LANCZOS, box=bx); d = ImageDraw.Draw(Z)
P = lambda p: ((p[0] - bx[0]) * s, (p[1] - bx[1]) * s)
for p, col, r in ((A, (235, 90, 80), 18), (B, (90, 210, 130), 18)):
    x, y = P(p); d.ellipse((x - r, y - r, x + r, y + r), outline=col, width=5)
x, y = P(C); d.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(64, 200, 235))
Z.save(os.path.join(OUT, "discovery_zoom.png"))
# 6 detector overlays (actual, failures included)
O = Image.open(os.path.join(RES, "full_roi_overlays.png")).convert("RGB"); O.crop((0, 0, O.width, min(O.height, 576))).save(os.path.join(OUT, "overlays_full.png"))
Image.open(os.path.join(RES, "ws1_depth", "depth_fit_curves.png")).convert("RGB").save(os.path.join(OUT, "depth_fit_curves.png"))
# 7 dataset grid + degraded strip
imgs = sorted(os.listdir(os.path.join(WK, "dataset", "images")))[:15]
D = Image.new("RGB", (5 * 300, 3 * 110), (11, 13, 17))
for i, f in enumerate(imgs):
    D.paste(eye(os.path.join(WK, "dataset", "images", f), (230, 420, 794, 610)).resize((290, 98), Image.LANCZOS), ((i % 5) * 300 + 5, (i // 5) * 110 + 6))
D.save(os.path.join(OUT, "dataset_grid.png"))
deg = sorted(f for f in os.listdir(os.path.join(WK, "ds2", "degraded")) if f.endswith(".png"))[:4]
E = Image.new("RGB", (4 * 360, 170), (11, 13, 17)); d = ImageDraw.Draw(E)
for i, f in enumerate(deg):
    sp = json.load(open(os.path.join(WK, "ds2", "degraded", f[:-4] + ".degrade.json")))
    E.paste(eye(os.path.join(WK, "ds2", "degraded", f), (230, 420, 794, 610)).resize((350, 118), Image.LANCZOS), (i * 360 + 5, 5)); d.text((i * 360 + 8, 132), " + ".join(o["op"] for o in sp["spec"]), font=F(22), fill=(64, 200, 235))
E.save(os.path.join(OUT, "degraded_strip.png"))
# 8 dynamics: 6 saccade stills + vergence first/last
dj = json.load(open(os.path.join(WK, "dynamics", "dynamics.json"))); fr = dj["saccade"]["frames"]; idx = [0, 6, 9, 11, 13, 26]
Y = Image.new("RGB", (3 * 400, 2 * 175), (11, 13, 17)); d = ImageDraw.Draw(Y)
for j, i in enumerate(idx):
    Y.paste(eye(os.path.join(WK, "dynamics", fr[i]["file"]), (230, 430, 794, 600)).resize((390, 118), Image.LANCZOS), ((j % 3) * 400 + 5, (j // 3) * 175 + 5)); d.text(((j % 3) * 400 + 8, (j // 3) * 175 + 130), f"t = {fr[i]['t'] * 1000:.1f} ms", font=F(22), fill=(150, 160, 172))
Y.save(os.path.join(OUT, "saccade_stills.png"))
vf = dj["vergence"]["frames"]; V = Image.new("RGB", (2 * 600, 230), (11, 13, 17)); d = ImageDraw.Draw(V)
for j, i in enumerate((0, len(vf) - 1)):
    V.paste(eye(os.path.join(WK, "dynamics", vf[i]["file"]), (230, 430, 794, 600)).resize((590, 178), Image.LANCZOS), (j * 600 + 5, 5)); d.text((j * 600 + 8, 192), f"target depth {vf[i]['depth_m'] * 100:.0f} cm", font=F(24), fill=(150, 160, 172))
V.save(os.path.join(OUT, "vergence.png"))
print("deck assets written to", OUT)
