"""WS4 post step (pure Python): image-quality variants, coverage report and integrity check for dataset_v2.

    python3 research/dataset_v2_post.py <DIR>

* quality: for each sample, with probability cfg.quality.p (seeded per sample ID), one op from cfg.quality.ops
  with parameters drawn from its ranges is applied by research/degrade.py -> DIR/degraded/<id>.png plus
  <id>.degrade.json; the clean image and annotation are never modified (hashes re-checked).
* coverage: DIR/coverage.json + coverage.png (gaze scatter by kind, iris, lighting, camera, occlusion, quality).
* integrity: DIR/integrity.json; exit 1 on any problem (missing/extra files, hash mismatch, wrong size, pupils
  outside the image, planned samples missing, failures recorded).
"""
import hashlib, json, os, random, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import degrade as DG
D = sys.argv[1]; man = json.load(open(os.path.join(D, "manifest.json"))); cfg = man["config"]
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
problems = []; recs = {}
for s, e in sorted(man["samples"].items()):
    for k in ("image", "annotation"):
        p = os.path.join(D, e[k])
        if not os.path.exists(p): problems.append(f"{s}: missing {k}")
        elif sha(p) != e[k + "_sha256"]: problems.append(f"{s}: {k} hash mismatch")
    a = json.load(open(os.path.join(D, e["annotation"]))); recs[s] = a
    w, h = struct.unpack(">II", open(os.path.join(D, e["image"]), "rb").read(24)[16:24])
    if (w, h) != (1024, 1024): problems.append(f"{s}: size {w}x{h}")
    for side in "LR":
        x, y = a[f"pupil_center_2D_{side}"]
        if not (0 <= x < 1024 and 0 <= y < 1024): problems.append(f"{s}: pupil {side} outside image")
# quality variants
Q = cfg.get("quality", {}); qlog = {}
os.makedirs(os.path.join(D, "degraded"), exist_ok=True)
for s, e in sorted(man["samples"].items()):
    r = random.Random(f"{cfg['seed']}:quality:{s}")
    if r.random() >= Q.get("p", 0): qlog[s] = None; continue
    op = dict(r.choice(Q["ops"])); spec = {"op": op.pop("op")}
    for k, v in op.items(): spec[k] = r.uniform(*v) if isinstance(v, list) else v
    if spec["op"] == "jpeg": spec["quality"] = int(round(spec["quality"]))
    ann = os.path.join(D, e["annotation"]); before = sha(ann)
    _, prov = DG.apply_file(os.path.join(D, e["image"]), ann, os.path.join(D, "degraded"), [spec], r.randrange(2 ** 31), s)
    os.remove(os.path.join(D, "degraded", s + ".label.json"))          # the label is the annotation itself; keep one copy
    if sha(ann) != before or prov["label_sha256"] != e["annotation_sha256"]: problems.append(f"{s}: annotation changed by degradation")
    qlog[s] = dict(spec=spec, seed=prov["seed"], output_sha256=prov["output_sha256"])
# coverage
H = np.array([[a["input"]["h"], a["input"]["v"]] for a in recs.values()])
kinds = {}; [kinds.__setitem__(a["kind"], kinds.get(a["kind"], 0) + 1) for a in recs.values()]
cov = dict(n_samples=len(recs), planned=man.get("planned_samples"), failures=len(man["failures"]), kinds=kinds,
           gaze=dict(h_range=[float(H[:, 0].min()), float(H[:, 0].max())], v_range=[float(H[:, 1].min()), float(H[:, 1].max())],
                     quadrant_counts={q: int(((np.sign(H[:, 0]) == sh) & (np.sign(H[:, 1]) == sv)).sum()) for q, sh, sv in (("+h+v", 1, 1), ("+h-v", 1, -1), ("-h+v", -1, 1), ("-h-v", -1, -1))}),
           iris_value_range=[min(a["iris"]["value"] for a in recs.values()), max(a["iris"]["value"] for a in recs.values())],
           iris_hue_range=[min(a["iris"]["hue_shift"] for a in recs.values()), max(a["iris"]["hue_shift"] for a in recs.values())],
           camera_variants=sum(1 for a in recs.values() if a["camera_variant"]), occluded=sum(1 for a in recs.values() if a["occlusion"]),
           quality_variants={}, mean_render_s=round(float(np.mean([a["render_s"] for a in recs.values()])), 2))
for q in qlog.values():
    if q: cov["quality_variants"][q["spec"]["op"]] = cov["quality_variants"].get(q["spec"]["op"], 0) + 1
if cov["planned"] and cov["n_samples"] != cov["planned"]: problems.append(f"{cov['n_samples']} of {cov['planned']} planned samples present")
if man["failures"]: problems.append(f"{len(man['failures'])} failed samples: {sorted(man['failures'])}")
json.dump(dict(coverage=cov, quality=qlog), open(os.path.join(D, "coverage.json"), "w"), indent=1)
json.dump(dict(ok=not problems, problems=problems), open(os.path.join(D, "integrity.json"), "w"), indent=1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 3, figsize=(13, 4))
for k in kinds:
    sel = np.array([a["kind"] == k for a in recs.values()]); ax[0].scatter(H[sel, 0], H[sel, 1], label=k, s=18)
ax[0].set_xlim(-1.1, 1.1); ax[0].set_ylim(-1.1, 1.1); ax[0].set_aspect("equal"); ax[0].set_title("gaze inputs"); ax[0].legend(fontsize=8); ax[0].grid(alpha=.3)
ax[1].scatter([a["iris"]["hue_shift"] for a in recs.values()], [a["iris"]["value"] for a in recs.values()], s=18); ax[1].set_xlabel("iris hue shift"); ax[1].set_ylabel("iris value"); ax[1].set_title("iris appearance")
lab = ["camera var.", "occluded", "quality var."]; val = [cov["camera_variants"], cov["occluded"], sum(cov["quality_variants"].values())]
ax[2].bar(lab, val); ax[2].set_title(f"conditions (n={len(recs)})")
fig.tight_layout(); fig.savefig(os.path.join(D, "coverage.png"), dpi=110)
print(json.dumps(cov, indent=1)); print("INTEGRITY", "OK" if not problems else problems)
sys.exit(1 if problems else 0)
