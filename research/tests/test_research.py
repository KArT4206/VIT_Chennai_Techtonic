"""Automated tests for research/ modules that run without Blender.

    python3 -m pytest -q research/tests        (or: python3 research/tests/test_research.py)
"""
import json, math, os, subprocess, sys, tempfile, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.dirname(HERE); sys.path.insert(0, RES)
import degrade, dynamics, pupil_detector as P


def synthetic_eye(cx, cy, r=15.0, glint=True, size=200):
    yy, xx = np.mgrid[:size, :size].astype(float) + 0.5
    img = np.full((size, size, 3), 200.0)                                    # sclera/skin
    iris = (xx - cx) ** 2 + (yy - cy) ** 2 < (2.6 * r) ** 2; img[iris] = [120, 80, 50]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2); a = np.clip(r + 0.5 - d, 0, 1)[..., None]   # anti-aliased pupil edge
    img = img * (1 - a) + 8 * a
    if glint:
        img[int(cy - r):int(cy - r + 6), int(cx + 4):int(cx + 9)] = 255
    return img.astype(np.uint8)


def test_detector_subpixel_on_synthetic_pair():
    img = np.concatenate([synthetic_eye(100.3, 101.7), synthetic_eye(99.6, 100.2)], axis=1)
    det = P.detect(img)
    assert len(det) == 2
    for d, (gx, gy) in zip(det, ((100.3, 101.7), (299.6, 100.2))):
        assert math.dist(d["centre"], (gx, gy)) < 0.3, (d["centre"], gx, gy)
        assert abs(d["radius"] - 15.0) < 0.6


def test_detector_never_needs_ground_truth():
    import inspect
    src = inspect.getsource(P)
    assert "metadata" not in src.split('"""', 2)[2] and "pupil_center_2D" not in src


def test_degrade_selftest():
    assert degrade.selftest()


def test_degrade_preserves_label_bytes():
    with tempfile.TemporaryDirectory() as t:
        from PIL import Image
        Image.fromarray(synthetic_eye(100, 100)).save(os.path.join(t, "a.png"))
        lab = dict(pupil_center_2D_L=[100, 100], pupil_center_2D_R=[100, 100], input=dict(h=0, v=0)); json.dump(lab, open(os.path.join(t, "a.json"), "w"))
        _, prov = degrade.apply_file(os.path.join(t, "a.png"), os.path.join(t, "a.json"), os.path.join(t, "o"),
                                     [dict(op="noise", full_well_e=300), dict(op="jpeg", quality=40), dict(op="glint", n=2)], 3)
        assert prov["label_sha256"] == prov["label_copy_sha256"]
        _, prov2 = degrade.apply_file(os.path.join(t, "a.png"), os.path.join(t, "a.json"), os.path.join(t, "o2"),
                                      [dict(op="noise", full_well_e=300), dict(op="jpeg", quality=40), dict(op="glint", n=2)], 3)
        assert prov["output_sha256"] == prov2["output_sha256"], "same spec + seed must reproduce the same image"


def test_dynamics_selftest():
    ok, _ = dynamics.selftest(); assert ok


def test_gpu_queue_serialises_jobs():
    lock = tempfile.mktemp(suffix=".lock"); env = dict(os.environ, GPUQ_IGNORE_BLENDER="1", GPUQ_LOCK=lock, GPUQ_JOBLOG=lock + ".log"); t0 = time.time()
    ps = [subprocess.Popen([sys.executable, os.path.join(RES, "gpuq.py"), "--", sys.executable, "-c",
                            "import time,sys;print('S',time.time());time.sleep(1);print('E',time.time())"], env=env, stdout=subprocess.PIPE, text=True) for _ in range(2)]
    outs = [p.communicate()[0] for p in ps]
    spans = sorted((float(o.split("S ")[1].split()[0]), float(o.split("E ")[1].split()[0])) for o in outs)
    assert spans[1][0] >= spans[0][1] - 0.05, f"jobs overlapped: {spans}"


if __name__ == "__main__":
    fails = 0
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            try:
                f(); print("PASS", n)
            except Exception as e:
                fails += 1; print("FAIL", n, repr(e)[:300])
    sys.exit(1 if fails else 0)
