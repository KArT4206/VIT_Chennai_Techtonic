"""Replace GNM-template control offsets with the scan-calibrated ones (scan_controls.py) in gnm_scan.blend.

    blender -b --factory-startup --disable-autoexec build/gnm_scan.blend --python apply_scan_keys.py -- build/scan_key_offsets.npz
Keys: blink, lid_follow, squint, surprise, brow_raise (L/R) = scan-shaped basis + re-fitted offset. Saves in place.
"""
import sys
import bpy
import numpy as np
off = np.load(sys.argv[sys.argv.index("--") + 1])
key = bpy.data.objects["GNM_Head"].data.shape_keys
basis = np.empty(len(key.key_blocks["Basis"].data) * 3, np.float32); key.key_blocks["Basis"].data.foreach_get("co", basis)
for name in off.files:
    key.key_blocks[name].data.foreach_set("co", basis + off[name].reshape(-1))
    print("KEY", name, "max offset mm", round(float(np.linalg.norm(off[name], axis=1).max()) * 1000, 2))
for kb in key.key_blocks[1:]:
    kb.value = 0.0
bpy.ops.wm.save_mainfile()
print("SAVED")
