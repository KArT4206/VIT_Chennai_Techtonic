#!/usr/bin/env bash
# Build research/demo/final_round_silent.mp4 from the clean-run renders and AUDIT/results (no Blender rendering).
#   research/demo/source/make.sh <clean_run_work_dir>
# Env PYTHON: python with numpy, pillow. Needs ffmpeg/ffprobe on PATH.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; demo="$(dirname "$here")"; WK="$1"; PY="${PYTHON:-python3}"
"$PY" -I "$here/build_video.py" "$WK" "$demo/assets"
"$PY" -I "$here/music.py" "$demo/assets/soundtrack.wav" "$demo/assets/scene_timeline.csv"
ffmpeg -y -loglevel error -i "$demo/assets/video_noaudio.mp4" -i "$demo/assets/soundtrack.wav" -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart "$demo/final_round_silent.mp4"
cp "$demo/assets/scene_timeline.csv" "$demo/scene_timeline.csv"; cp "$demo/assets/asset_manifest.json" "$demo/asset_manifest.json"
cp "$demo/assets/thumbnail.png" "$demo/thumbnail.png"
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,pix_fmt,channels,sample_rate -of json "$demo/final_round_silent.mp4" > "$demo/assets/ffprobe.json"
echo MAKE_DONE
