"use client";

import { TrendingUp, Brain } from "lucide-react";
import { cn, bloomColor } from "@/lib/cn";

interface SkillProgress {
  skill: string;
  thetas: number[];
  bloomLevels: number[];
}

interface IrtSidebarProps {
  currentSkill: string;
  progress: Record<string, SkillProgress>;
}

export function IrtSidebar({ currentSkill, progress }: IrtSidebarProps) {
  const skills = Object.values(progress);

  return (
    <div className="sticky top-8 p-5 rounded-xl bg-bg-800/50 border border-bg-700">
      <div className="flex items-center gap-2 mb-4">
        <Brain size={18} className="text-brand-400" />
        <h3 className="font-medium text-slate-200">Adaptive interview state</h3>
      </div>

      <p className="text-xs text-slate-500 mb-5 leading-relaxed">
        Question difficulty tracks your running ability estimate (θ) via Item
        Response Theory. Bloom level updates after each answer.
      </p>

      <div className="space-y-4">
        {skills.length === 0 && (
          <p className="text-sm text-slate-500 italic">No skills probed yet.</p>
        )}
        {skills.map((s) => (
          <SkillRow key={s.skill} skill={s} isCurrent={s.skill === currentSkill} />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-bg-700">
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">
          Bloom levels
        </div>
        <div className="grid grid-cols-5 gap-1 text-[10px] text-center">
          {([1, 2, 3, 4, 5] as const).map((l) => (
            <div
              key={l}
              className={cn(
                "py-1 rounded border",
                bloomColor(l),
              )}
            >
              L{l}
            </div>
          ))}
        </div>
        <div className="mt-2 grid grid-cols-5 gap-1 text-[9px] text-center text-slate-500">
          <div>Remem</div>
          <div>Under</div>
          <div>Apply</div>
          <div>Anlz</div>
          <div>Eval</div>
        </div>
      </div>
    </div>
  );
}

function SkillRow({ skill, isCurrent }: { skill: SkillProgress; isCurrent: boolean }) {
  const lastTheta = skill.thetas.at(-1) ?? 0;
  const lastBloom = (skill.bloomLevels.at(-1) ?? 3) as 1 | 2 | 3 | 4 | 5;
  const trend =
    skill.thetas.length >= 2
      ? skill.thetas.at(-1)! - skill.thetas.at(-2)!
      : 0;

  return (
    <div
      className={cn(
        "p-3 rounded-lg border transition-colors",
        isCurrent
          ? "bg-brand-500/10 border-brand-500/40"
          : "bg-bg-900/50 border-bg-700",
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-sm font-medium",
              isCurrent ? "text-brand-300" : "text-slate-200",
            )}
          >
            {skill.skill}
          </span>
          {isCurrent && (
            <span className="text-[10px] uppercase tracking-wider text-brand-400 bg-brand-500/20 px-1.5 py-0.5 rounded">
              now
            </span>
          )}
        </div>
        <div
          className={cn(
            "px-1.5 py-0.5 rounded border text-[10px] font-mono",
            bloomColor(lastBloom),
          )}
        >
          L{lastBloom}
        </div>
      </div>

      {/* Theta value with trend */}
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-xs text-slate-500">θ =</span>
        <span className="text-sm font-mono text-slate-200">
          {lastTheta >= 0 ? "+" : ""}
          {lastTheta.toFixed(2)}
        </span>
        {trend !== 0 && (
          <span
            className={cn(
              "text-[10px] font-mono flex items-center gap-0.5",
              trend > 0 ? "text-emerald-400" : "text-amber-400",
            )}
          >
            <TrendingUp size={10} className={trend < 0 ? "rotate-180" : ""} />
            {trend > 0 ? "+" : ""}
            {trend.toFixed(2)}
          </span>
        )}
      </div>

      {/* Theta bar (range -3..+3 mapped to 0..100%) */}
      <div className="relative h-1.5 bg-bg-700 rounded-full overflow-hidden mb-2">
        <div
          className="absolute top-0 left-1/2 w-px h-full bg-bg-800/50"
          aria-hidden
        />
        <div
          className={cn(
            "absolute top-0 h-full rounded-full transition-all",
            isCurrent ? "bg-brand-500" : "bg-slate-500",
          )}
          style={{
            left: lastTheta >= 0 ? "50%" : `${50 + (lastTheta / 3) * 50}%`,
            width: `${Math.abs(lastTheta / 3) * 50}%`,
          }}
        />
      </div>

      {/* Bloom-level history dots */}
      <div className="flex gap-1">
        {skill.bloomLevels.map((lvl, i) => (
          <div
            key={i}
            className={cn(
              "w-2 h-2 rounded-full",
              {
                1: "bg-bloom-1",
                2: "bg-bloom-2",
                3: "bg-bloom-3",
                4: "bg-bloom-4",
                5: "bg-bloom-5",
              }[lvl as 1 | 2 | 3 | 4 | 5],
            )}
            title={`Q${i + 1}: L${lvl}`}
          />
        ))}
      </div>
    </div>
  );
}
