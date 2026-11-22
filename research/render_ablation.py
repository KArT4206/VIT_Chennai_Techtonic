"""Ablation renders for validation: the 10 clockwise poses with selected scene parts hidden.

    blender -b --factory-startup <bundle>/scene.blend -P research/render_ablation.py -- <out_dir> <mode> [--samples N] [--poses heldout]

--poses heldout renders the 14 held-out gaze inputs (frame_20..33) instead of the 10-frame ring + reset (frame_00..10).

mode  full        : unchanged scene
      no_lids     : skin, lashes, brows, teeth, tongue hidden (removes eyelid occlusion and lid shadows)
      no_lids_lens: as no_lids and the corneal 'Lens' meshes hidden too (no refraction)
      no_lids_lens_nodisp: as no_lids_lens and the eyeball material's displacement removed
      no_lids_lens_flat: as no_lids_lens_nodisp and the eyeball normal map removed
Writes <out_dir>/<mode>/frame_NN.png and state_NN.json (the wrapper's own state() for that pose).
The wrapper (wrapper/eyes.py next to scene.blend) is imported unchanged; nothing is saved to the .blend.
"""
import json, math, os, sys
import bpy
argv = sys.argv[sys.argv.index("--") + 1:]
out, mode = argv[0], argv[1]
samples = int(argv[argv.index("--samples") + 1]) if "--samples" in argv else 64
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402


def heldout_poses():
    """14 gaze inputs never used for fitting: r=0.5 ring at half-step angles (k=0..9) + 4 diagonals (+-0.7, +-0.7).
    Numbered 20..33 so they never collide with the 0..10 fit poses."""
    out = []
    for k in range(10):
        th = 2 * math.pi * k / 10 + math.pi / 10
        out.append((20 + k, th, 0.5 * math.sin(th), 0.5 * math.cos(th)))
    for j, (h, v) in enumerate(((0.7, 0.7), (0.7, -0.7), (-0.7, -0.7), (-0.7, 0.7))):
        out.append((30 + j, None, h, v))
    return out
HIDE = {"full": [], "no_lids": ["Head", "Lashes", "Brows", "Teeth", "Tongue"],
        "no_lids_lens": ["Head", "Lashes", "Brows", "Teeth", "Tongue", "Lens Left", "Lens Right"],
        "no_lids_lens_nodisp": ["Head", "Lashes", "Brows", "Teeth", "Tongue", "Lens Left", "Lens Right"],
        "no_lids_lens_flat": ["Head", "Lashes", "Brows", "Teeth", "Tongue", "Lens Left", "Lens Right"]}[mode]
if mode.endswith("flat"):       # also drop the eyeball normal map (keeps the texture, removes relief shading)
    nt = bpy.data.materials["Realtime Eyeball Left"].node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for l in list(b.inputs["Normal"].links):
        nt.links.remove(l)
    print("NORMAL MAP link removed", flush=True)
if mode.endswith(("nodisp", "flat")):     # as tools/pupil_mask_check.py does: drop the eyeball material's displacement
    nt = bpy.data.materials["Realtime Eyeball Left"].node_tree
    o = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    print("DISPLACEMENT links removed:", [l.from_node.name for l in o.inputs["Displacement"].links],
          "method:", bpy.data.materials["Realtime Eyeball Left"].displacement_method, flush=True)
    for l in list(o.inputs["Displacement"].links):
        nt.links.remove(l)
for n in HIDE:
    bpy.data.objects[n].hide_render = True
eyes.use_best_device(); bpy.context.scene.cycles.samples = samples
d = os.path.join(out, mode); os.makedirs(d, exist_ok=True)
if "--poses" in argv and argv[argv.index("--poses") + 1] == "heldout":
    poses = heldout_poses()
else:
    poses = list(eyes.sequence_inputs()) + [(10, None, 0.0, 0.0)]
for k, _, h, v in poses:
    eyes.move(h, v)
    s = eyes.render(os.path.join(d, f"frame_{k:02d}.png"))
    json.dump(s, open(os.path.join(d, f"state_{k:02d}.json"), "w"), indent=1)
print("ABLATION_DONE", mode, flush=True)
