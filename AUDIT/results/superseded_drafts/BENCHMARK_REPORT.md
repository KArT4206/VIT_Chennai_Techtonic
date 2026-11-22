> **SUPERSEDED. Do not cite.** This is a draft written during the research upgrade (2026-11-22/23), before the clean-extraction run. Some figures are stale: some predate the half-pixel detector correction, and some cite the earlier 15.8 mm / 16.0 mm-boundary depth estimate. The authoritative report is [`../INTEGRATION_REPORT.md`](../INTEGRATION_REPORT.md). The text below is kept unchanged for the record.

# Benchmark report

Hardware: Apple M5, 24 GB RAM, Blender 5.3.0, Cycles on Metal GPU.

| Measurement | Value | Source |
|---|---|---|
| Ablation `full`: 11 poses at 64 spp, including scene load | 133.8 s wall time (≈ 12 s per frame) | `/usr/bin/time`, 22 Nov 2026 |
| Wrapper render at the scene's default samples, per frame | TODO | `AUDIT/results/benchmark.json` |
| 10-frame sequence | TODO | |
| Dataset throughput (frames per minute, 32 spp) | TODO | dataset manifest `runs[].mean_render_s` |
| Peak memory | TODO (`/usr/bin/time -l`, maximum resident set size) | |
| Repeatability: same pose rendered twice on the same machine, pixel difference | TODO | |
| Repeatability of metadata | Regenerated `metadata.json` is byte-identical to the packaged one (run_demo.sh, 22 Nov) | `demo/final_hair/validation_results.txt` |
| Failure / retry rate | TODO (dataset manifest `failures`) | |

Known incident: one earlier combined Blender run ran out of memory (exit 137) and was rerun as separate steps. Renders are therefore run one at a time.
