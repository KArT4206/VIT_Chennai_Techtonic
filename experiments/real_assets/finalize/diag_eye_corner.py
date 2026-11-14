"""Phase 2E diagnostic: inner eye-corner pink patch on the scan-based GNM head.

    blender -b --factory-startup --disable-autoexec ../3dscanstore/build/gnm_scan.blend --python diag_eye_corner.py -- OUTDIR SPP

1. Per eye-interior vertex: angle theta from the rest gaze axis about the eye centre, azimuth
   (nasal / temporal / up / down) and the baked texture colour at its UV -> pinkness profile.
2. Renders, with the beauty material and with a theta-band debug emission (cornea hidden):
   neutral, 10/15/20 deg left, 15/20 deg right, blink neutral, blink at 15 deg left.
The scene file is not saved.
"""
import json
import os
import sys

import bpy
import numpy as np
import OpenImageIO as oiio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "gnm_qualification"))
import gnm_engine  # noqa: E402

out, spp = sys.argv[sys.argv.index("--") + 1:][:2]
spp = int(spp); os.makedirs(out, exist_ok=True)
BUILD = os.path.join(HERE, "..", "3dscanstore", "build")
sc = bpy.context.scene; sc.cycles.samples = spp; sc.cycles.seed = 0
p = bpy.context.preferences.addons["cycles"].preferences; p.compute_device_type = "METAL"; p.get_devices()
for d in p.devices:
    d.use = d.type == "METAL"
sc.cycles.device = "GPU"
gh = bpy.data.objects["GNM_Head"]; me = gh.data
G = gnm_engine.GNMRig(os.path.join(BUILD, "gnm_scan_keys.npz"))
J = np.load(os.path.join(BUILD, "gnm_scan_keys.npz")); names = [str(n) for n in J["joint_names"]]
nv = len(me.vertices)
V = np.empty(nv * 3, np.float32); me.vertices.foreach_get("co", V); V = V.reshape(-1, 3).astype(np.float64)
gi = {g.name: g.index for g in gh.vertex_groups}
memb = [set(g.group for g in v.groups) for v in me.vertices]
# per-vertex UV (first loop) on the UDIM layer
uvl = me.uv_layers["UDIM"]; uv = np.empty(len(me.loops) * 2, np.float32); uvl.data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
lv = np.empty(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", lv)
vuv = np.zeros((nv, 2)); vuv[lv] = uv
mi = np.empty(len(me.polygons), np.int32); me.polygons.foreach_get("material_index", mi)
theta = np.full(nv, -1.0, np.float32)
report = {}
for side, slot, tile in (("left", 1, 1002), ("right", 3, 1004)):
    c = J["joints"][names.index(f"{side}_eye")]
    ids = np.unique([v for poly, m in zip(me.polygons, mi) if m == slot for v in poly.vertices])
    d = V[ids] - c; d /= np.linalg.norm(d, axis=1, keepdims=True)
    th = np.degrees(np.arccos(np.clip(d[:, 2], -1, 1))); theta[ids] = th
    # nasal direction: toward the midline (GNM +X is the subject's left)
    nasal_x = -1.0 if side == "left" else 1.0
    az = np.degrees(np.arctan2(d[:, 1], d[:, 0] * nasal_x))       # 0 = nasal, 90 = up, 180 = temporal
    img = oiio.ImageBuf(os.path.join(BUILD, f"scan_eye_albedo.{tile}.png")); px = img.get_pixels(oiio.FLOAT)
    H, W = px.shape[:2]
    u = vuv[ids, 0] - (tile - 1001); v = vuv[ids, 1]
    col = px[np.clip(((1 - v) * H).astype(int), 0, H - 1), np.clip((u * W).astype(int), 0, W - 1), :3]
    pink = (col[:, 0] - col[:, 1]) / np.maximum(col[:, 0], 1e-3)
    rows = []
    for lo in range(0, 100, 5):
        for name, a0, a1 in (("nasal", -45, 45), ("up", 45, 135), ("temporal", 135, 225), ("down", -135, -45)):
            a = (az - a0) % 360
            sel = (th >= lo) & (th < lo + 5) & (a <= (a1 - a0))
            if sel.sum():
                rows.append((lo, name, int(sel.sum()), round(float(np.median(pink[sel])), 3)))
    report[side] = rows
    print(f"== {side} eye: pinkness (R-G)/R by theta band and azimuth (sclera white ~0.05, vendor pink band ~0.5)")
    for r in rows:
        print("  theta %2d-%2d %-8s n=%4d pink %.3f" % (r[0], r[0] + 5, r[1], r[2], r[3]))
at = me.attributes.get("eye_theta") or me.attributes.new("eye_theta", "FLOAT", "POINT"); at.data.foreach_set("value", theta)
json.dump(report, open(os.path.join(out, "pink_profile.json"), "w"), indent=1)

# debug material: theta bands (green <40, yellow 40-50, orange 50-60, red 60-70, magenta >70)
dbg = bpy.data.materials.new("theta_debug"); dbg.use_nodes = True; nt = dbg.node_tree
for n in list(nt.nodes):
    if n.type != "OUTPUT_MATERIAL":
        nt.nodes.remove(n)
o = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
a = nt.nodes.new("ShaderNodeAttribute"); a.attribute_name = "eye_theta"
mp = nt.nodes.new("ShaderNodeMapRange"); mp.inputs["From Min"].default_value = 30; mp.inputs["From Max"].default_value = 80
nt.links.new(a.outputs["Fac"], mp.inputs["Value"])
ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"; el = ramp.color_ramp.elements
el[0].position = 0.0; el[0].color = (0, 0.8, 0, 1); el[1].position = 0.2; el[1].color = (1, 1, 0, 1)
for pos, colr in ((0.4, (1, 0.4, 0, 1)), (0.6, (1, 0, 0, 1)), (0.8, (1, 0, 1, 1))):
    e = el.new(pos); e.color = colr
nt.links.new(mp.outputs[0], ramp.inputs[0])
em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(ramp.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], o.inputs["Surface"])
orig = [me.materials[i] for i in range(len(me.materials))]
for n in ("Head", "Realtime Eyeball Left", "Realtime Eyeball Right", "Lens Left", "Lens Right", "Teeth", "Tongue"):
    bpy.data.objects[n].hide_render = True

POSES = [("neutral", 0, 0, 0), ("left10", 10, 0, 0), ("left15", 15, 0, 0), ("left20", 20, 0, 0), ("right15", -15, 0, 0),
         ("right20", -20, 0, 0), ("blink", 0, 0, 1.0), ("blink_left15", 15, 0, 1.0), ("halfblink_left15", 15, 0, 0.5)]


def pose(yaw, pitch, b):
    t = G.target(yaw, pitch); kw = {}
    for side, s in (("left", "L"), ("right", "R")):
        G.set_eye_quat(side, G.eye_rotation(side, t))
        kw[f"blink_{s}"] = b; kw[f"lid_follow_{s}"] = G.elevation(side, t) / 10.0 * (1 - b)
    G.set_keys(**kw); bpy.context.view_layer.update()


sc.camera = bpy.data.objects["V_eyes"]; sc.render.resolution_x = sc.render.resolution_y = 1024
for debug in (False, True):
    for i in (1, 3):
        me.materials[i] = dbg if debug else orig[i]
    for i in (2, 4):
        me.materials[i] = orig[i]
    # cornea is rendered normally; for debug hide it by a transparent material so the sphere is seen directly
    if debug:
        tr = bpy.data.materials.get("dbg_clear") or bpy.data.materials.new("dbg_clear"); tr.use_nodes = True
        tn = tr.node_tree; [tn.nodes.remove(n) for n in list(tn.nodes) if n.type != "OUTPUT_MATERIAL"]
        tp = tn.nodes.new("ShaderNodeBsdfTransparent"); tn.links.new(tp.outputs[0], next(n for n in tn.nodes if n.type == "OUTPUT_MATERIAL").inputs["Surface"])
        for i in (2, 4):
            me.materials[i] = tr
    for name, yaw, pitch, b in POSES:
        if debug and b > 0.99:
            continue
        pose(yaw, pitch, b)
        sc.cycles.samples = 32 if debug else spp
        sc.render.filepath = os.path.join(out, f"{'dbg_' if debug else ''}{name}.png")
        bpy.ops.render.render(write_still=True); print("RENDERED", sc.render.filepath, flush=True)
for i, m in enumerate(orig):
    me.materials[i] = m
G.set_keys()
