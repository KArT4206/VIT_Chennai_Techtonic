# Run the demo kit

Everything runs from the **release ZIP** (`dist/Techtonic.zip`, SHA-256 `91f4bafe…73a4`). The runner
checks that hash first. It extracts fresh copies into `demo/phase2h/work/` and never writes to the ZIP,
the repo's `scene.blend`, `wrapper/`, `renders/` or `metadata.json`.

## Requirements

- **Blender 5.3.0.** On macOS the binary is `/Applications/Blender.app/Contents/MacOS/Blender`; set
  `BLENDER=...` elsewhere.
- **For the evaluator check:** a Python with `numpy` and `pillow`. For example:

```bash
python3 -m venv /tmp/demo-venv && /tmp/demo-venv/bin/pip install numpy pillow
```

- `ffmpeg`, for the video.

## 1. Run the real pipeline (about 12–15 min on an Apple M5, Metal GPU)

```bash
cd ~/Desktop/Projects/SyntheticEyes-Track1
PYTHON=/tmp/demo-venv/bin/python demo/phase2h/run_demo.sh
```

| Step | What it does | Output |
|---|---|---|
| 1 | Makes six real wrapper calls in the extracted `scene.blend`: `eyes.reset()`, `eyes.move(-1,0)`, `eyes.move(1,0)`, `eyes.move(0,1)`, `eyes.move(0,-1)`, `eyes.reset()`, each followed by `eyes.render()`. Also renders two observer views of the scene | `work/demo/` |
| 2 | Five command-line direction renders (`--move`, `--reset`) | `work/verify/directions/` |
| 3 | Regenerates the 10-frame clockwise sequence with no arguments | `work/sequence/` |
| 4 | Runs the original `verify.py` and the Phase 2G API test | — |
| 5 | Writes `validation_results.txt` and copies the evidence to `demo_assets/` | — |

## 2. Build the video (about 1 min)

```bash
/Applications/Blender.app/Contents/Resources/5.3/python/bin/python3.13 demo/phase2h/tools/compose_video.py demo/phase2h
```

Output: `demo/phase2h/work/demo_track1.mp4` (1920×1080, 30 fps, H.264, 1:45, no audio). Add the
voice-over from `NARRATION.md` in any editor, or record it as described in `RECORDING_INSTRUCTIONS.md`.

## 3. Live calls for a screen recording (optional)

Open Blender's Python console with the extracted scene:

```bash
/Applications/Blender.app/Contents/MacOS/Blender demo/phase2h/work/pkg/scene.blend
```

In the console (Scripting workspace):

```python
import sys; sys.dont_write_bytecode = True
sys.path.append(bpy.path.abspath("//wrapper")); import eyes
eyes.reset();      eyes.render("/tmp/live_reset.png")
eyes.move(-1, 0);  eyes.render("/tmp/live_left.png")
eyes.move(1, 0);   eyes.render("/tmp/live_right.png")
eyes.move(0, 1);   eyes.render("/tmp/live_up.png")
eyes.move(0, -1);  eyes.render("/tmp/live_down.png")
eyes.reset()
```

Each `render()` takes about 30 s at the scene's 512 samples. Cut the waits in editing.
