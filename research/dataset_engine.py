"""Stage 4 + 6: config-driven, resumable synthetic gaze dataset generator (separate from the official bundle output).

    blender -b --factory-startup <bundle>/scene.blend -P research/dataset_engine.py -- --config cfg.json --out DIR

Config (JSON; every key optional, defaults shown in DEFAULTS). Per sample i, an independent RNG seeded with
(seed, i) draws: gaze (h, v) ~ U[-1,1]^2, lighting gains, and an appearance variant (iris hue shift / iris value
scale applied with a Hue-Saturation node on the eyeball texture). Because each sample has its own seed, a resumed
run produces the same samples as an uninterrupted one.

Output
  DIR/images/NNNNNN.png          1024x1024 render (official camera, unchanged)
  DIR/annotations/NNNNNN.json    wrapper state(): inputs, eye rotations, 2D/3D pupil centres + K, [R|t], variant, lighting
  DIR/manifest.json              provenance (Blender/Python/OS/device, config + its SHA-256, seed, git commit, timestamps),
                                 one entry per sample with file SHA-256s. Rewritten after every sample (atomic rename).
Resume: a sample is skipped when its PNG and JSON both exist and the JSON records the same config hash.
Failures: an exception on one sample is recorded in manifest['failures'] and the run continues.
"""
import datetime, hashlib, json, os, platform, random, sys, time, traceback
import bpy

DEFAULTS = dict(name="techtonic_gaze", n=20, seed=1, samples=32, light_gain=[0.6, 1.4], world_gain=[0.6, 1.4],
                exposure=[-0.4, 0.4], iris_hue_shift=[0.0, 0.05], iris_value=[0.45, 1.15], gaze_box=1.0)

a = sys.argv[sys.argv.index("--") + 1:]
cfg = dict(DEFAULTS); cfg_path = a[a.index("--config") + 1] if "--config" in a else None
if cfg_path:
    cfg.update(json.load(open(cfg_path)))
out = a[a.index("--out") + 1]
commit = a[a.index("--commit") + 1] if "--commit" in a else None
cfg_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()

sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402

sc = bpy.context.scene
device = eyes.use_best_device(); sc.cycles.samples = cfg["samples"]
lights = [o for o in bpy.data.objects if o.type == "LIGHT"]; base_e = {o.name: o.data.energy for o in lights}
bg = sc.world.node_tree.nodes.get("Background") if sc.world and sc.world.use_nodes else None
base_w = bg.inputs[1].default_value if bg else None; base_x = sc.view_settings.exposure

# appearance node: Hue/Sat on the eyeball diffuse texture, limited to dark texels (the iris), sclera untouched
mat = bpy.data.materials.get("Realtime Eyeball Left")
hs = None
if mat:
    nt = mat.node_tree
    tex = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "Diffuse" in n.image.name)
    users = [l.to_socket for l in tex.outputs[0].links]
    hs = nt.nodes.new("ShaderNodeHueSaturation")
    bw = nt.nodes.new("ShaderNodeRGBToBW"); m = nt.nodes.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = 0.55, 0.35   # bright sclera -> 0, iris -> 1
    nt.links.new(tex.outputs[0], bw.inputs[0]); nt.links.new(bw.outputs[0], m.inputs[0]); nt.links.new(m.outputs[0], hs.inputs["Fac"])
    nt.links.new(tex.outputs[0], hs.inputs["Color"])
    for s in users:
        nt.links.new(hs.outputs[0], s)

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

def wjson(p, obj):
    tmp = p + ".tmp"; json.dump(obj, open(tmp, "w"), indent=1); os.replace(tmp, p)

for d in ("images", "annotations"):
    os.makedirs(os.path.join(out, d), exist_ok=True)
mpath = os.path.join(out, "manifest.json")
man = json.load(open(mpath)) if os.path.exists(mpath) else {}
if man.get("config_sha256") not in (None, cfg_hash):
    raise SystemExit("manifest in DIR was made with a different config; use a new --out")
man.update(dataset_name=cfg["name"], schema_version="1.0", config=cfg, config_sha256=cfg_hash, git_commit=commit,
           provenance=dict(blender=bpy.app.version_string, python=platform.python_version(), os=platform.platform(),
                           machine=platform.machine(), render_device=device, cycles_samples=cfg["samples"]),
           image=dict(width=1024, height=1024, format="PNG"),
           calibration=dict(fixation_distance_m=eyes.FIXATION_DISTANCE_M, motion_bound_m=eyes.MOTION_BOUND_M,
                            camera_distance_m=0.40, camera_matrix=eyes.camera_matrices()[0], camera_extrinsic_world_to_cam=eyes.camera_matrices()[1]))
man.setdefault("samples", {}); man.setdefault("failures", {}); man.setdefault("runs", [])
man["runs"].append(dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat()))
times = []
for i in range(cfg["n"]):
    stem = f"{i:06d}"; png = os.path.join(out, "images", stem + ".png"); js = os.path.join(out, "annotations", stem + ".json")
    if os.path.exists(png) and os.path.exists(js):
        try:
            if json.load(open(js)).get("config_sha256") == cfg_hash:
                continue
        except ValueError:
            pass
    try:
        r = random.Random(f"{cfg['seed']}:{i}")
        h, v = (r.uniform(-cfg["gaze_box"], cfg["gaze_box"]) for _ in range(2))
        light = {o.name: r.uniform(*cfg["light_gain"]) for o in lights}
        wg, ex = r.uniform(*cfg["world_gain"]), r.uniform(*cfg["exposure"])
        hue, val = r.uniform(*cfg["iris_hue_shift"]), r.uniform(*cfg["iris_value"])
        for o in lights: o.data.energy = base_e[o.name] * light[o.name]
        if bg is not None: bg.inputs[1].default_value = base_w * wg
        sc.view_settings.exposure = base_x + ex
        if hs: hs.inputs["Hue"].default_value, hs.inputs["Value"].default_value = 0.5 + hue, val
        eyes.move(h, v)
        t = time.time(); st = eyes.render(png + ".part.png"); dt = time.time() - t; times.append(dt)
        os.replace(png + ".part.png", png)
        rec = dict(st, sample=i, file=f"images/{stem}.png", config_sha256=cfg_hash, render_s=round(dt, 3),
                   variant=dict(iris_hue_shift=round(hue, 5), iris_value=round(val, 5)),
                   lighting=dict(light_gain={k: round(x, 5) for k, x in light.items()}, world_gain=round(wg, 5), exposure_delta=round(ex, 5)))
        wjson(js, rec)
        man["samples"][stem] = dict(image=rec["file"], annotation=f"annotations/{stem}.json", image_sha256=sha(png), annotation_sha256=sha(js))
        man["failures"].pop(stem, None)
        print(f"[dataset] {stem} h={h:+.3f} v={v:+.3f} hue={hue:+.3f} val={val:.2f} {dt:.1f}s", flush=True)
    except Exception:
        man["failures"][stem] = traceback.format_exc(limit=3)
        print(f"[dataset] {stem} FAILED", flush=True)
    wjson(mpath, man)
man["runs"][-1].update(finished=datetime.datetime.now(datetime.timezone.utc).isoformat(), rendered=len(times),
                       mean_render_s=round(sum(times) / len(times), 3) if times else None)
wjson(mpath, man)
eyes.reset()
print("DATASET_DONE", len(man["samples"]), "samples,", len(man["failures"]), "failures", flush=True)
