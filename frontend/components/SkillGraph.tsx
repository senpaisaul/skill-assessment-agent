"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeProps,
} from "reactflow";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import type { SkillAssessment, SkillGap } from "@/lib/types";
import { cn, bloomColor, severityColor } from "@/lib/cn";

interface SkillGraphProps {
  strengths: string[];
  gaps: SkillGap[];
  assessments: SkillAssessment[];
}

// Custom node renderers
const nodeTypes = {
  strength: StrengthNode,
  gap: GapNode,
};

export function SkillGraph({ strengths, gaps, assessments }: SkillGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const assessmentBySkill = Object.fromEntries(
      assessments.map((a) => [a.skill.toLowerCase().trim(), a]),
    );

    // Collect all unique adjacent skills from gaps (these are strengths in disguise —
    // skills the candidate has that bridge to the gap)
    const adjacencySources = new Set<string>();
    gaps.forEach((g) =>
      g.adjacent_known_skills.forEach((s) => adjacencySources.add(s)),
    );

    // Strengths (left column) — union of explicit strengths + skills appearing
    // as adjacent for any gap
    const leftSkills = Array.from(
      new Set([...strengths, ...adjacencySources]),
    );
    const rightSkills = gaps;

    const VERTICAL_SPACING = 90;
    const COLUMN_WIDTH = 380;

    const leftStartY = -((leftSkills.length - 1) * VERTICAL_SPACING) / 2;
    const rightStartY = -((rightSkills.length - 1) * VERTICAL_SPACING) / 2;

    const nodes: Node[] = [];

    leftSkills.forEach((skill, i) => {
      const a = assessmentBySkill[skill.toLowerCase().trim()];
      nodes.push({
        id: `strength-${skill}`,
        type: "strength",
        position: { x: 0, y: leftStartY + i * VERTICAL_SPACING },
        data: {
          skill,
          level: a?.level ?? null,
          confidence: a?.confidence ?? null,
        },
      });
    });

    rightSkills.forEach((gap, i) => {
      nodes.push({
        id: `gap-${gap.skill}`,
        type: "gap",
        position: { x: COLUMN_WIDTH, y: rightStartY + i * VERTICAL_SPACING },
        data: {
          gap,
        },
      });
    });

    // Edges: from each adjacent_known_skill on a gap, draw an edge to the gap
    const edges: Edge[] = [];
    gaps.forEach((gap) => {
      gap.adjacent_known_skills.forEach((adj) => {
        edges.push({
          id: `e-${adj}-${gap.skill}`,
          source: `strength-${adj}`,
          target: `gap-${gap.skill}`,
          animated: true,
          style: { stroke: "#6366f1", strokeWidth: 1.5, strokeOpacity: 0.5 },
        });
      });
    });

    return { nodes, edges };
  }, [strengths, gaps, assessments]);

  return (
    <div style={{ height: 480 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1f2937" gap={24} />
        <Controls
          showInteractive={false}
          className="!bg-bg-800 !border-bg-700 [&>button]:!bg-bg-800 [&>button]:!border-bg-700 [&>button]:!text-slate-300 [&>button:hover]:!bg-bg-700"
        />
      </ReactFlow>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom nodes
// ---------------------------------------------------------------------------

function StrengthNode({ data }: NodeProps<{ skill: string; level: 1 | 2 | 3 | 4 | 5 | null; confidence: number | null }>) {
  return (
    <div
      className={cn(
        "px-3 py-2 rounded-lg border shadow-sm min-w-[140px]",
        "bg-emerald-500/10 border-emerald-500/40 text-emerald-200",
      )}
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 size={14} className="text-emerald-400 shrink-0" />
        <span className="text-sm font-medium truncate">{data.skill}</span>
      </div>
      {data.level && (
        <div className="text-[10px] text-emerald-400/60 mt-0.5 font-mono">
          L{data.level}
          {data.confidence !== null && (
            <span className="ml-1.5 opacity-70">
              · {Math.round(data.confidence * 100)}%
            </span>
          )}
        </div>
      )}
      <Handle
        type="source"
        position={Position.Right}
        className="!bg-emerald-500 !border-emerald-400 !w-2 !h-2"
      />
    </div>
  );
}

function GapNode({ data }: NodeProps<{ gap: SkillGap }>) {
  const { gap } = data;
  const sevColor = severityColor(gap.severity);
  const colorClass = gap.severity >= 0.7 ? "text-red-400" : gap.severity >= 0.4 ? "text-amber-400" : "text-emerald-400";

  return (
    <div
      className={cn(
        "px-3 py-2 rounded-lg border shadow-sm min-w-[160px]",
        sevColor,
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!bg-current !border-current !w-2 !h-2"
      />
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className={cn("shrink-0", colorClass)} />
        <span className="text-sm font-medium truncate">{gap.skill}</span>
      </div>
      <div className="text-[10px] mt-0.5 font-mono opacity-70">
        Need: L{gap.required_level}
        {gap.current_level && <span> · Have: L{gap.current_level}</span>}
        <span className="ml-1.5">· sev {gap.severity.toFixed(2)}</span>
      </div>
    </div>
  );
}
