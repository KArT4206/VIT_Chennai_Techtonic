"""Ground-truth accuracy check that does not depend on lighting: renders the painted pupil as a pure emission
mask (everything else hidden, no lights, no eyelids in the way) at the 10 sequence poses and reset, and compares
the mask centroid with the wrapper's pupil_center_2D.

    blender -b scene.blend --factory-startup -P tools/pupil_mask_check.py -- <out_prefix>
    python3 tools/pupil_mask_check.py --score <out_prefix>          (needs numpy and pillow)

Written for the scan-head scene (eyeball material 'Realtime Eyeball Left', pupil = texels darker than 0.05).
The bundle's wrapper/eyes.py is imported from the folder that contains scene.blend; nothing is saved.
"""
import json
import math
import sys


def render(out):
    import bpy
    sys.path.append(bpy.path.abspath("//wrapper"))
    import eyes
    sc = bpy.context.scene
    sc.cycles.samples = 8
    sc.view_settings.view_transform = "Standard"; sc.view_settings.exposure = 0
    t = bpy.data.materials["Realtime Eyeball Left"].node_tree
    img = next(n for n in t.nodes if n.type == "TEX_IMAGE" and "Diffuse" in n.image.name)
    out_node = next(n for n in t.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    bw = t.nodes.new("ShaderNodeRGBToBW"); lt = t.nodes.new("ShaderNodeMath"); lt.operation = "LESS_THAN"; lt.inputs[1].default_value = 0.05
    em = t.nodes.new("ShaderNodeEmission")
    t.links.new(img.outputs[0], bw.inputs[0]); t.links.new(bw.outputs[0], lt.inputs[0]); t.links.new(lt.outputs[0], em.inputs[1])
    t.links.new(em.outputs[0], out_node.inputs["Surface"])
    for link in list(out_node.inputs["Displacement"].links):
        t.links.remove(link)
    for ob in bpy.data.objects:
        if ob.type in ("MESH", "LIGHT", "CURVES") and not ob.name.startswith("Realtime Eyeball"):
            ob.hide_render = True
    sc.world.use_nodes = False; sc.world.color = (0, 0, 0)
    res = {}
    for k in range(10):
        th = 2 * math.pi * k / 10
        eyes.move(math.sin(th), math.cos(th))
        st = eyes.render(f"{out}_{k}.png")
        res[str(k)] = {s: st[f"pupil_center_2D_{s}"] for s in "LR"}
    eyes.reset()
    st = eyes.render(f"{out}_reset.png")
    res["reset"] = {s: st[f"pupil_center_2D_{s}"] for s in "LR"}
    json.dump(res, open(out + ".json", "w"), indent=1)


def score(out):
    import numpy as np
    from PIL import Image
    meta = json.load(open(out + ".json"))
    errs = []
    for k, d in meta.items():
        a = np.asarray(Image.open(f"{out}_{k}.png").convert("L")).astype(float)
        for s in "LR":
            g = np.array(d[s])
            x0, y0 = int(g[0]) - 50, int(g[1]) - 50
            ys, xs = np.nonzero(a[y0:y0 + 100, x0:x0 + 100] > 128)
            c = np.array([x0 + xs.mean(), y0 + ys.mean()])
            e = float(np.linalg.norm(c - g)); errs.append(e)
            print(f"pose {k:>5} {s}: metadata ({g[0]:.2f}, {g[1]:.2f})  mask ({c[0]:.2f}, {c[1]:.2f})  error {e:.2f} px")
    print(f"\nPUPIL MASK: {len(errs)} pupils, mean error {np.mean(errs):.2f} px, max {max(errs):.2f} px")
    return max(errs)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    if args and args[0] == "--score":
        sys.exit(0 if score(args[1]) < 1.0 else 1)
    render(args[0])
