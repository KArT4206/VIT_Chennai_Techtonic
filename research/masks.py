"""WS3: semantic label renders (Blender side). Post-processing / metrics: research/masks_eval.py.

    blender -b --factory-startup <bundle>/scene.blend -P research/masks.py -- <out_dir> [--poses seq|<dataset_dir>] [--band]

For each pose (default: the 10 clockwise frames + reset as frame 10) it writes, all 1024x1024 in the official camera:
  classes_refr/frame_NN.png   occlusion-correct class colours seen THROUGH the corneal Lens mesh (its own material)
  classes_unrefr/frame_NN.png same, Lens meshes hidden (no refraction)
  pupil_unoccluded/frame_NN.png  pupil class only, lids/lashes/brows/hair/skin hidden, Lens on (for visible fraction)
  cornea/frame_NN.png         visible corneal (Lens) region, occluded by everything else
  state_NN.json               the wrapper's state() for the pose (ground truth, unchanged)
Class colours (linear emission): pupil R, iris G, sclera B, skin(eyelid) R+G, lashes R+B, brows/hair/other G+B, bg black.
Eyeball classes follow the scan texture's UV layout: pupil r_uv < 0.034, iris r_uv < 0.112 about UV (0.5008, 0.4943)
(the same constants tools/generate_dataset.py measured from the texture). The pupil class is therefore the
geometric painted-pupil disc, independent of lighting.
Filter width 0.01 px: each pixel's samples are taken at its centre, so labels are not blended across classes.
"""
import json, os, sys
import bpy
a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]; poses_arg = a[a.index("--poses") + 1] if "--poses" in a else "seq"
sys.dont_write_bytecode = True
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402
sc = bpy.context.scene
eyes.use_best_device()
if "--band" in a:
    import speed; speed.apply()

def emission(name, rgb):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial"); e = nt.nodes.new("ShaderNodeEmission")
    e.inputs[0].default_value = (*rgb, 1); nt.links.new(e.outputs[0], o.inputs[0]); return m

def eye_material(pupil_only=False):
    m = bpy.data.materials.new("lbl_eye"); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out_n = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["UV"], sep.inputs[0])
    fx = nt.nodes.new("ShaderNodeMath"); fx.operation = "FRACT"; nt.links.new(sep.outputs[0], fx.inputs[0])
    dx = nt.nodes.new("ShaderNodeMath"); dx.operation = "SUBTRACT"; dx.inputs[1].default_value = 0.5008; nt.links.new(fx.outputs[0], dx.inputs[0])
    dy = nt.nodes.new("ShaderNodeMath"); dy.operation = "SUBTRACT"; dy.inputs[1].default_value = 0.4943; nt.links.new(sep.outputs[1], dy.inputs[0])
    cmb = nt.nodes.new("ShaderNodeCombineXYZ"); nt.links.new(dx.outputs[0], cmb.inputs[0]); nt.links.new(dy.outputs[0], cmb.inputs[1])
    hyp = nt.nodes.new("ShaderNodeVectorMath"); hyp.operation = "LENGTH"; nt.links.new(cmb.outputs[0], hyp.inputs[0])
    p = nt.nodes.new("ShaderNodeMath"); p.operation = "LESS_THAN"; p.inputs[1].default_value = 0.034; nt.links.new(hyp.outputs["Value"], p.inputs[0])
    ir = nt.nodes.new("ShaderNodeMath"); ir.operation = "LESS_THAN"; ir.inputs[1].default_value = 0.112; nt.links.new(hyp.outputs["Value"], ir.inputs[0])
    g = nt.nodes.new("ShaderNodeMath"); g.operation = "SUBTRACT"; nt.links.new(ir.outputs[0], g.inputs[0]); nt.links.new(p.outputs[0], g.inputs[1])
    b = nt.nodes.new("ShaderNodeMath"); b.operation = "SUBTRACT"; b.inputs[0].default_value = 1.0; nt.links.new(ir.outputs[0], b.inputs[1])
    cc = nt.nodes.new("ShaderNodeCombineColor"); nt.links.new(p.outputs[0], cc.inputs[0])
    if not pupil_only:
        nt.links.new(g.outputs[0], cc.inputs[1]); nt.links.new(b.outputs[0], cc.inputs[2])
    nt.links.new(cc.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out_n.inputs[0]); return m

ORIG = {o.name: [s.material for s in o.material_slots] for o in bpy.data.objects if o.type in ("MESH", "CURVES")}
VIS = {o.name: o.hide_render for o in bpy.data.objects}
def set_mat(o, m):
    for s in o.material_slots:
        s.link = "OBJECT"; s.material = m
    if not o.material_slots:
        o.data.materials.append(m)
def restore():
    for o in bpy.data.objects:
        o.hide_render = VIS[o.name]
        for s, m in zip(o.material_slots, ORIG.get(o.name, [])):
            s.link = "OBJECT"; s.material = m

M = dict(skin=emission("lbl_skin", (1, 1, 0)), lash=emission("lbl_lash", (1, 0, 1)), other=emission("lbl_other", (0, 1, 1)),
         black=emission("lbl_black", (0, 0, 0)), white=emission("lbl_white", (1, 1, 1)), eye=eye_material(), eye_pupil=eye_material(True))

def setup(mode):
    restore()
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
        if o.type not in ("MESH", "CURVES"):
            continue
        n = o.name
        if n.startswith("Realtime Eyeball"):
            set_mat(o, M["eye_pupil"] if mode == "pupil_unoccluded" else M["black"] if mode == "cornea" else M["eye"])
        elif n.startswith("Lens"):
            if mode == "classes_unrefr":
                o.hide_render = True
            elif mode == "cornea":
                set_mat(o, M["white"])
            # classes_refr / pupil_unoccluded: keep the Lens and its own (refracting) material
        elif mode == "pupil_unoccluded":
            o.hide_render = True
        elif mode == "cornea":
            set_mat(o, M["black"])
        elif n == "Head":
            set_mat(o, M["skin"])
        elif n == "Lashes":
            set_mat(o, M["lash"])
        else:
            set_mat(o, M["other"])
    sc.cycles.samples = 1 if mode == "cornea" else 16
SPP = {}
sc.world.use_nodes = False; sc.world.color = (0, 0, 0)
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"; sc.view_settings.exposure = 0
sc.cycles.use_denoising = False; sc.cycles.filter_width = 0.01
sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGB"

if poses_arg == "seq":
    poses = [(k, h, v) for k, _, h, v in eyes.sequence_inputs()] + [(10, 0.0, 0.0)]
else:
    man = json.load(open(os.path.join(poses_arg, "manifest.json")))
    poses = [(int(s), json.load(open(os.path.join(poses_arg, e["annotation"])))["input"]["h"], json.load(open(os.path.join(poses_arg, e["annotation"])))["input"]["v"]) for s, e in sorted(man["samples"].items())]
MODES = ("classes_refr", "classes_unrefr", "pupil_unoccluded", "cornea")
for m in MODES:
    os.makedirs(os.path.join(out, m), exist_ok=True)
for k, h, v in poses:
    eyes.move(h, v); st = eyes.state()
    json.dump(st, open(os.path.join(out, f"state_{k:02d}.json"), "w"), indent=1)
    for m in MODES:
        p = os.path.join(out, m, f"frame_{k:02d}.png")
        if os.path.exists(p):
            continue
        setup(m); eyes.move(h, v)
        sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    print("MASKS", k, flush=True)
restore(); eyes.reset()
json.dump(dict(modes=MODES, palette=dict(pupil=[1, 0, 0], iris=[0, 1, 0], sclera=[0, 0, 1], skin=[1, 1, 0], lash=[1, 0, 1], other=[0, 1, 1], bg=[0, 0, 0]),
               uv_pupil_r=0.034, uv_iris_r=0.112, uv_centre=[0.5008, 0.4943], spp=dict(classes=16, cornea=1), filter_width_px=0.01,
               blender=bpy.app.version_string, band="--band" in a), open(os.path.join(out, "masks_info.json"), "w"), indent=1)
print("MASKS_DONE", len(poses), flush=True)
