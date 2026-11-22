# AI Disclosure: Team Techtonic (VIT Chennai), Samsung PRISM XR Hackathon 2026, Track 1

**AI coding assistant used:** an AI coding assistant (Claude Code) helped the team with:
- writing and debugging Python and Blender scripts (the `wrapper/eyes.py` API, scene build, hair grooming, dataset generator, gaze-model training);
- the verification and test tooling (`tools/verify.py` extensions, pupil-mask check, API tests, demo runner);
- drafting documentation, the README, the deck and the demo-video narration.

**What the team did:** defined the approach, made the design and look decisions, reviewed every render and result, ran and checked the verification, and approved each change.

**No AI-generated images, video or 3D models.** Every image and video frame is rendered by Blender Cycles from the 3D scene. The head is the 3D Scan Store "Free HD Head" scan, used with the vendor's permission for this submission only. The MakeHuman comparison head is CC0. Hair strands are grown procedurally by `tools/groom_hair.py`.

**All reported numbers are measured** by the scripts in `tools/` and `demo/final_hair/run_demo.sh`, and can be reproduced from the release files.
