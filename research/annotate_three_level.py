"""Three-level pupil annotation for research use (pure Python). Never modifies the official metadata.json.

    python3 research/annotate_three_level.py <bundle_dir> <depth_ext.json> <roi_reset.png> <out.json>

For each released frame (frame k = probe pose k) and each eye it writes three separately labelled levels:

  A  anatomical (ground truth, geometry)
     A.pupil_3D_world_m           anatomical pupil centre, rotated about the eye pivot   (metadata pupil_center_3D_*)
     A.projected_2D_px            straight pinhole projection of A.pupil_3D              (metadata pupil_center_2D_unrefracted_*)
     A.apparent_2D_analytic_px    the wrapper's primary GT: A seen through an ANALYTIC corneal sphere (metadata pupil_center_2D_*)
  B  rendered apparent (ground truth, geometry of the asset that is actually rendered)
     B.painted_pupil_2D_px        projection of the eyeball-mesh surface point under the texture's painted-pupil UV
                                  centroid (research/depth_probe_extended.py). The scene's 'Lens' material is
                                  Transparent+Glossy (no refraction), so the straight projection is what the render shows.
  C  detected (PREDICTION, not ground truth)
     C.detected_2D_px, confidence, status, radius_px   from research/pupil_detector.py on the RGB image only.

Pixel convention for every 2D value: origin at the image's top-left corner, x right, y down, pixel (i, j) centred
at (i + 0.5, j + 0.5); 1024 x 1024. World: Blender metres, +Z up, face looks along -Y.
"""
import hashlib, json, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pupil_detector as P

b, probe_p, roi_png, out = sys.argv[1:5]
meta = json.load(open(os.path.join(b, "metadata.json"))); R = json.load(open(probe_p))
ref = P.detect(Image.open(roi_png).convert("RGB"))
ROI = [(int(d["centre"][0]) - 90, int(d["centre"][1]) - 90, int(d["centre"][0]) + 90, int(d["centre"][1]) + 90) for d in ref]
det_sha = hashlib.sha256(open(P.__file__, "rb").read()).hexdigest()
frames = []
for f in meta["frames"]:
    k = f"{f['frame']:02d}"; dets = P.detect(Image.open(os.path.join(b, f["file"])).convert("RGB"), roi=ROI); rec = dict(frame=f["frame"], file=f["file"], input=f["input"])
    for s in "LR":
        g = f[f"pupil_center_2D_{s}"]; m = min(dets, key=lambda d: abs(d["centre"][0] - g[0])) if dets else None
        bp = R["poses"][k][s]["painted_surface_2D"]
        rec[s] = dict(
            A=dict(level="anatomical ground truth", pupil_3D_world_m=f[f"pupil_center_3D_{s}"], projected_2D_px=f[f"pupil_center_2D_unrefracted_{s}"],
                   apparent_2D_analytic_px=g),
            B=dict(level="rendered-asset ground truth", painted_pupil_2D_px=[round(x, 3) for x in bp]),
            C=dict(level="prediction (not ground truth)", detected_2D_px=[round(x, 3) for x in m["centre"]] if m else None,
                   confidence=m.get("confidence") if m else None, status=m["status"] if m else "none", radius_px=round(m["radius"], 3) if m else None))
        assert abs(R["poses"][k]["input"][0] - f["input"]["h"]) < 1e-5 and abs(R["poses"][k]["input"][1] - f["input"]["v"]) < 1e-5
    frames.append(rec)
doc = dict(schema="techtonic.research.pupil_levels/1.0", source_metadata_sha256=hashlib.sha256(open(os.path.join(b, "metadata.json"), "rb").read()).hexdigest(),
           detector_sha256=det_sha, probe=os.path.basename(probe_p),
           conventions=dict(pixels="origin top-left corner; x right, y down; pixel (i,j) centre at (i+0.5, j+0.5); 1024x1024",
                            world="Blender metres, +Z up, face looks along -Y",
                            levels=dict(A="anatomical pupil (wrapper geometry): 3D, straight projection, and analytic-cornea apparent point",
                                        B="painted pupil of the rendered asset (mesh + texture, no fitted parameter); the Lens mesh does not refract",
                                        C="image-only detector output; a prediction with confidence, never used as ground truth")),
           frames=frames)
json.dump(doc, open(out, "w"), indent=1)
print("wrote", out, len(frames), "frames")
