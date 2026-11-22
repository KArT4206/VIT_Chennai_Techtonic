# AUDIT/results — index

**The authoritative research report is [`INTEGRATION_REPORT.md`](INTEGRATION_REPORT.md).** The release summary is [`RELEASE_NOTE.md`](RELEASE_NOTE.md), and the browsable view is [`dashboard/index.html`](dashboard/index.html). All three are generated from the files in this folder, by `research/build_report.py`, `research/build_release_note.py` and `research/dashboard.py`.

| Folder / file | What it is | Status |
|---|---|---|
| `INTEGRATION_REPORT.md` | Full research report (sections 1–13) | **authoritative** |
| `results_check.json`, `integrity_check.json` | Completeness and staleness check; submission integrity | current |
| `compliance.json` | 40 Track 01 compliance and calibration checks | current |
| `*_metrics.json`, `*_per_pupil.csv`, `*_overlays.png` | Detector validation (frozen detector) on the released frames and 5 ablation conditions | current |
| `ws1_depth/` | Pupil-depth probe (12–20 mm) and effective-depth fit with held-out validation | current |
| `ws1_depth_baseline_scratch/` | The same fit on the first (pre-clean) renders; kept for comparison | baseline, not authoritative |
| `research_pupil_levels.json` | Three-level pupil annotation (A anatomical, B painted/rendered, C detected) | current |
| `ws2_degradation/` | Detector robustness and label invariance under image degradations | current |
| `ws3_masks/` | Semantic masks and the unclassified-pixel audit | **provisional** |
| `ws4_dataset/`, `ws6_dataset_v1/` | Dataset generation and integrity (v2 pilot, v1 40 samples) | current |
| `ws5_dynamics/` | Eye-movement models and rendered-trajectory measurements | current |
| `ws6_performance/` | Render benchmarks, eye-band audit, GPU/CPU repeatability | current |
| `ws8_comparison/`, `model_comparison.json` | Planar vs sphere vs anatomical eye models | current |
| `run_comparison.json` | Checkpoint and baseline vs clean-run differences | current |
| `checkpoint_pre_clean/` | Results recorded before the clean run (corrected detector; `ws2_degradation` copy predates the correction) | historical |
| `superseded_drafts/` | Earlier draft reports, each marked SUPERSEDED | **superseded, do not cite** |
| `gpu_job_log.jsonl`, `run_environment.txt` | GPU job queue log (commands, exit codes, times); software and hardware | provenance |
