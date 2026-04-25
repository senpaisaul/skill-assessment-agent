"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Brain, Network, Target, Loader2, AlertCircle } from "lucide-react";
import { startAssessment, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import {
  SAMPLE_RESUME,
  SAMPLE_JD,
} from "@/lib/sample-data";

export default function LandingPage() {
  const router = useRouter();
  const [resume, setResume] = useState("");
  const [jd, setJd] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSample = () => {
    setResume(SAMPLE_RESUME);
    setJd(SAMPLE_JD);
    setError(null);
  };

  const handleStart = async () => {
    if (!resume.trim() || !jd.trim()) {
      setError("Please paste both a resume and a job description.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await startAssessment({ resume_text: resume, jd_text: jd });
      // Stash the first question payload + session id in sessionStorage for /assess to pick up
      sessionStorage.setItem(
        "assessment-init",
        JSON.stringify({
          session_id: res.session_id,
          first_question: res.next_question,
          status: res.status,
        }),
      );
      router.push(`/assess/${res.session_id}`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : (e as Error).message;
      setError(`Couldn't start the assessment: ${msg}`);
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-vignette">
      <div className="max-w-6xl mx-auto px-6 py-12">
        {/* Hero */}
        <header className="text-center mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-500/10 border border-brand-500/30 text-brand-400 text-sm mb-4">
            <Sparkles size={14} />
            <span>Built for the Deccan AI hackathon</span>
          </div>
          <h1 className="text-5xl font-bold tracking-tight mb-4">
            Skill <span className="text-brand-400">Assessment</span> Agent
          </h1>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto">
            A resume tells you what someone <em>claims</em> to know.
            <br />
            This agent finds out what they <strong>actually</strong> know.
          </p>
        </header>

        {/* Differentiators */}
        <div className="grid md:grid-cols-3 gap-4 mb-12">
          <Differentiator
            icon={<Brain size={20} />}
            title="IRT-driven adaptive questions"
            body="Question difficulty tracks the candidate's running ability estimate via Item Response Theory."
          />
          <Differentiator
            icon={<Network size={20} />}
            title="ESCO-grounded skill graph"
            body="Gaps are presented with adjacent already-known skills that make each gap learnable."
          />
          <Differentiator
            icon={<Target size={20} />}
            title="Evidence-required scoring"
            body="Every proficiency rating ships with quoted evidence and a confidence number. No black boxes."
          />
        </div>

        {/* Inputs */}
        <div className="grid md:grid-cols-2 gap-6 mb-6">
          <InputPane
            label="Candidate resume"
            placeholder="Paste the candidate's resume text here…"
            value={resume}
            onChange={setResume}
          />
          <InputPane
            label="Job description"
            placeholder="Paste the JD here…"
            value={jd}
            onChange={setJd}
          />
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={loadSample}
            className="text-sm text-slate-400 hover:text-brand-400 transition-colors underline underline-offset-4"
          >
            Load sample resume + JD
          </button>

          <button
            type="button"
            onClick={handleStart}
            disabled={loading || !resume.trim() || !jd.trim()}
            className={cn(
              "px-6 py-3 rounded-lg font-medium transition-all",
              "bg-brand-600 hover:bg-brand-500 text-white",
              "disabled:bg-bg-700 disabled:text-slate-500 disabled:cursor-not-allowed",
              "flex items-center gap-2",
            )}
          >
            {loading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Parsing…
              </>
            ) : (
              <>
                Start assessment
                <Sparkles size={16} />
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 flex items-start gap-3">
            <AlertCircle size={20} className="shrink-0 mt-0.5" />
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-bg-700 text-center text-sm text-slate-500">
          LangGraph supervisor over five workers · Bloom-aligned 1-5 rubric · roadmap.sh + freeCodeCamp + YouTube + DEV.to resources
        </footer>
      </div>
    </main>
  );
}

function Differentiator({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="p-5 rounded-xl bg-bg-800/50 border border-bg-700">
      <div className="w-10 h-10 rounded-lg bg-brand-500/10 border border-brand-500/30 text-brand-400 flex items-center justify-center mb-3">
        {icon}
      </div>
      <h3 className="font-medium text-slate-200 mb-1">{title}</h3>
      <p className="text-sm text-slate-400">{body}</p>
    </div>
  );
}

function InputPane({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-2">
        {label}
        <span className="ml-2 text-xs text-slate-500 font-normal">
          {value.trim() ? `${value.length.toLocaleString()} chars` : "required"}
        </span>
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={14}
        className={cn(
          "w-full p-4 rounded-lg",
          "bg-bg-800/50 border border-bg-700",
          "focus:border-brand-500 focus:ring-1 focus:ring-brand-500/30 focus:outline-none",
          "text-sm text-slate-200 placeholder:text-slate-600",
          "font-mono leading-relaxed resize-y",
        )}
      />
    </div>
  );
}
