"""Phase 2G: exercise the packaged wrapper API from inside the extracted bundle's scene.blend.

    blender -b --factory-startup <bundle>/scene.blend -P phase2g_api_test.py -- <bundle> <out_dir>
Also inventories every datablock that could carry an asset (images, fonts, sounds, libraries,
external file paths) for the licence audit.
"""
import json
import os
import sys

import bpy

bundle, out = sys.argv[sys.argv.index("--") + 1:][:2]
os.makedirs(out, exist_ok=True)
sys.path.insert(0, os.path.join(bundle, "wrapper"))
import eyes  # noqa: E402

res = []


def check(ok, msg):
    res.append(bool(ok)); print(("PASS " if ok else "FAIL ") + msg, flush=True)


sc = bpy.context.scene
cam = sc.camera
cam0 = [list(r) for r in cam.matrix_world]; lens0 = cam.data.lens
lights0 = {o.name: ([list(r) for r in o.matrix_world], o.data.energy) for o in bpy.data.objects if o.type == "LIGHT"}
world0 = sc.world.name if sc.world else None
check(sc.render.resolution_x == 1024 and sc.render.resolution_y == 1024 and sc.render.resolution_percentage == 100, "render settings 1024x1024 at 100%")

eyes.use_best_device()
sc.cycles.samples = 64
for name, call in (("move_left", lambda: eyes.move(-1, 0)), ("move_right", lambda: eyes.move(1, 0)), ("move_up", lambda: eyes.move(0, 1)),
                   ("move_down", lambda: eyes.move(0, -1)), ("reset", eyes.reset), ("move_diag", lambda: eyes.move(0.5, -0.3))):
    call()
    s = eyes.render(os.path.join(out, name + ".png"))
    img = bpy.data.images.load(os.path.join(out, name + ".png")); w, h = img.size; bpy.data.images.remove(img)
    keys = {"input", "eye_rotation_L", "eye_rotation_R", "pupil_center_2D_L", "pupil_center_2D_R"}
    check(w == 1024 and h == 1024 and keys <= set(s), f"{name}: render() wrote 1024x1024 PNG and returned {sorted(keys & set(s))}")
    json.dump(s, open(os.path.join(out, name + ".json"), "w"), indent=1)
L = {n: json.load(open(os.path.join(out, n + ".json"))) for n in ("move_left", "move_right", "move_up", "move_down", "reset")}
for side in ("L", "R"):
    k = f"pupil_center_2D_{side}"
    c = L["reset"][k]
    check(L["move_left"][k][0] < c[0] - 3 and L["move_right"][k][0] > c[0] + 3, f"{side}: h=-1 moves the pupil image-left, h=+1 image-right ({L['move_left'][k][0]:.1f} < {c[0]:.1f} < {L['move_right'][k][0]:.1f})")
    check(L["move_up"][k][1] < c[1] - 3 and L["move_down"][k][1] > c[1] + 3, f"{side}: v=+1 moves the pupil up, v=-1 down (image y {L['move_up'][k][1]:.1f} < {c[1]:.1f} < {L['move_down'][k][1]:.1f})")
check(L["reset"]["input"] in ({"h": 0.0, "v": 0.0}, [0.0, 0.0]) or L["reset"]["input"].get("h", 1) == 0, f"reset input is zero: {L['reset']['input']}")
# determinism: same input twice -> same state
eyes.move(0.5, -0.3); a = eyes.state(); eyes.reset(); eyes.move(0.5, -0.3); b = eyes.state()
check(json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True), "move(0.5,-0.3) is deterministic (identical state twice)")
try:
    eyes.move("x", 0); bad = False
except Exception:  # noqa: BLE001
    bad = True
check(bad, "non-numeric input rejected")
eyes.move(5, -5); s = eyes.state()
check(abs(s["input"]["h"]) <= 1 and abs(s["input"]["v"]) <= 1, f"inputs clamped to [-1, 1]: {s['input']}")
eyes.reset()
cam1 = [list(r) for r in cam.matrix_world]
check(cam1 == cam0 and cam.data.lens == lens0, "camera unchanged by move/reset/render")
lights1 = {o.name: ([list(r) for r in o.matrix_world], o.data.energy) for o in bpy.data.objects if o.type == "LIGHT"}
check(lights1 == lights0 and (sc.world.name if sc.world else None) == world0, f"lights ({len(lights0)}) and world unchanged")
mid = eyes._state["midpoint"]; dist = (cam.matrix_world.translation - mid).length
check(abs(dist - 0.40) < 0.002, f"camera {dist * 100:.2f} cm from the eye midpoint (40 cm)")

# asset inventory
inv = {"images": [], "libraries": [l.filepath for l in bpy.data.libraries], "fonts": [f.filepath for f in bpy.data.fonts],
       "sounds": [s.filepath for s in bpy.data.sounds], "movieclips": [m.filepath for m in bpy.data.movieclips]}
for im in bpy.data.images:
    inv["images"].append(dict(name=im.name, filepath=im.filepath, packed=im.packed_file is not None, source=im.source,
                              size=list(im.size), users=im.users))
ext = [i for i in inv["images"] if i["source"] == "FILE" and not i["packed"] and i["users"] > 0]
check(not ext and not inv["libraries"], f"no external image files or linked libraries ({len(inv['images'])} images, all packed or generated)")
inv["objects"] = sorted(o.name for o in bpy.data.objects)
inv["materials"] = sorted(m.name for m in bpy.data.materials)
inv["text_blocks"] = sorted(t.name for t in bpy.data.texts)
inv["custom_props_scene"] = {k: str(v)[:200] for k, v in sc.items()}
json.dump(inv, open(os.path.join(out, "asset_inventory.json"), "w"), indent=1)
print(f"\n{sum(res)}/{len(res)} PASSED" + ("" if all(res) else "  <-- FAILURES"))
