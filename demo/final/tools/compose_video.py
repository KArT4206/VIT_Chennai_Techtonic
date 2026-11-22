"""Phase 2H: assemble the 1:45 demo MP4 from the runner's REAL outputs (no simulated content).

    <blender python> compose_video.py <demo/phase2h dir>

Reads demo_assets/ (wrapper-call renders + their returned JSON, scene views, packaged sequence frames,
packaged metadata.json) and validation_results.txt. Writes 1920x1080 cards to work/cards/, then
encodes work/demo_track1.mp4 (H.264, 30 fps, yuv420p, no audio) with ffmpeg.
Every number on screen is read from those files at compose time.
"""
import json
import math
import os
import re
import subprocess
import sys

import OpenImageIO as oiio
from OpenImageIO import ImageBufAlgo as A

D = os.path.abspath(sys.argv[1]); S = os.path.join(D, "demo_assets"); W_ = os.path.join(D, "work"); C = os.path.join(W_, "cards")
os.makedirs(C, exist_ok=True)
SANS = "/System/Library/Fonts/HelveticaNeue.ttc"; MONO = "/System/Library/Fonts/Menlo.ttc"
BG = (0.07, 0.075, 0.085); FG = (0.93, 0.93, 0.93); DIM = (0.62, 0.64, 0.68); ACC = (1.0, 0.72, 0.18); GRN = (0.35, 0.85, 0.45); BLU = (0.45, 0.68, 1.0)
WW, HH = 1920, 1080


def canvas():
    b = oiio.ImageBuf(oiio.ImageSpec(WW, HH, 3, oiio.FLOAT)); A.fill(b, BG); return b


TEXT = []          # text items of the card being built; rendered later by tools/render_text.py (Blender)


def text(b, x, y, s, size=40, color=FG, font=SANS, align="left"):
    TEXT.append([float(x), float(y), str(s), float(size), list(color), "mono" if font == MONO else "sans"])


def header(b, step, title):
    text(b, 80, 92, step, 28, ACC); text(b, 80, 150, title, 54)
    A.render_box(b, 80, 175, 1840, 178, [0.25, 0.26, 0.3], fill=True)


def footer(b, s="Samsung PRISM Hackathon 2026 · Track 1 · Team Techtonic · MakeHuman/MPFB release package"):
    text(b, 80, 1048, s, 22, DIM)


def paste(b, img, x, y, w, h):
    src = oiio.ImageBuf(img) if isinstance(img, str) else img
    src = A.channels(src, (0, 1, 2))
    r = A.resize(src, roi=oiio.ROI(0, w, 0, h, 0, 1, 0, 3))
    A.paste(b, int(x), int(y), 0, 0, r)


def crop(img, x0, x1, y0, y1):
    return A.cut(A.channels(oiio.ImageBuf(img), (0, 1, 2)), oiio.ROI(x0, x1, y0, y1, 0, 1, 0, 3))


def cross(b, x, y, r, color, t=2):
    for d in range(-t // 2, t // 2 + 1):
        A.render_line(b, int(x - r), int(y + d), int(x + r), int(y + d), list(color))
        A.render_line(b, int(x + d), int(y - r), int(x + d), int(y + r), list(color))


SPEC = {}


def save(b, name):
    p = os.path.join(C, name); b.write(p, "uint8"); SPEC[name[:-4]] = list(TEXT); TEXT.clear(); return p


cards = []      # (path, seconds)
val = open(os.path.join(D, "validation_results.txt")).read()
facts = json.load(open(os.path.join(S, "scene", "scene_facts.json")))
ann = json.load(open(os.path.join(S, "scene", "annotations.json")))["pixels"]
meta = json.load(open(os.path.join(S, "metadata.json")))

# ---------------- Scene 1: problem and objective (10 s)
b = canvas()
text(b, 80, 120, "TRACK 1", 30, ACC)
text(b, 80, 200, "Synthetic Eye Movement &", 76); text(b, 80, 290, "Virtual Camera Rendering", 76)
text(b, 80, 420, "The problem", 34, ACC)
text(b, 80, 475, "Gaze estimators for XR need large, exactly labelled eye datasets.", 38)
text(b, 80, 528, "Capturing real eyes at extreme angles is slow, costly and privacy-restricted.", 38)
text(b, 80, 640, "Our objective", 34, ACC)
text(b, 80, 695, "A textured, rigged face in Blender whose eyes rotate about their true centres,", 38)
text(b, 80, 748, "driven by a deterministic Python API, rendering calibrated 1024 x 1024 frames", 38)
text(b, 80, 801, "with per-frame ground truth.", 38)
footer(b); cards.append((save(b, "s1.png"), 10))

# ---------------- Scene 2: head model and calibration (15 s)
for name, title, sec in (("overview", "The actual Blender scene: head, fixation target, locked camera", 8),
                         ("eyes_cutaway", "Eye bones and eye centres (skin and hair hidden for this view)", 7)):
    b = canvas(); header(b, "2 · MODEL AND CALIBRATION", title)
    paste(b, os.path.join(S, "scene", name + ".png"), 80, 200, 1440, 810)
    sx, sy = 1440 / 1920, 810 / 1080
    px = ann[name]
    hidden_L = " (inside the eyeball)" if name == "eyes_cutaway" else ""
    lab = {"render_camera_40cm": (f"{facts['camera']} (render camera) {facts['camera_distance_m'] * 100:.2f} cm", BLU),
           "fixation_target_35cm": (f"fixation target {facts['fixation_distance_m'] * 100:.2f} cm", GRN),
           "eye_centre_R": ("eye centre R", ACC), "eye_centre_L": ("eye centre L" + hidden_L, ACC)}
    # labels sit in the empty band at the top of the view, one row each, with a leader line to the point
    row = 0
    for k, (s, col) in lab.items():
        x, y = 80 + px[k][0] * sx, 200 + px[k][1] * sy
        if not (80 <= x <= 1520 and 200 <= y <= 1010):
            continue
        tx = min(max(x - 120, 110), 1100); ty = 250 + row * 44; row += 1
        text(b, tx, ty, s, 26, col)
        A.render_line(b, int(tx + 8), int(ty + 8), int(x), int(y), list(col))
        A.render_box(b, int(x) - 3, int(y) - 3, int(x) + 3, int(y) + 3, list(col), fill=True)
    text(b, 1560, 260, "Read from the scene", 28, ACC)
    rows = [("Rig", facts["rig"]), ("Eye bones", " / ".join(facts["eye_bones"])),
            ("Interocular", f"{facts['interocular_mm']:.1f} mm"),
            ("Fixation", f"{facts['fixation_distance_m'] * 100:.2f} cm"), ("Camera", f"{facts['camera_distance_m'] * 100:.2f} cm"),
            ("Lens", f"{facts['lens_mm']:.0f} mm"), ("Output", f"{facts['resolution'][0]} x {facts['resolution'][1]} PNG")]
    for i, (k, v) in enumerate(rows):
        text(b, 1560, 330 + i * 70, k, 24, DIM); text(b, 1560, 360 + i * 70, v, 30)
    legend = [("green: eye centre to target", GRN), ("grey: midpoint to camera", (0.8, 0.8, 0.8)),
              ("pink: eye-bone axis", (1.0, 0.6, 0.85)), ("yellow: eye centre", ACC)]
    for i, (s, col) in enumerate(legend):
        text(b, 1560, 860 + i * 30, s, 21, col)
    text(b, 1560, 990, "markers placed at scene data", 18, DIM)
    footer(b); cards.append((save(b, f"s2_{name}.png"), sec))

# ---------------- Scene 3: wrapper calls (30 s, 6 x 5 s)
calls = [("00_reset", "eyes.reset()", "CENTRE"), ("01_left", "eyes.move(-1, 0)", "LEFT"), ("02_right", "eyes.move(1, 0)", "RIGHT"),
         ("03_up", "eyes.move(0, 1)", "UP"), ("04_down", "eyes.move(0, -1)", "DOWN"), ("05_reset_again", "eyes.reset()", "RESET")]
ref = json.load(open(os.path.join(S, "00_reset.json")))
X0, X1, Y0, Y1 = 152, 872, 404, 620                  # eye region in the 1024 render (both eyes)
for i, (f, call, lab) in enumerate(calls):
    js = json.load(open(os.path.join(S, f + ".json")))
    b = canvas(); header(b, "3 · PYTHON WRAPPER, REAL CALLS ON THE RELEASE PACKAGE", call + "    then    eyes.render()")
    cw, ch = 1500, 450; ox, oy = 80, 230
    paste(b, crop(os.path.join(S, f + ".png"), X0, X1, Y0, Y1), ox, oy, cw, ch)
    k = cw / (X1 - X0)
    for side, col in (("L", ACC), ("R", ACC)):
        x, y = js[f"pupil_center_2D_{side}"]; rx, ry = ref[f"pupil_center_2D_{side}"]
        cross(b, ox + (rx - X0) * k, oy + (ry - Y0) * k, 14, DIM, 1)
        cross(b, ox + (x - X0) * k, oy + (y - Y0) * k, 22, col, 3)
    text(b, 1620, 300, lab, 72, ACC)
    text(b, 1620, 360, "pupil centres", 24, DIM)
    paste(b, os.path.join(S, f + ".png"), 1620, 420, 220, 220)
    A.render_box(b, 1620 + int(X0 * 220 / 1024), 420 + int(Y0 * 220 / 1024), 1620 + int(X1 * 220 / 1024), 420 + int(Y1 * 220 / 1024), list(ACC))
    text(b, 1620, 670, "full 1024 x 1024 frame", 20, DIM)
    y = 760
    text(b, 80, y, "returned by eyes.render():", 26, DIM)
    text(b, 80, y + 50, f"input  h = {js['input']['h']:+.2f}   v = {js['input']['v']:+.2f}", 32, FG, MONO)
    for j, side in enumerate(("L", "R")):
        x, yy = js[f"pupil_center_2D_{side}"]; rx, ry = ref[f"pupil_center_2D_{side}"]
        text(b, 80, y + 100 + j * 48, f"pupil_center_2D_{side} = ({x:7.2f}, {yy:7.2f}) px    shift vs reset ({x - rx:+6.2f}, {yy - ry:+6.2f})", 30, FG, MONO)
    text(b, 80, y + 220, "yellow cross: returned pupil centre   grey cross: centre gaze (reset)   image enlarged 3x", 22, DIM)
    footer(b); cards.append((save(b, f"s3_{i}.png"), 5))

# ---------------- Scene 4: clockwise sequence (20 s, 10 x 2 s)
frames = meta["frames"]
for k, fr in enumerate(frames):
    b = canvas(); header(b, "4 · TEN-FRAME CLOCKWISE SEQUENCE (PACKAGED RENDERS)", f"frame_{k:02d}.png")
    paste(b, os.path.join(S, "sequence", f"frame_{k:02d}.png"), 80, 200, 810, 810)
    paste(b, crop(os.path.join(S, "sequence", f"frame_{k:02d}.png"), X0, X1, Y0, Y1), 930, 200, 960, 288)
    cx, cy, R = 1240, 760, 190
    for j, g in enumerate(frames):
        a = g["theta"] if "theta" in g else 2 * math.pi * j / 10
        px, py = cx + R * math.sin(a), cy - R * math.cos(a)
        col = ACC if j == k else ([0.35, 0.36, 0.4] if j > k else DIM)
        A.render_box(b, int(px - 9), int(py - 9), int(px + 9), int(py + 9), list(col), fill=True)
        text(b, px + (16 if math.sin(a) >= 0 else -40), py + 8, str(j), 22, col)
    A.render_box(b, cx - 3, cy - 3, cx + 3, cy + 3, list(DIM), fill=True)
    text(b, cx - 34, cy - R - 30, "top", 22, DIM)
    th = fr.get("theta", 2 * math.pi * k / 10)
    text(b, 1500, 600, f"k = {k}", 40, ACC, MONO)
    text(b, 1500, 660, f"theta = {th:.4f}", 30, FG, MONO)
    text(b, 1500, 710, f"h = sin = {fr['input']['h']:+.3f}", 30, FG, MONO)
    text(b, 1500, 760, f"v = cos = {fr['input']['v']:+.3f}", 30, FG, MONO)
    text(b, 1500, 840, "starts at the top,", 24, DIM); text(b, 1500, 872, "clockwise on screen", 24, DIM)
    footer(b); cards.append((save(b, f"s4_{k}.png"), 2))

# ---------------- Scene 5: metadata (15 s, frame 3 record, verbatim values)
fr = frames[3]
b = canvas(); header(b, "5 · GROUND-TRUTH METADATA (packaged metadata.json, frame 3; values rounded for display)", "One record per render")


def fmt(v):
    if isinstance(v, list) and v and isinstance(v[0], list):
        return "[" + ", ".join("[" + ", ".join(f"{x:.4g}" for x in r) + "]" for r in v) + "]"
    if isinstance(v, list):
        return "[" + ", ".join(f"{x:.4f}" if isinstance(x, float) else str(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join(f'"{a}": {c}' for a, c in v.items()) + "}"
    return json.dumps(v)


lines = [("frame", fr["frame"]), ("theta", fr.get("theta")), ("input", fr["input"]), ("eye_rotation_L", fr["eye_rotation_L"]),
         ("eye_rotation_R", fr["eye_rotation_R"]), ("pupil_center_2D_L", fr["pupil_center_2D_L"]), ("pupil_center_2D_R", fr["pupil_center_2D_R"]),
         ("camera_matrix", fr["camera_matrix"])]
y = 250
for key, v in lines:
    text(b, 100, y, f'"{key}":', 30, ACC, MONO)
    s = fmt(v)
    for chunk_i in range(0, len(s), 70):
        text(b, 560, y, s[chunk_i:chunk_i + 70], 30, FG, MONO); y += 44
    y += 22
text(b, 100, y + 20, "Also per frame: rotation quaternions, 3-D pupil centres, camera extrinsics [R|t], fixation target.", 24, DIM)
text(b, 100, y + 56, "Rotations: world frame, degrees.  2-D pupils: pixels of the refracted (seen) pupil centre at 40 cm.", 24, DIM)
footer(b); cards.append((save(b, "s5.png"), 15))

# ---------------- Scene 6: validation and conclusion (15 s)
vpass = re.search(r"PASS lines: (\d+)\s+FAIL lines: (\d+)", val); api = re.search(r"(\d+)/(\d+) PASSED", val)
nren = len(re.findall(r"frame_\d\d\.png\s+1024x1024\s+PNG", val)); same = "BYTE-IDENTICAL" in val; untouched = "unchanged after the demo run" in val
b = canvas(); header(b, "6 · VALIDATION (this run, release ZIP 91f4bafe…)", "Measured, not claimed")
rows = [(f"{vpass.group(1)} / {int(vpass.group(1)) + int(vpass.group(2))}", "original evaluator checks (tools/verify.py) passed"),
        (f"{api.group(1)} / {api.group(2)}", "API tests: move / reset / render, conventions, fixed camera and lights"),
        (f"{nren} / 10", "clockwise renders present, each 1024 x 1024 PNG"),
        ("identical" if same else "DIFFERS", "metadata.json regenerated from the package vs packaged file (byte compare)"),
        ("unchanged" if untouched else "CHANGED", "packaged files after the demo run (SHA-256 before/after)")]
for i, (big, small) in enumerate(rows):
    text(b, 100, 300 + i * 105, big, 50, GRN if "DIFF" not in big and "CHANGED" not in big else (1, 0.3, 0.3))
    text(b, 520, 300 + i * 105, small, 32)
text(b, 100, 880, "A deterministic, calibrated, reproducible synthetic gaze-rendering pipeline:", 34, ACC)
text(b, 100, 930, "true spherical eye rotation, fixed 40 cm camera, per-frame ground truth.", 34, ACC)
footer(b); cards.append((save(b, "s6.png"), 15))

# ---------------- text overlays (Blender text objects), composited over each card
spec = os.path.join(W_, "text_spec.json"); json.dump(SPEC, open(spec, "w"), indent=0)
tdir = os.path.join(W_, "text"); B = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
r = subprocess.run([B, "-b", "--factory-startup", "-P", os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_text.py"), "--", spec, tdir],
                   capture_output=True, text=True)
assert "TEXT_DONE" in r.stdout, r.stdout[-2000:] + r.stderr[-2000:]
print([l for l in r.stdout.splitlines() if l.startswith("FONTS")][0])
for i, (p, sec) in enumerate(cards):
    base = oiio.ImageBuf(p); ov = oiio.ImageBuf(os.path.join(tdir, os.path.basename(p)))
    base = A.channels(base, (0, 1, 2, 1.0), newchannelnames=("R", "G", "B", "A"))
    comp = A.over(ov, base); A.channels(comp, (0, 1, 2)).write(p, "uint8")

# ---------------- encode: each card a clip with 0.25 s fades, then concat
clips = []
for i, (p, sec) in enumerate(cards):
    o = os.path.join(W_, "clips", f"c{i:02d}.mp4"); os.makedirs(os.path.dirname(o), exist_ok=True)
    fade = 0.25 if sec >= 5 else 0.12
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", "30", "-t", str(sec), "-i", p,
                    "-vf", f"fade=t=in:st=0:d={fade},fade=t=out:st={sec - fade}:d={fade},format=yuv420p",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-r", "30", "-pix_fmt", "yuv420p", o], check=True)
    clips.append(o)
lst = os.path.join(W_, "clips", "list.txt"); open(lst, "w").write("".join(f"file '{c}'\n" for c in clips))
outv = os.path.join(W_, "demo_track1.mp4")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", outv], check=True)
print("TOTAL_SECONDS", sum(s for _, s in cards), "CARDS", len(cards), "VIDEO", outv)
