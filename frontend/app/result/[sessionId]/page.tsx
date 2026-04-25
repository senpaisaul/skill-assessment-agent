"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Loader2,
  AlertCircle,
  CheckCircle2,
  Target,
  TrendingDown,
  Quote,
  Clock,
  ExternalLink,
  ArrowRight,
} from "lucide-react";
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
    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 12; // ~24s of polling

    async function poll() {
      try {
        const r = await getResult(sessionId);
        if (cancelled) return;
        // Keep polling until plan is populated (downstream nodes finish)
        if (!r.learning_plan && attempts < maxAttempts) {
          attempts += 1;
          setTimeout(poll, 2000);
          return;
        }
        setResult(r);
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof ApiError ? e.message : (e as Error).message;
        setError(`Couldn't load results: ${msg}`);
      }
    }
    poll();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  if (error) {
    return (
      <div className="min-h-screen bg-vignette flex items-center justify-center p-6">
        <div className="max-w-md p-6 rounded-xl bg-red-500/10 border border-red-500/30 text-center">
          <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
          <p className="text-red-300 mb-4">{error}</p>
          <Link
            href="/"
            className="inline-block px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm"
          >
            Start over
          </Link>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen bg-vignette flex items-center justify-center">
        <div className="text-center">
          <Loader2 size={32} className="animate-spin text-brand-400 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">
            Computing assessment, gaps, and learning plan…
          </p>
        </div>
      </div>
    );
  }

  const { skill_assessments, gap_analysis, learning_plan } = result;

  return (
    <main className="min-h-screen bg-vignette">
      <div className="max-w-7xl mx-auto px-6 py-10">
        {/* Header */}
        <header className="flex items-start justify-between mb-10">
          <div>
            <Link
              href="/"
              className="text-sm text-slate-500 hover:text-brand-400 mb-2 inline-block"
            >
              ← New assessment
            </Link>
            <h1 className="text-3xl font-semibold text-slate-100">
              Assessment Result
            </h1>
            {learning_plan?.candidate_name && (
              <p className="text-slate-400 mt-1">
                {learning_plan.candidate_name} · {learning_plan.target_role}
              </p>
            )}
          </div>

          {gap_analysis && (
            <div className="text-right">
              <div className="text-sm text-slate-500 uppercase tracking-wider mb-1">
                Overall match
              </div>
              <div
                className={cn(
                  "text-4xl font-semibold",
                  gap_analysis.overall_match_score >= 0.7
                    ? "text-emerald-400"
                    : gap_analysis.overall_match_score >= 0.4
                      ? "text-amber-400"
                      : "text-red-400",
                )}
              >
                {Math.round(gap_analysis.overall_match_score * 100)}%
              </div>
            </div>
          )}
        </header>

        {/* Honest summary */}
        {gap_analysis?.summary && (
          <div className="p-5 rounded-xl bg-bg-800/50 border border-bg-700 mb-10">
            <p className="text-slate-300 leading-relaxed">{gap_analysis.summary}</p>
          </div>
        )}

        {/* Skill graph — the second headline differentiator */}
        {gap_analysis && skill_assessments.length > 0 && (
          <section className="mb-10">
            <h2 className="text-xl font-semibold text-slate-100 mb-1">
              Skill graph
            </h2>
            <p className="text-sm text-slate-500 mb-4">
              Your strengths feed into your gaps via adjacent already-known skills.
            </p>
            <div className="rounded-xl bg-bg-800/50 border border-bg-700 overflow-hidden">
              <SkillGraph
                strengths={gap_analysis.strengths}
                gaps={gap_analysis.gaps}
                assessments={skill_assessments}
              />
            </div>
          </section>
        )}

        {/* Per-skill assessments */}
        <section className="mb-10">
          <h2 className="text-xl font-semibold text-slate-100 mb-1">
            Per-skill proficiency
          </h2>
          <p className="text-sm text-slate-500 mb-4">
            Evidence-grounded ratings on a Bloom 1-5 scale. Each rating ships
            with quoted evidence and a confidence number.
          </p>
          <div className="space-y-3">
            {skill_assessments.map((a) => (
              <SkillAssessmentRow key={a.skill} assessment={a} />
            ))}
          </div>
        </section>

        {/* Learning plan */}
        {learning_plan && learning_plan.modules.length > 0 && (
          <section>
            <div className="flex items-baseline justify-between mb-1">
              <h2 className="text-xl font-semibold text-slate-100">
                Personalised learning plan
              </h2>
              <div className="text-sm text-slate-400">
                <Clock size={14} className="inline mr-1" />
                {learning_plan.total_hours_min.toFixed(0)}–
                {learning_plan.total_hours_max.toFixed(0)} hours total
              </div>
            </div>
            <p className="text-sm text-slate-500 mb-4">
              Modules ordered by prerequisites — start at the top.
            </p>
            <div className="space-y-4">
              {learning_plan.modules.map((m, idx) => (
                <ModuleCard key={m.skill} module={m} stepNumber={idx + 1} />
              ))}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Per-skill assessment row
// ---------------------------------------------------------------------------

function SkillAssessmentRow({
  assessment: a,
}: {
  assessment: AssessmentResultResponse["skill_assessments"][number];
}) {
  const level = a.level as 1 | 2 | 3 | 4 | 5;
  const meetsRequired = (a.gap_to_required ?? 0) <= 0;

  return (
    <div className="p-4 rounded-lg bg-bg-800/50 border border-bg-700">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="font-medium text-slate-100">{a.skill}</span>
          {meetsRequired ? (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 inline-flex items-center gap-1">
              <CheckCircle2 size={12} /> meets requirement
            </span>
          ) : (
            (a.gap_to_required ?? 0) > 0 && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 inline-flex items-center gap-1">
                <TrendingDown size={12} /> gap of {a.gap_to_required}
              </span>
            )
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500">
            {Math.round(a.confidence * 100)}% confidence
          </span>
          <div
            className={cn(
              "px-2.5 py-1 rounded-full border text-xs font-medium",
              bloomColor(level),
            )}
          >
            {ProficiencyLevelName[level]}
            <span className="ml-1.5 opacity-60">L{level}</span>
          </div>
        </div>
      </div>

      <p className="text-sm text-slate-400 mb-3 leading-relaxed">{a.reasoning}</p>

      {a.evidence.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-slate-500 hover:text-slate-300 inline-flex items-center gap-1">
            <Quote size={12} /> evidence ({a.evidence.length})
          </summary>
          <ul className="mt-2 space-y-1.5 pl-4 border-l-2 border-bg-700">
            {a.evidence.map((e, i) => (
              <li key={i} className="text-slate-400 italic">
                &ldquo;{e}&rdquo;
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Learning plan module card
// ---------------------------------------------------------------------------

function ModuleCard({
  module: m,
  stepNumber,
}: {
  module: AssessmentResultResponse["learning_plan"] extends infer P
    ? P extends { modules: (infer M)[] }
      ? M
      : never
    : never;
  stepNumber: number;
}) {
  const level = m.target_level as 1 | 2 | 3 | 4 | 5;

  return (
    <div className="p-5 rounded-xl bg-bg-800/50 border border-bg-700">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-baseline gap-3">
          <span className="text-3xl font-bold text-brand-400/40 font-mono">
            {String(stepNumber).padStart(2, "0")}
          </span>
          <div>
            <h3 className="text-lg font-semibold text-slate-100">{m.skill}</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Target: {ProficiencyLevelName[level]}
              <span className="mx-2 opacity-50">·</span>
              {m.estimated_hours_min.toFixed(1)}–{m.estimated_hours_max.toFixed(1)} hr
            </p>
          </div>
        </div>
        <div
          className={cn(
            "px-2.5 py-1 rounded-full border text-xs font-medium",
            bloomColor(level),
          )}
        >
          L{level}
        </div>
      </div>

      <p className="text-sm text-slate-400 mb-3">{m.rationale}</p>

      {m.prerequisites.length > 0 && (
        <div className="text-xs text-slate-500 mb-3 flex items-center gap-2 flex-wrap">
          <span>Prerequisites:</span>
          {m.prerequisites.map((p) => (
            <span
              key={p}
              className="px-2 py-0.5 rounded-full bg-bg-900 border border-bg-700"
            >
              {p}
            </span>
          ))}
        </div>
      )}

      <div className="space-y-1.5">
        {m.resources.map((r, i) => (
          <a
            key={i}
            href={r.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-bg-700/50 border border-transparent hover:border-bg-700 transition-colors group"
          >
            <div className="flex-1 min-w-0">
              <div className="text-sm text-slate-200 group-hover:text-brand-300 truncate">
                {r.title}
              </div>
              <div className="text-xs text-slate-500 truncate">
                {r.source} · {r.estimated_minutes} min · {r.reason}
              </div>
            </div>
            <ExternalLink
              size={14}
              className="text-slate-600 group-hover:text-brand-400 shrink-0"
            />
          </a>
        ))}
      </div>
    </div>
  );
}
