"""Add combination-corrective shape keys and the brow-lowerer cap.

    blender -b --factory-startup gnm_wrinkles.blend --python add_correctives.py -- corrective_keys.npz OUT_BLEND

corr_blink_raise_L/R    = 0.02 x blink offset (solve_correctives C1: closes the blink under a 3 mm brow raise)
                          driven by blink * min(brow_raise / 1.5, 1)
corr_blink_lowerer_L/R  = eye-block corrective fitted on GNM (fit_corrective.py, lambda 1e-6): pushes the
                          14-16 lid vertices that press into the eye back to 0.05 mm clearance
                          driven by blink * min(brow_furrow / 0.67, 1)
brow_furrow slider max 0.67 (= 1.0 x semantic DISGUST eye blocks): above that the lowerer alone presses
the lid into the eye beyond GNM's own 0.31 mm (measured 0.39 mm at x1.25, 0.48 mm at x1.5).
"""

import os
import sys

import bpy
import numpy as np

npz, out_blend = sys.argv[sys.argv.index("--") + 1:]
c = np.load(npz)
ob = bpy.data.objects["GNM_Head"]; key = ob.data.shape_keys
basis = np.empty(len(ob.data.vertices) * 3, np.float32); key.key_blocks["Basis"].data.foreach_get("co", basis)
for s in "LR":
    key.key_blocks[f"brow_furrow_{s}"].slider_max = 0.67
for name, expr in (("corr_blink_raise", "b * min(r / 1.5, 1.0)"), ("corr_blink_lowerer", "b * min(f / 0.67, 1.0)")):
    for s in "LR":
        kb = key.key_blocks.get(f"{name}_{s}") or ob.shape_key_add(name=f"{name}_{s}", from_mix=False)
        kb.data.foreach_set("co", basis + c[f"{name}_{s}"].reshape(-1))
        kb.slider_min, kb.slider_max = 0.0, 1.0
        fc = kb.driver_add("value"); d = fc.driver; d.type = "SCRIPTED"
        for vn, src in (("b", f"blink_{s}"), ("r", f"brow_raise_{s}"), ("f", f"brow_furrow_{s}")):
            v = d.variables.new(); v.name = vn; v.type = "SINGLE_PROP"
            v.targets[0].id_type = "KEY"; v.targets[0].id = key; v.targets[0].data_path = f'key_blocks["{src}"].value'
        d.expression = expr
        print("CORRECTIVE", kb.name, "=", expr)
# saved rest state: every expression key at 0 (the furrow keys had been left at their maximum)
for kb in key.key_blocks[1:]:
    if not kb.name.startswith("corr_"):
        kb.value = 0.0
bpy.context.view_layer.update()
print("REST_STATE", {kb.name: round(kb.value, 3) for kb in key.key_blocks[1:] if abs(kb.value) > 1e-6})
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out_blend), compress=True)
print("SAVED", out_blend)
