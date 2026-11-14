import { readFile } from "node:fs/promises";

/**
 * LOCAL-ONLY: serves a private character GLB from outside the app (path in PRIVATE_CHARACTER_GLB).
 * Used for the 3D Scan Store scan preview under the user's one-time permission. With the env var
 * unset (any normal build or deployment) it always returns 404, so no private file is ever served.
 */
export const dynamic = "force-dynamic";

export async function GET() {
  const p = process.env.PRIVATE_CHARACTER_GLB;
  if (!p || !p.toLowerCase().endsWith(".glb")) return new Response("No private character configured", { status: 404 });
  try {
    const data = await readFile(p);
    return new Response(new Uint8Array(data), { headers: { "content-type": "model/gltf-binary", "cache-control": "no-store", "x-robots-tag": "noindex" } });
  } catch {
    return new Response("Private character file not found", { status: 404 });
  }
}
