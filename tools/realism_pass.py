"""Cinematic realism pass for the scan-head Track 1 scene (lighting, skin, grade). Geometry and rig untouched.

    blender -b scene.blend --factory-startup -P tools/realism_pass.py -- <scan_original.blend> <out.blend>

Environment knobs (defaults are the chosen look):
  KEY_SIZE (1.4 m)  KEY_GAIN (1.0)  FILL_GAIN (1.0)  RIM_GAIN (0.8)
  HDRI_STRENGTH (0.35)  SPEC_GAIN (0.6)  ROUGH_ADD (0.08)  LOOK ("AgX - Base Contrast")  EXPOSURE (-0.6)
Changes:
  * key light enlarged to a soft box (KEY_SIZE), so the hard shadow down the nose softens into a natural falloff;
  * the vendor's own studio HDRI (HDRI.exr, from the vendor scene) lights the world at low strength, giving
    natural ambient fill and realistic reflections in skin and eyes; the camera still sees the plain backdrop;
  * skin specular scaled by SPEC_GAIN and roughness raised by ROUGH_ADD (tames the vendor's shiny cheek streaks);
  * filmic AgX look and exposure. Everything is constant across frames (the brief's constant lighting).
"""
import os
import sys

import bpy

src, out = sys.argv[sys.argv.index("--") + 1:][:2]
E = lambda k, d: float(os.environ.get(k, d))
sc = bpy.context.scene

# ---- lights ----
L = {o.name: o for o in bpy.data.objects if o.type == "LIGHT"}
if "KeyLight" in L:
    k = L["KeyLight"].data
    old = k.size; k.size = E("KEY_SIZE", 1.4)
    if hasattr(k, "size_y"): k.size_y = k.size
    k.energy *= E("KEY_GAIN", 1.0) * (k.size / old) ** 0.5   # keep exposure similar as the box grows
if "FillLight" in L:
    L["FillLight"].data.energy *= E("FILL_GAIN", 1.0)
if "RimLight" in L:
    L["RimLight"].data.energy *= E("RIM_GAIN", 0.8)

# ---- world: vendor studio HDRI for ambient + reflections, plain backdrop to camera ----
with bpy.data.libraries.load(src, link=False) as (df, dt):
    dt.images = [n for n in df.images if n == "HDRI.exr"]
hdri = dt.images[0] if dt.images else None
w = sc.world; nt = w.node_tree
bgs = [n for n in nt.nodes if n.type == "BACKGROUND"]
lp = next((n for n in nt.nodes if n.type == "LIGHT_PATH"), None)
if hdri is not None and lp is not None and len(bgs) >= 2:
    # the scene's world is Mix(LightPath.IsCameraRay): one background for camera rays (keep), one for lighting
    mix = next(n for n in nt.nodes if n.type == "MIX_SHADER")
    light_bg = next(b for b in bgs if any(l.to_node == mix and l.to_socket == mix.inputs[1] for l in b.outputs[0].links)) if any(
        l.to_socket == mix.inputs[1] for b in bgs for l in b.outputs[0].links) else bgs[0]
    env = nt.nodes.new("ShaderNodeTexEnvironment"); env.image = hdri; hdri.pack()
    nt.links.new(env.outputs[0], light_bg.inputs[0]); light_bg.inputs[1].default_value = E("HDRI_STRENGTH", 0.35)
    print("HDRI on world lighting background:", light_bg.name)
else:
    print("HDRI not applied (world layout differs)")

# ---- skin ----
m = bpy.data.materials.get("Material.001")
if m:
    t = m.node_tree; p = next(n for n in t.nodes if n.type == "BSDF_PRINCIPLED")
    def scale(name, f=None, add=None):
        s = p.inputs[name]
        node = t.nodes.new("ShaderNodeMath"); node.operation = "MULTIPLY_ADD"
        node.inputs[1].default_value = f if f is not None else 1.0; node.inputs[2].default_value = add if add is not None else 0.0
        if s.is_linked:
            t.links.new(s.links[0].from_socket, node.inputs[0])
        else:
            node.inputs[0].default_value = s.default_value
        t.links.new(node.outputs[0], s)
    scale("Specular IOR Level", f=E("SPEC_GAIN", 0.6))
    scale("Roughness", add=E("ROUGH_ADD", 0.08))

# ---- grade ----
try:
    sc.view_settings.look = os.environ.get("LOOK", "AgX - Base Contrast")
except TypeError as e:
    print("look not set:", e)
sc.view_settings.exposure = E("EXPOSURE", -0.6)
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("REALISM_SAVED", out)
