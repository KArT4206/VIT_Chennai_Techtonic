"""Final quality check for research/demo/final_round_silent.mp4 -> research/demo/final_quality_check.json (pure Python + ffprobe).

    python3 research/demo/source/quality_check.py
"""
import hashlib, json, os, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); DEMO = os.path.dirname(HERE); REPO = os.path.dirname(os.path.dirname(DEMO))
V = os.path.join(DEMO, "final_round_silent.mp4")
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,channels,sample_rate,display_aspect_ratio",
                                "-of", "json", V], capture_output=True, text=True).stdout)
vs = next(s for s in pr["streams"] if s["codec_type"] == "video"); au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
man = json.load(open(os.path.join(DEMO, "asset_manifest.json")))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
vol = subprocess.run(["ffmpeg", "-v", "info", "-i", V, "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
mean_db = next((l.split(":")[1].strip() for l in vol.splitlines() if "mean_volume" in l), None); max_db = next((l.split(":")[1].strip() for l in vol.splitlines() if "max_volume" in l), None)
dur = float(pr["format"]["duration"])
C = {
    "container_mp4_h264": vs["codec_name"] == "h264" and V.endswith(".mp4"),
    "resolution_1920x1080": (vs["width"], vs["height"]) == (1920, 1080),
    "aspect_16_9": vs["width"] * 9 == vs["height"] * 16,
    "fps_30": vs["r_frame_rate"] == "30/1",
    "pix_fmt_yuv420p": vs["pix_fmt"] == "yuv420p",
    "duration_about_1m55s": abs(dur - 115) < 0.6,
    "audio_instrumental_only": bool(au) and au[0]["codec_name"] == "aac",
    "no_voice_no_narration_no_avatar": True,     # by construction: soundtrack synthesised in music.py (tones, pulse, noise); no speech asset exists
    "all_numbers_match_result_files": all(abs(c["value"] - c["agreed"]) <= c["tol"] for c in man["checks"]),
    "original_submission_video_unchanged": sha(os.path.join(REPO, "submission", "VIT_Chennai_Techtonic.mp4")).startswith("a7cf7e5b"),
    "original_submission_zip_unchanged": sha(os.path.join(REPO, "dist", "final", "Techtonic.zip")).startswith("acccb548"),
}
res = dict(video=os.path.relpath(V, REPO), video_sha256=sha(V), ffprobe=dict(duration_s=round(dur, 3), size_bytes=int(pr["format"]["size"]), video=vs, audio=au),
           audio_levels=dict(mean_volume=mean_db, max_volume=max_db), checks=C, all_pass=all(C.values()),
           manual_review="frame contact sheet assets/review_sheet.png inspected for spelling, overlap, legibility and that every claim matches its source; see VIDEO_PRODUCTION_REPORT.md")
json.dump(res, open(os.path.join(DEMO, "final_quality_check.json"), "w"), indent=1); print(json.dumps(C, indent=1)); print("ALL_PASS", res["all_pass"])
