> **SUPERSEDED. Do not cite.** This is a draft written during the research upgrade (2026-11-22/23), before the clean-extraction run. Some figures are stale: some predate the half-pixel detector correction, and some cite the earlier 15.8 mm / 16.0 mm-boundary depth estimate. The authoritative report is [`../INTEGRATION_REPORT.md`](../INTEGRATION_REPORT.md). The text below is kept unchanged for the record.

# Known limitations

1. **One face asset.** The scanned head is licensed for this publication only, so no further identities were added. Variation is limited to iris hue/value, lighting and exposure (`research/dataset_engine.py`). This is not demographic or population diversity, and no claim of that is made.
2. **Visual plausibility is not anatomical validation.** The rotation geometry is exact (pivot, Listing's law, vergence). Eyeball size, corneal shape and lid kinematics come from the asset and literature values, not from measurements of a person.
3. **The 2D ground truth versus the visible painted pupil.**
   - `pupil_center_2D_*` is an anatomical pupil placed 14.2 mm from the eye centre, with refraction through an analytic cornea.
   - The scanned eyeball's painted pupil lies on the mesh surface at about 15.8 mm.
   - In the released photoreal renders, the independent detector finds the visible pupil a mean 2.6 px lower than the metadata point (up to 4.4 px).
   - The gaze-dependent part of this offset is explained by the depth difference. About 1.9 px of constant offset is not yet explained.
   - For the photoreal image, the 2D labels should be treated as accurate to about 3–5 px, not sub-pixel.
   - The earlier "0.24 px" mask-check figure is withdrawn as a pupil-accuracy claim until it is re-measured (VALIDATION_REPORT.md §2.2).
4. **The original `tools/verify.py` reports 22 FAILs on the submission.** The causes are explained in TECHNICAL_AUDIT.md §4. The script is intentionally unchanged, to preserve the baseline.
5. **The eye-movement models (Stage 5) are textbook first-order models.** They are a minimum-jerk saccade with main-sequence duration, a fixed-latency pursuit, geometric vergence and cosine blink ramps, and they are not fitted to human recordings. Blink closure is reported but not driven onto the lid bones. A 16° saccade peaks at about 537 °/s with min-jerk, higher than typical human values (about 400 °/s).
6. **No pixel-identical determinism across machines is claimed.** Cycles noise depends on device and driver. Repeatability was measured on one machine only (see BENCHMARK_REPORT.md).
7. **Planar vs anatomical model.** Within the spec's ±5 cm range (about 8°), the pupil-centre positions of the three models differ by under 1 px (see VALIDATION_REPORT.md §3). The difference that matters within the spec range is image appearance (foreshortening, iris/limbus and lid interaction), not centre position.
8. **Post-deadline work.** Everything in `research/` and `AUDIT/` was produced after the 18 Nov 2026 deadline. None of it is part of the submitted package.
