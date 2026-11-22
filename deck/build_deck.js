// Builds deck/VIT_Chennai_Techtonic.pptx (Samsung PRISM XR Hackathon 2026, Track 1).
// Run: NODE_PATH=<dir containing pptxgenjs> node deck/build_deck.js
// Every image is a real render from this repository; every number comes from validation/VALIDATION.md.
const path = require("path");
const pptxgen = require("pptxgenjs");
const { applyTheme } = require(process.env.APPLY_THEME);

const ROOT = path.resolve(__dirname, "..");
const IMG = {
  hero: path.join(ROOT, "renders/frame_00.png"),
  overview: path.join(ROOT, "demo/phase2h/demo_assets/scene/overview.png"),
  cutaway: path.join(ROOT, "demo/phase2h/demo_assets/scene/eyes_cutaway.png"),
  contact: path.join(ROOT, "contact_sheet.png"),
  dirs: path.join(ROOT, "validation/five_directions_zoom3x.png"),
  closing: path.join(__dirname, "assets/closing_eye.png"),
};

const THEME = {
  name: "Techtonic Gaze",
  headFontFace: "Calibri",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "0F2326", lt1: "FFFFFF", dk2: "1C3A3E", lt2: "CFE3DF",
    accent1: "9EE6A8", accent2: "E8A85A", accent3: "F2B8D0", accent4: "7CC4D6", accent5: "5E8A8F", accent6: "2A4A4E",
    hlink: "9EE6A8", folHlink: "7CC4D6",
  },
};
const HEX = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10 x 5.625 in
pres.title = "Synthetic Eye Movement & Virtual Camera Rendering";
pres.author = "Team Techtonic, VIT Chennai";
pres.company = "Team Techtonic";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.35, w: 5.2, h: 1.9, fontSize: 36, bold: true, color: C.background1, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.35, w: 5.2, h: 1.4, fontSize: 16, color: C.background2, valign: "top", align: "left" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT_DARK",
  background: { color: HEX.dk1 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9.0, h: 0.75, fontSize: 30, bold: true, color: C.background1, valign: "middle", margin: 0 }, text: "" } },
    { text: { text: "Team Techtonic · VIT Chennai · Track 1", options: { x: 0.5, y: 5.22, w: 5, h: 0.25, fontSize: 10, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 9.1, y: 5.2, w: 0.4, h: 0.28, fontSize: 10, color: C.accent5, align: "right" },
});

let n = 0;
const section = (t) => pres.addSection({ title: t });
const content = (sec, title, notes) => {
  const s = pres.addSlide({ masterName: "CONTENT_DARK", sectionTitle: sec });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  n += 1;
  return s;
};
const card = (s, x, y, w, h, name) =>
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.text2 }, line: { color: C.text2 }, objectName: name });
const txt = (s, t, o) => s.addText(t, Object.assign({ isTextBox: true, margin: 0, color: C.background1, fontSize: 14, valign: "top" }, o));
const badge = (s, x, y, label, col, name) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.46, h: 0.46, fill: { color: col }, line: { color: col }, objectName: name });
  txt(s, label, { x, y, w: 0.46, h: 0.46, fontSize: 16, bold: true, color: C.text1, align: "center", valign: "middle" });
};

// ---------- 1. Title ----------
section("Opening");
{
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Opening" });
  s.addImage({ path: IMG.hero, x: 6.05, y: 0, w: 3.95, h: 5.625, sizing: { type: "cover", w: 3.95, h: 5.625 }, altText: "Packaged render frame 0: the textured face looking up", objectName: "hero" });
  s.addText("Synthetic Eye Movement & Virtual Camera Rendering", { placeholder: "title" });
  s.addText([
    { text: "Samsung PRISM XR Hackathon 2026 · Track 1", options: { breakLine: true } },
    { text: "Team Techtonic · Vellore Institute of Technology, Chennai", options: { breakLine: true } },
    { text: "Sahana S · Karthik B", options: { color: C.accent1 } },
  ], { placeholder: "body" });
  s.addNotes("We are Team Techtonic from VIT Chennai. Our Track 1 entry is a calibrated, scriptable synthetic-eye renderer in Blender that produces gaze images with exact ground truth.");
}

// ---------- 2. Problem ----------
section("Problem and approach");
{
  const s = content("Problem and approach", "Gaze models need data that is hard to collect",
    "Real gaze datasets are slow, expensive and privacy-restricted, especially at extreme angles. Synthetic rendering removes all three problems, provided the geometry and the labels are exactly right. That is what we optimised for.");
  const items = [
    ["1", "Slow and costly", "Capturing real eyes across many gaze angles needs rigs, subjects and hours of annotation.", C.accent2],
    ["2", "Privacy-restricted", "Eye images are biometric data; collecting and sharing them is tightly regulated.", C.accent3],
    ["3", "Labels are noisy", "Hand-labelled pupil centres drift by pixels; a renderer can know them exactly.", C.accent4],
  ];
  items.forEach(([k, h, b, col], i) => {
    const x = 0.5 + i * 3.05;
    card(s, x, 1.35, 2.85, 2.55, "problem_card_" + k);
    badge(s, x + 0.25, 1.6, k, col, "problem_badge_" + k);
    txt(s, h, { x: x + 0.25, y: 2.22, w: 2.4, h: 0.4, fontSize: 18, bold: true });
    txt(s, b, { x: x + 0.25, y: 2.67, w: 2.4, h: 1.15, fontSize: 14, color: C.background2 });
  });
  txt(s, [{ text: "Our answer: ", options: { bold: true, color: C.accent1 } }, { text: "a textured face whose eyes rotate like real eyes, rendered by a locked camera, with sub-pixel ground truth for every frame." }],
    { x: 0.5, y: 4.2, w: 9.0, h: 0.75, fontSize: 16 });
}

// ---------- 3. Pipeline ----------
{
  const s = content("Problem and approach", "One command from rig to labelled dataset",
    "The pipeline has four stages. The evaluator only runs one command: blender -b scene.blend -P wrapper/eyes.py. Everything else is packed in the scene file.");
  const steps = [
    ["Face rig", "Textured CC0 head with left / right eye bones and anatomical eyeballs"],
    ["eyes.py API", "move(h, v), reset(), render(); inputs clamped to [-1, 1]"],
    ["Locked camera", "Locked 40 cm ahead, fixation 35 cm, constant studio light"],
    ["Data out", "1024² PNG frames plus metadata.json with 2D and 3D ground truth"],
  ];
  steps.forEach(([h, b], i) => {
    const x = 0.5 + i * 2.3;
    card(s, x, 1.55, 2.05, 2.4, "step_card_" + i);
    badge(s, x + 0.2, 1.78, String(i + 1), C.accent1, "step_badge_" + i);
    txt(s, h, { x: x + 0.2, y: 2.38, w: 1.75, h: 0.35, fontSize: 16, bold: true });
    txt(s, b, { x: x + 0.2, y: 2.82, w: 1.7, h: 1.05, fontSize: 13, color: C.background2 });
  });
  txt(s, [{ text: "blender -b scene.blend -P wrapper/eyes.py", options: { fontFace: "Courier New", color: C.accent1 } }],
    { x: 0.5, y: 4.3, w: 9.0, h: 0.4, fontSize: 15 });
}

// ---------- 4. Calibration ----------
section("How it works");
{
  const s = content("How it works", "The scene is calibrated in metres, not by eye",
    "Side view of the real scene. The camera sits 40 cm in front of the eye midpoint and the fixation target 35 cm in front, moving within plus or minus 5 cm. The checker measures these values from the files: 0.40 m and 0.35 m.");
  s.addImage({ path: IMG.overview, x: 0.5, y: 1.25, w: 5.6, h: 3.15, altText: "Side view: head, fixation target and camera with sight lines", objectName: "overview" });
  const stats = [["40 cm", "camera to eye midpoint"], ["35 cm", "fixation target, ±5 cm"], ["1024²", "PNG, constant lighting"]];
  stats.forEach(([v, l], i) => {
    txt(s, v, { x: 6.5, y: 1.2 + i * 1.08, w: 3.0, h: 0.6, fontSize: 36, bold: true, color: C.accent1 });
    txt(s, l, { x: 6.5, y: 1.78 + i * 1.08, w: 3.0, h: 0.35, fontSize: 13, color: C.background2 });
  });
  txt(s, "Measured by our independent checker: camera 0.40 m, fixation 0.35 m.", { x: 0.5, y: 4.55, w: 9.0, h: 0.35, fontSize: 13, color: C.background2, italic: true });
}

// ---------- 5. Anatomy ----------
{
  const s = content("How it works", "Eyes that move like real eyes",
    "Each eyeball rotates in 3D about its own centre, so the two eyes converge on the target and turn by different amounts. The cornea refracts the pupil, and we record both the refracted and unrefracted pupil centres. The eyelids follow vertical gaze.");
  s.addImage({ path: IMG.cutaway, x: 4.4, y: 1.25, w: 5.1, h: 2.87, altText: "Cutaway: both eyeballs with gaze axes converging", objectName: "cutaway" });
  const pts = [
    ["True 3D rotation", "about each eyeball's centre, not 2D pupil sliding"],
    ["Convergence", "both eyes aim at the same fixation point"],
    ["Corneal refraction", "refracted and raw pupil centres in metadata"],
    ["Lids follow gaze", "upper lid tracks up and down movement"],
  ];
  pts.forEach(([h, b], i) => {
    const y = 1.3 + i * 0.85;
    s.addShape(pres.shapes.OVAL, { x: 0.5, y: y + 0.07, w: 0.18, h: 0.18, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "dot_" + i });
    txt(s, h, { x: 0.85, y, w: 3.4, h: 0.32, fontSize: 16, bold: true });
    txt(s, b, { x: 0.85, y: y + 0.33, w: 3.4, h: 0.45, fontSize: 13, color: C.background2 });
  });
}

// ---------- 6. Automation ----------
{
  const s = content("How it works", "A small, strict API",
    "Three calls do everything. Inputs outside minus one to one are clamped and non-numbers are rejected. The command line picks Metal, OptiX, CUDA, HIP or oneAPI automatically and falls back to the CPU.");
  card(s, 0.5, 1.3, 5.0, 3.3, "code_card");
  txt(s, [
    { text: "import eyes", options: { breakLine: true } },
    { text: "eyes.move(0.5, -0.3)  # h, v", options: { breakLine: true } },
    { text: "eyes.render(\"frame.png\")", options: { breakLine: true } },
    { text: "eyes.reset()", options: { breakLine: true } },
    { text: " ", options: { breakLine: true } },
    { text: "# full 10-frame sequence + metadata", options: { breakLine: true, color: C.accent5 } },
    { text: "blender -b scene.blend \\", options: { breakLine: true } },
    { text: "  -P wrapper/eyes.py" },
  ], { x: 0.75, y: 1.55, w: 4.6, h: 2.9, fontFace: "Courier New", fontSize: 14, color: C.accent1 });
  const feats = [
    ["No setup", "All textures packed; no add-ons"],
    ["Any device", "GPU auto-detect, CPU fallback"],
    ["Deterministic", "Re-run gives bit-identical metadata"],
  ];
  feats.forEach(([h, b], i) => {
    const y = 1.35 + i * 1.1;
    badge(s, 5.9, y, "✓", C.accent1, "feat_badge_" + i);
    txt(s, h, { x: 6.55, y, w: 3.0, h: 0.35, fontSize: 17, bold: true });
    txt(s, b, { x: 6.55, y: y + 0.38, w: 3.0, h: 0.4, fontSize: 13, color: C.background2 });
  });
}

// ---------- 7. Results ----------
section("Results");
{
  const s = content("Results", "The ten clockwise frames",
    "These are the ten packaged frames: theta k equals 2 pi k over 10, h equals sine theta, v equals cosine theta, starting at the top and running clockwise on screen.");
  const w = 4.9, h = w * 976 / 1320;
  s.addImage({ path: IMG.contact, x: 0.5, y: 1.2, w, h, altText: "Contact sheet of the ten packaged clockwise frames", objectName: "contact" });
  card(s, 5.75, 1.2, 3.75, 3.0, "seq_card");
  txt(s, "Sequence", { x: 6.0, y: 1.4, w: 2.4, h: 0.35, fontSize: 17, bold: true });
  txt(s, [
    { text: "θk = 2πk / 10, k = 0…9", options: { breakLine: true } },
    { text: "h = sin θk,  v = cos θk", options: { breakLine: true } },
    { text: "Starts at the top", options: { breakLine: true } },
    { text: "Clockwise on screen" },
  ], { x: 6.0, y: 1.85, w: 3.3, h: 1.6, fontSize: 14, color: C.background2, paraSpaceAfter: 6 });
  txt(s, "Verified: order and clockwise motion", { x: 6.0, y: 3.6, w: 3.3, h: 0.45, fontSize: 13, color: C.accent1, bold: true });
}

// ---------- 8. Five directions ----------
{
  const s = content("Results", "All five directions pass, measured in pixels",
    "Left, right, up, down and reset, rendered through the shipped wrapper. The pupils were detected in the rendered pixels, not taken from our metadata. Red marks the reset pupil, green the moved pupil, shown at 3 times zoom. The brief's plus or minus 5 centimetre bound limits the shift to about 9 pixels for every team.");
  s.addImage({ path: IMG.dirs, x: 0.5, y: 1.2, w: 9.0, h: 9.0 * 875 / 3350, altText: "Five-direction sheet at 3x zoom with reset and moved pupil markers", objectName: "dirs" });
  const rows = [
    [{ text: "Direction", options: { bold: true, color: C.text1, fill: { color: C.accent1 } } }, { text: "Left eye", options: { bold: true, color: C.text1, fill: { color: C.accent1 } } }, { text: "Right eye", options: { bold: true, color: C.text1, fill: { color: C.accent1 } } }, { text: "Result", options: { bold: true, color: C.text1, fill: { color: C.accent1 } } }],
    ["Left", "8.1 px", "8.9 px", "PASS"], ["Right", "8.6 px", "8.0 px", "PASS"], ["Up", "8.0 px", "7.8 px", "PASS"],
    ["Down", "9.8 px", "9.6 px", "PASS"], ["Reset", "0.61 px off centre", "0.67 px", "PASS"],
  ];
  s.addTable(rows, { x: 0.5, y: 3.65, w: 9.0, colW: [2.0, 2.6, 2.6, 1.8], rowH: 0.24, fontSize: 11, color: C.background1, fill: { color: C.text2 }, border: { type: "solid", pt: 0.5, color: HEX.dk1 }, margin: 0.03 });
}

// ---------- 9. Proof ----------
section("Proof");
{
  const s = content("Proof", "Sub-pixel ground truth, independently checked",
    "Our checker never imports the wrapper. It finds each pupil in the rendered image and compares it with the metadata. Across all twenty pupils the error is at most 1.18 pixels on a 1024 pixel image. Camera matrices reproject to within a thousandth of a pixel. A fresh re-run produced bit-identical metadata.");
  const err = { L: [0.67, 0.55, 0.90, 0.31, 0.51, 1.00, 0.85, 1.07, 0.91, 0.89], R: [0.90, 1.18, 1.01, 0.88, 0.80, 0.96, 0.39, 0.16, 0.71, 0.16] };
  const labels = err.L.map((_, i) => "F" + i);
  s.addChart(pres.charts.BAR, [{ name: "Left eye", labels, values: err.L }, { name: "Right eye", labels, values: err.R }], {
    x: 0.5, y: 1.2, w: 5.6, h: 3.6, barDir: "col", barGrouping: "clustered",
    showTitle: true, title: "Rendered pupil vs metadata (px)", titleColor: HEX.lt1, titleFontSize: 13, titleFontFace: "+mn-lt",
    chartColors: [HEX.accent1, HEX.accent2], showLegend: true, legendPos: "b", legendColor: HEX.lt2, legendFontFace: "+mn-lt", legendFontSize: 11,
    catAxisLabelColor: HEX.lt2, valAxisLabelColor: HEX.lt2, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
    valAxisMinVal: 0, valAxisMaxVal: 1.5, valAxisMajorUnit: 0.5, valGridLine: { color: HEX.accent6, size: 0.75 }, catGridLine: { style: "none" },
    catAxisLineShow: false, valAxisLineShow: false,
  });
  const stats = [["71 / 71", "independent checks pass"], ["≤ 1.18 px", "pupil error, 20 pupils"], ["0.001 px", "camera reprojection"], ["0 diffs", "metadata on re-run (642 values)"]];
  stats.forEach(([v, l], i) => {
    const y = 1.2 + i * 0.92;
    txt(s, v, { x: 6.5, y, w: 3.0, h: 0.5, fontSize: 28, bold: true, color: i === 1 ? C.accent2 : C.accent1 });
    txt(s, l, { x: 6.5, y: y + 0.5, w: 3.0, h: 0.3, fontSize: 12, color: C.background2 });
  });
}

// ---------- 10. Metadata ----------
{
  const s = content("Proof", "Ground truth a gaze model can train on",
    "Every frame records the inputs, the eye rotations as Euler angles and quaternions, the 2D and 3D pupil centres with and without corneal refraction, the fixation target, and the full camera intrinsics and extrinsics. That goes beyond the brief and makes the output usable as training data.");
  card(s, 0.5, 1.25, 4.9, 3.55, "json_card");
  txt(s, [
    { text: "{ \"frame\": 3,", options: { breakLine: true } },
    { text: "  \"theta\": 1.885,", options: { breakLine: true } },
    { text: "  \"input\": { \"h\": 0.951, \"v\": -0.309 },", options: { breakLine: true } },
    { text: "  \"eye_rotation_L\": [-5.56, -0.29, -0.40],", options: { breakLine: true } },
    { text: "  \"pupil_center_2D_L\": [644.94, 515.13],", options: { breakLine: true } },
    { text: "  \"pupil_center_2D_R\": [395.61, 515.07],", options: { breakLine: true } },
    { text: "  \"camera_matrix\": [[1706.7, 0, 512], …]", options: { breakLine: true } },
    { text: "}" },
  ], { x: 0.7, y: 1.45, w: 4.6, h: 3.2, fontFace: "Courier New", fontSize: 12, color: C.accent1 });
  txt(s, "Required by the brief", { x: 5.8, y: 1.3, w: 3.7, h: 0.35, fontSize: 16, bold: true });
  txt(s, "frame, theta, input h/v, eye_rotation_L/R, pupil_center_2D_L/R, camera_matrix", { x: 5.8, y: 1.68, w: 3.7, h: 0.75, fontSize: 13, color: C.background2 });
  txt(s, "Added by us", { x: 5.8, y: 2.6, w: 3.7, h: 0.35, fontSize: 16, bold: true, color: C.accent1 });
  txt(s, [
    { text: "Quaternions for both eyes", options: { bullet: true, breakLine: true } },
    { text: "3D pupil centres, with and without cornea", options: { bullet: true, breakLine: true } },
    { text: "Fixation target position", options: { bullet: true, breakLine: true } },
    { text: "Camera extrinsics [R|t]", options: { bullet: true } },
  ], { x: 5.8, y: 2.98, w: 3.7, h: 1.6, fontSize: 13, color: C.background2, paraSpaceAfter: 4 });
}

// ---------- 11. Limitations ----------
section("Closing");
{
  const s = content("Closing", "Known limits and what comes next",
    "We list our limits openly. The scene is tested on Blender 5.3. A full run takes minutes on a GPU and longer on a CPU, so the README gives a faster samples option. The brief asks for one face, one light and one camera; scaling identities, lighting and camera poses is the natural next step for a training dataset.");
  const lim = [
    ["Blender 5.3 only", "Built and tested on 5.3.0; stated in the README"],
    ["Render time", "6–14 min on GPU; --samples 128 is faster"],
    ["Small shift", "±5 cm bound gives about 9 px; shown zoomed"],
  ];
  const next = [
    ["More identities", "Vary faces, skin, iris colour"],
    ["Lighting and pose", "Randomised light and head pose"],
    ["Dense sweeps", "Hundreds of gaze directions per run"],
  ];
  txt(s, "Limits", { x: 0.5, y: 1.25, w: 4.3, h: 0.35, fontSize: 18, bold: true, color: C.accent2 });
  txt(s, "Next", { x: 5.2, y: 1.25, w: 4.3, h: 0.35, fontSize: 18, bold: true, color: C.accent1 });
  [[lim, 0.5], [next, 5.2]].forEach(([arr, x]) => arr.forEach(([h, b], i) => {
    const y = 1.75 + i * 1.0;
    card(s, x, y, 4.3, 0.85, "lim_card_" + x + "_" + i);
    txt(s, h, { x: x + 0.2, y: y + 0.1, w: 3.9, h: 0.32, fontSize: 15, bold: true });
    txt(s, b, { x: x + 0.2, y: y + 0.44, w: 3.9, h: 0.32, fontSize: 13, color: C.background2 });
  }));
}

// ---------- 12. Summary ----------
{
  const s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Closing" });
  s.addShape(pres.shapes.RECTANGLE, { x: 6.05, y: 0, w: 3.95, h: 5.625, fill: { color: "1C3A3E" }, line: { color: "1C3A3E" }, objectName: "closing_panel" });
  s.addImage({ path: IMG.closing, x: 6.35, y: 0, w: 3.645, h: 5.625, altText: "Anatomical eyeball with its gaze axis", objectName: "closing_eye" });
  s.addText("Real eye geometry, exact labels, proven", { placeholder: "title" });
  s.addText([
    { text: "5 / 5 directions · 71 / 71 checks · ≤ 1.18 px", options: { breakLine: true, color: C.accent1, bold: true } },
    { text: "One command, deterministic, ready to scale", options: { breakLine: true } },
    { text: "Thank you · Team Techtonic, VIT Chennai" },
  ], { placeholder: "body" });
  s.addNotes("In summary: eyes that rotate like real eyes, calibrated in metres, with sub-pixel ground truth that an independent checker verifies. Thank you.");
}

(async () => {
  const out = path.join(__dirname, "VIT_Chennai_Techtonic.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("WROTE", out);
})();
