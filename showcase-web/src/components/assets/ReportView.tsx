"use client";

import { useState } from "react";
import type { AssetReport, CheckStatus } from "@/lib/assets/gltf-inspect";

const STATUS: Record<CheckStatus, { label: string; cls: string; icon: string }> = {
  pass: { label: "Pass", cls: "bg-ok-500/15 text-ok-500", icon: "✓" },
  warn: { label: "Warning", cls: "bg-warn-500/15 text-warn-500", icon: "!" },
  fail: { label: "Fail", cls: "bg-err-500/15 text-err-500", icon: "✕" },
  info: { label: "Info", cls: "bg-info-500/15 text-info-500", icon: "i" },
};

export const VERDICT_STYLE = {
  "not-compatible": { label: "Not compatible", cls: "border-err-500/40 bg-err-500/10 text-err-500" },
  "partially-ready": { label: "Partially ready", cls: "border-warn-500/40 bg-warn-500/10 text-warn-500" },
  "structurally-ready": { label: "Structurally ready", cls: "border-ok-500/40 bg-ok-500/10 text-ok-500" },
} as const;

const fmtBytes = (n: number | null) => (n === null ? "–" : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);

type Tab = "checks" | "textures" | "rig" | "shapes" | "animations" | "meshes";

export function ReportView({ report }: { report: AssetReport }) {
  const [tab, setTab] = useState<Tab>("checks");
  const head = report.meshes.find((m) => m.name === report.headMesh);
  const shapes = report.meshes.filter((m) => m.morphCount > 0);
  const tabs: Array<[Tab, string, number]> = [
    ["checks", "Compatibility checks", report.checks.length],
    ["textures", "Textures", report.textures.length],
    ["rig", "Facial rig", report.bones.length + report.eyes.length],
    ["shapes", "Shape keys", shapes.reduce((n, m) => n + m.morphCount, 0)],
    ["animations", "Animations", report.clips.length],
    ["meshes", "Meshes", report.meshes.length],
  ];
  const v = VERDICT_STYLE[report.verdict];
  return (
    <div className="space-y-4">
      <div className={`rounded-lg border px-4 py-3 ${v.cls}`}>
        <p className="text-sm font-semibold">{v.label}</p>
        <p className="mt-0.5 text-sm opacity-90">{report.verdictText}</p>
        <p className="mt-1 text-xs opacity-75">Structural checks read the file&apos;s own data. A file that loads is not automatically compatible, and passing checks does not judge visual quality.</p>
      </div>
      <div className="flex flex-wrap gap-1 border-b border-ink-800" role="tablist">
        {tabs.map(([id, label, n]) => (
          <button key={id} role="tab" type="button" aria-selected={tab === id} onClick={() => setTab(id)} className={`-mb-px border-b-2 px-3 py-2 text-xs ${tab === id ? "border-accent-500 text-ink-100" : "border-transparent text-ink-400 hover:text-ink-200"}`}>
            {label} <span className="font-mono opacity-60">{n}</span>
          </button>
        ))}
      </div>

      {tab === "checks" && (
        <ul className="divide-y divide-ink-800 rounded-lg border border-ink-800">
          {report.checks.map((c) => (
            <li key={c.id} className="grid grid-cols-[6.5rem_1fr] gap-3 px-4 py-3">
              <span className={`h-fit rounded px-2 py-0.5 text-center text-xs font-medium ${STATUS[c.status].cls}`}>
                {STATUS[c.status].icon} {STATUS[c.status].label}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink-100">{c.label}</p>
                <p className="text-sm text-ink-300">{c.detail}</p>
                {c.evidence.length > 0 && (
                  <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-ink-500">
                    {c.evidence.map((e, i) => (
                      <li key={i} className="truncate">
                        {e}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {tab === "textures" && (
        <Table empty="No textures in the file." head={["Texture", "Type", "Size", "Stored", "Used by"]} rows={report.textures.map((t) => [t.name, t.mimeType, fmtBytes(t.bytes), t.source, t.usedBy.join(", ") || "unused"])} />
      )}

      {tab === "rig" && (
        <div className="space-y-4">
          <Table
            empty="No eye objects or eye bones found."
            head={["Eye", "Kind", "Pivot offset", "Radius", "Pivot at centre"]}
            rows={report.eyes.map((e) => [e.name, e.kind === "node" ? "separate object" : "bone", e.pivotOffsetMm === null ? "–" : `${e.pivotOffsetMm.toFixed(1)} mm`, e.radiusMm === null ? "–" : `${e.radiusMm.toFixed(1)} mm`, e.pivotCentred === null ? "not verifiable" : e.pivotCentred ? "yes" : "no"])}
          />
          <Table
            empty="No armature in the file."
            head={["Bone", "Parent", "Facial"]}
            rows={[...report.bones].sort((a, b) => Number(b.facial) - Number(a.facial)).map((b) => [b.name, b.parent ?? "(root)", b.facial ? "yes" : ""])}
          />
        </div>
      )}

      {tab === "shapes" &&
        (shapes.length ? (
          <div className="space-y-3">
            {shapes.map((m) => (
              <div key={m.name} className="rounded-lg border border-ink-800 p-3">
                <p className="text-sm text-ink-100">
                  {m.name} <span className="text-xs text-ink-500">{m.morphCount} morph targets{m.name === report.headMesh ? " · head mesh" : ""}</span>
                </p>
                <p className="mt-1 flex flex-wrap gap-1">
                  {(m.morphTargets.length ? m.morphTargets : Array.from({ length: m.morphCount }, (_, i) => `(unnamed ${i})`)).map((n) => (
                    <span key={n} className="rounded bg-ink-800 px-1.5 py-0.5 font-mono text-[11px] text-ink-300">
                      {n}
                    </span>
                  ))}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-400">No morph targets (shape keys) in the file.</p>
        ))}

      {tab === "animations" && (
        <Table
          empty="No animation clips in the file."
          head={["Clip", "Duration", "Morph ch.", "Facial bone ch.", "Other ch.", "Expression"]}
          rows={report.clips.map((c) => [c.name, `${c.durationS.toFixed(2)} s`, String(c.morphChannels), String(c.facialBoneChannels), String(c.otherChannels), c.expressionId ?? (c.facial ? "no matching ID" : "not facial")])}
        />
      )}

      {tab === "meshes" && (
        <Table
          empty="No meshes."
          head={["Mesh", "Vertices", "UV sets", "Normals", "Morphs", "Skinned", "Materials"]}
          rows={report.meshes.map((m) => [`${m.name}${m.name === report.headMesh ? " (head)" : ""}`, m.vertexCount.toLocaleString(), m.uvSets.join(", ") || "none", m.hasNormals ? "yes" : "no", String(m.morphCount), m.skinned ? "yes" : "no", m.materials.join(", ")])}
        />
      )}
      {head && <p className="text-xs text-ink-500">Head mesh used for checks: {head.name}</p>}
    </div>
  );
}

function Table({ head, rows, empty }: { head: string[]; rows: string[][]; empty: string }) {
  if (!rows.length) return <p className="text-sm text-ink-400">{empty}</p>;
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-ink-800">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-ink-850 text-ink-400">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-ink-800 text-ink-300">
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j} className={`px-3 py-2 ${j === 0 ? "font-mono text-ink-200" : ""}`}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
