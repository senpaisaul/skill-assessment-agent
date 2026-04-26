"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Brain, Network, Target, Loader2, AlertCircle, Upload, FileText, X, Mic } from "lucide-react";
import { startAssessment, startAssessmentWithUpload, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { SAMPLE_RESUME, SAMPLE_JD } from "@/lib/sample-data";

export default function LandingPage() {
  const router = useRouter();
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeText, setResumeText] = useState("");
  const [jd, setJd] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadSample = () => { setResumeFile(null); setResumeText(SAMPLE_RESUME); setJd(SAMPLE_JD); setError(null); };
  const handleFileDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files?.[0]; if (f) { setResumeFile(f); setResumeText(""); setError(null); }
  }, []);
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; if (f) { setResumeFile(f); setResumeText(""); setError(null); }
  };
  const clearFile = () => { setResumeFile(null); if (fileInputRef.current) fileInputRef.current.value = ""; };
  const hasResume = !!resumeFile || !!resumeText.trim();

  const handleStart = async () => {
    if (!hasResume || !jd.trim()) { setError("Provide both a resume and a job description."); return; }
    setLoading(true); setError(null);
    try {
      const res = resumeFile
        ? await startAssessmentWithUpload({ resumeFile, jd_text: jd })
        : await startAssessment({ resume_text: resumeText, jd_text: jd });
      sessionStorage.setItem("assessment-init", JSON.stringify({ session_id: res.session_id, first_question: res.next_question, status: res.status }));
      router.push(`/assess/${res.session_id}`);
    } catch (e) {
      setError(`Couldn't start: ${e instanceof ApiError ? e.message : (e as Error).message}`);
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-vignette">
      <div className="max-w-5xl mx-auto px-6 py-16">
        <header className="text-center mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs tracking-wide mb-5">
            <Mic size={12} /><span>Voice-powered AI assessment</span>
          </div>
          <h1 className="text-5xl font-bold tracking-tight mb-4 text-white">
            Skill <span className="text-brand-400">Assessment</span> Agent
          </h1>
          <p className="text-base text-slate-400 max-w-xl mx-auto leading-relaxed">
            Have a conversation with an AI interviewer that adapts to your level in real-time.
          </p>
        </header>

        <div className="grid md:grid-cols-3 gap-3 mb-14">
          <Diff icon={<Brain size={18} />} title="Adaptive difficulty" body="Questions get harder when you're strong, easier when you struggle — like a real interviewer." />
          <Diff icon={<Network size={18} />} title="Skill graph" body="See which skills you have that bridge to each gap. Learn smarter." />
          <Diff icon={<Target size={18} />} title="Evidence-based" body="Every rating has quoted evidence and a confidence number. No black boxes." />
        </div>

        <div className="grid md:grid-cols-2 gap-5 mb-6">
          <div>
            <label className="flex items-center justify-between text-sm font-medium text-slate-300 mb-2">
              <span>Resume</span>
              <span className="text-xs text-slate-500 font-normal">{resumeFile ? resumeFile.name : resumeText.trim() ? "text loaded" : "PDF, DOCX, or TXT"}</span>
            </label>
            {resumeFile ? (
              <div className="h-[340px] rounded-xl bg-bg-900 border border-bg-700 flex flex-col items-center justify-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-brand-500/10 border border-brand-500/30 flex items-center justify-center"><FileText size={28} className="text-brand-400" /></div>
                <div className="text-center"><p className="text-sm text-slate-200 font-medium">{resumeFile.name}</p><p className="text-xs text-slate-500 mt-1">{(resumeFile.size / 1024).toFixed(0)} KB</p></div>
                <button onClick={clearFile} className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-red-400"><X size={12} /> Remove</button>
              </div>
            ) : resumeText.trim() ? (
              <div className="relative">
                <textarea value={resumeText} onChange={e => setResumeText(e.target.value)} rows={14}
                  className="w-full h-[340px] p-4 rounded-xl bg-bg-900 border border-bg-700 focus:border-brand-500/50 focus:ring-1 focus:ring-brand-500/20 focus:outline-none text-xs text-slate-300 font-mono leading-relaxed resize-none" />
                <button onClick={() => setResumeText("")} className="absolute top-3 right-3 text-slate-500 hover:text-red-400"><X size={14} /></button>
              </div>
            ) : (
              <div className={cn("h-[340px] rounded-xl drop-zone cursor-pointer bg-bg-900 flex flex-col items-center justify-center gap-4", dragOver && "drag-over")}
                onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)} onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}>
                <input ref={fileInputRef} type="file" accept=".pdf,.docx,.doc,.txt,.md" onChange={handleFileSelect} className="hidden" />
                <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center"><Upload size={24} className="text-brand-400" /></div>
                <div className="text-center"><p className="text-sm text-slate-300 mb-1">Drop your resume here</p><p className="text-xs text-slate-500">PDF, DOCX, or TXT</p></div>
              </div>
            )}
          </div>
          <div>
            <label className="flex items-center justify-between text-sm font-medium text-slate-300 mb-2">
              <span>Job description</span>
              <span className="text-xs text-slate-500 font-normal">{jd.trim() ? `${jd.length.toLocaleString()} chars` : "paste the JD"}</span>
            </label>
            <textarea value={jd} onChange={e => setJd(e.target.value)} placeholder="Paste the job description here…" rows={14}
              className="w-full h-[340px] p-4 rounded-xl bg-bg-900 border border-bg-700 focus:border-brand-500/50 focus:ring-1 focus:ring-brand-500/20 focus:outline-none text-xs text-slate-300 font-mono leading-relaxed resize-none placeholder:text-slate-600" />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <button onClick={loadSample} className="text-xs text-slate-500 hover:text-brand-400 underline underline-offset-4">Load sample data</button>
          <button onClick={handleStart} disabled={loading || !hasResume || !jd.trim()}
            className={cn("px-6 py-3 rounded-xl font-medium text-sm flex items-center gap-2 transition-all",
              "bg-brand-600 hover:bg-brand-500 text-white disabled:bg-bg-700 disabled:text-slate-600 disabled:cursor-not-allowed")}>
            {loading ? <><Loader2 size={16} className="animate-spin" /> Parsing…</> : <><Sparkles size={14} /> Begin interview</>}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 flex items-start gap-3">
            <AlertCircle size={18} className="shrink-0 mt-0.5" /><p className="text-sm">{error}</p>
          </div>
        )}

        <footer className="mt-20 pt-6 border-t border-bg-700 text-center text-xs text-slate-600">
          LangGraph supervisor · IRT adaptive questioning · Bloom 1-5 rubric · Voice-first interface
        </footer>
      </div>
    </main>
  );
}

function Diff({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="p-4 rounded-xl bg-bg-900 border border-bg-700">
      <div className="w-9 h-9 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center mb-3">{icon}</div>
      <h3 className="font-medium text-sm text-slate-200 mb-1">{title}</h3>
      <p className="text-xs text-slate-500 leading-relaxed">{body}</p>
    </div>
  );
}