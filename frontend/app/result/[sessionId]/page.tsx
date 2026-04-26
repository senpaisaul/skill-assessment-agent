"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Loader2, AlertCircle, CheckCircle2, TrendingDown, Quote, Clock, ExternalLink } from "lucide-react";
import Link from "next/link";
import { getResult, ApiError } from "@/lib/api";
import type { AssessmentResultResponse } from "@/lib/types";
import { ProficiencyLevelName } from "@/lib/types";
import { cn, bloomColor, severityColor } from "@/lib/cn";
import { SkillGraph } from "@/components/SkillGraph";

export default function ResultsPage() {
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;
  const [result, setResult] = useState<AssessmentResultResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false; let attempts = 0;
    async function poll() {
      try {
        const r = await getResult(sessionId);
        if (cancelled) return;
        if (!r.learning_plan && attempts < 15) { attempts++; setTimeout(poll, 2000); return; }
        setResult(r);
      } catch (e) {
        if (!cancelled) setError(`Couldn't load results: ${e instanceof ApiError ? e.message : (e as Error).message}`);
      }
    }
    poll();
    return () => { cancelled = true; };
  }, [sessionId]);

  if (error) return (
    <div className="min-h-screen bg-vignette flex items-center justify-center p-6">
      <div className="max-w-md p-6 rounded-2xl bg-red-500/10 border border-red-500/20 text-center">
        <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
        <p className="text-red-300 text-sm mb-4">{error}</p>
        <Link href="/" className="inline-block px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm">Start over</Link>
      </div>
    </div>
  );

  if (!result) return (
    <div className="min-h-screen bg-vignette flex items-center justify-center">
      <div className="text-center"><Loader2 size={32} className="animate-spin text-brand-400 mx-auto mb-3" /><p className="text-slate-400 text-sm">Building your results…</p></div>
    </div>
  );

  const { skill_assessments, gap_analysis, learning_plan } = result;

  return (
    <main className="min-h-screen bg-vignette">
      <div className="max-w-6xl mx-auto px-6 py-10">
        <header className="flex items-start justify-between mb-10">
          <div>
            <Link href="/" className="text-xs text-slate-500 hover:text-brand-400 mb-2 inline-block">← New assessment</Link>
            <h1 className="text-2xl font-semibold text-white">Assessment Result</h1>
            {learning_plan?.candidate_name && <p className="text-sm text-slate-400 mt-1">{learning_plan.candidate_name} · {learning_plan.target_role}</p>}
          </div>
          {gap_analysis && (
            <div className="text-right">
              <div className="text-xs text-slate-500 uppercase tracking-widest mb-1">Overall match</div>
              <div className={cn("text-4xl font-bold",
                gap_analysis.overall_match_score >= 0.7 ? "text-emerald-400" : gap_analysis.overall_match_score >= 0.4 ? "text-amber-400" : "text-red-400")}>
                {Math.round(gap_analysis.overall_match_score * 100)}%
              </div>
            </div>
          )}
        </header>

        {gap_analysis?.summary && (
          <div className="p-5 rounded-2xl bg-bg-900 border border-bg-700 mb-10">
            <p className="text-sm text-slate-300 leading-relaxed">{gap_analysis.summary}</p>
          </div>
        )}

        {gap_analysis && skill_assessments.length > 0 && (
          <section className="mb-10">
            <h2 className="text-lg font-semibold text-white mb-1">Skill graph</h2>
            <p className="text-xs text-slate-500 mb-4">Strengths feed into gaps via adjacent skills.</p>
            <div className="rounded-2xl bg-bg-900 border border-bg-700 overflow-hidden">
              <SkillGraph strengths={gap_analysis.strengths} gaps={gap_analysis.gaps} assessments={skill_assessments} />
            </div>
          </section>
        )}

        <section className="mb-10">
          <h2 className="text-lg font-semibold text-white mb-1">Per-skill proficiency</h2>
          <p className="text-xs text-slate-500 mb-4">Bloom 1-5, evidence-grounded.</p>
          <div className="space-y-3">
            {skill_assessments.map(a => {
              const level = a.level as 1 | 2 | 3 | 4 | 5;
              const meets = (a.gap_to_required ?? 0) <= 0;
              return (
                <div key={a.skill} className="p-4 rounded-xl bg-bg-900 border border-bg-700">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="font-medium text-sm text-slate-100">{a.skill}</span>
                      {meets ? (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center gap-1"><CheckCircle2 size={10} /> meets</span>
                      ) : (a.gap_to_required ?? 0) > 0 && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center gap-1"><TrendingDown size={10} /> gap {a.gap_to_required}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[10px] text-slate-500">{Math.round(a.confidence * 100)}%</span>
                      <div className={cn("px-2 py-0.5 rounded-full border text-[10px] font-medium", bloomColor(level))}>{ProficiencyLevelName[level]} L{level}</div>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400 mb-3 leading-relaxed">{a.reasoning}</p>
                  {a.evidence.length > 0 && (
                    <details className="text-[11px]">
                      <summary className="cursor-pointer text-slate-500 hover:text-slate-300 inline-flex items-center gap-1"><Quote size={10} /> evidence ({a.evidence.length})</summary>
                      <ul className="mt-2 space-y-1.5 pl-4 border-l-2 border-bg-700">
                        {a.evidence.map((e, i) => <li key={i} className="text-slate-400 italic">&ldquo;{e}&rdquo;</li>)}
                      </ul>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        {learning_plan && learning_plan.modules.length > 0 && (
          <section>
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="text-lg font-semibold text-white">Learning plan</h2>
              <div className="text-xs text-slate-400"><Clock size={12} className="inline mr-1" />{learning_plan.total_hours_min.toFixed(0)}–{learning_plan.total_hours_max.toFixed(0)} hr</div>
            </div>
            <p className="text-xs text-slate-500 mb-4">Ordered by prerequisites.</p>
            <div className="space-y-4">
              {learning_plan.modules.map((m, idx) => {
                const level = m.target_level as 1 | 2 | 3 | 4 | 5;
                return (
                  <div key={m.skill} className="p-5 rounded-2xl bg-bg-900 border border-bg-700">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-baseline gap-3">
                        <span className="text-2xl font-bold text-brand-400/30 font-mono">{String(idx + 1).padStart(2, "0")}</span>
                        <div><h3 className="text-base font-semibold text-white">{m.skill}</h3>
                          <p className="text-[10px] text-slate-500 mt-0.5">Target: {ProficiencyLevelName[level]} · {m.estimated_hours_min.toFixed(1)}–{m.estimated_hours_max.toFixed(1)} hr</p></div>
                      </div>
                      <div className={cn("px-2 py-0.5 rounded-full border text-[10px] font-medium", bloomColor(level))}>L{level}</div>
                    </div>
                    <p className="text-xs text-slate-400 mb-3">{m.rationale}</p>
                    {m.prerequisites.length > 0 && (
                      <div className="text-[10px] text-slate-500 mb-3 flex items-center gap-2 flex-wrap">
                        <span>Prerequisites:</span>
                        {m.prerequisites.map(p => <span key={p} className="px-2 py-0.5 rounded-full bg-bg-950 border border-bg-700">{p}</span>)}
                      </div>
                    )}
                    <div className="space-y-1.5">
                      {m.resources.map((r, i) => (
                        <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-bg-700/50 border border-transparent hover:border-bg-700 transition-colors group">
                          <div className="flex-1 min-w-0">
                            <div className="text-xs text-slate-200 group-hover:text-brand-300 truncate">{r.title}</div>
                            <div className="text-[10px] text-slate-500 truncate">{r.source} · {r.estimated_minutes} min</div>
                          </div>
                          <ExternalLink size={12} className="text-slate-600 group-hover:text-brand-400 shrink-0" />
                        </a>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}