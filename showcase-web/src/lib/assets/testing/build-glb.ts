/**
 * TEST FIXTURE BUILDER ONLY. Builds tiny synthetic GLB files (boxes and named nodes) to exercise the
 * validator. These are not characters and are never used as studio content.
 */

export interface FixtureOptions {
  headName?: string;
  uv?: boolean;
  morphNames?: string[] | null; // null = morphs without names
  morphCount?: number;
  textures?: boolean;
  normalMap?: boolean;
  eyes?: "centred" | "offset" | "bones" | "none";
  armature?: "facial" | "plain" | "none";
  clips?: string[];
  clipTargetsMorphs?: boolean;
  externalImage?: boolean;
}

const PNG_1PX = Uint8Array.from([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 31, 21, 196, 137, 0, 0, 0, 13, 73, 68, 65, 84, 120, 156, 99, 248, 15, 4, 0, 9, 251, 3, 253, 227, 85, 242, 156, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130]);

export function buildGlb(o: FixtureOptions = {}): ArrayBuffer {
  const opt: Required<FixtureOptions> = {
    headName: "Head",
    uv: true,
    morphNames: ["jawOpen", "browInnerUp"],
    morphCount: 2,
    textures: true,
    normalMap: true,
    eyes: "centred",
    armature: "facial",
    clips: ["gentle_smile"],
    clipTargetsMorphs: true,
    externalImage: false,
    ...o,
  };
  const chunks: Uint8Array[] = [];
  let byteOffset = 0;
  const views: Array<{ buffer: 0; byteOffset: number; byteLength: number }> = [];
  const accessors: Array<Record<string, unknown>> = [];
  const pushView = (bytes: Uint8Array) => {
    const pad = (4 - (bytes.byteLength % 4)) % 4;
    const b = new Uint8Array(bytes.byteLength + pad);
    b.set(bytes);
    views.push({ buffer: 0, byteOffset, byteLength: bytes.byteLength });
    chunks.push(b);
    byteOffset += b.byteLength;
    return views.length - 1;
  };
  const f32 = (data: number[], type: "VEC3" | "VEC2" | "SCALAR" | "VEC4" | "MAT4", minmax = false) => {
    const comps = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 }[type];
    const view = pushView(new Uint8Array(new Float32Array(data).buffer));
    const count = data.length / comps;
    const a: Record<string, unknown> = { bufferView: view, componentType: 5126, count, type };
    if (minmax) {
      a.min = Array.from({ length: comps }, (_, k) => Math.min(...data.filter((_, i) => i % comps === k)));
      a.max = Array.from({ length: comps }, (_, k) => Math.max(...data.filter((_, i) => i % comps === k)));
    }
    accessors.push(a);
    return accessors.length - 1;
  };
  const box = (cx: number, cy: number, cz: number, r: number) => [cx - r, cy - r, cz - r, cx + r, cy - r, cz - r, cx, cy + r, cz + r];

  const headPos = f32(box(0, 0, 0, 0.1), "VEC3", true);
  const attrs: Record<string, number> = { POSITION: headPos, NORMAL: f32([0, 0, 1, 0, 0, 1, 0, 0, 1], "VEC3") };
  if (opt.uv) attrs.TEXCOORD_0 = f32([0, 0, 1, 0, 0, 1], "VEC2");
  if (opt.armature !== "none") {
    attrs.JOINTS_0 = f32([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], "VEC4");
    attrs.WEIGHTS_0 = f32([1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0], "VEC4");
  }
  const targets = Array.from({ length: opt.morphCount }, () => ({ POSITION: f32([0, 0, 0.01, 0, 0, 0.01, 0, 0, 0.01], "VEC3", true) }));

  const images: Array<Record<string, unknown>> = [];
  const textures: Array<Record<string, unknown>> = [];
  const material: Record<string, unknown> = { name: "Skin", pbrMetallicRoughness: {} };
  if (opt.textures) {
    images.push(opt.externalImage ? { uri: "skin_albedo.png", name: "skin_albedo" } : { bufferView: pushView(PNG_1PX), mimeType: "image/png", name: "skin_albedo" });
    textures.push({ source: 0, name: "skin_albedo" });
    (material.pbrMetallicRoughness as Record<string, unknown>).baseColorTexture = { index: 0 };
    if (opt.normalMap) {
      images.push({ bufferView: pushView(PNG_1PX), mimeType: "image/png", name: "skin_normal" });
      textures.push({ source: 1, name: "skin_normal" });
      material.normalTexture = { index: 1 };
    }
  }

  const nodes: Array<Record<string, unknown>> = [];
  const meshes: Array<Record<string, unknown>> = [];
  const headMesh: Record<string, unknown> = { name: opt.headName, primitives: [{ attributes: attrs, material: 0, ...(opt.morphCount ? { targets } : {}) }] };
  if (opt.morphCount && opt.morphNames) headMesh.extras = { targetNames: opt.morphNames };
  meshes.push(headMesh);
  nodes.push({ name: opt.headName, mesh: 0, ...(opt.armature !== "none" ? { skin: 0 } : {}) });
  const sceneNodes = [0];

  if (opt.eyes === "centred" || opt.eyes === "offset") {
    for (const [side, x] of [["L", 0.03], ["R", -0.03]] as const) {
      const c = opt.eyes === "centred" ? 0 : 0.008;
      const eyePos = f32(box(c, c, c, 0.012), "VEC3", true);
      meshes.push({ name: `Eye_${side}`, primitives: [{ attributes: { POSITION: eyePos } }] });
      nodes.push({ name: `Eye_${side}`, mesh: meshes.length - 1, translation: [x, 0.03, 0.06] });
      sceneNodes.push(nodes.length - 1);
    }
  }

  const skins: Array<Record<string, unknown>> = [];
  if (opt.armature !== "none") {
    const names = opt.armature === "facial" ? ["root", "head", "jaw", ...(opt.eyes === "bones" ? ["eye.L", "eye.R"] : [])] : ["root", "spine", "arm"];
    const first = nodes.length;
    names.forEach((n, i) => nodes.push({ name: n, ...(i < names.length - 1 && i < 1 ? { children: names.slice(1).map((_, k) => first + 1 + k) } : {}) }));
    skins.push({ name: "Armature", joints: names.map((_, i) => first + i), inverseBindMatrices: f32(names.flatMap(() => [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]), "MAT4") });
    sceneNodes.push(first);
  }

  const animations = opt.clips.map((name) => {
    const input = f32([0, 0.5, 1], "SCALAR", true);
    if (opt.clipTargetsMorphs && opt.morphCount) {
      const output = f32(Array.from({ length: 3 * opt.morphCount }, (_, i) => (i >= opt.morphCount && i < 2 * opt.morphCount ? 1 : 0)), "SCALAR");
      return { name, samplers: [{ input, output }], channels: [{ sampler: 0, target: { node: 0, path: "weights" } }] };
    }
    const output = f32([0, 0, 0, 0, 0, 1, 0, 0, 0], "VEC3");
    return { name, samplers: [{ input, output }], channels: [{ sampler: 0, target: { node: 0, path: "translation" } }] };
  });

  const bin = new Uint8Array(byteOffset);
  let p = 0;
  for (const c of chunks) {
    bin.set(c, p);
    p += c.byteLength;
  }
  const json = {
    asset: { version: "2.0", generator: "validator test fixture" },
    scene: 0,
    scenes: [{ nodes: sceneNodes }],
    nodes,
    meshes,
    materials: [material],
    ...(images.length ? { images, textures } : {}),
    ...(skins.length ? { skins } : {}),
    ...(animations.length ? { animations } : {}),
    accessors,
    bufferViews: views,
    buffers: [{ byteLength: bin.byteLength }],
  };
  let jsonBytes = new TextEncoder().encode(JSON.stringify(json));
  const jpad = (4 - (jsonBytes.byteLength % 4)) % 4;
  if (jpad) {
    const j = new Uint8Array(jsonBytes.byteLength + jpad).fill(0x20);
    j.set(jsonBytes);
    jsonBytes = j;
  }
  const total = 12 + 8 + jsonBytes.byteLength + 8 + bin.byteLength;
  const out = new ArrayBuffer(total);
  const dv = new DataView(out);
  dv.setUint32(0, 0x46546c67, true);
  dv.setUint32(4, 2, true);
  dv.setUint32(8, total, true);
  dv.setUint32(12, jsonBytes.byteLength, true);
  dv.setUint32(16, 0x4e4f534a, true);
  new Uint8Array(out, 20, jsonBytes.byteLength).set(jsonBytes);
  const o2 = 20 + jsonBytes.byteLength;
  dv.setUint32(o2, bin.byteLength, true);
  dv.setUint32(o2 + 4, 0x004e4942, true);
  new Uint8Array(out, o2 + 8, bin.byteLength).set(bin);
  return out;
}
