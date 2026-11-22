"""WS4: configuration-driven dataset renderer, v2 (experimental; the official 10-frame output is untouched).

    blender -b --factory-startup <bundle>/scene.blend -P research/dataset_v2_render.py -- --config cfg.json --out DIR [--fast] [--commit SHA]

Each sample gets a deterministic ID: sha1(config_sha256 : index)[:12], and its own RNG seeded with (seed, index), so
interrupted runs resume to the same dataset. Per sample it draws gaze (or a dynamics profile frame), iris hue/value,
lighting gains, an optional camera variant (distance along the optical axis, focal-length scale; K/[R|t] recorded),
and optional extra upper-lid lowering (occlusion). Clean renders + annotations are written; image-quality
degradation is a separate pure-Python step (dataset_v2_post.py) so the clean source is always kept.
DIR/clean/<id>.png, DIR/annotations/<id>.json, DIR/manifest.json (provenance, per-sample hashes, failures).
"""
import datetime, hashlib, json, math, os, platform, random, sys, time, traceback
import bpy
from mathutils import Quaternion, Vector
a = sys.argv[sys.argv.index("--") + 1:]
cfg = json.load(open(a[a.index("--config") + 1])); out = a[a.index("--out") + 1]
commit = a[a.index("--commit") + 1] if "--commit" in a else None
CH = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here); sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402
import dynamics as DY  # noqa: E402
sc = bpy.context.scene; dev = eyes.use_best_device(); sc.cycles.samples = cfg["samples"]
band = None
if "--fast" in a:
    import speed; band = speed.apply()
cam = sc.camera; cam_m0 = cam.matrix_world.copy(); lens0 = cam.data.lens
lights = [o for o in bpy.data.objects if o.type == "LIGHT"]; E0 = {o.name: o.data.energy for o in lights}
bg = sc.world.node_tree.nodes.get("Background") if sc.world and sc.world.use_nodes else None; W0 = bg.inputs[1].default_value if bg else None
X0 = sc.view_settings.exposure
mat = bpy.data.materials.get("Realtime Eyeball Left"); hs = None
if mat:
    nt = mat.node_tree; tex = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image and "Diffuse" in n.image.name)
    users = [l.to_socket for l in tex.outputs[0].links]; hs = nt.nodes.new("ShaderNodeHueSaturation")
    bw = nt.nodes.new("ShaderNodeRGBToBW"); mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.55, 0.35
    nt.links.new(tex.outputs[0], bw.inputs[0]); nt.links.new(bw.outputs[0], mr.inputs[0]); nt.links.new(mr.outputs[0], hs.inputs["Fac"]); nt.links.new(tex.outputs[0], hs.inputs["Color"])
    for s_ in users: nt.links.new(hs.outputs[0], s_)

# ---- sample plan (deterministic, independent of what is already on disk)
plan = []
for i in range(cfg["n_static"]):
    plan.append(dict(index=len(plan), kind="static"))
P = cfg.get("profiles", {})
for j in range(P.get("n", 0)):
    kind = P["kinds"][j % len(P["kinds"])]
    for f in range(P["frames_per_profile"]):
        plan.append(dict(index=len(plan), kind=kind, profile=j, profile_frame=f))
def sid(i): return hashlib.sha1(f"{CH}:{i}".encode()).hexdigest()[:12]
def U(r, lo_hi): return r.uniform(*lo_hi)

def profile_input(p, r):
    rp = random.Random(f"{cfg['seed']}:profile:{p['profile']}"); n = P["frames_per_profile"]
    if p["kind"] == "saccade":
        h0, v0, h1, v1 = (rp.uniform(-1, 1) for _ in range(4)); fr = DY.saccade(h0, v0, h1, v1, fps=1000)["frames"]
    else:
        fr = DY.pursuit(amp=rp.uniform(0.4, 1.0), freq=rp.uniform(0.2, 0.5), dur=1.0, fps=1000)["frames"]
    f = fr[int(round(p["profile_frame"] * (len(fr) - 1) / max(1, n - 1)))]
    return f["h"], f["v"], dict(profile_kind=p["kind"], profile_id=p["profile"], profile_frame=p["profile_frame"], t_s=f["t"])

for d in ("clean", "annotations"): os.makedirs(os.path.join(out, d), exist_ok=True)
mp = os.path.join(out, "manifest.json"); man = json.load(open(mp)) if os.path.exists(mp) else {}
if man.get("config_sha256") not in (None, CH): raise SystemExit("DIR holds a dataset made with a different config")
man.update(dataset_name=cfg["name"], schema_version=cfg.get("schema_version", "2.0"), config=cfg, config_sha256=CH, git_commit=commit,
           provenance=dict(blender=bpy.app.version_string, python=platform.python_version(), os=platform.platform(), render_device=dev, eye_band_px=band))
man.setdefault("samples", {}); man.setdefault("failures", {}); man.setdefault("runs", []).append(dict(started=datetime.datetime.now(datetime.timezone.utc).isoformat()))
def wj(p, o): t = p + ".tmp"; json.dump(o, open(t, "w"), indent=1); os.replace(t, p)
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
done = 0
for p in plan:
    i = p["index"]; s = sid(i); png = os.path.join(out, "clean", s + ".png"); js = os.path.join(out, "annotations", s + ".json")
    if os.path.exists(png) and os.path.exists(js) and s in man["samples"]:
        continue
    try:
        r = random.Random(f"{cfg['seed']}:{i}")
        if p["kind"] == "static":
            h, v = U(r, [-cfg["gaze"]["box"], cfg["gaze"]["box"]]), U(r, [-cfg["gaze"]["box"], cfg["gaze"]["box"]]); prof = None
        else:
            h, v, prof = profile_input(p, r)
        iris = dict(hue_shift=U(r, cfg["iris"]["hue_shift"]), value=U(r, cfg["iris"]["value"]))
        L = cfg["lighting"]; light = dict(light_gain={o.name: U(r, L["light_gain"]) for o in lights}, world_gain=U(r, L["world_gain"]), exposure_delta=U(r, L["exposure"]))
        C = cfg["camera"]; camv = dict(distance_m=U(r, C["distance_m"]), lens_scale=U(r, C["lens_scale"])) if r.random() < C["p_variant"] else None
        O = cfg["occlusion"]; occ = dict(extra_upper_lid_deg=U(r, O["extra_upper_lid_deg"])) if r.random() < O["p"] else None
        # apply
        for o in lights: o.data.energy = E0[o.name] * light["light_gain"][o.name]
        if bg is not None: bg.inputs[1].default_value = W0 * light["world_gain"]
        sc.view_settings.exposure = X0 + light["exposure_delta"]
        if hs: hs.inputs["Hue"].default_value, hs.inputs["Value"].default_value = 0.5 + iris["hue_shift"], iris["value"]
        cam.matrix_world = cam_m0; cam.data.lens = lens0
        eyes.move(max(-1, min(1, h)), max(-1, min(1, v)))
        if camv:
            mid = eyes._state["midpoint"]; fwd = (cam_m0.translation - mid).normalized(); M = cam_m0.copy(); M.translation = mid + fwd * camv["distance_m"]
            cam.matrix_world = M; cam.data.lens = lens0 * camv["lens_scale"]
        if occ:
            tgt = eyes.target_point(eyes._state["h"], eyes._state["v"])
            for side in "LR":
                up, _ = eyes.lid_rotations(side, tgt)
                eyes._set_bone_world_rotation(eyes.UPPER_LID_BONES[side], Quaternion(Vector((1, 0, 0)), math.radians(occ["extra_upper_lid_deg"])) @ up)
        bpy.context.view_layer.update()
        t = time.time(); st = eyes.render(png + ".part.png"); dt = time.time() - t; os.replace(png + ".part.png", png)
        K, RT = eyes.camera_matrices()
        rec = dict(st, sample_id=s, index=i, kind=p["kind"], profile=prof, iris=iris, lighting=light, camera_variant=camv, camera_matrix=K,
                   camera_extrinsic_world_to_cam=RT, occlusion=occ, config_sha256=CH, render_s=round(dt, 3), file=f"clean/{s}.png")
        wj(js, rec); man["samples"][s] = dict(index=i, image=rec["file"], annotation=f"annotations/{s}.json", image_sha256=sha(png), annotation_sha256=sha(js))
        man["failures"].pop(s, None); done += 1
        print(f"[v2] {s} #{i} {p['kind']} h={h:+.2f} v={v:+.2f} cam={'var' if camv else 'std'} occ={'y' if occ else 'n'} {dt:.1f}s", flush=True)
    except Exception:
        man["failures"][s] = dict(index=i, error=traceback.format_exc(limit=4)); print(f"[v2] {s} FAILED", flush=True)
    wj(mp, man)
cam.matrix_world = cam_m0; cam.data.lens = lens0; eyes.reset()
man["runs"][-1].update(finished=datetime.datetime.now(datetime.timezone.utc).isoformat(), rendered=done, planned=len(plan)); man["planned_samples"] = len(plan)
wj(mp, man); print("V2_DONE", len(man["samples"]), "of", len(plan), "failures", len(man["failures"]), flush=True)
