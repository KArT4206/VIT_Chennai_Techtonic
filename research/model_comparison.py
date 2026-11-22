"""Stage 3: same-condition comparison of three eye models, computed from the real scene geometry.

    blender -b --factory-startup <bundle>/scene.blend -P research/model_comparison.py -- <out.json>

For each of the 10 clockwise inputs and both eyes, using the scene's calibrated camera:
  A planar   : the pupil slides in the plane facing the camera (no rotation); its displacement is
               scaled so the h=+1 image shift equals the spherical model's (the most favourable fit).
  B sphere   : rigid rotation of the eyeball about its pivot, pupil projected straight (no cornea).
  C anatomic : the project's model = B + refraction through the corneal sphere (entrance pupil),
               which is what wrapper/eyes.py writes to metadata (pupil_center_2D).
Reports per-model image positions and the differences A-C, B-C (px), plus pupil foreshortening
(projected pupil aspect ratio: a disc that rotates is seen as an ellipse; planar sliding never is).
"""
import json, math, sys
import bpy
from mathutils import Vector
out = sys.argv[sys.argv.index("--") + 1:][0]
sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper"))
import eyes  # noqa: E402

eyes.reset()
rows = []
proj = eyes._project
cam = bpy.context.scene.camera.matrix_world.translation
gain = {}
for side in "LR":
    c = eyes._eye_centre(side)
    p0 = eyes._pupil_world(side)
    eyes.move(1, 0); p1 = eyes._pupil_world(side); eyes.reset()
    gain[side] = (Vector(proj(p1)) - Vector(proj(p0))).x       # px per unit h, fitted for model A
for k, th, h, v in eyes.sequence_inputs():
    eyes.move(h, v)
    st = eyes.state()
    for side in "LR":
        eyes.reset(); p0 = eyes._pupil_world(side); u0 = Vector(proj(p0)); eyes.move(h, v)
        A = [u0.x + gain[side] * h, u0.y - gain[side] * v]
        B = proj(eyes._pupil_world(side))
        C = st[f"pupil_center_2D_{side}"]
        # foreshortening: project a small pupil disc (r = 1.5 mm) in the iris plane
        axis = (eyes._iris(side).matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        e1 = axis.orthogonal().normalized(); e2 = axis.cross(e1); P = eyes._pupil_world(side)
        pts = [Vector(proj(P + 0.0015 * (math.cos(a) * e1 + math.sin(a) * e2))) for a in [i * math.pi / 36 for i in range(72)]]
        cen = sum(pts, Vector((0, 0))) / len(pts)
        import numpy as np
        M = np.array([[q.x - cen.x, q.y - cen.y] for q in pts]); ev = np.linalg.eigvalsh(M.T @ M)
        aspect = float(math.sqrt(ev[0] / ev[1]))
        tilt = math.degrees(axis.angle((cam - P).normalized()))
        rows.append(dict(frame=k, side=side, h=round(h, 4), v=round(v, 4), planar=[round(x, 3) for x in A], sphere=[round(x, 3) for x in B],
                         anatomic=C, planar_minus_anatomic_px=round(math.dist(A, C), 3), sphere_minus_anatomic_px=round(math.dist(B, C), 3),
                         pupil_aspect_anatomic=round(aspect, 4), pupil_aspect_planar=1.0, iris_tilt_to_camera_deg=round(tilt, 3)))
eyes.reset()
# extended sweep beyond the spec's +-5 cm (~8 deg): horizontal gaze angle 0..35 deg, left eye, math only
ext = []
side = "L"; c = eyes._eye_centre(side); mid = eyes._state["midpoint"]
p0 = eyes._pupil_world(side); u0 = Vector(proj(p0)); px_per_deg = None
for deg in range(0, 36, 5):
    tgt = mid + Vector((0.35 * math.tan(math.radians(deg)), -0.35, 0))
    q = eyes._world_rotation(side, tgt)
    P = c + q @ (eyes._state[f"axis_{side}"] * eyes._state[f"pupil_depth_{side}"])
    B = Vector(proj(P)); C = Vector(eyes.apparent_pupil(side, P)[0])
    if deg == 5:
        px_per_deg = (C.x - u0.x) / 5
    A = Vector((u0.x + (px_per_deg or 0) * deg, u0.y))
    ext.append(dict(gaze_deg=deg, planar_x=round(A.x, 2), sphere_x=round(B.x, 2), anatomic=[round(C.x, 2), round(C.y, 2)],
                    planar_minus_anatomic_px=round((A - C).length, 2), sphere_minus_anatomic_px=round((B - C).length, 2)))
import statistics as S
summ = {m: dict(mean=round(S.mean(r[m] for r in rows), 3), max=round(max(r[m] for r in rows), 3))
        for m in ("planar_minus_anatomic_px", "sphere_minus_anatomic_px")}
summ["pupil_aspect_range"] = [min(r["pupil_aspect_anatomic"] for r in rows), max(r["pupil_aspect_anatomic"] for r in rows)]
summ["planar_gain_px_per_unit_h"] = {k: round(v, 3) for k, v in gain.items()}
json.dump(dict(summary=summ, rows=rows, extended_sweep_left_eye=ext), open(out, "w"), indent=1)
print("COMPARISON", json.dumps(summ), flush=True); print("EXT", json.dumps(ext), flush=True)
