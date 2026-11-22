"""Bias probe: separate detector bias, shading and ground-truth definition (Stage 2 follow-up).

    blender -b --factory-startup <bundle>/scene.blend -P research/render_bias_probe.py -- <out_dir> [--samples 16]

Renders the 11 poses (10 sequence + reset) in two unlit conditions, lids/lashes/brows/skin and the corneal
'Lens' meshes hidden (same geometry as ablation 'no_lids_lens'):
  albedo/frame_NN.png : eyeball shows its diffuse texture as emission (no lighting, no shading, no highlights)
  mask/frame_NN.png   : eyeball emits white where the texture is darker than 0.05 (the painted pupil),
                        i.e. the same definition tools/pupil_mask_check.py validates the metadata against
and state_NN.json (the wrapper's state() for that pose). The wrapper is imported unchanged; nothing is saved.
"""
import json, os, sys
import bpy
a = sys.argv[sys.argv.index("--") + 1:]
out = a[0]; samples = int(a[a.index("--samples") + 1]) if "--samples" in a else 16
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402
sc = bpy.context.scene
eyes.use_best_device(); sc.cycles.samples = samples
sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"; sc.view_settings.exposure = 0; sc.view_settings.gamma = 1
for ob in bpy.data.objects:
    if ob.type in ("MESH", "LIGHT", "CURVES") and not ob.name.startswith("Realtime Eyeball"):
        ob.hide_render = True
sc.world.use_nodes = False; sc.world.color = (0, 0, 0)
t = bpy.data.materials["Realtime Eyeball Left"].node_tree
img = next(n for n in t.nodes if n.type == "TEX_IMAGE" and n.image and "Diffuse" in n.image.name)
outn = next(n for n in t.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
for l in list(outn.inputs["Displacement"].links):
    t.links.remove(l)
em = t.nodes.new("ShaderNodeEmission")
bw = t.nodes.new("ShaderNodeRGBToBW"); lt = t.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.05
t.links.new(img.outputs[0], bw.inputs[0]); t.links.new(bw.outputs[0], lt.inputs[0])
t.links.new(em.outputs[0], outn.inputs["Surface"])
poses = list(eyes.sequence_inputs()) + [(10, None, 0.0, 0.0)]
for mode in ("albedo", "mask"):
    for l in list(em.inputs["Color"].links) + list(em.inputs["Strength"].links):
        t.links.remove(l)
    if mode == "albedo":
        t.links.new(img.outputs[0], em.inputs["Color"]); em.inputs["Strength"].default_value = 1.0
    else:
        em.inputs["Color"].default_value = (1, 1, 1, 1); t.links.new(lt.outputs[0], em.inputs["Strength"])
    d = os.path.join(out, mode); os.makedirs(d, exist_ok=True)
    for k, _, h, v in poses:
        eyes.move(h, v)
        s = eyes.render(os.path.join(d, f"frame_{k:02d}.png"))
        json.dump(s, open(os.path.join(d, f"state_{k:02d}.json"), "w"), indent=1)
print("PROBE_DONE", flush=True)
