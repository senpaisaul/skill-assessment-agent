"use client";

import { TrendingUp, TrendingDown, Minus, Lightbulb, Target } from "lucide-react";
import { cn } from "@/lib/cn";

interface SkillProgress {
    skill: string;
    thetas: number[];
    bloomLevels: number[];
}

interface BloomInsightsProps {
    currentSkill: string;
    progress: Record<string, SkillProgress>;
}

const BLOOM_LABELS: Record<number, string> = {
    1: "Recall", 2: "Understand", 3: "Apply", 4: "Analyze", 5: "Evaluate",
};

function getPerformanceLabel(theta: number) {
    if (theta >= 1.0) return { label: "Excellent", color: "text-emerald-400", icon: TrendingUp };
    if (theta >= 0.3) return { label: "Solid", color: "text-teal-400", icon: TrendingUp };
    if (theta >= -0.3) return { label: "Developing", color: "text-amber-400", icon: Minus };
    return { label: "Needs work", color: "text-red-400", icon: TrendingDown };
}

function getActionableInsight(skill: string, theta: number): string {
    if (theta >= 1.0) return `Strong command of ${skill}. You're operating at the Analyze/Evaluate level — keep showcasing system design thinking.`;
    if (theta >= 0.3) return `Good grasp of ${skill}. To level up, focus on explaining trade-offs and real-world debugging scenarios.`;
    if (theta >= -0.3) return `You understand the basics of ${skill}. Try connecting concepts to specific projects you've built — concrete examples score higher.`;
    return `${skill} needs strengthening. Start with practical hands-on projects. Mention any adjacent experience you have.`;
}

function getProgressPercent(theta: number): number {
    return Math.max(0, Math.min(100, ((theta + 3) / 6) * 100));
}

export function BloomInsights({ currentSkill, progress }: BloomInsightsProps) {
    const skills = Object.values(progress);

    return (
        <div className="sticky top-8 space-y-4">
            <div className="p-4 rounded-xl bg-bg-900 border border-bg-700">
                <div className="flex items-center gap-2 mb-2">
                    <Lightbulb size={16} className="text-teal-400" />
                    <h3 className="font-medium text-slate-200 text-sm tracking-wide">Live Performance</h3>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                    Real-time analysis of your responses. Question difficulty adapts based on your proficiency.
                </p>
            </div>

            {skills.length === 0 && (
                <div className="p-4 rounded-xl bg-bg-900 border border-bg-700">
                    <p className="text-sm text-slate-500 italic text-center py-4">Insights appear as you answer</p>
                </div>
            )}

            {skills.map((s) => {
                const lastTheta = s.thetas.at(-1) ?? 0;
                const lastBloom = s.bloomLevels.at(-1) ?? 3;
                const isCurrent = s.skill === currentSkill;
                const perf = getPerformanceLabel(lastTheta);
                const PerfIcon = perf.icon;
                const insight = getActionableInsight(s.skill, lastTheta);
                const progressPct = getProgressPercent(lastTheta);

                return (
                    <div key={s.skill} className={cn(
                        "insight-card p-4 rounded-xl border-l-2 transition-all",
                        isCurrent
                            ? "bg-teal-500/[0.06] border-l-teal-400 border-t border-r border-b border-bg-700"
                            : "bg-bg-900 border-l-bg-700 border-t border-r border-b border-bg-700",
                    )}>
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <span className={cn("text-sm font-medium", isCurrent ? "text-teal-300" : "text-slate-200")}>{s.skill}</span>
                                {isCurrent && (
                                    <span className="text-[9px] uppercase tracking-widest text-teal-400 bg-teal-500/20 px-1.5 py-0.5 rounded font-medium">active</span>
                                )}
                            </div>
                            <div className={cn("flex items-center gap-1 text-xs font-medium", perf.color)}>
                                <PerfIcon size={12} />{perf.label}
                            </div>
                        </div>

                        <div className="relative h-1.5 bg-bg-700 rounded-full overflow-hidden mb-3">
                            <div className={cn(
                                "absolute top-0 left-0 h-full rounded-full transition-all duration-700",
                                lastTheta >= 0.3 ? "bg-emerald-500" : lastTheta >= -0.3 ? "bg-amber-500" : "bg-red-500",
                            )} style={{ width: `${progressPct}%` }} />
                            <div className="absolute top-0 left-1/2 w-px h-full bg-slate-600/40" />
                        </div>

                        <div className="flex items-center justify-between mb-3 text-xs text-slate-500">
                            <span>Level: <span className="text-slate-300 font-medium">{BLOOM_LABELS[lastBloom] ?? `L${lastBloom}`}</span></span>
                            <span>{s.bloomLevels.length}Q</span>
                        </div>

                        <div className="flex gap-1 mb-3">
                            {s.bloomLevels.map((lvl, i) => (
                                <div key={i} className={cn(
                                    "h-1.5 rounded-full transition-all",
                                    i === s.bloomLevels.length - 1 ? "w-4" : "w-1.5",
                                    { 1: "bg-red-400/70", 2: "bg-amber-400/70", 3: "bg-emerald-400/70", 4: "bg-sky-400/70", 5: "bg-violet-400/70" }[lvl as 1 | 2 | 3 | 4 | 5] ?? "bg-slate-500",
                                )} title={`Q${i + 1}: ${BLOOM_LABELS[lvl]}`} />
                            ))}
                        </div>

                        <p className="text-xs text-slate-400 leading-relaxed">{insight}</p>
                    </div>
                );
            })}

            {skills.length > 0 && (
                <div className="p-3 rounded-xl bg-bg-900 border border-bg-700">
                    <div className="flex items-start gap-2">
                        <Target size={14} className="text-amber-400 mt-0.5 shrink-0" />
                        <p className="text-[11px] text-slate-500 leading-relaxed">
                            <span className="text-slate-400 font-medium">Tip:</span> Be specific — reference real projects, tools, and decisions. Generic answers cap at "Understand".
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}