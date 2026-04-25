"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { respondToQuestion, ApiError } from "@/lib/api";
import type { QuestionPayload } from "@/lib/types";
import { ProficiencyLevelName } from "@/lib/types";
import { cn, bloomColor } from "@/lib/cn";
import { IrtSidebar } from "@/components/IrtSidebar";

interface SkillProgress {
  skill: string;
  thetas: number[]; // running theta value before each question on this skill
  bloomLevels: number[]; // bloom levels asked
}

export default function AssessmentPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [currentQuestion, setCurrentQuestion] = useState<QuestionPayload | null>(null);
  const [response, setResponse] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [progress, setProgress] = useState<Record<string, SkillProgress>>({});

  // On mount, pull the init payload stashed by the landing page
  useEffect(() => {
    const raw = sessionStorage.getItem("assessment-init");
    if (!raw) {
      setError("No active assessment session. Please start over.");
      return;
    }
    try {
      const init = JSON.parse(raw);
      if (init.session_id !== sessionId) {
        setError("Session ID mismatch. Please start over.");
        return;
      }
      if (init.status === "complete") {
        // No questions to ask — pipeline ran straight to end
        setCompleted(true);
        return;
      }
      if (init.first_question) {
        const q = init.first_question as QuestionPayload;
        setCurrentQuestion(q);
        appendProgress(q);
      }
    } catch {
      setError("Couldn't read session state. Please start over.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Auto-redirect once interview is complete (small delay so user sees the success state)
  useEffect(() => {
    if (!completed) return;
    const t = setTimeout(() => router.push(`/result/${sessionId}`), 1200);
    return () => clearTimeout(t);
  }, [completed, sessionId, router]);

  const appendProgress = useCallback((q: QuestionPayload) => {
    setProgress((prev) => {
      const existing = prev[q.skill] ?? { skill: q.skill, thetas: [], bloomLevels: [] };
      return {
        ...prev,
        [q.skill]: {
          skill: q.skill,
          thetas: [...existing.thetas, q.theta_before],
          bloomLevels: [...existing.bloomLevels, q.bloom_level],
        },
      };
    });
  }, []);

  const handleSubmit = async () => {
    if (!response.trim() || !currentQuestion) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await respondToQuestion({
        session_id: sessionId,
        response: response.trim(),
      });

      if (res.status === "complete") {
        setCompleted(true);
        return;
      }

      if (res.next_question) {
        setCurrentQuestion(res.next_question);
        appendProgress(res.next_question);
        setResponse("");
      }
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : (e as Error).message;
      setError(`Failed to submit answer: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-vignette flex items-center justify-center p-6">
        <div className="max-w-md p-6 rounded-xl bg-red-500/10 border border-red-500/30 text-center">
          <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
          <p className="text-red-300 mb-4">{error}</p>
          <button
            onClick={() => router.push("/")}
            className="px-4 py-2 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-sm"
          >
            Start over
          </button>
        </div>
      </div>
    );
  }

  if (completed) {
    return (
      <div className="min-h-screen bg-vignette flex items-center justify-center p-6">
        <div className="max-w-md p-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-center">
          <CheckCircle2 size={40} className="text-emerald-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-emerald-300 mb-2">
            Interview complete
          </h2>
          <p className="text-slate-400 mb-4">
            Scoring your responses, computing gaps, and building your learning plan…
          </p>
          <Loader2 size={20} className="animate-spin text-brand-400 mx-auto" />
        </div>
      </div>
    );
  }

  if (!currentQuestion) {
    return (
      <div className="min-h-screen bg-vignette flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-brand-400" />
      </div>
    );
  }

  const bloomLevel = currentQuestion.bloom_level as 1 | 2 | 3 | 4 | 5;

  return (
    <main className="min-h-screen bg-vignette">
      <div className="max-w-7xl mx-auto px-6 py-8 grid lg:grid-cols-[1fr_360px] gap-8">
        {/* Question + answer pane */}
        <section>
          {/* Skill header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">
                Skill {currentQuestion.skill_index + 1} of {currentQuestion.skills_total}
              </div>
              <h2 className="text-3xl font-semibold text-slate-100">
                {currentQuestion.skill}
              </h2>
            </div>
            <div
              className={cn(
                "px-3 py-1.5 rounded-full border text-sm font-medium",
                bloomColor(bloomLevel),
              )}
            >
              {ProficiencyLevelName[bloomLevel]}
              <span className="ml-2 opacity-60">L{bloomLevel}</span>
            </div>
          </div>

          {/* The question */}
          <div className="p-6 rounded-xl bg-bg-800/50 border border-bg-700 mb-6">
            <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">
              Question
            </div>
            <p className="text-lg text-slate-100 leading-relaxed">
              {currentQuestion.question}
            </p>
          </div>

          {/* Answer input */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Your answer
            </label>
            <textarea
              value={response}
              onChange={(e) => setResponse(e.target.value)}
              placeholder="Take your time. Cite specific tools, decisions, trade-offs you've encountered…"
              rows={8}
              disabled={submitting}
              className={cn(
                "w-full p-4 rounded-lg",
                "bg-bg-800/50 border border-bg-700",
                "focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 focus:outline-none",
                "text-slate-200 placeholder:text-slate-600 resize-y",
                "disabled:opacity-60",
              )}
              autoFocus
            />

            <div className="mt-4 flex items-center justify-between">
              <p className="text-xs text-slate-500">
                Be specific. Vague answers get scored as REMEMBER level.
              </p>
              <button
                onClick={handleSubmit}
                disabled={submitting || !response.trim()}
                className={cn(
                  "px-5 py-2.5 rounded-lg font-medium transition-all flex items-center gap-2",
                  "bg-brand-600 hover:bg-brand-500 text-white",
                  "disabled:bg-bg-700 disabled:text-slate-500 disabled:cursor-not-allowed",
                )}
              >
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Scoring…
                  </>
                ) : (
                  <>
                    Submit answer
                    <ArrowRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </section>

        {/* IRT progress sidebar — the headline differentiator visualization */}
        <aside>
          <IrtSidebar
            currentSkill={currentQuestion.skill}
            progress={progress}
          />
        </aside>
      </div>
    </main>
  );
}
