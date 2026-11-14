"use client";

import { Grid, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { presetById, type CameraPresetId } from "@/lib/character/cameras";
import { QUALITY_INFO, type Quality } from "@/lib/settings/settings";

/**
 * Real-time viewport. With no character connected it renders only an empty stage (floor grid); the
 * empty-state card is drawn by ViewerPanel. A future character mounts at <CharacterSlot/> with its
 * eye midpoint at the origin (docs/CHARACTER_INTEGRATION.md). Nothing face-like is ever drawn here.
 */
export default function ViewerScene({ camera, nonce, quality }: { camera: CameraPresetId; nonce: number; quality: Quality }) {
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
      <CharacterSlot />
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

/** Integration point for the real character (docs/CHARACTER_INTEGRATION.md). Empty until connected. */
function CharacterSlot() {
  return null;
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
