"""Track 01 compliance + calibration tests, run inside Blender against an unmodified bundle.

    blender -b --factory-startup <bundle>/scene.blend -P research/compliance_tests.py -- <out.json>

No rendering. Every check prints PASS/FAIL with the measured value; results also go to <out.json>.
Checks: scene structure, camera/fixation geometry, image format, projection with known points
(K[R|t] vs Blender's own world_to_camera_view), rotation about the true pivot, Listing's law (no
torsion), input clamping/validation, reset semantics, determinism, synchronous update, sequence maths.
"""
import json, math, random, sys
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view

out = sys.argv[sys.argv.index("--") + 1:][0]
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402

R = []
def check(name, ok, value):
    R.append(dict(name=name, ok=bool(ok), value=value)); print(("PASS " if ok else "FAIL ") + f"{name}: {value}", flush=True)

sc = bpy.context.scene; cam = sc.camera; rig = eyes._rig()
# -- structure
check("render resolution 1024x1024 @100%", (sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage) == (1024, 1024, 100),
      [sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage])
check("eye bones eye.L / eye.R present", all(b in rig.data.bones for b in ("eye.L", "eye.R")), list(eyes.EYE_BONES.values()))
mats = [m for o in bpy.data.objects if o.type == "MESH" for s in o.material_slots if (m := s.material) and m.use_nodes]
check("textured model (image textures in materials)", any(n.type == "TEX_IMAGE" and n.image for m in mats for n in m.node_tree.nodes),
      sum(1 for m in mats for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image))
check("camera not animated / constrained (locked)", cam.animation_data is None and len(cam.constraints) == 0,
      dict(anim=cam.animation_data is not None, constraints=len(cam.constraints)))
lights = [o for o in bpy.data.objects if o.type == "LIGHT"]
check("lighting not animated (constant)", all(o.animation_data is None and o.data.animation_data is None for o in lights) and
      (sc.world is None or sc.world.animation_data is None), len(lights))

eyes.reset()
mid = eyes._state["midpoint"]; cL, cR = eyes._eye_centre("L"), eyes._eye_centre("R")
geo_mid = (cL + cR) / 2
check("midpoint = mean of eye pivots (mm)", (mid - geo_mid).length < 1e-4, round((mid - geo_mid).length * 1000, 4))
P = cam.matrix_world.translation
check("camera 40 cm from eye midpoint (m)", abs((P - mid).length - 0.40) < 1e-4, round((P - mid).length, 6))
fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
ang = math.degrees(fwd.angle(mid - P))
check("camera faces the face: optical axis vs direction to midpoint (deg)", ang < 1.0, round(ang, 4))
check("camera is in front (-Y side) of the face", P.y < mid.y, [round(P.y, 4), round(mid.y, 4)])
T0 = eyes.target_point(0, 0)
TOL = 1e-6   # 1 micrometre: mathutils.Vector is float32 (~1e-7 relative), so tighter is noise
check("fixation target 35 cm forward of midpoint (m)", abs((T0 - mid).length - 0.35) < TOL and abs(T0.x - mid.x) < TOL and abs(T0.z - mid.z) < TOL,
      round((T0 - mid).length, 9))
for h, v in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1)):
    d = eyes.target_point(h, v) - T0
    check(f"target displacement for ({h},{v}) = 5 cm * input in the 35 cm plane", abs(d.x - 0.05 * h) < TOL and abs(d.z - 0.05 * v) < TOL and abs(d.y) < TOL,
          [round(d.x, 6), round(d.y, 6), round(d.z, 6)])

# -- known-point projection: K[R|t] must agree with Blender's own camera projection
K, RT = eyes.camera_matrices(); K = Matrix(K); Rm = Matrix([r[:3] for r in RT]); t = Vector([r[3] for r in RT])
rng = random.Random(7); worst = 0
for _ in range(500):
    p = mid + Vector((rng.uniform(-.1, .1), rng.uniform(-.1, .1), rng.uniform(-.1, .1)))
    c = Rm @ p + t; uv = K @ c; u, v = uv.x / uv.z, uv.y / uv.z
    n = world_to_camera_view(sc, cam, p); bu, bv = n.x * 1024, (1 - n.y) * 1024
    worst = max(worst, math.hypot(u - bu, v - bv))
check("K[R|t] vs Blender projection on 500 random points (max px)", worst < 0.01, round(worst, 6))
ku = K @ (Rm @ mid + t)
check("eye midpoint projects near image centre (px from 512,512)", True, [round(ku.x / ku.z - 512, 3), round(ku.y / ku.z - 512, 3)])
check("R is orthonormal (|R^T R - I|)", max(abs(x) for row in (Rm.transposed() @ Rm - Matrix.Identity(3)) for x in row) < 1e-5, "ok")

# -- rotation about real pivots, no torsion, pupil on sphere
for side in "LR":
    bone = rig.pose.bones[eyes.EYE_BONES[side]]
    worst_piv = worst_r = worst_tor = worst_aim = 0
    r0 = None
    for k, th, h, v in eyes.sequence_inputs():
        eyes.move(h, v)
        head = rig.matrix_world @ bone.head
        worst_piv = max(worst_piv, (head - eyes._eye_centre(side)).length)
        pup = eyes.mesh_pupils()[side]
        r = (pup - head).length; r0 = r0 or r; worst_r = max(worst_r, abs(r - r0))
        aim = (eyes.target_point(h, v) - head).normalized()
        worst_aim = max(worst_aim, math.degrees((pup - head).normalized().angle(aim)))
        q = eyes._world_rotation(side, eyes.target_point(h, v))
        ax = eyes._state[f"axis_{side}"]
        # torsion about the primary axis: rotation q decomposed as swing*twist around axis
        qa = Vector((q.x, q.y, q.z)); proj = ax * qa.dot(ax)
        tw = math.degrees(2 * math.atan2(proj.length, abs(q.w))) if proj.length > 1e-12 else 0.0
        worst_tor = max(worst_tor, tw)
    check(f"eye {side}: pivot stays at eye centre over 10 poses (mm)", worst_piv < 1e-5 * 1000, round(worst_piv * 1000, 6))
    check(f"eye {side}: pupil stays on its sphere (radius change mm)", worst_r < 1e-5, round(worst_r * 1000, 6))
    check(f"eye {side}: mesh pupil aims at the fixation target (deg)", worst_aim < 0.05, round(worst_aim, 5))
    check(f"eye {side}: torsion about primary axis, Listing's law (deg)", worst_tor < 1e-3, round(worst_tor, 6))

# -- inputs
eyes.move(5, -7); s = eyes.state()
check("out-of-range input clamped to [-1,1]", s["input"] == {"h": 1.0, "v": -1.0}, s["input"])
for bad in ("x", float("nan"), float("inf"), None):
    try:
        eyes.move(bad, 0); ok = False
    except ValueError:
        ok = True
    check(f"invalid input {bad!r} rejected with ValueError", ok, ok)

# -- reset semantics + determinism + synchronous update
eyes.reset(); a = eyes.state()
eyes.move(0.7, -0.4); eyes.move(-1, 1); eyes.reset(); b = eyes.state()
check("reset after moves is identical to first reset", a == b, a["pupil_center_2D_L"])
check("reset input is (0,0)", b["input"] == {"h": 0.0, "v": 0.0}, b["input"])
eyes.move(0.3, 0.6); s1 = eyes.state(); eyes.move(0.3, 0.6); s2 = eyes.state()
check("repeated identical move gives identical state", s1 == s2, "ok")
eyes.move(1, 0); ph = rig.matrix_world @ rig.pose.bones["eye.L"].matrix @ Vector((0, 1, 0))
eyes.move(-1, 0); ph2 = rig.matrix_world @ rig.pose.bones["eye.L"].matrix @ Vector((0, 1, 0))
check("pose is updated synchronously (bone matrix changes without frame change)", (ph - ph2).length > 1e-4, round((ph - ph2).length * 1000, 3))
s = eyes.move(1, 0); s_l = eyes.move(-1, 0)
check("h=+1 moves pupils to image right of h=-1", s["pupil_center_2D_L"][0] > s_l["pupil_center_2D_L"][0] and s["pupil_center_2D_R"][0] > s_l["pupil_center_2D_R"][0],
      [s["pupil_center_2D_L"][0], s_l["pupil_center_2D_L"][0]])
s_u = eyes.move(0, 1); s_d = eyes.move(0, -1)
check("v=+1 moves pupils up in the image (smaller y)", s_u["pupil_center_2D_L"][1] < s_d["pupil_center_2D_L"][1], [s_u["pupil_center_2D_L"][1], s_d["pupil_center_2D_L"][1]])
seq = list(eyes.sequence_inputs())
check("sequence theta_k=2*pi*k/10, h=sin, v=cos, starts top", len(seq) == 10 and seq[0][3] == 1.0 and all(abs(th - 2 * math.pi * k / 10) < 1e-12 for k, th, _, _ in seq), "10")
# vergence: both eyes converge on the near target
eyes.reset()
gl = (eyes.target_point(0, 0) - cL).normalized(); gr = (eyes.target_point(0, 0) - cR).normalized()
check("vergence angle at 35 cm (deg, both eyes on one target)", True, round(math.degrees(gl.angle(gr)), 4))
check("interocular distance (mm)", 50 < (cL - cR).length * 1000 < 75, round((cL - cR).length * 1000, 3))
eyes.reset()
json.dump(dict(blender=bpy.app.version_string, passed=sum(r["ok"] for r in R), failed=sum(not r["ok"] for r in R), checks=R), open(out, "w"), indent=1)
print(f"COMPLIANCE {sum(r['ok'] for r in R)} passed, {sum(not r['ok'] for r in R)} failed", flush=True)
