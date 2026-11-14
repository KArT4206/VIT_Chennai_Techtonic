"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TEST_COMBOS, type Weights } from "./combos";

/**
 * STAGING TEST PAGE (Phase 2N). Loads the preset candidate GLB exactly as exported and drives its
 * real morph targets. Not part of the Studio; the Studio's Play controls stay disabled.
 * Query: ?combo=<id>&view=<front|three_quarter|eyes|mouth>&ui=0 (used for screenshots).
 */

type View = "front" | "three_quarter" | "profile" | "eyes" | "mouth";
const VIEWS: Array<[View, string]> = [
  ["front", "Front"],
  ["three_quarter", "¾"],
  ["profile", "Profile"],
  ["eyes", "Eyes"],
  ["mouth", "Mouth"],
];

interface FaceFrame {
  eyeMid: THREE.Vector3;
  eyes: Array<{ name: string; bone: THREE.Vector3; centre: THREE.Vector3; radiusMm: number; offsetMm: number }>;
  targets: Array<{ name: string; maxMm: number; region: string; side: string; centroid: THREE.Vector3 }>;
}

function cameraFor(v: View, f: FaceFrame): { pos: THREE.Vector3; target: THREE.Vector3 } {
  const m = f.eyeMid;
  const t = m.clone().add(new THREE.Vector3(0, -0.035, 0));
  if (v === "front") return { pos: t.clone().add(new THREE.Vector3(0, 0.0, 0.62)), target: t };
  if (v === "three_quarter") return { pos: t.clone().add(new THREE.Vector3(0.44, 0.0, 0.44)), target: t };
  if (v === "profile") return { pos: t.clone().add(new THREE.Vector3(0.62, 0, 0)), target: t };
  if (v === "eyes") return { pos: m.clone().add(new THREE.Vector3(0, 0, 0.26)), target: m.clone() };
  const mouth = m.clone().add(new THREE.Vector3(0, -0.075, 0.02));
  return { pos: mouth.clone().add(new THREE.Vector3(0, 0, 0.24)), target: mouth };
}

function regionOf(y: number, eyeY: number): string {
  const d = (y - eyeY) * 1000;
  if (d > 12) return "brow / forehead";
  if (d > -12) return "eyes / lids";
  if (d > -40) return "nose / cheeks";
  if (d > -75) return "mouth / lips";
  return "jaw / chin";
}

export interface Combo {
  id: string;
  label: string;
  weights: Weights;
}

/** Rejected Ara candidate (Phase 2N), kept as a staging record. */
export function PresetTest() {
  return <CharacterTest src="/api/staging/preset" banner="STAGING TEST · rejected Ara preset candidate" fileLabel="female_preset.glb · Ara 3D Gen export" combos={TEST_COMBOS} />;
}

export function CharacterTest({ src, banner, fileLabel, combos }: { src: string; banner: string; fileLabel: string; combos: Combo[] }) {
  const [status, setStatus] = useState<string>("Loading candidate GLB…");
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [morphNames, setMorphNames] = useState<string[]>([]);
  const [weights, setWeights] = useState<Weights>({});
  const [view, setView] = useState<View>("front");
  const [nonce, setNonce] = useState(0);
  const [frame, setFrame] = useState<FaceFrame | null>(null);
  const [ui, setUi] = useState(true);
  const [combo, setCombo] = useState<string>("neutral");

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("ui") === "0") setUi(false);
    const v = q.get("view") as View | null;
    if (v && VIEWS.some(([id]) => id === v)) setView(v);
    const c = q.get("combo");
    if (c) {
      const found = combos.find((x) => x.id === c);
      if (found) {
        setWeights(found.weights);
        setCombo(found.id);
      }
    }
    let alive = true;
    fetch(src)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.arrayBuffer();
      })
      .then((buf) => new GLTFLoader().parseAsync(buf, ""))
      .then((gltf) => {
        if (!alive) return;
        const root = gltf.scene;
        root.updateMatrixWorld(true);
        let names: string[] = [];
        root.traverse((o) => {
          const m = o as THREE.Mesh;
          if (m.isMesh && m.morphTargetDictionary && !names.length) names = Object.entries(m.morphTargetDictionary).sort((a, b) => a[1] - b[1]).map(([n]) => n);
        });
        setMorphNames(names);
        setScene(root);
        setFrame(measure(root, names));
        setStatus("Loaded");
        (window as unknown as { __presetReady?: boolean; __presetScene?: THREE.Object3D }).__presetReady = true;
        (window as unknown as { __presetScene?: THREE.Object3D }).__presetScene = root; // staging diagnostics
      })
      .catch((e: unknown) => alive && setStatus(`Failed: ${e instanceof Error ? e.message : String(e)}`));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!scene) return;
    scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh || !m.morphTargetDictionary || !m.morphTargetInfluences) return;
      for (const [n, i] of Object.entries(m.morphTargetDictionary)) m.morphTargetInfluences[i] = weights[n] ?? 0;
    });
  }, [scene, weights]);

  const apply = (id: string, w: Weights) => {
    setCombo(id);
    setWeights(w);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
      <div className="relative min-h-[70vh] flex-1 bg-ink-950">
        <Canvas camera={{ position: [0, 1.6, 1], fov: 26, near: 0.01, far: 30 }} dpr={[1, 2]} gl={{ antialias: true, preserveDrawingBuffer: true }} onCreated={({ gl }) => ((gl.toneMapping = THREE.ACESFilmicToneMapping), gl.setClearColor("#15171c"))}>
          <hemisphereLight args={["#e9eef7", "#2a2420", 0.75]} />
          <directionalLight position={[1.2, 2.4, 2]} intensity={2.2} />
          <directionalLight position={[-1.6, 1.8, 1.2]} intensity={0.8} />
          <directionalLight position={[0, 2, -2]} intensity={0.6} />
          {scene && <primitive object={scene} />}
          {frame && <Rig view={view} nonce={nonce} frame={frame} />}
        </Canvas>
        {ui && (
          <div className="pointer-events-none absolute left-3 top-3 rounded-lg bg-ink-900/85 px-3 py-2 text-xs backdrop-blur">
            <p className="font-semibold text-warn-500">{banner}</p>
            <p className="text-ink-300">{fileLabel} · {status}</p>
          </div>
        )}
        {!ui && (
          <div className="pointer-events-none absolute bottom-3 left-3 rounded bg-ink-900/80 px-2 py-1 font-mono text-[11px] text-ink-200">
            {combos.find((c) => c.id === combo)?.label ?? "Neutral"} · {view} · real morph targets
          </div>
        )}
      </div>
      {ui && (
        <aside className="w-full space-y-5 overflow-y-auto border-l border-ink-800 bg-ink-900 p-4 text-sm lg:h-[calc(100dvh-3.5rem)] lg:w-[380px]">
          <section>
            <h2 className="mb-2 font-semibold text-ink-100">Camera</h2>
            <div className="flex flex-wrap gap-1">
              {VIEWS.map(([id, label]) => (
                <button key={id} type="button" aria-pressed={view === id} onClick={() => (setView(id), setNonce((n) => n + 1))} className={`rounded px-2.5 py-1 text-xs ${view === id ? "bg-ink-700 text-ink-100" : "border border-ink-700 text-ink-300"}`}>
                  {label}
                </button>
              ))}
            </div>
          </section>
          <section>
            <div className="mb-2 flex items-center justify-between">
              <h2 className="font-semibold text-ink-100">Test combinations</h2>
              <button type="button" onClick={() => apply("neutral", {})} className="rounded border border-ink-700 px-2 py-1 text-xs text-ink-200">
                Neutral pose
              </button>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {combos.map((c) => (
                <button key={c.id} type="button" aria-pressed={combo === c.id} onClick={() => apply(c.id, c.weights)} className={`rounded px-2 py-1.5 text-left text-xs ${combo === c.id ? "bg-accent-900 text-accent-300" : "border border-ink-700 text-ink-300"}`}>
                  {c.label}
                </button>
              ))}
            </div>
          </section>
          <section>
            <h2 className="mb-2 font-semibold text-ink-100">Morph targets ({morphNames.length})</h2>
            <div className="space-y-1.5">
              {morphNames.map((n) => (
                <label key={n} className="grid grid-cols-[9.5rem_1fr_2.5rem] items-center gap-2 text-xs">
                  <span className="truncate font-mono text-ink-300">{n}</span>
                  <input type="range" min={0} max={1} step={0.01} value={weights[n] ?? 0} onChange={(e) => (setCombo("custom"), setWeights((w) => ({ ...w, [n]: Number(e.target.value) })))} />
                  <span className="text-right font-mono text-ink-400">{(weights[n] ?? 0).toFixed(2)}</span>
                </label>
              ))}
            </div>
          </section>
          {frame && <Measurements frame={frame} />}
        </aside>
      )}
    </div>
  );
}

function Measurements({ frame }: { frame: FaceFrame }) {
  return (
    <section className="space-y-2" id="measurements">
      <h2 className="font-semibold text-ink-100">Measured from the GLB</h2>
      {frame.eyes.map((e) => (
        <p key={e.name} className="font-mono text-[11px] text-ink-300">
          {e.name}: eyeball radius {e.radiusMm.toFixed(1)} mm, bone pivot {e.offsetMm.toFixed(2)} mm from eyeball centre
        </p>
      ))}
      <table className="w-full text-[11px]">
        <thead className="text-ink-400">
          <tr>
            <th className="text-left">target</th>
            <th className="text-left">region</th>
            <th>side</th>
            <th className="text-right">max mm</th>
          </tr>
        </thead>
        <tbody className="font-mono text-ink-300">
          {frame.targets.map((t) => (
            <tr key={t.name}>
              <td>{t.name}</td>
              <td className="font-sans">{t.region}</td>
              <td className="text-center">{t.side}</td>
              <td className="text-right">{t.maxMm.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** Eye pivots and per-target deformation, computed from the loaded geometry (rest pose). */
function measure(root: THREE.Object3D, names: string[]): FaceFrame {
  const bone = (n: RegExp) => {
    let found: THREE.Object3D | undefined;
    root.traverse((o) => {
      if (!found && n.test(o.name)) found = o;
    });
    return found ? new THREE.Vector3().setFromMatrixPosition(found.matrixWorld) : null;
  };
  const le = bone(/^(LeftEye|left_eye)$/);
  const re = bone(/^(RightEye|right_eye)$/);
  const head = bone(/^(Head|head)$/) ?? new THREE.Vector3(0, 1.6, 0);
  const eyeMid = le && re ? le.clone().add(re).multiplyScalar(0.5) : head;
  const eyes: FaceFrame["eyes"] = [];
  const deltas = new Map<string, { max: number; sum: THREE.Vector3; w: number; xs: number }>();
  root.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    const mat = (Array.isArray(m.material) ? m.material[0] : m.material) as THREE.Material;
    const pos = m.geometry.getAttribute("position") as THREE.BufferAttribute;
    // Rendered (skinned) rest position in world space. For skinned meshes the raw attribute is in
    // bind space; getVertexPosition applies the bind matrix and bone transforms (morphs are 0 here).
    const toWorld = (i: number, v = new THREE.Vector3()) => {
      if ((m as THREE.SkinnedMesh).isSkinnedMesh) return m.localToWorld((m as THREE.SkinnedMesh).getVertexPosition(i, v));
      return v.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld);
    };
    // glTF primitives often share one vertex buffer: only this primitive's indexed vertices count.
    const own: number[] = m.geometry.index ? [...new Set(Array.from(m.geometry.index.array as ArrayLike<number>))] : Array.from({ length: pos.count }, (_, i) => i);
    if (mat && /^Eye/.test(mat.name) && le && re) {
      for (const [nm, b] of [["LeftEye", le], ["RightEye", re]] as const) {
        if (eyes.some((e) => e.name === nm)) continue;
        const box = new THREE.Box3();
        const v = new THREE.Vector3();
        for (const i of own) {
          toWorld(i, v);
          if ((v.x > eyeMid.x) === (b.x > eyeMid.x)) box.expandByPoint(v);
        }
        if (box.isEmpty()) continue; // this primitive holds only the other eye
        const c = box.getCenter(new THREE.Vector3());
        const s = box.getSize(new THREE.Vector3());
        eyes.push({ name: nm, bone: b, centre: c, radiusMm: (Math.max(s.x, s.y) / 2) * 1000, offsetMm: c.distanceTo(b) * 1000 });
      }
    }
    if (mat?.name === "Skin" && m.geometry.morphAttributes.position) {
      const rel = m.geometry.morphTargetsRelative;
      m.geometry.morphAttributes.position.forEach((attr, ti) => {
        const name = names[ti] ?? `t${ti}`;
        const acc = deltas.get(name) ?? { max: 0, sum: new THREE.Vector3(), w: 0, xs: 0 };
        const d = new THREE.Vector3();
        const base = new THREE.Vector3();
        for (const i of own) {
          d.fromBufferAttribute(attr as THREE.BufferAttribute, i);
          if (!rel) d.sub(base.fromBufferAttribute(pos, i));
          const len = d.length();
          if (len < 1e-5) continue;
          const p = toWorld(i);
          acc.max = Math.max(acc.max, len);
          acc.sum.addScaledVector(p, len);
          acc.w += len;
          acc.xs += (p.x - eyeMid.x) * len;
        }
        deltas.set(name, acc);
      });
    }
  });
  const targets = names
    .filter((n) => deltas.has(n))
    .map((n) => {
      const a = deltas.get(n)!;
      const c = a.w ? a.sum.clone().multiplyScalar(1 / a.w) : new THREE.Vector3();
      const xm = a.w ? (a.xs / a.w) * 1000 : 0;
      return { name: n, maxMm: a.max * 1000, region: regionOf(c.y, eyeMid.y), side: Math.abs(xm) < 4 ? "both" : xm > 0 ? "+X (char. left)" : "−X (char. right)", centroid: c };
    });
  return { eyeMid, eyes, targets };
}

function Rig({ view, nonce, frame }: { view: View; nonce: number; frame: FaceFrame }) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const goal = useRef<{ pos: THREE.Vector3; target: THREE.Vector3; t: number } | null>(null);
  const first = useRef(true);
  const c = useMemo(() => cameraFor(view, frame), [view, frame]);
  useEffect(() => {
    if (first.current) {
      camera.position.copy(c.pos);
      controls.current?.target.copy(c.target);
      controls.current?.update();
      first.current = false;
      return;
    }
    goal.current = { pos: c.pos.clone(), target: c.target.clone(), t: 0 };
  }, [c, nonce, camera]);
  useFrame((_, dt) => {
    const g = goal.current;
    if (!g || !controls.current) return;
    g.t = Math.min(1, g.t + dt / 0.5);
    camera.position.lerp(g.pos, g.t);
    controls.current.target.lerp(g.target, g.t);
    controls.current.update();
    if (g.t >= 1) goal.current = null;
  });
  return <OrbitControls ref={controls} makeDefault enableDamping minDistance={0.12} maxDistance={4} />;
}
