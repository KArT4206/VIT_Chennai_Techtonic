// Final-round presentation for Team Techtonic (research/upgrade). Every number is read from AUDIT/results at build
// time and asserted against the figures used in final_round_silent.mp4; images are real renders cut by deck_assets.py.
//   NODE_PATH=<dir with pptxgenjs> APPLY_THEME=<pptx skill>/scripts/apply_theme.js node research/demo/source/build_deck.js
const fs = require("fs"), path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.APPLY_THEME);
const DEMO = path.resolve(__dirname, ".."), REPO = path.resolve(DEMO, "..", ".."), RES = path.join(REPO, "AUDIT", "results");
const A = (f) => path.join(DEMO, "presentation_assets", f);
const J = (f) => JSON.parse(fs.readFileSync(path.join(RES, f), "utf8"));

// ------------------------------------------------------------------ numbers from result files
const comp = J("compliance.json"), fit = J("ws1_depth/depth_fit.json"), probe = J("ws1_depth/depth_probe_extended.json");
const det = [["Released frames", J("release_metrics.json")], ["Full scene", J("full_roi_metrics.json")],
             ["Clean condition", J("no_lids_lens_roi_metrics.json")], ["40-sample dataset", J("ws6_dataset_v1/dataset_roi_metrics.json")]];
const m1 = J("ws6_dataset_v1/manifest.json"), cov = J("ws4_dataset/coverage.json").coverage, int2 = J("ws4_dataset/integrity.json");
const dyn = J("ws5_dynamics/dynamics_render_check.json"), bench = J("ws6_performance/bench_compare.json"), band = J("ws6_performance/band_audit.json");
const unc = J("ws3_masks/unclassified_audit.json").summary;
const legacy = fs.readFileSync(path.join(RES, "verify_py_release_bundle.txt"), "utf8").split("\n");
const C = fit.conditions.no_lids_lens, FULL = fit.conditions.full;
// refraction shift of the RELEASED metadata (Techtonic.zip), via the three-level annotation built from it
const LV = J("research_pupil_levels.json");
const rd = LV.frames.flatMap((f) => ["L", "R"].map((e) => Math.hypot(f[e].A.apparent_2D_analytic_px[0] - f[e].A.projected_2D_px[0], f[e].A.apparent_2D_analytic_px[1] - f[e].A.projected_2D_px[1])));
const REFR = [Math.min(...rd), Math.max(...rd)];
const N = {
  comp: comp.passed, compTot: comp.passed + comp.failed,
  anatL: probe.reset_pose.L.wrapper_pupil_depth_mm, anatR: probe.reset_pose.R.wrapper_pupil_depth_mm,
  paintL: probe.reset_pose.L.painted_surface_depth_along_axis_mm, paintR: probe.reset_pose.R.painted_surface_depth_along_axis_mm,
  fitL: C.L.best_depth_mm, fitR: C.R.best_depth_mm, ciL: C.L.bootstrap_depth_mm, ciR: C.R.bootstrap_depth_mm,
  hoFitL: C.L.heldout_fitted_depth_model.rmse_px, hoFitR: C.R.heldout_fitted_depth_model.rmse_px,
  hoMeshL: C.L.heldout_mesh_painted_no_fit.rmse_px, hoMeshR: C.R.heldout_mesh_painted_no_fit.rmse_px,
  hoGtL: C.L.heldout_wrapper_gt_no_offset.rmse_px, hoGtR: C.R.heldout_wrapper_gt_no_offset.rmse_px, nHeld: C.L.n_heldout,
  sacL: dyn.saccade.image_left.measured_duration_5_95_ms, sacR: dyn.saccade.image_right.measured_duration_5_95_ms,
  sacCmd: dyn.saccade.image_left.commanded_duration_5_95_ms, sacDt: dyn.saccade.image_left.frame_interval_ms,
  glitch: dyn.saccade.image_right.max_residual_px, lag: dyn.pursuit.image_left.measured_lag_ms, lagRes: dyn.pursuit.image_left.lag_resolution_ms,
  gainL: dyn.pursuit.image_left.measured_gain_vs_target, gainR: dyn.pursuit.image_right.measured_gain_vs_target,
  pers: bench.configs.persistent.speedup_sequence_vs_original, persMax: band.configs.persistent[0].band_interior_max,
  roiIn: band.configs.band[0].band_interior_max, roiEdge: band.configs.band[0].band_edge_frame_max,
  legP: legacy.filter((l) => l.startsWith("PASS ")).length, legF: legacy.filter((l) => l.startsWith("FAIL ")).length,
};
const AGREED = [[N.comp, 40, 0], [N.compTot, 40, 0], [N.anatL, 14.19, .01], [N.anatR, 14.29, .01], [N.paintL, 16.28, .01], [N.paintR, 16.35, .01],
  [N.fitL, 16.10, 1e-9], [N.fitR, 16.15, 1e-9], [N.hoFitL, .116, 1e-9], [N.hoFitR, .136, 1e-9], [N.hoGtL, 3.14, .005], [N.hoGtR, 3.15, .005], [N.nHeld, 14, 0],
  [det[0][1].success_rate, .90, .005], [det[1][1].success_rate, .68, .005], [det[2][1].success_rate, 1.0, 1e-9], [det[3][1].success_rate, .75, 1e-9],
  [m1.samples ? Object.keys(m1.samples).length : 0, 40, 0], [cov.n_samples, 22, 0], [N.sacL, 33.9, .05], [N.sacR, 37.1, .05], [N.sacCmd, 36.7, .05],
  [N.lag, 100, 0], [N.lagRes, 33.3, .05], [N.glitch, 8.09, .005], [N.pers, 1.12, .005], [N.persMax, 1, 0], [N.roiIn, 37, 0], [N.roiEdge, 181, 0], [N.legP, 51, 0], [N.legF, 20, 0]];
const bad = AGREED.filter(([v, e, t]) => Math.abs(v - e) > t);
if (bad.length) throw new Error("result files disagree with the video figures: " + JSON.stringify(bad));
if (bench.configs.band.accept || !bench.configs.persistent.accept || !int2.ok) throw new Error("unexpected acceptance state");

// ------------------------------------------------------------------ theme and layouts
const THEME = { name: "Techtonic Research", headFontFace: "Arial", bodyFontFace: "Arial",
  colors: { dk1: "0B0D11", lt1: "F0F3F7", dk2: "141A24", lt2: "96A0AC", accent1: "40C8EB", accent2: "4682F0", accent3: "F0AA3C", accent4: "5AD282", accent5: "EB5A50", accent6: "1E2633", hlink: "40C8EB", folHlink: "4682F0" } };
const pres = new pptxgen(); pres.layout = "LAYOUT_16x9"; pres.title = "Techtonic final round"; pres.author = "Team Techtonic";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const S = pres.SchemeColor;
const HEX = { bg: "0B0D11", panel: "141A24", grid: "1E2633", white: "F0F3F7", grey: "96A0AC", cyan: "40C8EB", amber: "F0AA3C", green: "5AD282", red: "EB5A50", blue: "4682F0" };
pres.defineSlideMaster({ title: "CONTENT", background: { color: HEX.bg },
  objects: [{ rect: { x: 0.5, y: 0.98, w: 0.6, h: 0.04, fill: { color: HEX.cyan } } },
            { text: { text: "Team Techtonic · VIT Chennai · Samsung PRISM XR Hackathon 2026 · Track 01", options: { x: 0.5, y: 5.3, w: 7, h: 0.25, fontSize: 9, color: HEX.grey } } },
            { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.65, fontSize: 22, bold: true, color: HEX.white, valign: "bottom", align: "left" }, text: "" } }],
  slideNumber: { x: 9.2, y: 5.3, w: 0.4, h: 0.25, fontSize: 9, color: HEX.grey } });
pres.defineSlideMaster({ title: "COVER", background: { color: HEX.bg }, objects: [] });

const sections = ["Introduction", "System", "Validation", "Results", "Close"];
let sec = null;
function slide(title, section, notes) {
  if (section !== sec) { pres.addSection({ title: section }); sec = section; }
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section }); s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes); return s;
}
const T = (s, text, o) => s.addText(text, Object.assign({ isTextBox: true, fontFace: "Arial", color: HEX.white, fontSize: 14, margin: 0, valign: "top" }, o));
const src = (s, text) => T(s, "Source: " + text, { x: 0.5, y: 5.02, w: 9, h: 0.25, fontSize: 9, color: HEX.grey });
const img = (s, f, x, y, w, h, alt) => s.addImage({ path: A(f), x, y, w, h, altText: alt });
const panel = (s, x, y, w, h, color) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, fill: { color: HEX.panel }, line: { color: color || HEX.grid, width: 1 } });
const big = (s, v, lab, x, y, w, color) => { T(s, v, { x, y, w, h: 0.55, fontSize: 30, bold: true, color: color || HEX.white }); T(s, lab, { x, y: y + 0.55, w, h: 0.3, fontSize: 11, color: HEX.grey }); };
const f2 = (v) => v.toFixed(2), f3 = (v) => v.toFixed(3), pct = (v) => Math.round(v * 100) + "%";
const chartBase = { catAxisLabelColor: HEX.grey, valAxisLabelColor: HEX.grey, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", dataLabelFontFace: "+mn-lt",
  valGridLine: { color: HEX.grid, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, showValue: true, dataLabelColor: HEX.white, dataLabelFontSize: 11, catAxisLabelFontSize: 11, valAxisLabelFontSize: 10 };

// ------------------------------------------------------------------ 0 cover
{ pres.addSection({ title: "Cover" }); const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Cover" });
  s.addImage({ path: A("hero_eyes.png"), x: 0, y: 0, w: 10, h: 4.97, altText: "Both eyes of the rendered head, frame 0 of the shipped sequence" });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 3.55, w: 10, h: 2.08, fill: { color: HEX.bg, transparency: 8 }, line: { type: "none" } });
  T(s, "Synthetic gaze. Real geometry. Measured results.", { x: 0.5, y: 3.7, w: 9, h: 0.5, fontSize: 26, bold: true });
  T(s, "Team Techtonic · VIT Chennai", { x: 0.5, y: 4.25, w: 9, h: 0.35, fontSize: 16, color: HEX.cyan, bold: true });
  T(s, "Samsung PRISM XR Hackathon 2026 · Track 01 — XR Perception Group · final round", { x: 0.5, y: 4.62, w: 9, h: 0.3, fontSize: 12, color: HEX.grey });
  T(s, "Research branch research/upgrade · baseline submission tag submission-baseline-v1.0 (unchanged)", { x: 0.5, y: 5.2, w: 9, h: 0.25, fontSize: 9, color: HEX.grey });
  s.addNotes("Opening. The image is frame 0 of the shipped ten-frame sequence; nothing on this slide is generated imagery."); }

// ------------------------------------------------------------------ 1 problem
{ const s = slide("Problem: gaze data needs trustworthy ground truth", "Introduction",
    "Eye tracking for XR is trained and tested on images whose pupil position must be known exactly. Real captures cannot give exact ground truth, and a flat sliding pupil is not how an eye looks.");
  img(s, "scene_eyes_cutaway.png", 5.3, 1.2, 4.2, 2.36, "Research render of the shipped scene with gaze lines from both eyes to the fixation target");
  T(s, "Research render of the shipped scene; gaze lines to the fixation target", { x: 5.3, y: 3.6, w: 4.2, h: 0.3, fontSize: 9, color: HEX.cyan });
  const items = [["1", "Eye articulation", "each eyeball must rotate about its own centre"], ["2", "Calibrated camera", "known intrinsics K and extrinsics [R|t]"], ["3", "Ground-truth annotation", "2-D pupil centre per eye, per frame"]];
  items.forEach(([n, h, d], i) => { const y = 1.25 + i * 0.95; panel(s, 0.5, y, 4.5, 0.8); T(s, n, { x: 0.65, y: y + 0.17, w: 0.4, h: 0.45, fontSize: 24, bold: true, color: HEX.cyan });
    T(s, h, { x: 1.15, y: y + 0.12, w: 3.7, h: 0.3, fontSize: 15, bold: true }); T(s, d, { x: 1.15, y: y + 0.45, w: 3.7, h: 0.28, fontSize: 11, color: HEX.grey }); });
  T(s, "Synthetic data must be more than a pupil sliding across a flat image.", { x: 0.5, y: 4.25, w: 9, h: 0.35, fontSize: 14, bold: true, color: HEX.amber }); }

// ------------------------------------------------------------------ 2 solution
{ const s = slide("Solution: a rigged scanned face with a gaze API", "System",
    "One Blender scene and one Python module. eyes.move takes normalised inputs; the eyes converge on a target 35 cm ahead; render writes the PNG and the ground truth.");
  img(s, "scene_overview.png", 0.5, 1.2, 4.9, 2.76, "Side view of the real scene: camera, fixation target and eye centres");
  T(s, "Side view of the real scene: camera (blue), fixation target (green), eye centres", { x: 0.5, y: 4.0, w: 4.9, h: 0.3, fontSize: 9, color: HEX.cyan });
  panel(s, 5.7, 1.2, 3.8, 2.76);
  T(s, "import eyes\n\neyes.move(h, v)  # h, v: -1..+1\neyes.reset()\neyes.render('frame.png')\n\n# returns inputs, eye rotations,\n# 2-D/3-D pupil centres, K, [R|t]", { x: 5.9, y: 1.4, w: 3.5, h: 2.4, fontFace: "Courier New", fontSize: 12, color: HEX.white });
  T(s, "Deliverable kept frozen: tag submission-baseline-v1.0 · research work lives only in research/ and AUDIT/results/", { x: 0.5, y: 4.45, w: 9, h: 0.3, fontSize: 11, color: HEX.grey }); }

// ------------------------------------------------------------------ 3 architecture (schematic)
{ const s = slide("System architecture", "System", "Schematic of the data flow. Each box is a real component in the repository.");
  const boxes = [["Blender scene", "scene.blend"], ["Eye rig", "eye.L / eye.R bones"], ["Gaze controller", "wrapper/eyes.py"], ["Camera render", "Cycles, 1024×1024"], ["Ground truth", "metadata.json"]];
  boxes.forEach(([h, d], i) => { const x = 0.5 + i * 1.86; panel(s, x, 1.6, 1.6, 1.1, HEX.cyan);
    T(s, h, { x: x + 0.1, y: 1.75, w: 1.4, h: 0.35, fontSize: 13, bold: true, align: "center" }); T(s, d, { x: x + 0.1, y: 2.15, w: 1.4, h: 0.4, fontSize: 10, color: HEX.grey, align: "center" });
    if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + 1.62, y: 2.05, w: 0.22, h: 0.2, fill: { color: HEX.cyan }, line: { type: "none" } }); });
  const r = [["Research layer (post-deadline)", "compliance suite · depth probe · independent detector · datasets · dynamics · benchmarks · report builders"],
             ["Reproducibility", "research/verify_all.sh re-runs every result from a clean extraction of the release ZIP, one GPU job at a time"]];
  r.forEach(([h, d], i) => { const y = 3.05 + i * 0.85; panel(s, 0.5, y, 9, 0.7); T(s, h, { x: 0.7, y: y + 0.1, w: 3, h: 0.28, fontSize: 13, bold: true, color: HEX.cyan }); T(s, d, { x: 0.7, y: y + 0.38, w: 8.6, h: 0.28, fontSize: 11, color: HEX.grey }); });
  T(s, "SCHEMATIC — not a measured output", { x: 7.0, y: 1.2, w: 2.5, h: 0.25, fontSize: 9, color: HEX.amber, align: "right" }); }

// ------------------------------------------------------------------ 4 articulation
{ const s = slide("Anatomical eye articulation", "System", "Real renders from the wrapper calls. Each eye rotates about its own bone pivot by the shortest arc, so there is no torsion and the eyes converge.");
  img(s, "directions.png", 0.5, 1.2, 9, 1.11, "Five wrapper calls rendered: down, left, reset, right, up");
  big(s, "0.000°", "torsion about the gaze axis (Listing's law)", 0.5, 2.7, 2.9, HEX.cyan);
  big(s, "0 mm", "pivot drift over the 10 poses", 3.55, 2.7, 2.6, HEX.cyan);
  big(s, "9.70°", "vergence at the 35 cm target", 6.4, 2.7, 3.1, HEX.cyan);
  T(s, "Upper lid follows vertical gaze (gain 1.1), lower lid partly (0.35).", { x: 0.5, y: 3.75, w: 9, h: 0.3, fontSize: 12, color: HEX.grey });
  const tors = comp.checks.find((c) => c.name.startsWith("eye L: torsion")).value, piv = comp.checks.find((c) => c.name.startsWith("eye L: pivot")).value, verg = comp.checks.find((c) => c.name.startsWith("vergence")).value;
  if (Math.abs(tors) > 1e-3 || Math.abs(piv) > 1e-3 || Math.abs(verg - 9.70) > .005) throw new Error("articulation numbers changed");
  src(s, "AUDIT/results/compliance.json · renders: demo/final_hair/demo_assets"); }

// ------------------------------------------------------------------ 5 calibration
{ const s = slide("Calibration and compliance", "Validation", "The ten clockwise frames, the calibrated distances, and the new 40-check research compliance suite. The legacy verifier is reported separately and unchanged.");
  img(s, "ring.png", 0.5, 1.2, 5.2, 1.21, "The ten shipped frames, k = 0..9, clockwise from the top");
  [["35 cm", "fixation distance"], ["40 cm", "camera distance"], ["1024 × 1024", "PNG output"], ["10", "clockwise gaze positions"]].forEach(([v, l], i) => big(s, v, l, 0.5 + (i % 2) * 2.6, 2.6 + Math.floor(i / 2) * 0.95, 2.5));
  panel(s, 6.0, 1.2, 3.5, 1.6, HEX.green);
  T(s, `${N.comp}/${N.compTot}`, { x: 6.2, y: 1.3, w: 3.1, h: 0.65, fontSize: 40, bold: true, color: HEX.green });
  T(s, "research compliance checks passed (new deterministic suite: geometry, projection, pivots, inputs, reset)", { x: 6.2, y: 2.0, w: 3.1, h: 0.7, fontSize: 11, color: HEX.grey });
  panel(s, 6.0, 3.0, 3.5, 1.15, HEX.amber);
  T(s, `Legacy tools/verify.py (unmodified): ${N.legP} PASS / ${N.legF} FAIL records`, { x: 6.2, y: 3.1, w: 3.1, h: 0.5, fontSize: 12, bold: true, color: HEX.amber });
  T(s, "Its FAILs come from its own pupil detector, tuned on an earlier head.", { x: 6.2, y: 3.6, w: 3.1, h: 0.5, fontSize: 10, color: HEX.grey });
  src(s, "AUDIT/results/compliance.json · AUDIT/results/verify_py_release_bundle.txt · renders/frame_00..09.png"); }

// ------------------------------------------------------------------ 6 discovery
{ const s = slide("Discovery: official and painted pupils differ", "Results",
    "Red is the official ground truth (anatomical pupil through an analytic cornea). Green is the pupil painted on the rendered eye, measured from mesh and texture with nothing fitted. Cyan is the independent detector.");
  img(s, "discovery_zoom.png", 0.5, 1.2, 4.0, 3.0, "Frame 5, eye on the image right, zoomed: red official GT, green painted pupil, cyan detector");
  T(s, [{ text: "red ", options: { color: HEX.red, bold: true } }, { text: "official GT   ", options: { color: HEX.grey } }, { text: "green ", options: { color: HEX.green, bold: true } }, { text: "painted pupil   ", options: { color: HEX.grey } }, { text: "cyan ", options: { color: HEX.cyan, bold: true } }, { text: "detector", options: { color: HEX.grey } }], { x: 0.5, y: 4.25, w: 4.0, h: 0.28, fontSize: 11 });
  T(s, "Depth of the pupil from the eye centre", { x: 4.9, y: 1.2, w: 4.6, h: 0.3, fontSize: 12, color: HEX.grey });
  panel(s, 4.9, 1.55, 2.2, 1.3, HEX.red); T(s, "ANATOMICAL (official GT)", { x: 5.05, y: 1.62, w: 2.0, h: 0.25, fontSize: 10, bold: true, color: HEX.red });
  T(s, `L ${f2(N.anatL)} mm\nR ${f2(N.anatR)} mm`, { x: 5.05, y: 1.95, w: 2.0, h: 0.8, fontSize: 20, bold: true });
  panel(s, 7.3, 1.55, 2.2, 1.3, HEX.green); T(s, "PAINTED ON THE ASSET", { x: 7.45, y: 1.62, w: 2.0, h: 0.25, fontSize: 10, bold: true, color: HEX.green });
  T(s, `L ${f2(N.paintL)} mm\nR ${f2(N.paintR)} mm`, { x: 7.45, y: 1.95, w: 2.0, h: 0.8, fontSize: 20, bold: true });
  T(s, "Effective fitted depth (clean condition)", { x: 4.9, y: 3.05, w: 4.6, h: 0.3, fontSize: 12, color: HEX.grey });
  T(s, `LEFT ${f2(N.fitL)} mm · RIGHT ${f2(N.fitR)} mm`, { x: 4.9, y: 3.35, w: 4.6, h: 0.42, fontSize: 18, bold: true, color: HEX.cyan });
  T(s, `95% bootstrap CI ${f2(N.ciL.p2_5)}–${f2(N.ciL.p97_5)} · ${f2(N.ciR.p2_5)}–${f2(N.ciR.p97_5)} mm`, { x: 4.9, y: 3.8, w: 4.6, h: 0.25, fontSize: 10, color: HEX.grey });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 4.9, y: 4.15, w: 4.6, h: 0.38, rectRadius: 0.05, fill: { color: HEX.bg }, line: { color: HEX.amber, width: 1 } });
  T(s, "EFFECTIVE FITTED PARAMETERS — NOT ANATOMICAL MEASUREMENTS", { x: 4.95, y: 4.24, w: 4.5, h: 0.22, fontSize: 8.5, bold: true, color: HEX.amber, align: "center" });
  src(s, "research_pupil_levels.json · ws1_depth/depth_probe_extended.json · ws1_depth/depth_fit.json"); }

// ------------------------------------------------------------------ 7 held-out validation
{ const s = slide("Independent held-out validation", "Results",
    `The depth and a constant offset are fitted on 11 gaze poses per eye. ${N.nHeld} other gaze positions are only predicted. The fitted model predicts them far better than the official ground truth. Bootstrap: 2000 resamples of fit poses, seed 12345.`);
  s.addChart(pres.charts.BAR, [{ name: "Fitted model", labels: ["Left eye", "Right eye"], values: [N.hoFitL, N.hoFitR] },
                               { name: "Mesh only, nothing fitted", labels: ["Left eye", "Right eye"], values: [N.hoMeshL, N.hoMeshR] },
                               { name: "Official ground truth", labels: ["Left eye", "Right eye"], values: [N.hoGtL, N.hoGtR] }],
    Object.assign({}, chartBase, { x: 0.5, y: 1.2, w: 5.6, h: 3.4, barDir: "bar", barGrouping: "clustered", chartColors: [HEX.cyan, HEX.green, HEX.red], showLegend: true, legendPos: "b", legendColor: HEX.grey, legendFontFace: "+mn-lt", legendFontSize: 10,
      showTitle: true, title: "Held-out RMSE (px), 14 positions per eye", titleColor: HEX.white, titleFontFace: "+mn-lt", titleFontSize: 13, dataLabelFormatCode: "0.000", valAxisMinVal: 0 }));
  big(s, String(N.nHeld), "held-out gaze positions per eye, never used for fitting", 6.4, 1.25, 3.1, HEX.amber);
  T(s, `Clean condition (lids and lens mesh hidden). Full scene with lids: RMSE ${f3(FULL.L.heldout_fitted_depth_model.rmse_px)} / ${f3(FULL.R.heldout_fitted_depth_model.rmse_px)} px; right eye excludes ${FULL.R.heldout_fitted_depth_model.excluded_poses.length} held-out poses where the detector failed.`, { x: 6.4, y: 2.3, w: 3.1, h: 1.1, fontSize: 11, color: HEX.grey });
  T(s, "Valid for this asset and this detector — not for other eyes or human subjects.", { x: 6.4, y: 3.55, w: 3.1, h: 0.6, fontSize: 12, bold: true, color: HEX.amber });
  src(s, "AUDIT/results/ws1_depth/depth_fit.json (per-pose errors included)"); }

// ------------------------------------------------------------------ 7b detector
{ const s = slide("Independent detector: condition by condition", "Results", "An image-only pupil detector, frozen after a half-pixel correction. Failures are kept in the overlays and in the statistics.");
  img(s, "overlays_full.png", 0.5, 1.2, 4.6, 1.73, "Actual detector overlays on the full scene; green ground truth, red detection, failed tiles labelled");
  T(s, "Actual overlays, full scene: green = ground truth, red = detection, orange label = failed (> 5 px)", { x: 0.5, y: 2.97, w: 4.6, h: 0.4, fontSize: 9, color: HEX.cyan });
  s.addChart(pres.charts.BAR, [{ name: "Within 5 px", labels: det.map((d) => d[0]), values: det.map((d) => d[1].success_rate * 100) }],
    Object.assign({}, chartBase, { x: 5.3, y: 1.15, w: 4.2, h: 3.2, barDir: "bar", chartColors: [HEX.cyan], valAxisMaxVal: 100, valAxisMinVal: 0, dataLabelFormatCode: "0\"%\"",
      showTitle: true, title: "Detections within 5 px of ground truth", titleColor: HEX.white, titleFontFace: "+mn-lt", titleFontSize: 12 }));
  T(s, "Detection percentages are condition-specific; missed detections are retained in reporting.", { x: 0.5, y: 3.55, w: 4.6, h: 0.6, fontSize: 12, bold: true, color: HEX.amber });
  src(s, "release / full_roi / no_lids_lens_roi _metrics.json · ws6_dataset_v1/dataset_roi_metrics.json · full_roi_overlays.png"); }

// ------------------------------------------------------------------ 8 dataset
{ const s = slide("Synthetic dataset generation", "Results", "Seeded, resumable generators with hashed manifests. Generation success is reported separately from detector accuracy.");
  img(s, "dataset_grid.png", 0.5, 1.2, 4.7, 1.03, "Fifteen dataset v1 renders with random gaze, iris colour and lighting");
  img(s, "degraded_strip.png", 0.5, 2.4, 4.7, 0.55, "Four dataset v2 samples after image-quality degradation");
  big(s, `${Object.keys(m1.samples).length}/${m1.config.n}`, "dataset v1 samples (iris, lighting variants)", 5.6, 1.2, 1.9, HEX.white);
  big(s, `${cov.n_samples}/${cov.planned}`, `dataset v2 pilot: ${cov.kinds.static} static · ${cov.kinds.pursuit} pursuit · ${cov.kinds.saccade} saccade`, 7.6, 1.2, 1.9, HEX.white);
  T(s, "Variations: camera · eyelid occlusion · noise · JPEG · motion blur · defocus", { x: 5.6, y: 2.25, w: 3.9, h: 0.5, fontSize: 11, color: HEX.grey });
  T(s, `${Object.keys(m1.failures).length + cov.failures} generation failures · integrity checks passed`, { x: 5.6, y: 2.8, w: 3.9, h: 0.3, fontSize: 13, bold: true, color: HEX.green });
  T(s, "Generation success is not detector accuracy.", { x: 0.5, y: 3.3, w: 9, h: 0.3, fontSize: 12, bold: true, color: HEX.amber });
  T(s, `Semantic masks remain provisional: ${(unc.unclassified_fraction_range[0] * 100).toFixed(1)}% of mask pixels unclassified.`, { x: 0.5, y: 3.65, w: 9, h: 0.3, fontSize: 11, color: HEX.amber });
  src(s, "ws6_dataset_v1/manifest.json + integrity.txt · ws4_dataset/coverage.json + integrity.json · ws3_masks/unclassified_audit.json"); }

// ------------------------------------------------------------------ 9 dynamics
{ const s = slide("Dynamic eye movement (rendered and measured)", "Results", "Rendered frames measured by the detector. These are simulation measurements, not human-subject data. Blinks are modelled as a closure curve but not rendered.");
  img(s, "saccade_stills.png", 0.5, 1.2, 4.5, 1.31, "Six frames of the rendered saccade with their timestamps");
  img(s, "vergence.png", 0.5, 2.65, 4.5, 0.86, "Vergence: first and last rendered frames as the target moves from 35 to 20 cm");
  panel(s, 5.3, 1.2, 4.2, 1.3);
  T(s, "SACCADE (5–95 % duration)", { x: 5.45, y: 1.28, w: 4, h: 0.25, fontSize: 11, bold: true, color: HEX.cyan });
  T(s, `image-left eye   ${N.sacL.toFixed(1)} ms\nimage-right eye  ${N.sacR.toFixed(1)} ms\ncommanded        ${N.sacCmd.toFixed(1)} ms\nframe interval   ${N.sacDt.toFixed(2)} ms`, { x: 5.45, y: 1.56, w: 4, h: 0.85, fontFace: "Courier New", fontSize: 11 });
  panel(s, 5.3, 2.55, 4.2, 0.85);
  T(s, "SMOOTH PURSUIT", { x: 5.45, y: 2.62, w: 4, h: 0.25, fontSize: 11, bold: true, color: HEX.cyan });
  T(s, `lag ≈ ${N.lag.toFixed(0)} ms (resolution ${N.lagRes.toFixed(1)} ms) · gain ≈ ${N.gainL.toFixed(2)} / ${N.gainR.toFixed(2)}`, { x: 5.45, y: 2.92, w: 4, h: 0.4, fontSize: 11 });
  T(s, `Vergence: both eyes move inward. Kept in the data: one ${N.glitch.toFixed(2)} px detector glitch in the image-right saccade. Blink: not rendered.`, { x: 5.3, y: 3.5, w: 4.2, h: 0.65, fontSize: 11, color: HEX.amber });
  src(s, "AUDIT/results/ws5_dynamics/dynamics_render_check.json · ws5_dynamics/dynamics_validation.json"); }

// ------------------------------------------------------------------ 10 rendering
{ const s = slide("Rendering optimisation: verify before adopting", "Results", "Every optimisation must reproduce the full render. Persistent scene data passes; eye-band (ROI) rendering fails and is not used.");
  const o = bench.configs.original, p = bench.configs.persistent;
  s.addChart(pres.charts.BAR, [{ name: "6-pose sequence (s)", labels: ["Full render", "Persistent data"], values: [o.sequence_s, p.sequence_s] }],
    Object.assign({}, chartBase, { x: 0.5, y: 1.2, w: 4.4, h: 2.4, barDir: "bar", chartColors: [HEX.green], valAxisMinVal: 0, dataLabelFormatCode: "0.0\" s\"",
      showTitle: true, title: "6-pose sequence at 128 spp (s)", titleColor: HEX.white, titleFontFace: "+mn-lt", titleFontSize: 12 }));
  T(s, `PERSISTENT SCENE DATA — PASSED: ${N.pers.toFixed(2)}× faster, pixels within ${N.persMax}/255`, { x: 0.5, y: 3.7, w: 4.4, h: 0.5, fontSize: 13, bold: true, color: HEX.green });
  panel(s, 5.2, 1.2, 4.3, 2.95, HEX.amber);
  T(s, "ROI (EYE-REGION) RENDERING —\nNOT ADOPTED", { x: 5.4, y: 1.35, w: 4.0, h: 0.6, fontSize: 13, bold: true, color: HEX.amber });
  T(s, [`difference up to ${N.roiIn}/255 inside the region`, `difference up to ${N.roiEdge}/255 at its edges`, "fails the equivalence test", "its faster timing is not claimed"].map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })),
    { x: 5.4, y: 2.05, w: 4.0, h: 1.6, fontSize: 13, paraSpaceAfter: 6 });
  src(s, "AUDIT/results/ws6_performance/bench_compare.json · ws6_performance/band_audit.json"); }

// ------------------------------------------------------------------ 11 limitations
{ const s = slide("Limitations", "Close", "Stated plainly so the results are read correctly.");
  const L = [["Pupil depth", "effective fitted parameters for this asset and detector, not anatomical measurements"],
             ["Corneal refraction", `official GT adds analytic refraction (${REFR[0].toFixed(2)}–${REFR[1].toFixed(2)} px) that the rendered Lens material does not produce`],
             ["Segmentation", `provisional: ${(unc.unclassified_fraction_range[0] * 100).toFixed(1)}% of mask pixels unclassified`],
             ["ROI rendering", "rejected after failing equivalence"],
             ["Legacy verifier", `unchanged; ${N.legP} PASS / ${N.legF} FAIL on the released bundle`],
             ["Scope", "one face asset, one detector, one machine; dynamics are simulations, blinks not rendered"]];
  L.forEach(([h, d], i) => { const y = 1.2 + i * 0.6; T(s, h, { x: 0.5, y, w: 2.2, h: 0.5, fontSize: 13, bold: true, color: HEX.amber }); T(s, d, { x: 2.8, y, w: 6.7, h: 0.5, fontSize: 12, color: HEX.white }); });
  src(s, "AUDIT/results/INTEGRATION_REPORT.md §10 · refraction range: research_pupil_levels.json (A apparent vs projected, from the released metadata)"); }

// ------------------------------------------------------------------ 12 future + conclusion
{ const s = slide("Future research and conclusion", "Close", "What would make the platform stronger, and the one-sentence takeaway.");
  const F2 = ["Add a pupil-level ground-truth field that matches the painted pupil, alongside the anatomical one", "Render masks with a true black background and resolve the remaining unclassified pixels",
              "More face assets and detectors; cross-hardware repeatability", "Fit eye-movement profiles to recorded human data; render blinks"];
  T(s, F2.map((t, i, a) => ({ text: t, options: { bullet: true, breakLine: i < a.length - 1 } })), { x: 0.5, y: 1.25, w: 5.2, h: 2.6, fontSize: 13, paraSpaceAfter: 8 });
  panel(s, 6.0, 1.25, 3.5, 2.6, HEX.cyan);
  T(s, "From synthetic eye rendering to scientifically validated gaze generation.", { x: 6.2, y: 1.45, w: 3.1, h: 1.4, fontSize: 18, bold: true });
  T(s, "Everything shown is reproducible from the release ZIP with research/verify_all.sh.", { x: 6.2, y: 2.95, w: 3.1, h: 0.8, fontSize: 11, color: HEX.grey });
  T(s, "Team Techtonic · VIT Chennai", { x: 0.5, y: 4.2, w: 9, h: 0.35, fontSize: 16, bold: true, color: HEX.cyan }); }

(async () => {
  const out = path.join(DEMO, "final_round_presentation.pptx");
  await pres.writeFile({ fileName: out }); await applyTheme(out, THEME);
  fs.writeFileSync(path.join(DEMO, "presentation_numbers.json"), JSON.stringify({ numbers: N, detector: det.map(([k, m]) => [k, m.success_rate]), checks: AGREED.map(([v, e, t]) => ({ value: v, agreed: e, tol: t })) }, null, 1));
  console.log("DECK_DONE", out);
})();
