"""One-command synthetic gaze dataset from a Track 1 bundle (uses the bundle's own wrapper/eyes.py, unchanged).

    blender -b scene.blend --factory-startup -P tools/generate_dataset.py -- --out DIR [--n 150] [--seed 1] [--samples 32]

For each sample:
  * a random gaze (h, v) uniform in [-1, 1]^2 and a random lighting setup (domain randomisation: every light's
    energy x U(0.5, 1.5), world strength x U(0.5, 1.5), exposure + U(-0.5, 0.5));
  * DIR/rgb/NNNN.png      the photoreal 1024x1024 render (calibrated 40 cm camera, unchanged);
  * DIR/mask/NNNN.png     a pixel-exact, occlusion-correct label image of the same view:
                          red = pupil, green = iris, blue = sclera, black = everything else (lids, lashes, skin occlude);
  * DIR/labels.jsonl      one record per sample: inputs, unit gaze vectors per eye (world), eye rotations, 2D/3D pupil
                          centres, camera K and [R|t], lighting parameters, and mask pixel counts per class.
Masks come from a second render with flat emission materials (no lighting, no anti-aliasing noise in the labels).
Works on the MakeHuman scene (separate pupil/iris/sclera meshes) and the scanned head (UV circles on the scanned
eyeball texture: pupil r = 0.034, iris r = 0.112 around UV (0.5008, 0.4943), measured from the texture).
"""
import argparse
import json
import math
import os
import random
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True); ap.add_argument("--n", type=int, default=150)
ap.add_argument("--seed", type=int, default=1); ap.add_argument("--samples", type=int, default=32)
ap.add_argument("--head", default="")
args = ap.parse_args(argv)

sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402

sc = bpy.context.scene
os.makedirs(os.path.join(args.out, "rgb"), exist_ok=True); os.makedirs(os.path.join(args.out, "mask"), exist_ok=True)
SCAN = "Realtime Eyeball Left" in bpy.data.objects
head = args.head or ("scan" if SCAN else "makehuman")
eyes.use_best_device()
sc.cycles.samples = args.samples
rng = random.Random(args.seed)

lights = [o for o in bpy.data.objects if o.type == "LIGHT"]
base_energy = {o.name: o.data.energy for o in lights}
bg = sc.world.node_tree.nodes.get("Background") if sc.world and sc.world.use_nodes else None
base_world = bg.inputs[1].default_value if bg else None
base_exposure = sc.view_settings.exposure

def apply_lighting(p):
    for o in lights:
        o.data.energy = base_energy[o.name] * p["light_gain"][o.name]
    if bg is not None:
        bg.inputs[1].default_value = base_world * p["world_gain"]
    sc.view_settings.exposure = base_exposure + p["exposure_delta"]

# ---------------- pass 1: photoreal renders ----------------
records = []
for i in range(args.n):
    h, v = rng.uniform(-1, 1), rng.uniform(-1, 1)
    light = {"light_gain": {o.name: round(rng.uniform(0.5, 1.5), 4) for o in lights},
             "world_gain": round(rng.uniform(0.5, 1.5), 4), "exposure_delta": round(rng.uniform(-0.5, 0.5), 4)}
    apply_lighting(light)
    eyes.move(h, v)
    st = eyes.render(os.path.join(args.out, "rgb", f"{i:04d}.png"))
    tgt = Vector(st["fixation_target"])
    rec = {"id": i, "head": head, "rgb": f"rgb/{i:04d}.png", "mask": f"mask/{i:04d}.png", "input": st["input"], "lighting": light,
           "fixation_target": st["fixation_target"]}
    for s in "LR":
        g = (tgt - eyes._eye_centre(s)).normalized()
        rec[f"gaze_vector_{s}"] = [round(c, 6) for c in g]
        rec[f"gaze_yaw_pitch_deg_{s}"] = [round(math.degrees(math.atan2(g.x, -g.y)), 4), round(math.degrees(math.asin(g.z)), 4)]
        for k in ("eye_rotation", "eye_rotation_quat", "pupil_center_2D", "pupil_center_3D"):
            rec[f"{k}_{s}"] = st[f"{k}_{s}"]
    k_mat, rt = eyes.camera_matrices()
    rec["camera_matrix"] = [list(r) for r in k_mat]; rec["camera_extrinsic_world_to_cam"] = [list(r) for r in rt]
    records.append(rec)
    print(f"[dataset] rgb {i + 1}/{args.n}", flush=True)
apply_lighting({"light_gain": {o.name: 1.0 for o in lights}, "world_gain": 1.0, "exposure_delta": 0.0})

# ---------------- pass 2: label masks (flat emission, same poses) ----------------
def emission(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1); nt.links.new(e.outputs[0], o.inputs[0]); return m

def set_mat(o, m):
    o.data.materials.clear(); o.data.materials.append(m)
    for slot in o.material_slots:
        slot.link = "DATA"

BLACK = emission("lbl_other", (0, 0, 0))
if SCAN:
    m = bpy.data.materials.new("lbl_eye"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["UV"], sep.inputs[0])
    fx = nt.nodes.new("ShaderNodeMath"); fx.operation = "FRACT"; nt.links.new(sep.outputs[0], fx.inputs[0])
    dx = nt.nodes.new("ShaderNodeMath"); dx.operation = "SUBTRACT"; dx.inputs[1].default_value = 0.5008; nt.links.new(fx.outputs[0], dx.inputs[0])
    dy = nt.nodes.new("ShaderNodeMath"); dy.operation = "SUBTRACT"; dy.inputs[1].default_value = 0.4943; nt.links.new(sep.outputs[1], dy.inputs[0])
    hyp = nt.nodes.new("ShaderNodeVectorMath"); hyp.operation = "LENGTH"
    cmb = nt.nodes.new("ShaderNodeCombineXYZ"); nt.links.new(dx.outputs[0], cmb.inputs[0]); nt.links.new(dy.outputs[0], cmb.inputs[1])
    nt.links.new(cmb.outputs[0], hyp.inputs[0])
    p = nt.nodes.new("ShaderNodeMath"); p.operation = "LESS_THAN"; p.inputs[1].default_value = 0.034; nt.links.new(hyp.outputs["Value"], p.inputs[0])
    ir = nt.nodes.new("ShaderNodeMath"); ir.operation = "LESS_THAN"; ir.inputs[1].default_value = 0.112; nt.links.new(hyp.outputs["Value"], ir.inputs[0])
    g = nt.nodes.new("ShaderNodeMath"); g.operation = "SUBTRACT"; nt.links.new(ir.outputs[0], g.inputs[0]); nt.links.new(p.outputs[0], g.inputs[1])
    b = nt.nodes.new("ShaderNodeMath"); b.operation = "SUBTRACT"; b.inputs[0].default_value = 1.0; nt.links.new(ir.outputs[0], b.inputs[1])
    cc = nt.nodes.new("ShaderNodeCombineColor"); nt.links.new(p.outputs[0], cc.inputs[0]); nt.links.new(g.outputs[0], cc.inputs[1]); nt.links.new(b.outputs[0], cc.inputs[2])
    nt.links.new(cc.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.name.startswith("Realtime Eyeball"):
            set_mat(o, m)
        elif o.name.startswith("Lens"):
            o.hide_render = True                      # clear cornea: labels are what you see through it
        else:
            set_mat(o, BLACK)
else:
    RED, GREEN, BLUE = emission("lbl_pupil", (1, 0, 0)), emission("lbl_iris", (0, 1, 0)), emission("lbl_sclera", (0, 0, 1))
    for o in bpy.data.objects:
        if o.type not in ("MESH", "CURVES"):
            continue
        n = o.name
        if n.endswith(".Cornea") or n.endswith(".TearLine"):
            o.hide_render = True
        elif n.endswith(".PupilDark"):
            set_mat(o, RED)
        elif n.endswith(".Iris"):
            set_mat(o, GREEN)
        elif n.endswith(".Sclera"):
            set_mat(o, BLUE)
        else:
            o.data.materials.clear(); o.data.materials.append(BLACK)
for o in lights:
    o.hide_render = True
sc.world.use_nodes = False; sc.world.color = (0, 0, 0)
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"; sc.view_settings.exposure = 0
sc.cycles.samples = 1; sc.cycles.use_denoising = False
sc.cycles.filter_width = 0.01                       # one sample at the pixel centre: hard, un-blended labels
sc.render.image_settings.color_mode = "RGB"
import numpy as np  # noqa: E402
for rec in records:
    eyes.move(rec["input"]["h"], rec["input"]["v"])
    sc.render.filepath = os.path.join(args.out, rec["mask"]); bpy.ops.render.render(write_still=True)
    px = np.array(bpy.data.images.load(sc.render.filepath, check_existing=False).pixels[:]).reshape(-1, 4)[:, :3] > 0.5
    rec["mask_pixels"] = {"pupil": int(px[:, 0].sum()), "iris": int(px[:, 1].sum()), "sclera": int(px[:, 2].sum())}
    print(f"[dataset] mask {rec['id'] + 1}/{args.n}", flush=True)
with open(os.path.join(args.out, "labels.jsonl"), "w") as fh:
    for rec in records:
        fh.write(json.dumps(rec) + "\n")
json.dump({"head": head, "n": args.n, "seed": args.seed, "samples": args.samples, "resolution": [sc.render.resolution_x, sc.render.resolution_y],
           "mask_colours": {"pupil": "red", "iris": "green", "sclera": "blue", "other": "black"},
           "gaze_sampling": "h, v uniform in [-1, 1]; fixation 35 cm ahead of the eye midpoint, displaced by (h, v) x 5 cm",
           "lighting": "per-sample light energy x U(0.5,1.5), world x U(0.5,1.5), exposure + U(-0.5,0.5)"},
          open(os.path.join(args.out, "dataset_info.json"), "w"), indent=1)
print("DATASET_DONE", args.out)
