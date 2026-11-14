/**
 * Structural compatibility validator for glTF 2.0 character files (.glb, or .gltf with embedded data).
 *
 * It reads the file's own JSON and binary chunk; it does not render anything. Each check reports what
 * the file actually declares, with evidence. Passing every check means the file is STRUCTURALLY ready
 * for the studio. It does not mean the character looks right or that its expressions are good: that
 * needs a visual review. A file that merely loads is never reported as compatible.
 */

import { EXPRESSION_IDS } from "@/data/expressions";

export type CheckStatus = "pass" | "warn" | "fail" | "info";

export interface Check {
  id: "container" | "resources" | "head" | "uv" | "materials" | "armature" | "morphs" | "eyes" | "clips";
  label: string;
  status: CheckStatus;
  detail: string;
  evidence: string[];
}

export interface MeshInfo {
  name: string;
  nodes: string[];
  vertexCount: number;
  primitives: number;
  uvSets: string[];
  hasNormals: boolean;
  morphTargets: string[];
  morphCount: number;
  skinned: boolean;
  materials: string[];
}

export interface TextureInfo {
  name: string;
  mimeType: string;
  bytes: number | null;
  source: "embedded" | "data-uri" | "external";
  usedBy: string[];
}

export interface BoneInfo {
  name: string;
  parent: string | null;
  facial: boolean;
}

export interface EyeInfo {
  name: string;
  kind: "node" | "joint";
  /** Distance from the node origin (pivot) to the eye mesh's bounding-box centre, millimetres. */
  pivotOffsetMm: number | null;
  radiusMm: number | null;
  pivotCentred: boolean | null;
}

export interface ClipInfo {
  name: string;
  durationS: number;
  channels: number;
  morphChannels: number;
  facialBoneChannels: number;
  otherChannels: number;
  facial: boolean;
  expressionId: string | null;
}

export type Verdict = "not-compatible" | "partially-ready" | "structurally-ready";

export interface AssetReport {
  fileName: string;
  fileSize: number;
  container: "glb" | "gltf" | "unknown";
  generator: string | null;
  checks: Check[];
  meshes: MeshInfo[];
  headMesh: string | null;
  materials: Array<{ name: string; maps: string[]; extensions: string[] }>;
  textures: TextureInfo[];
  bones: BoneInfo[];
  eyes: EyeInfo[];
  clips: ClipInfo[];
  expressionCoverage: { matched: string[]; unmatchedClips: string[] };
  extensionsUsed: string[];
  verdict: Verdict;
  verdictText: string;
}

const FACIAL_WORDS = /(jaw|eye|lid|brow|lip|mouth|cheek|nose|nostril|tongue|teeth|chin|oris|orbicular|levator|risorius|oculi|zygom|corrugator|frontalis|mentalis|buccinator|platysma|face|facial)/i;
const EYE_WORDS = /(^|[^a-z])(eye|eyeball|eye_?ball|iris|pupil|cornea|sclera)/i;
const HEAD_WORDS = /(head|face)/i;

// ------------------------------------------------------------------ container

interface Gltf {
  asset?: { version?: string; generator?: string };
  scenes?: Array<{ nodes?: number[] }>;
  nodes?: Array<{ name?: string; mesh?: number; skin?: number; children?: number[]; translation?: number[]; rotation?: number[]; scale?: number[]; matrix?: number[] }>;
  meshes?: Array<{ name?: string; extras?: { targetNames?: unknown }; primitives: Array<{ attributes: Record<string, number>; targets?: Array<Record<string, number>>; material?: number }> }>;
  accessors?: Array<{ count: number; min?: number[]; max?: number[]; type?: string }>;
  materials?: Array<{ name?: string; pbrMetallicRoughness?: Record<string, unknown>; normalTexture?: unknown; occlusionTexture?: unknown; emissiveTexture?: unknown; extensions?: Record<string, unknown> }>;
  textures?: Array<{ name?: string; source?: number; extensions?: Record<string, { source?: number }> }>;
  images?: Array<{ name?: string; uri?: string; mimeType?: string; bufferView?: number }>;
  bufferViews?: Array<{ byteLength: number }>;
  buffers?: Array<{ uri?: string; byteLength: number }>;
  skins?: Array<{ name?: string; joints: number[]; skeleton?: number }>;
  animations?: Array<{ name?: string; channels: Array<{ sampler: number; target: { node?: number; path: string } }>; samplers: Array<{ input: number }> }>;
  extensionsUsed?: string[];
  extensionsRequired?: string[];
}

export interface Container {
  kind: "glb" | "gltf";
  json: Gltf;
}

export class ContainerError extends Error {}

export function readContainer(fileName: string, buf: ArrayBuffer): Container {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".blend")) throw new ContainerError("Blender .blend files cannot be read in the browser. Export the character from Blender as glTF 2.0 binary (.glb); see the Blender export guide.");
  const view = new DataView(buf);
  if (buf.byteLength >= 12 && view.getUint32(0, true) === 0x46546c67) {
    const version = view.getUint32(4, true);
    if (version !== 2) throw new ContainerError(`GLB version ${version} is not supported (glTF 2.0 is required).`);
    const length = view.getUint32(8, true);
    if (length > buf.byteLength) throw new ContainerError("The GLB file is truncated.");
    let off = 12;
    let json: Gltf | null = null;
    while (off + 8 <= length) {
      const chunkLen = view.getUint32(off, true);
      const type = view.getUint32(off + 4, true);
      const start = off + 8;
      if (start + chunkLen > length) throw new ContainerError("A GLB chunk runs past the end of the file.");
      if (type === 0x4e4f534a) json = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, start, chunkLen))) as Gltf;
      off = start + chunkLen;
    }
    if (!json) throw new ContainerError("The GLB file has no JSON chunk.");
    return { kind: "glb", json };
  }
  if (lower.endsWith(".gltf") || lower.endsWith(".json")) {
    try {
      return { kind: "gltf", json: JSON.parse(new TextDecoder().decode(buf)) as Gltf };
    } catch (e) {
      throw new ContainerError(`Not valid glTF JSON: ${(e as Error).message}`);
    }
  }
  throw new ContainerError("Unsupported file. Import a glTF 2.0 file: .glb (recommended) or .gltf with embedded data.");
}

// ------------------------------------------------------------------ inspection

const nm = (s: string | undefined, fallback: string) => (s && s.trim() ? s : fallback);

export function inspectGltf(fileName: string, buf: ArrayBuffer): AssetReport {
  const base: AssetReport = {
    fileName,
    fileSize: buf.byteLength,
    container: "unknown",
    generator: null,
    checks: [],
    meshes: [],
    headMesh: null,
    materials: [],
    textures: [],
    bones: [],
    eyes: [],
    clips: [],
    expressionCoverage: { matched: [], unmatchedClips: [] },
    extensionsUsed: [],
    verdict: "not-compatible",
    verdictText: "",
  };
  let c: Container;
  try {
    c = readContainer(fileName, buf);
  } catch (e) {
    base.checks.push({ id: "container", label: "File container", status: "fail", detail: (e as Error).message, evidence: [] });
    base.verdictText = "The file could not be read as glTF 2.0.";
    return base;
  }
  const g = c.json;
  const r: AssetReport = { ...base, container: c.kind, generator: g.asset?.generator ?? null, extensionsUsed: g.extensionsUsed ?? [] };
  const checks = r.checks;

  const ver = g.asset?.version ?? "";
  checks.push(
    ver.startsWith("2")
      ? { id: "container", label: "File container", status: "pass", detail: `glTF ${ver} (${c.kind.toUpperCase()})`, evidence: [g.asset?.generator ? `Generator: ${g.asset.generator}` : "No generator recorded"] }
      : { id: "container", label: "File container", status: "fail", detail: `asset.version is "${ver || "missing"}"; glTF 2.0 is required.`, evidence: [] },
  );

  // external resources
  const ext: string[] = [];
  (g.buffers ?? []).forEach((b, i) => {
    if (b.uri && !b.uri.startsWith("data:")) ext.push(`buffer ${i}: ${b.uri}`);
    if (!b.uri && c.kind === "gltf") ext.push(`buffer ${i}: no data`);
  });
  (g.images ?? []).forEach((im, i) => {
    if (im.uri && !im.uri.startsWith("data:")) ext.push(`image ${i}: ${im.uri}`);
  });
  checks.push(
    ext.length
      ? { id: "resources", label: "Embedded resources", status: "fail", detail: "The file references external files that cannot be loaded from a single upload. Export as .glb (everything embedded).", evidence: ext.slice(0, 12) }
      : { id: "resources", label: "Embedded resources", status: "pass", detail: "All buffers and images are embedded.", evidence: [] },
  );
  const required = (g.extensionsRequired ?? []).filter((e) => !["KHR_materials_emissive_strength", "KHR_texture_transform", "KHR_mesh_quantization", "KHR_materials_ior", "KHR_materials_specular", "KHR_materials_volume", "KHR_materials_transmission", "KHR_materials_clearcoat", "KHR_materials_sheen"].includes(e));
  if (required.length) checks[checks.length - 1] = { ...checks[checks.length - 1], status: "fail", detail: `${checks[checks.length - 1].detail} Required extensions the studio does not handle: ${required.join(", ")}.` };

  // nodes and parents
  const nodes = g.nodes ?? [];
  const parent = new Map<number, number>();
  nodes.forEach((n, i) => (n.children ?? []).forEach((ch) => parent.set(ch, i)));
  const nodeName = (i: number) => nm(nodes[i]?.name, `node ${i}`);

  // meshes
  const acc = g.accessors ?? [];
  const matName = (i: number | undefined) => (i === undefined ? "(default)" : nm(g.materials?.[i]?.name, `material ${i}`));
  r.meshes = (g.meshes ?? []).map((m, mi) => {
    const users = nodes.map((n, i) => (n.mesh === mi ? i : -1)).filter((i) => i >= 0);
    const names = Array.isArray(m.extras?.targetNames) ? (m.extras!.targetNames as unknown[]).filter((x): x is string => typeof x === "string") : [];
    const morphCount = Math.max(0, ...m.primitives.map((p) => p.targets?.length ?? 0));
    return {
      name: nm(m.name, `mesh ${mi}`),
      nodes: users.map(nodeName),
      vertexCount: m.primitives.reduce((s, p) => s + (acc[p.attributes.POSITION]?.count ?? 0), 0),
      primitives: m.primitives.length,
      uvSets: [...new Set(m.primitives.flatMap((p) => Object.keys(p.attributes).filter((k) => k.startsWith("TEXCOORD_"))))].sort(),
      hasNormals: m.primitives.every((p) => p.attributes.NORMAL !== undefined),
      morphTargets: names,
      morphCount,
      skinned: users.some((i) => nodes[i].skin !== undefined) || m.primitives.some((p) => p.attributes.JOINTS_0 !== undefined),
      materials: [...new Set(m.primitives.map((p) => matName(p.material)))],
    };
  });

  // head mesh
  const named = r.meshes.filter((m) => HEAD_WORDS.test(m.name) || m.nodes.some((n) => HEAD_WORDS.test(n)));
  const pool = (named.length ? named : r.meshes).filter((m) => !EYE_WORDS.test(m.name));
  const head = [...pool].sort((a, b) => b.morphCount - a.morphCount || b.vertexCount - a.vertexCount)[0];
  r.headMesh = head?.name ?? null;
  if (!head) checks.push({ id: "head", label: "Head mesh", status: "fail", detail: "No mesh found.", evidence: [] });
  else {
    const ev = [`${head.name}: ${head.vertexCount.toLocaleString()} vertices, ${head.primitives} primitive(s), ${head.morphCount} morph target(s), ${head.skinned ? "skinned" : "not skinned"}`];
    if (!named.length) checks.push({ id: "head", label: "Head mesh", status: "warn", detail: 'No mesh or node is named "head" or "face"; the largest candidate was assumed. Name the head mesh explicitly in Blender.', evidence: ev });
    else if (head.morphCount === 0 && !head.skinned) checks.push({ id: "head", label: "Head mesh", status: "warn", detail: "A head mesh exists but has no morph targets and no skinning, so it cannot deform.", evidence: ev });
    else checks.push({ id: "head", label: "Head mesh", status: "pass", detail: "A named, deformable head mesh is present.", evidence: ev });
  }

  // UVs
  if (head) {
    checks.push(
      head.uvSets.includes("TEXCOORD_0")
        ? { id: "uv", label: "UV maps", status: "pass", detail: `Head mesh has ${head.uvSets.length} UV set(s).`, evidence: [`${head.name}: ${head.uvSets.join(", ")}`] }
        : { id: "uv", label: "UV maps", status: "fail", detail: "The head mesh has no TEXCOORD_0 UV map, so textures cannot be applied.", evidence: [] },
    );
  }

  // materials and textures
  const texUse = new Map<number, string[]>();
  const slot = (mi: number, slotName: string, t: unknown) => {
    const idx = (t as { index?: number } | undefined)?.index;
    if (typeof idx === "number") texUse.set(idx, [...(texUse.get(idx) ?? []), `${nm(g.materials?.[mi]?.name, `material ${mi}`)}.${slotName}`]);
    return typeof idx === "number";
  };
  r.materials = (g.materials ?? []).map((m, mi) => {
    const maps: string[] = [];
    const pbr = m.pbrMetallicRoughness ?? {};
    if (slot(mi, "baseColor", pbr.baseColorTexture)) maps.push("baseColor");
    if (slot(mi, "metallicRoughness", pbr.metallicRoughnessTexture)) maps.push("metallicRoughness");
    if (slot(mi, "normal", m.normalTexture)) maps.push("normal");
    if (slot(mi, "occlusion", m.occlusionTexture)) maps.push("occlusion");
    if (slot(mi, "emissive", m.emissiveTexture)) maps.push("emissive");
    for (const [en, ex] of Object.entries(m.extensions ?? {}))
      for (const [k, v] of Object.entries(ex as Record<string, unknown>)) if (k.endsWith("Texture") && slot(mi, `${en}.${k}`, v)) maps.push(`${en}.${k}`);
    return { name: nm(m.name, `material ${mi}`), maps, extensions: Object.keys(m.extensions ?? {}) };
  });
  const views = g.bufferViews ?? [];
  r.textures = (g.textures ?? []).map((t, ti) => {
    const srcIdx = t.source ?? Object.values(t.extensions ?? {}).find((e) => typeof e?.source === "number")?.source;
    const im = srcIdx !== undefined ? g.images?.[srcIdx] : undefined;
    const source: TextureInfo["source"] = !im ? "external" : im.bufferView !== undefined ? "embedded" : im.uri?.startsWith("data:") ? "data-uri" : "external";
    const bytes = im?.bufferView !== undefined ? (views[im.bufferView]?.byteLength ?? null) : im?.uri?.startsWith("data:") ? Math.floor((im.uri.length - im.uri.indexOf(",") - 1) * 0.75) : null;
    return { name: nm(t.name ?? im?.name, `texture ${ti}`), mimeType: im?.mimeType ?? (im?.uri?.match(/^data:([^;,]+)/)?.[1] ?? "unknown"), bytes, source, usedBy: texUse.get(ti) ?? [] };
  });
  // When the whole character is one mesh (common for generator exports), judge only its skin/face
  // material, not every material on the mesh (a normal-mapped blouse must not count as skin detail).
  const allHeadMats = head ? r.materials.filter((m) => head.materials.includes(m.name)) : [];
  const skinMats = allHeadMats.filter((m) => /(skin|face|head)/i.test(m.name) && !/detail/i.test(m.name));
  const headMats = skinMats.length ? skinMats : allHeadMats;
  const headHasColour = headMats.some((m) => m.maps.includes("baseColor"));
  checks.push(
    !r.materials.length
      ? { id: "materials", label: "Materials and textures", status: "fail", detail: "No materials.", evidence: [] }
      : headHasColour
        ? { id: "materials", label: "Materials and textures", status: headMats.some((m) => m.maps.includes("normal")) ? "pass" : "warn", detail: headMats.some((m) => m.maps.includes("normal")) ? "Head material has colour and normal textures." : "Head material has a colour texture but no normal map; skin detail will be limited.", evidence: headMats.map((m) => `${m.name}: ${m.maps.join(", ") || "no maps"}`) }
        : { id: "materials", label: "Materials and textures", status: "warn", detail: "The head material has no base-colour texture.", evidence: headMats.map((m) => `${m.name}: ${m.maps.join(", ") || "no maps"}`) },
  );

  // armature
  const jointSet = new Set<number>();
  (g.skins ?? []).forEach((s) => s.joints.forEach((j) => jointSet.add(j)));
  r.bones = [...jointSet].map((j) => ({ name: nodeName(j), parent: parent.has(j) ? nodeName(parent.get(j)!) : null, facial: FACIAL_WORDS.test(nodeName(j)) }));
  const facialBones = r.bones.filter((b) => b.facial);
  checks.push(
    !(g.skins ?? []).length
      ? { id: "armature", label: "Armature and bone hierarchy", status: "info", detail: "No armature. Acceptable only if every facial motion (including eye rotation) is driven by morph targets or separate eye objects.", evidence: [] }
      : facialBones.length
        ? { id: "armature", label: "Armature and bone hierarchy", status: "pass", detail: `${(g.skins ?? []).length} skin(s), ${r.bones.length} joints, ${facialBones.length} facial joints.`, evidence: facialBones.slice(0, 16).map((b) => `${b.name} ← ${b.parent ?? "root"}`) }
        : { id: "armature", label: "Armature and bone hierarchy", status: "warn", detail: `${r.bones.length} joints but none with facial names (jaw, eye, lid, brow, lip, …).`, evidence: r.bones.slice(0, 10).map((b) => b.name) },
  );

  // morph targets
  if (head) {
    checks.push(
      head.morphCount === 0
        ? { id: "morphs", label: "Morph targets / shape keys", status: facialBones.length ? "warn" : "fail", detail: facialBones.length ? "No morph targets on the head; expressions would rely on bones only." : "No morph targets and no facial bones: the face cannot form expressions.", evidence: [] }
        : head.morphTargets.length === head.morphCount
          ? { id: "morphs", label: "Morph targets / shape keys", status: "pass", detail: `${head.morphCount} named morph targets on the head mesh.`, evidence: head.morphTargets.slice(0, 40) }
          : { id: "morphs", label: "Morph targets / shape keys", status: "warn", detail: `${head.morphCount} morph targets but ${head.morphTargets.length} names; export with shape-key names (mesh extras.targetNames).`, evidence: head.morphTargets.slice(0, 20) },
    );
  }

  // eyes
  nodes.forEach((n, i) => {
    if (!EYE_WORDS.test(nodeName(i)) || jointSet.has(i)) return;
    if (n.mesh === undefined) return;
    const prims = g.meshes?.[n.mesh]?.primitives ?? [];
    const pos = prims.map((p) => acc[p.attributes.POSITION]).filter((a) => a?.min && a?.max);
    if (!pos.length) return r.eyes.push({ name: nodeName(i), kind: "node", pivotOffsetMm: null, radiusMm: null, pivotCentred: null });
    const min = [0, 1, 2].map((k) => Math.min(...pos.map((a) => a!.min![k])));
    const max = [0, 1, 2].map((k) => Math.max(...pos.map((a) => a!.max![k])));
    const centre = min.map((v, k) => (v + max[k]) / 2);
    const radius = Math.max(...max.map((v, k) => (v - min[k]) / 2));
    const off = Math.hypot(...centre);
    r.eyes.push({ name: nodeName(i), kind: "node", pivotOffsetMm: off * 1000, radiusMm: radius * 1000, pivotCentred: off <= 0.15 * radius });
  });
  r.bones.filter((b) => /eye/i.test(b.name) && !/(lid|brow|lash)/i.test(b.name)).forEach((b) => r.eyes.push({ name: b.name, kind: "joint", pivotOffsetMm: null, radiusMm: null, pivotCentred: null }));
  const eyeNodes = r.eyes.filter((e) => e.kind === "node");
  const eyeJoints = r.eyes.filter((e) => e.kind === "joint");
  const off = eyeNodes.filter((e) => e.pivotCentred === false);
  checks.push(
    !r.eyes.length
      ? { id: "eyes", label: "Eye objects and pivots", status: "fail", detail: "No eye objects or eye bones found (names containing eye / eyeball / iris). The studio needs eyes that rotate about their own centres.", evidence: [] }
      : off.length
        ? { id: "eyes", label: "Eye objects and pivots", status: "fail", detail: "Eye object origins are not at the eyeball centre, so they would not rotate about their centres.", evidence: off.map((e) => `${e.name}: pivot ${e.pivotOffsetMm!.toFixed(1)} mm from centre (radius ${e.radiusMm!.toFixed(1)} mm)`) }
        : eyeNodes.some((e) => e.pivotCentred)
          ? { id: "eyes", label: "Eye objects and pivots", status: "pass", detail: "Eye objects have their pivot at the eyeball centre.", evidence: [...eyeNodes.map((e) => `${e.name}: pivot ${e.pivotOffsetMm?.toFixed(1)} mm from centre, radius ${e.radiusMm?.toFixed(1)} mm`), ...eyeJoints.map((e) => `bone ${e.name}`)] }
          : { id: "eyes", label: "Eye objects and pivots", status: "warn", detail: "Eye bones exist, but their pivot against the eyeball cannot be verified without evaluating the skin; check in the preview.", evidence: eyeJoints.map((e) => `bone ${e.name}`) },
  );

  // clips
  const morphNodes = new Set(nodes.map((n, i) => (n.mesh !== undefined && (g.meshes?.[n.mesh]?.primitives.some((p) => p.targets?.length) ?? false) ? i : -1)).filter((i) => i >= 0));
  r.clips = (g.animations ?? []).map((a, ai) => {
    let morphCh = 0;
    let faceCh = 0;
    let other = 0;
    for (const ch of a.channels) {
      const node = ch.target.node;
      if (ch.target.path === "weights" && node !== undefined && morphNodes.has(node)) morphCh++;
      else if (node !== undefined && jointSet.has(node) && FACIAL_WORDS.test(nodeName(node))) faceCh++;
      else if (node !== undefined && EYE_WORDS.test(nodeName(node))) faceCh++;
      else other++;
    }
    const dur = Math.max(0, ...a.samplers.map((s) => acc[s.input]?.max?.[0] ?? 0));
    const name = nm(a.name, `animation ${ai}`);
    const norm = name.trim().toLowerCase().replace(/[\s-]+/g, "_");
    return { name, durationS: dur, channels: a.channels.length, morphChannels: morphCh, facialBoneChannels: faceCh, otherChannels: other, facial: morphCh + faceCh > 0, expressionId: EXPRESSION_IDS.has(norm) ? norm : null };
  });
  const matched = [...new Set(r.clips.filter((c2) => c2.facial && c2.expressionId).map((c2) => c2.expressionId!))];
  r.expressionCoverage = { matched, unmatchedClips: r.clips.filter((c2) => !c2.expressionId).map((c2) => c2.name) };
  const facialClips = r.clips.filter((c2) => c2.facial);
  checks.push(
    !r.clips.length
      ? { id: "clips", label: "Facial animation clips", status: "fail", detail: "No animation clips. Each expression needs a clip named with its expression ID (e.g. gentle_smile).", evidence: [] }
      : !facialClips.length
        ? { id: "clips", label: "Facial animation clips", status: "fail", detail: "Clips exist but none animates morph targets, facial bones or eyes.", evidence: r.clips.slice(0, 10).map((c2) => c2.name) }
        : {
            id: "clips",
            label: "Facial animation clips",
            status: matched.length === EXPRESSION_IDS.size ? "pass" : "warn",
            detail: `${facialClips.length} facial clip(s); ${matched.length} of 60 match an expression ID by name.`,
            evidence: [...facialClips.slice(0, 12).map((c2) => `${c2.name}: ${c2.durationS.toFixed(2)} s, ${c2.morphChannels} morph + ${c2.facialBoneChannels} bone channels${c2.expressionId ? ` → ${c2.expressionId}` : ""}`)],
          },
  );

  const fails = checks.filter((x) => x.status === "fail").length;
  const warns = checks.filter((x) => x.status === "warn").length;
  r.verdict = fails ? "not-compatible" : warns ? "partially-ready" : "structurally-ready";
  r.verdictText =
    r.verdict === "not-compatible"
      ? `${fails} required check(s) failed. The file is not usable as a studio character yet.`
      : r.verdict === "partially-ready"
        ? `No blocking failures, ${warns} warning(s). Some features will be missing until they are resolved.`
        : "Every structural check passed. Visual quality and expression realism still need a human review.";
  return r;
}
