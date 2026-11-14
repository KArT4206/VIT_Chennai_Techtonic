# Recording instructions (manual screen capture)

I can't record your desktop. The automatic cut (`work/demo_track1.mp4`) is built only from real
render and log outputs. These steps add **live footage** of Blender and the terminal, plus a voice-over.

## Display setup

- Use a 1920×1080 display mode, or record a 1920×1080 region:
  - **System Settings → Displays:** pick "1920 × 1080" if your display offers it.
  - **Otherwise:** record a region and scale it in the editor.
- **Blender:** Preferences → Interface → Resolution Scale 1.2, so text is legible. Hide unused
  editors.
- **Terminal:** font size 18–20, dark theme, window about 1200×700.
- Turn on Do Not Disturb and close other apps.

## QuickTime Player (built in)

1. Press `Cmd+Shift+5`.
2. Choose "Record Selected Portion" and drag a 16:9 box.
3. Under Options:
   - **Save to:** `~/Desktop/Projects/SyntheticEyes-Track1/demo/phase2h/recordings/`
   - **Microphone:** your mic, for live narration.
   - **Show Mouse Clicks:** on.
4. Click Record. Stop with the stop icon in the menu bar.

QuickTime saves `.mov` files. Convert them to H.264 1080p30:

```bash
ffmpeg -i in.mov -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 160k out.mp4
```

## OBS Studio (alternative)

| Setting | Value |
|---|---|
| Settings → Video, base resolution | 1920×1080 |
| Settings → Video, output resolution | 1920×1080 |
| Settings → Video, FPS | 30 |
| Settings → Output, recording format | mp4 |
| Settings → Output, encoder | Apple VT H264 Hardware or x264, CRF 18 |
| Sources | "macOS Screen Capture" (window: Blender, then Terminal) and "Audio Input Capture" (mic) |

## What to record (live inserts; see the [LIVE] rows in `SHOT_LIST.md`)

**1. Blender scene, about 15 s, for Scene 2.**
- Open `demo/phase2h/work/pkg/scene.blend` (the extracted release copy).
- In the Outliner, expand `Human.rig` and select the bones `eye.L` and `eye.R`.
- Click `FixationTarget`, then `EyeCam`; the Properties panel shows their locations.
- Press Numpad 0 for the camera view.

**2. Wrapper calls, about 30 s, for Scene 3.** Choose one:
- Run `demo/phase2h/run_demo.sh` in the terminal and let it print its steps. Fast-forward the render
  waits in editing.
- Use the Python console steps in `RUN_DEMO.md` §3. Show each call and the returned dictionary.

**3. Voice-over.** Read `NARRATION.md` over the automatic cut. Each block is timed to its scene.

## Assembly

- Put the live clips over the matching sections of `work/demo_track1.mp4`, or cut them in.
- Keep the total at **1:45**.
- Export at 1920×1080, 30 fps, H.264 (yuv420p), AAC audio.
- Final file: `demo/phase2h/final/Techtonic_Track1_demo.mp4`.

**Do not** speed up or edit the renders themselves, and do not type commands that weren't actually
run.
