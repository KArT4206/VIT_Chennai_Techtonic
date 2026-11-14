"""Phase 2E renders on phase2e/gnm_scan_2e.blend (not saved back).

    blender -b --factory-startup --disable-autoexec BLEND --python render_2e.py -- OUT SPP SECTION [VARIANT]

SECTION eyefix | disp | expr | closeups.   VARIANT (skin displacement) A | B | C | D (default A):
  A  current: vendor normal (macro+micro overlay), no displacement
  B  displacement only (0.70 mm per unit, true displacement), no normal map
  C  vendor normal + controlled displacement (0.35 mm per unit, displacement + bump)
  D  displacement 0.70 mm per unit + micro (high-frequency) normal only, macro normal removed
Per shot: wall time and Cycles peak memory (from the render stats) -> OUT/stats_<section>_<variant>.json
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "gnm_qualification"))
import gnm_engine  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
out, spp, section = args[0], int(args[1]), args[2]
variant = args[3] if len(args) > 3 else "A"
os.makedirs(out, exist_ok=True)
BUILD = os.path.join(HERE, "..", "3dscanstore", "build")
sc = bpy.context.scene; sc.cycles.samples = spp; sc.cycles.seed = 0
p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
gh = bpy.data.objects["GNM_Head"]; me = gh.data; V2W = gh.matrix_world.copy()
G = gnm_engine.GNMRig(os.path.join(BUILD, "gnm_scan_keys.npz"))
kbs = me.shape_keys.key_blocks

# ------------------------------------------------------------------ skin variant
skin = bpy.data.materials["Skin_2E"]; nt = skin.node_tree; N = nt.nodes
S = 0.0007                                                     # metres per unit (normal-map fit, cheeks 0.66-0.83 mm)
disp = N["DISP"]; nmap = N["NMAP"]; bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")
micro = N["Image Texture.005"]
adaptive = None
if variant != "A":
    sub = next(m for m in gh.modifiers if m.type == "SUBSURF")
    for attr, obj in (("use_adaptive_subdivision", sub), ("use_adaptive_subdivision", getattr(gh, "cycles", None))):
        if obj is not None and hasattr(obj, attr):
            try:
                setattr(obj, attr, True); adaptive = f"{type(obj).__name__}.{attr}"; break
            except Exception as e:  # noqa: BLE001
                print("adaptive attr failed", attr, e)
    if hasattr(sc.cycles, "feature_set") and adaptive and "Cycles" in adaptive:
        sc.cycles.feature_set = "EXPERIMENTAL"
    for o, a, v in ((sub, "adaptive_pixel_size", 2.0), (sc.cycles, "dicing_rate", 2.0), (gh.cycles if hasattr(gh, "cycles") else None, "dicing_rate", 2.0)):
        if o is not None and hasattr(o, a):
            setattr(o, a, v)
print("VARIANT", variant, "adaptive:", adaptive)
if variant == "B":
    disp.inputs["Scale"].default_value = S; skin.displacement_method = "DISPLACEMENT"
    for l in list(bsdf.inputs["Normal"].links):
        nt.links.remove(l)
elif variant == "C":
    disp.inputs["Scale"].default_value = 0.5 * S; skin.displacement_method = "BOTH"
elif variant == "D":
    disp.inputs["Scale"].default_value = S; skin.displacement_method = "DISPLACEMENT"
    nt.links.new(micro.outputs["Color"], nmap.inputs["Color"])
else:
    disp.inputs["Scale"].default_value = 0.0; skin.displacement_method = "BUMP"

# ------------------------------------------------------------------ cameras
gi = {g.name: g.index for g in gh.vertex_groups}
V0 = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", V0); V0 = V0.reshape(-1, 3)


def group_pts(*names):
    ids = [gi[n] for n in names]
    return np.array([V0[v.index] for v in me.vertices if all(any(g.group == i for g in v.groups) for i in ids)])


def camera(name, eye_g, look_g, lens):
    cam = bpy.data.cameras.new(name); cam.lens = lens; cam.clip_start = 0.5
    ob = bpy.data.objects.new(name, cam); sc.collection.objects.link(ob)
    e = V2W @ Vector(eye_g); t = V2W @ Vector(look_g)
    up = (V2W.to_3x3().normalized() @ Vector((0, 1, 0))).normalized()
    f = (t - e).normalized(); r = f.cross(up).normalized(); u = r.cross(f)
    M = Matrix(((r.x, u.x, -f.x), (r.y, u.y, -f.y), (r.z, u.z, -f.z))).to_4x4(); M.translation = e
    ob.matrix_world = M
    return name


cL = G.centre["left"]; cR = G.centre["right"]
eyeL = camera("C_eyeL", (cL.x, cL.y, cL.z + 0.11), (cL.x, cL.y, cL.z), 120)
eyeR = camera("C_eyeR", (cR.x, cR.y, cR.z + 0.11), (cR.x, cR.y, cR.z), 120)
ear = group_pts("gnm_ears"); earL = ear[ear[:, 0] > 0].mean(0); earR = ear[ear[:, 0] < 0].mean(0)
camera("C_earL", (earL[0] + 0.16, earL[1] + 0.01, earL[2] + 0.02), tuple(earL), 70)
camera("C_earR", (earR[0] - 0.16, earR[1] + 0.01, earR[2] + 0.02), tuple(earR), 70)
fh = group_pts("gnm_forehead_region"); top = fh[fh[:, 1] > np.percentile(fh[:, 1], 80)].mean(0)
camera("C_hairline", (top[0], top[1] + 0.06, top[2] + 0.16), tuple(top), 70)

# ------------------------------------------------------------------ poses
stats = {}; last = {"s": ""}


def on_stats(st):
    last["s"] = st


bpy.app.handlers.render_stats.append(on_stats)


def pose(yaw=0.0, pitch=0.0, **w):
    t = G.target(yaw, pitch); kw = {}
    for side, s in (("left", "L"), ("right", "R")):
        G.set_eye_quat(side, G.eye_rotation(side, t))
        b = w.get("blink", 0.0)
        kw[f"blink_{s}"] = b
        kw[f"lid_follow_{s}"] = G.elevation(side, t) / 10.0 * (1 - b)
        for k in ("squint", "surprise", "brow_raise"):
            kw[f"{k}_{s}"] = w.get(k, 0.0)
    G.set_keys(**kw)
    for s in ("L", "R"):
        kbs[f"brow_furrow_{s}"].value = w.get("brow_furrow", 0.0)
    bpy.context.view_layer.update()


def shot(name, cam, res):
    sc.camera = bpy.data.objects[cam]
    sc.render.resolution_x, sc.render.resolution_y = res if isinstance(res, tuple) else (res, res)
    sc.render.filepath = os.path.join(out, name)
    t = time.time(); bpy.ops.render.render(write_still=True); dt = round(time.time() - t, 1)
    peak = None
    for tok in last["s"].split("|"):
        if "Peak" in tok:
            peak = tok.strip()
    stats[name] = dict(seconds=dt, mem=peak)
    print("RENDERED", name, dt, peak, flush=True)


if section == "eyefix":
    for name, kw in (("neutral", {}), ("left10", dict(yaw=10)), ("left15", dict(yaw=15)), ("left20", dict(yaw=20)), ("right15", dict(yaw=-15)),
                     ("right20", dict(yaw=-20)), ("blink", dict(blink=1.0)), ("blink_left15", dict(yaw=15, blink=1.0)),
                     ("halfblink_left15", dict(yaw=15, blink=0.5))):
        pose(**kw); shot(f"eyes_{name}.png", "V_eyes", 1024)
    for name, kw in (("neutral", {}), ("left15", dict(yaw=15)), ("up12", dict(pitch=12))):
        pose(**kw); shot(f"eyeL_{name}.png", eyeL, 1024); shot(f"eyeR_{name}.png", eyeR, 1024)
elif section == "disp":
    pose(); shot(f"skin_{variant}.png", "V_skin", 2048); shot(f"front_{variant}.png", "V_front", 1024)
    shot(f"brow_{variant}.png", "V_brow", 1024)
elif section == "expr":
    P = [("neutral", {}), ("squint", dict(squint=1.0)), ("surprise", dict(surprise=1.0)), ("brow_raise", dict(brow_raise=1.0)),
         ("brow_lowerer", dict(brow_furrow=1.0)), ("blink", dict(blink=1.0)), ("half_blink", dict(blink=0.5)),
         ("blink_up12", dict(blink=1.0, pitch=12)), ("blink_down7", dict(blink=1.0, pitch=-7)), ("blink_left15", dict(blink=1.0, yaw=15)),
         ("squint_left15", dict(squint=1.0, yaw=15)), ("brow_raise_up12", dict(brow_raise=1.0, pitch=12)),
         ("look_left15", dict(yaw=15)), ("look_right15", dict(yaw=-15)), ("look_up12", dict(pitch=12)), ("look_down7", dict(pitch=-7))]
    for name, kw in P:
        pose(**kw); shot(f"front_{name}.png", "V_front", 1024); shot(f"eyes_{name}.png", "V_eyes", 1024)
elif section == "iris":
    # inspection only: each eye looks straight into its own close-up camera, plus a small frontal fill
    # (the vendor key light leaves the subject's left eye in shadow); the fill is not part of the look.
    ld = bpy.data.lights.new("iris_fill", "AREA"); ld.energy = 2.0; ld.size = 8.0
    lo = bpy.data.objects.new("iris_fill", ld); sc.collection.objects.link(lo)
    pose()
    for side, cam, c in (("left", eyeL, cL), ("right", eyeR, cR)):
        tgt = Vector((c.x, c.y, c.z + 0.11))
        for s2 in ("left", "right"):
            G.set_eye_quat(s2, G.eye_rotation(s2, tgt))
        cw = bpy.data.objects[cam].matrix_world
        lo.matrix_world = cw @ Matrix.Translation((0, 0.0, 2.0))
        bpy.context.view_layer.update()
        shot(f"iris_{side}.png", cam, 1024)
elif section == "evenlight":
    # diagnostic only, NOT the look: every scene light off, uniform grey world (identical exposure for
    # all shots), so iris and sclera texture can be compared without the vendor key/fill shadows.
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    w = bpy.data.worlds.new("even"); w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND"); bg.inputs[0].default_value = (1, 1, 1, 1); bg.inputs[1].default_value = 1.0
    sc.world = w; sc.view_settings.exposure = 0.0
    for side, cam, c in (("left", eyeL, cL), ("right", eyeR, cR)):
        tgt = Vector((c.x, c.y, c.z + 0.11))
        for s2 in ("left", "right"):
            G.set_eye_quat(s2, G.eye_rotation(s2, tgt))
        bpy.context.view_layer.update()
        shot(f"even_iris_{side}.png", cam, 1024)
    for name, kw in (("neutral", {}), ("left10", dict(yaw=10)), ("left15", dict(yaw=15)), ("left20", dict(yaw=20)),
                     ("right10", dict(yaw=-10)), ("right15", dict(yaw=-15)), ("right20", dict(yaw=-20))):
        pose(**kw); shot(f"even_eyes_{name}.png", "V_eyes", 1024)
elif section == "closeups":
    pose()
    shot("three_quarter.png", "V_34", 1024); shot("eye_closeup.png", "V_eyes", 1024); shot("skin_closeup.png", "V_skin", 2048)
    shot("brow_closeup.png", "V_brow", 1024); shot("hairline.png", "C_hairline", 1024)
    shot("ear_left.png", "C_earL", 1024); shot("ear_right.png", "C_earR", 1024)
json.dump(dict(variant=variant, adaptive=adaptive, shots=stats), open(os.path.join(out, f"stats_{section}_{variant}.json"), "w"), indent=1)
