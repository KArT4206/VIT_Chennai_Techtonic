import { describe, expect, it } from "vitest";
import { EXPRESSIONS } from "@/data/expressions";
import { inspectGltf, type Check } from "./gltf-inspect";
import { buildGlb } from "./testing/build-glb";

const check = (r: { checks: Check[] }, id: Check["id"]) => r.checks.find((c) => c.id === id)!;

describe("GLB/glTF compatibility validator", () => {
  it("a complete synthetic fixture passes structure but is only partially ready (1 of 60 clips)", () => {
    const r = inspectGltf("fixture.glb", buildGlb());
    for (const id of ["container", "resources", "head", "uv", "materials", "armature", "morphs", "eyes"] as const) expect(check(r, id).status, id).toBe("pass");
    expect(check(r, "clips").status).toBe("warn");
    expect(r.expressionCoverage.matched).toEqual(["gentle_smile"]);
    expect(r.verdict).toBe("partially-ready");
    expect(r.headMesh).toBe("Head");
    expect(r.meshes[0].morphTargets).toEqual(["jawOpen", "browInnerUp"]);
    expect(r.bones.map((b) => b.name)).toEqual(["root", "head", "jaw"]);
    expect(r.textures.map((t) => [t.name, t.source, t.usedBy[0]])).toEqual([
      ["skin_albedo", "embedded", "Skin.baseColor"],
      ["skin_normal", "embedded", "Skin.normal"],
    ]);
    expect(r.eyes.every((e) => e.pivotCentred)).toBe(true);
  });

  it("is structurally ready only when all 60 expressions have facial clips", () => {
    const r = inspectGltf("full.glb", buildGlb({ clips: EXPRESSIONS.map((e) => e.id) }));
    expect(r.verdict).toBe("structurally-ready");
    expect(r.verdictText).toMatch(/human review/);
  });

  it("a file that imports but has nothing facial is not compatible", () => {
    const r = inspectGltf("box.glb", buildGlb({ headName: "Cube", morphCount: 0, armature: "none", eyes: "none", clips: [], textures: false }));
    expect(r.verdict).toBe("not-compatible");
    expect(check(r, "head").status).toBe("warn");
    expect(check(r, "morphs").status).toBe("fail");
    expect(check(r, "eyes").status).toBe("fail");
    expect(check(r, "clips").status).toBe("fail");
  });

  it("detects eye pivots that are not at the eyeball centre", () => {
    const r = inspectGltf("eyes.glb", buildGlb({ eyes: "offset" }));
    expect(check(r, "eyes").status).toBe("fail");
    expect(r.eyes[0].pivotOffsetMm).toBeCloseTo(13.86, 1);
  });

  it("accepts eye bones with a warning (pivot not verifiable statically)", () => {
    const r = inspectGltf("bones.glb", buildGlb({ eyes: "bones" }));
    expect(check(r, "eyes").status).toBe("warn");
    expect(r.eyes.map((e) => e.name)).toEqual(["eye.L", "eye.R"]);
  });

  it("flags missing UVs, unnamed morphs, non-facial armatures and non-facial clips", () => {
    expect(check(inspectGltf("a.glb", buildGlb({ uv: false })), "uv").status).toBe("fail");
    expect(check(inspectGltf("b.glb", buildGlb({ morphNames: null })), "morphs").status).toBe("warn");
    expect(check(inspectGltf("c.glb", buildGlb({ armature: "plain" })), "armature").status).toBe("warn");
    expect(check(inspectGltf("d.glb", buildGlb({ clipTargetsMorphs: false, armature: "none" })), "clips").status).toBe("fail");
    expect(check(inspectGltf("e.glb", buildGlb({ normalMap: false })), "materials").status).toBe("warn");
  });

  it("fails external resources and refuses .blend, broken and non-glTF files", () => {
    expect(check(inspectGltf("ext.glb", buildGlb({ externalImage: true })), "resources").status).toBe("fail");
    const blend = inspectGltf("character.blend", new TextEncoder().encode("BLENDER-v405").buffer as ArrayBuffer);
    expect(blend.verdict).toBe("not-compatible");
    expect(check(blend, "container").detail).toMatch(/Export the character from Blender as glTF/);
    expect(inspectGltf("x.glb", new ArrayBuffer(8)).verdict).toBe("not-compatible");
    const truncated = buildGlb().slice(0, 40);
    expect(check(inspectGltf("t.glb", truncated), "container").status).toBe("fail");
    expect(check(inspectGltf("x.gltf", new TextEncoder().encode("{oops").buffer as ArrayBuffer), "container").status).toBe("fail");
  });

  it("judges only the skin material of a merged single-mesh character", () => {
    const glb = buildGlb({ normalMap: false });
    // add a second, normal-mapped "Blouse" material to the same mesh by patching the JSON chunk
    const dv = new DataView(glb);
    const jl = dv.getUint32(12, true);
    const json = JSON.parse(new TextDecoder().decode(new Uint8Array(glb, 20, jl)));
    json.materials.push({ name: "Silk blouse", pbrMetallicRoughness: { baseColorTexture: { index: 0 } }, normalTexture: { index: 0 } });
    json.meshes[0].primitives.push({ ...json.meshes[0].primitives[0], material: 1 });
    let enc = new TextEncoder().encode(JSON.stringify(json));
    const pad = (4 - (enc.length % 4)) % 4;
    const j2 = new Uint8Array(enc.length + pad).fill(0x20);
    j2.set(enc);
    enc = j2;
    const binStart = 20 + jl;
    const bin = new Uint8Array(glb, binStart);
    const out = new ArrayBuffer(20 + enc.length + bin.length);
    const o = new DataView(out);
    o.setUint32(0, 0x46546c67, true);
    o.setUint32(4, 2, true);
    o.setUint32(8, out.byteLength, true);
    o.setUint32(12, enc.length, true);
    o.setUint32(16, 0x4e4f534a, true);
    new Uint8Array(out, 20).set(enc);
    new Uint8Array(out, 20 + enc.length).set(bin);
    const r = inspectGltf("merged.glb", out);
    expect(check(r, "materials").status).toBe("warn");
    expect(check(r, "materials").evidence.join()).toMatch(/^Skin:/);
  });

  it("reads .gltf JSON with embedded data URIs", () => {
    const gltf = { asset: { version: "2.0" }, meshes: [{ name: "Head", primitives: [{ attributes: { POSITION: 0 } }] }], accessors: [{ count: 3, min: [0, 0, 0], max: [1, 1, 1] }], buffers: [{ uri: "data:application/octet-stream;base64,AAAA", byteLength: 3 }], nodes: [{ name: "Head", mesh: 0 }] };
    const r = inspectGltf("x.gltf", new TextEncoder().encode(JSON.stringify(gltf)).buffer as ArrayBuffer);
    expect(r.container).toBe("gltf");
    expect(check(r, "resources").status).toBe("pass");
    expect(check(r, "uv").status).toBe("fail");
  });
});
