import { readFile } from "node:fs/promises";
import path from "node:path";

/**
 * STAGING ONLY: serves the preset candidate GLB for the isolated /preset-test page while it is under
 * review. Not used by the Studio. Remove when the candidate is approved and bundled properly.
 */
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await readFile(path.join(process.cwd(), "staging", "preset-candidate", "female_preset.glb"));
    return new Response(new Uint8Array(data), { headers: { "content-type": "model/gltf-binary", "cache-control": "no-store" } });
  } catch {
    return new Response("Preset candidate not found", { status: 404 });
  }
}
