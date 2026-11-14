"use client";

import { Grid, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { presetById, type CameraPresetId } from "@/lib/character/cameras";
import { QUALITY_INFO, type Quality } from "@/lib/settings/settings";
import type { CharacterAdapter } from "@/lib/character/adapter";
import { SCAN_HEAD_URL, ScanHeadAdapter, type MorphBinding } from "@/lib/character/scan-head";

/**
 * Real-time viewport. With no character connected it renders only an empty stage (floor grid); the
 * empty-state card is drawn by ViewerPanel. The built-in scan head mounts at <CharacterSlot/> with its
 * eye midpoint at the origin (docs/CHARACTER_INTEGRATION.md).
 */
export default function ViewerScene({ camera, nonce, quality, adapter }: { camera: CameraPresetId; nonce: number; quality: Quality; adapter: CharacterAdapter }) {
  const p = presetById("front");
  const q = QUALITY_INFO[quality];
  return (
    <Canvas
      key={quality}
      camera={{ position: p.position, fov: 28, near: 0.01, far: 20 }}
      dpr={q.dpr}
      gl={{ antialias: q.antialias }}
      onCreated={({ gl }) => gl.setClearColor("#0d0f13")}
      aria-label="3D viewport"
    >
      <hemisphereLight args={["#cfd6e6", "#1a1c22", 0.6]} />
      <directionalLight position={[0.6, 0.8, 1]} intensity={1.2} />
      <CameraRig preset={camera} nonce={nonce} />
      <Suspense fallback={null}>{adapter instanceof ScanHeadAdapter && <CharacterSlot adapter={adapter} />}</Suspense>
      <Grid
        position={[0, -0.33, 0]}
        args={[3, 3]}
        cellSize={0.05}
        cellThickness={0.5}
        cellColor="#22262f"
        sectionSize={0.25}
        sectionThickness={0.9}
        sectionColor="#323845"
        fadeDistance={2.2}
        fadeStrength={1.6}
        infiniteGrid
      />
    </Canvas>
  );
}

/** The built-in scan head, placed with its eye midpoint at the origin; its morphs are driven by the adapter. */
function CharacterSlot({ adapter }: { adapter: ScanHeadAdapter }) {
  const { scene } = useGLTF(SCAN_HEAD_URL);
  const offset = useMemo(() => {
    scene.updateMatrixWorld(true);
    const a = new THREE.Vector3(), b = new THREE.Vector3();
    const l = scene.getObjectByName("left_eye"), r = scene.getObjectByName("right_eye");
    if (!l || !r) return new THREE.Vector3();
    l.getWorldPosition(a);
    r.getWorldPosition(b);
    return a.add(b).multiplyScalar(-0.5);
  }, [scene]);

  useEffect(() => {
    const map = new Map<string, MorphBinding[]>();
    scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.frustumCulled = false;
      if (!m.morphTargetDictionary || !m.morphTargetInfluences) return;
      for (const [name, index] of Object.entries(m.morphTargetDictionary)) {
        if (!map.has(name)) map.set(name, []);
        map.get(name)!.push({ influences: m.morphTargetInfluences, index });
      }
    });
    adapter.attach(map);
    (window as unknown as { __studioScene?: THREE.Object3D }).__studioScene = scene;
    return () => adapter.detach();
  }, [scene, adapter]);

  useFrame((_, dt) => adapter.tick(Math.min(dt, 0.1)));

  return <primitive object={scene} position={offset} />;
}

/** Animates the camera to the selected preset; orbit and zoom stay free afterwards. */
function CameraRig({ preset, nonce }: { preset: CameraPresetId; nonce: number }) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera } = useThree();
  const goal = useRef<{ pos: THREE.Vector3; target: THREE.Vector3; t: number } | null>(null);

  useEffect(() => {
    const p = presetById(preset);
    goal.current = { pos: new THREE.Vector3(...p.position), target: new THREE.Vector3(...p.target), t: 0 };
  }, [preset, nonce]);

  useFrame((_, dt) => {
    const g = goal.current;
    const c = controls.current;
    if (!g || !c) return;
    g.t = Math.min(1, g.t + dt / 0.6);
    const k = 1 - Math.pow(1 - g.t, 3);
    camera.position.lerp(g.pos, k);
    c.target.lerp(g.target, k);
    c.update();
    if (g.t >= 1) goal.current = null;
  });

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      minDistance={0.15}
      maxDistance={2.5}
      target={presetById("front").target}
      onStart={() => {
        goal.current = null;
      }}
    />
  );
}
