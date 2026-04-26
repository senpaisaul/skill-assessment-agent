"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background, Controls, Handle, Position,
  type Node, type Edge, type NodeProps,
} from "reactflow";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import type { SkillAssessment, SkillGap } from "@/lib/types";
import { cn, severityColor } from "@/lib/cn";

interface SkillGraphProps {
  strengths: string[];
  gaps: SkillGap[];
  assessments: SkillAssessment[];
}

const nodeTypes = { strength: StrengthNode, gap: GapNode };

export function SkillGraph({ strengths, gaps, assessments }: SkillGraphProps) {
  const { nodes, edges } = useMemo(() => {
    // Case-insensitive assessment lookup
    const bySkill = Object.fromEntries(
      assessments.map(a => [a.skill.toLowerCase().trim(), a])
    );

    // Collect all skills that appear as adjacency sources
    const adjSources = new Set<string>();
    gaps.forEach(g => g.adjacent_known_skills.forEach(s => adjSources.add(s)));

    // Left column: union of strengths + adjacency source skills (deduped, case-insensitive)
    const leftSkillsRaw = [...strengths];
    adjSources.forEach(adj => {
      const alreadyPresent = leftSkillsRaw.some(
        s => s.toLowerCase().trim() === adj.toLowerCase().trim()
      );
      if (!alreadyPresent) leftSkillsRaw.push(adj);
    });

    // Build a canonical ID for each left-side skill (lowercase+trimmed) → display name
    // This lets edge lookup be case-insensitive regardless of what the backend returns.
    const leftCanonicalToDisplay: Record<string, string> = {};
    leftSkillsRaw.forEach(s => {
      leftCanonicalToDisplay[s.toLowerCase().trim()] = s;
    });
    const leftSkills = Object.values(leftCanonicalToDisplay);

    const V_SPACING = 110;
    const COL_WIDTH = 440;

    const leftH = Math.max(0, (leftSkills.length - 1) * V_SPACING);
    const rightH = Math.max(0, (gaps.length - 1) * V_SPACING);
    const maxH = Math.max(leftH, rightH);
    const leftStartY = (maxH - leftH) / 2;
    const rightStartY = (maxH - rightH) / 2;

    const nodes: Node[] = [];

    leftSkills.forEach((skill, i) => {
      const a = bySkill[skill.toLowerCase().trim()];
      // Node ID is based on lowercase canonical so edges can find it reliably
      nodes.push({
        id: `strength-${skill.toLowerCase().trim()}`,
        type: "strength",
        position: { x: 0, y: leftStartY + i * V_SPACING },
        data: { skill, level: a?.level ?? null, confidence: a?.confidence ?? null },
      });
    });

    gaps.forEach((gap, i) => {
      nodes.push({
        id: `gap-${gap.skill.toLowerCase().trim()}`,
        type: "gap",
        position: { x: COL_WIDTH, y: rightStartY + i * V_SPACING },
        data: { gap },
      });
    });

    const edges: Edge[] = [];
    gaps.forEach(gap => {
      gap.adjacent_known_skills.forEach(adj => {
        const adjKey = adj.toLowerCase().trim();
        const gapKey = gap.skill.toLowerCase().trim();

        // Only draw edge if the source node actually exists in the left column
        const sourceExists = leftSkills.some(
          s => s.toLowerCase().trim() === adjKey
        );
        if (!sourceExists) return;

        edges.push({
          id: `e-${adjKey}-${gapKey}`,
          source: `strength-${adjKey}`,
          target: `gap-${gapKey}`,
          animated: true,
          style: { stroke: "#14b8a6", strokeWidth: 1.5, strokeOpacity: 0.5 },
          type: "default",
        });
      });
    });

    return { nodes, edges };
  }, [strengths, gaps, assessments]);

  // Correct height: count actual node objects, not filter by type key
  const strengthCount = nodes.filter(n => n.type === "strength").length;
  const gapCount = nodes.filter(n => n.type === "gap").length;
  const graphH = Math.max(400, Math.max(strengthCount, gapCount) * 110 + 100);

  return (
    <div style={{ height: graphH }}>
      <ReactFlow
        nodes={nodes} edges={edges} nodeTypes={nodeTypes}
        fitView fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        proOptions={{ hideAttribution: true }}>
        <Background color="#1e2d33" gap={24} />
        <Controls showInteractive={false}
          className="!bg-bg-800 !border-bg-700 [&>button]:!bg-bg-800 [&>button]:!border-bg-700 [&>button]:!text-slate-300 [&>button:hover]:!bg-bg-700" />
      </ReactFlow>
    </div>
  );
}

function StrengthNode({ data }: NodeProps<{ skill: string; level: 1 | 2 | 3 | 4 | 5 | null; confidence: number | null }>) {
  return (
    <div className="px-4 py-3 rounded-xl border shadow-sm min-w-[160px] bg-emerald-500/10 border-emerald-500/30 text-emerald-200">
      <div className="flex items-center gap-2">
        <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
        <span className="text-sm font-medium truncate">{data.skill}</span>
      </div>
      {data.level && (
        <div className="text-[10px] text-emerald-400/60 mt-1 font-mono">
          L{data.level}{data.confidence !== null && <span className="ml-1.5 opacity-70">· {Math.round(data.confidence * 100)}%</span>}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!bg-emerald-500 !border-emerald-400 !w-2 !h-2" />
    </div>
  );
}

function GapNode({ data }: NodeProps<{ gap: SkillGap }>) {
  const { gap } = data;
  const sevColor = severityColor(gap.severity);
  const iconColor = gap.severity >= 0.7 ? "text-red-400" : gap.severity >= 0.4 ? "text-amber-400" : "text-emerald-400";

  return (
    <div className={cn("px-4 py-3 rounded-xl border shadow-sm min-w-[180px]", sevColor)}>
      <Handle type="target" position={Position.Left} className="!bg-current !border-current !w-2 !h-2" />
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className={cn("shrink-0", iconColor)} />
        <span className="text-sm font-medium truncate">{gap.skill}</span>
      </div>
      <div className="text-[10px] mt-1 font-mono opacity-70">
        Need: L{gap.required_level}
        {gap.current_level && <span> · Have: L{gap.current_level}</span>}
        <span className="ml-1.5">· sev {gap.severity.toFixed(2)}</span>
      </div>
    </div>
  );
}