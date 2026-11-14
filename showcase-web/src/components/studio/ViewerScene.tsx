"use client";

import { Grid, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { presetById, type CameraPresetId } from "@/lib/character/cameras";

/**
 * Real-time viewport. While no character is imported it shows only neutral framing guides
 * (a wireframe head-sized volume and eye / mouth level rings) so the camera presets can be judged.
 * It never draws a face. A future character mounts at <CharacterSlot/> with its eye midpoint at the
 * origin.
 */
export default function ViewerScene({ camera, nonce }: { camera: CameraPresetId; nonce: number }) {
  const p = presetById("front");
  return (
    <Canvas
      camera={{ position: p.position, fov: 28, near: 0.01, far: 20 }}
      dpr={[1, 2]}
      gl={{ antialias: true }}
      onCreated={({ gl }) => gl.setClearColor("#0d0f13")}
      aria-label="3D viewport"
    >
      <hemisphereLight args={["#cfd6e6", "#1a1c22", 0.6]} />
      <directionalLight position={[0.6, 0.8, 1]} intensity={1.2} />
      <CameraRig preset={camera} nonce={nonce} />
      <PendingGuides />
      <CharacterSlot />
      <Grid
        position={[0, -0.33, 0]}
        args={[3, 3]}
        cellSize={0.05}
        cellThickness={0.5}
        cellColor="#2a2f3a"
        sectionSize={0.25}
        sectionThickness={0.9}
        sectionColor="#3a4150"
        fadeDistance={2.4}
        fadeStrength={1.5}
        infiniteGrid
      />
    </Canvas>
  );
}

/** Integration point for the real character (docs/CHARACTER_INTEGRATION.md). Empty until imported. */
function CharacterSlot() {
  return null;
}

function PendingGuides() {
  const group = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (group.current) group.current.rotation.y += dt * 0.08;
  });
  return (
    <group>
      <group ref={group} position={[0, -0.03, -0.02]}>
        <mesh scale={[0.078, 0.112, 0.094]}>
          <sphereGeometry args={[1, 32, 20]} />
          <meshBasicMaterial color="#5b6378" wireframe transparent opacity={0.28} />
        </mesh>
      </group>
      <Ring y={0} r={0.11} color="#d9a35b" label="eye level" />
      <Ring y={-0.075} r={0.1} color="#6aa6e8" label="mouth level" />
      <mesh position={[0, -0.33, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.18, 0.185, 96]} />
        <meshBasicMaterial color="#3a4150" transparent opacity={0.8} />
      </mesh>
    </group>
  );
}

function Ring({ y, r, color }: { y: number; r: number; color: string; label: string }) {
  return (
    <mesh position={[0, y, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <ringGeometry args={[r, r + 0.0015, 128]} />
      <meshBasicMaterial color={color} transparent opacity={0.45} side={THREE.DoubleSide} />
    </mesh>
  );
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
