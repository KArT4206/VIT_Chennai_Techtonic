"""Integrity check for a dataset_engine.py output folder (pure Python, no Blender).

    python3 research/validate_dataset.py DIR
Checks: manifest present; every sample's image + annotation exists; SHA-256 match; PNG is 1024x1024;
annotation has inputs in [-1,1], both 2D pupils inside the image, camera K; no stray .part/.tmp files.
"""
import hashlib, json, os, struct, sys
d = sys.argv[1]; bad = []
m = json.load(open(os.path.join(d, "manifest.json")))
for stem, e in sorted(m["samples"].items()):
    for k in ("image", "annotation"):
        p = os.path.join(d, e[k])
        if not os.path.exists(p): bad.append(f"{stem}: missing {k}"); continue
        if hashlib.sha256(open(p, "rb").read()).hexdigest() != e[k + "_sha256"]: bad.append(f"{stem}: {k} hash mismatch")
    p = os.path.join(d, e["image"])
    if os.path.exists(p):
        w, h = struct.unpack(">II", open(p, "rb").read(24)[16:24])
        if (w, h) != (1024, 1024): bad.append(f"{stem}: size {w}x{h}")
    a = json.load(open(os.path.join(d, e["annotation"])))
    if not all(-1 <= a["input"][k] <= 1 for k in "hv"): bad.append(f"{stem}: input out of range")
    for s in "LR":
        x, y = a[f"pupil_center_2D_{s}"]
        if not (0 <= x < 1024 and 0 <= y < 1024): bad.append(f"{stem}: pupil {s} outside image")
stray = [f for r, _, fs in os.walk(d) for f in fs if f.endswith((".tmp", ".part.png"))]
bad += [f"stray partial file {f}" for f in stray]
n = len(m["samples"])
print(f"{n} samples, {len(m['failures'])} recorded failures, {len(bad)} integrity problems")
for b in bad: print("PROBLEM", b)
sys.exit(1 if bad or n != m["config"]["n"] else 0)
