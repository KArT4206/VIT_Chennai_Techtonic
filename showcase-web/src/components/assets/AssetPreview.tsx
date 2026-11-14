"use client";

import { Bounds, Center, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useEffect, useState } from "react";
import type { Object3D } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export type PreviewStatus = { state: "loading" } | { state: "loaded"; meshes: number } | { state: "failed"; error: string };

/**
 * Static preview of the stored file, rendered by three.js exactly as loaded. No animation is played
 * and no pose is applied: it shows what the file contains, nothing more.
 */
export default function AssetPreview({ data, onStatus }: { data: ArrayBuffer; onStatus: (s: PreviewStatus) => void }) {
  const [scene, setScene] = useState<Object3D | null>(null);

  useEffect(() => {
    let alive = true;
    onStatus({ state: "loading" });
    new GLTFLoader()
      .parseAsync(data.slice(0), "")
      .then((gltf) => {
        if (!alive) return;
        let meshes = 0;
        gltf.scene.traverse((o) => {
          if ((o as { isMesh?: boolean }).isMesh) meshes++;
        });
        setScene(gltf.scene);
        onStatus({ state: "loaded", meshes });
      })
      .catch((e: unknown) => alive && onStatus({ state: "failed", error: e instanceof Error ? e.message : String(e) }));
    return () => {
      alive = false;
    };
  }, [data, onStatus]);

  return (
    <Canvas camera={{ position: [0, 0, 1.2], fov: 30, near: 0.005, far: 50 }} dpr={[1, 2]} onCreated={({ gl }) => gl.setClearColor("#0d0f13")}>
      <hemisphereLight args={["#dfe6f2", "#1a1c22", 0.8]} />
      <directionalLight position={[0.8, 1, 1.2]} intensity={1.6} />
      <directionalLight position={[-1, 0.4, 0.6]} intensity={0.5} />
      {scene && (
        <Bounds fit clip observe margin={1.15}>
          <Center>
            <primitive object={scene} />
          </Center>
        </Bounds>
      )}
      <OrbitControls makeDefault enableDamping />
    </Canvas>
  );
}
