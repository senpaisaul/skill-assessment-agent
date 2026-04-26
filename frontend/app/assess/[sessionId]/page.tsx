"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  Mic, MicOff, Send, Loader2, AlertCircle, CheckCircle2,
  Keyboard, Volume2, RotateCcw, MessageCircleQuestion, X,
} from "lucide-react";
import { respondToQuestion, textToSpeech, clarifyQuestion, ApiError } from "@/lib/api";
import type { QuestionPayload } from "@/lib/types";
import { ProficiencyLevelName } from "@/lib/types";
import { cn } from "@/lib/cn";
import { SoundWave, AgentStatusText, type AgentState } from "@/components/SoundWave";
import { BloomInsights } from "@/components/BloomInsights";

function cleanTranscript(raw: string): string {
  return raw
    .replace(/\b(um+|uh+|er+|ah+|hmm+|like,?\s|you know,?\s|so,?\s|basically,?\s|actually,?\s)/gi, " ")
    .replace(/\b(\w+)\s+\1\b/gi, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
}

interface SkillProgress { skill: string; thetas: number[]; bloomLevels: number[]; }

const CLARIFY_PRESETS = [
  { label: "Relate to my experience", msg: "Can you relate this question to something from my resume or projects?" },
  { label: "Break it down", msg: "Can you break this into a simpler, more specific question?" },
  { label: "Give an example", msg: "Can you give me a concrete example or scenario to think about?" },
];

export default function AssessmentPage() {
  const params = useParams<{ sessionId: string }>();
  const router = useRouter();
  const sessionId = params.sessionId;

  const [currentQuestion, setCurrentQuestion] = useState<QuestionPayload | null>(null);
  const [displayedQuestion, setDisplayedQuestion] = useState("");
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [transcript, setTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [clarifying, setClarifying] = useState(false);
  const [showClarifyMenu, setShowClarifyMenu] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [completed, setCompleted] = useState(false);
  const [progress, setProgress] = useState<Record<string, SkillProgress>>({});
  const [textMode, setTextMode] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [speechSupported, setSpeechSupported] = useState(true);

  const recognitionRef = useRef<any>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  // Track how many final results we've already consumed to prevent duplication
  const finalCountRef = useRef(0);

  useEffect(() => {
    const has = typeof window !== "undefined" && ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setSpeechSupported(has);
    if (!has) setTextMode(true);
  }, []);

  useEffect(() => {
    const raw = sessionStorage.getItem("assessment-init");
    if (!raw) { setError("No active assessment session. Please start over."); return; }
    try {
      const init = JSON.parse(raw);
      if (init.session_id !== sessionId) { setError("Session ID mismatch."); return; }
      if (init.status === "complete") { setCompleted(true); return; }
      if (init.first_question) {
        const q = init.first_question as QuestionPayload;
        setCurrentQuestion(q);
        setDisplayedQuestion(q.question);
        appendProgress(q);
        setTimeout(() => speakText(q.question), 800);
      }
    } catch { setError("Couldn't read session state."); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  useEffect(() => {
    if (!completed) return;
    const t = setTimeout(() => router.push(`/result/${sessionId}`), 2000);
    return () => clearTimeout(t);
  }, [completed, sessionId, router]);

  useEffect(() => {
    return () => { stopListening(); window.speechSynthesis?.cancel(); if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; } };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const appendProgress = useCallback((q: QuestionPayload) => {
    setProgress(prev => {
      const ex = prev[q.skill] ?? { skill: q.skill, thetas: [], bloomLevels: [] };
      return { ...prev, [q.skill]: { skill: q.skill, thetas: [...ex.thetas, q.theta_before], bloomLevels: [...ex.bloomLevels, q.bloom_level] } };
    });
  }, []);

  // ---- TTS: only set "speaking" when audio actually starts playing ----
  const speakText = useCallback(async (text: string) => {
    // Don't set speaking yet — wait for actual audio playback
    const audioBlob = await textToSpeech(text);
    if (audioBlob && audioBlob.size > 0) {
      const url = URL.createObjectURL(audioBlob);
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onplay = () => setAgentState("speaking");  // sync: speaking starts when audio plays
      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setAgentState("idle");
        if (!textMode) setTimeout(() => startListening(), 300);
      };
      audio.onerror = () => { URL.revokeObjectURL(url); audioRef.current = null; speakWithBrowser(text); };
      audio.play().catch(() => speakWithBrowser(text));
      return;
    }
    speakWithBrowser(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textMode]);

  const speakWithBrowser = useCallback((text: string) => {
    if (!window.speechSynthesis) { setAgentState("idle"); return; }
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.rate = 0.95; utt.pitch = 1.0;
    const voices = window.speechSynthesis.getVoices();
    const pref = voices.find(v => v.name.includes("Google") && v.lang.startsWith("en")) || voices.find(v => v.lang.startsWith("en"));
    if (pref) utt.voice = pref;
    utt.onstart = () => setAgentState("speaking");  // sync: speaking starts when utterance starts
    utt.onend = () => { setAgentState("idle"); if (!textMode) setTimeout(() => startListening(), 300); };
    utt.onerror = () => setAgentState("idle");
    window.speechSynthesis.speak(utt);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [textMode]);

  // ---- STT: fix duplication by tracking finalCount ----
  const startListening = useCallback(() => {
    if (!speechSupported || textMode) return;
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    if (recognitionRef.current) recognitionRef.current.abort();

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.maxAlternatives = 1;

    // Reset the counter for this recording session
    finalCountRef.current = 0;

    recognition.onstart = () => { setIsListening(true); setAgentState("listening"); };

    recognition.onresult = (event: any) => {
      let newFinals = "";
      let interim = "";
      // Only process results we haven't seen yet
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          if (i >= finalCountRef.current) {
            // This is a NEW final result we haven't appended yet
            newFinals += event.results[i][0].transcript + " ";
            finalCountRef.current = i + 1;
          }
          // else: already processed, skip
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      if (newFinals.trim()) {
        setTranscript(prev => (prev + " " + newFinals).trim());
      }
      setInterimTranscript(interim);
    };

    recognition.onerror = (e: any) => {
      if (e.error !== "no-speech" && e.error !== "aborted") console.error("STT:", e.error);
    };
    recognition.onend = () => { setIsListening(false); };

    recognitionRef.current = recognition;
    recognition.start();
  }, [speechSupported, textMode]);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) { recognitionRef.current.stop(); recognitionRef.current = null; }
    setIsListening(false); setInterimTranscript("");
  }, []);

  const toggleListening = () => {
    if (isListening) { stopListening(); setAgentState("idle"); }
    else { setTranscript(""); setInterimTranscript(""); startListening(); }
  };

  // ---- Clarify ----
  const handleClarify = async (message: string) => {
    if (!currentQuestion) return;
    setClarifying(true); setShowClarifyMenu(false);
    stopListening(); window.speechSynthesis?.cancel();
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    try {
      const res = await clarifyQuestion({
        session_id: sessionId, original_question: currentQuestion.question,
        skill: currentQuestion.skill, bloom_level: currentQuestion.bloom_level,
        candidate_message: message,
      });
      const full = res.context ? `${res.context} ${res.rephrased_question}` : res.rephrased_question;
      setDisplayedQuestion(res.rephrased_question);
      setTranscript(""); setTextInput("");
      await speakText(full);
    } catch (e) {
      setError(`Couldn't rephrase: ${e instanceof ApiError ? e.message : (e as Error).message}`);
    } finally { setClarifying(false); }
  };

  // ---- Submit ----
  const submitAnswer = async () => {
    const raw = textMode ? textInput : transcript;
    const cleaned = cleanTranscript(raw);
    if (!cleaned || !currentQuestion) return;
    stopListening(); window.speechSynthesis?.cancel();
    if (audioRef.current) { audioRef.current.pause(); audioRef.current = null; }
    setSubmitting(true); setAgentState("processing"); setShowClarifyMenu(false); setError(null);
    try {
      const res = await respondToQuestion({ session_id: sessionId, response: cleaned });
      if (res.status === "complete") { setCompleted(true); return; }
      if (res.next_question) {
        setCurrentQuestion(res.next_question);
        setDisplayedQuestion(res.next_question.question);
        appendProgress(res.next_question);
        setTranscript(""); setTextInput(""); setInterimTranscript("");
        setTimeout(() => speakText(res.next_question!.question), 600);
      }
    } catch (e) {
      setError(`Failed: ${e instanceof ApiError ? e.message : (e as Error).message}`);
      setAgentState("idle");
    } finally { setSubmitting(false); }
  };

  if (error) return (
    <div className="min-h-screen bg-vignette flex items-center justify-center p-6">
      <div className="max-w-md p-6 rounded-2xl bg-red-500/10 border border-red-500/20 text-center">
        <AlertCircle size={32} className="text-red-400 mx-auto mb-3" />
        <p className="text-red-300 text-sm mb-4">{error}</p>
        <button onClick={() => router.push("/")} className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-sm">Start over</button>
      </div>
    </div>
  );

  if (completed) return (
    <div className="min-h-screen bg-vignette flex items-center justify-center p-6">
      <div className="max-w-md p-8 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-center">
        <CheckCircle2 size={40} className="text-emerald-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-emerald-300 mb-2">Interview complete</h2>
        <p className="text-sm text-slate-400 mb-4">Scoring your answers and building a learning plan…</p>
        <Loader2 size={20} className="animate-spin text-brand-400 mx-auto" />
      </div>
    </div>
  );

  if (!currentQuestion) return (
    <div className="min-h-screen bg-vignette flex items-center justify-center">
      <Loader2 size={32} className="animate-spin text-brand-400" />
    </div>
  );

  const bloomLevel = currentQuestion.bloom_level as 1 | 2 | 3 | 4 | 5;
  const hasAnswer = cleanTranscript(textMode ? textInput : transcript).length > 5;

  return (
    <main className="min-h-screen bg-vignette">
      <div className="max-w-7xl mx-auto px-6 py-6 grid lg:grid-cols-[1fr_320px] gap-8 min-h-screen">
        <div className="flex flex-col">
          {/* Question */}
          <div className="mb-6">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-xs text-slate-500 uppercase tracking-widest">
                {currentQuestion.skill_index + 1}/{currentQuestion.skills_total}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400">
                {currentQuestion.skill}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-bg-700 text-slate-500">
                {ProficiencyLevelName[bloomLevel]} · L{bloomLevel}
              </span>
            </div>
            <div className="p-5 rounded-2xl bg-bg-900 border border-bg-700">
              <p className="text-base text-slate-200 leading-relaxed">{displayedQuestion}</p>
              <div className="mt-3 relative">
                <button onClick={() => setShowClarifyMenu(!showClarifyMenu)}
                  disabled={clarifying || submitting || agentState === "speaking"}
                  className={cn("text-xs flex items-center gap-1.5 transition-colors",
                    showClarifyMenu ? "text-brand-400" : "text-slate-500 hover:text-slate-300",
                    "disabled:text-slate-600 disabled:cursor-not-allowed")}>
                  {clarifying ? <><Loader2 size={12} className="animate-spin" /> Rephrasing…</>
                    : <><MessageCircleQuestion size={12} /> Need this rephrased?</>}
                </button>
                {showClarifyMenu && (
                  <div className="absolute top-8 left-0 z-10 w-72 p-2 rounded-xl bg-bg-800 border border-bg-700 shadow-xl fade-up">
                    <div className="flex items-center justify-between px-2 py-1 mb-1">
                      <span className="text-[10px] text-slate-500 uppercase tracking-widest">Quick options</span>
                      <button onClick={() => setShowClarifyMenu(false)} className="text-slate-500 hover:text-slate-300"><X size={12} /></button>
                    </div>
                    {CLARIFY_PRESETS.map(p => (
                      <button key={p.label} onClick={() => handleClarify(p.msg)}
                        className="w-full text-left px-3 py-2 rounded-lg text-xs text-slate-300 hover:bg-brand-500/10 hover:text-brand-300 transition-colors">
                        {p.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Agent */}
          <div className="flex-1 flex flex-col items-center justify-center gap-5">
            <div className={cn("w-44 h-44 rounded-full flex items-center justify-center border border-bg-700 bg-bg-950",
              agentState === "speaking" ? "glow-ring-active" : "glow-ring")}>
              <SoundWave state={agentState} barCount={20} />
            </div>
            <AgentStatusText state={agentState} />
            <div className="flex items-center gap-4">
              {!textMode ? (
                <>
                  <button onClick={toggleListening} disabled={submitting || agentState === "speaking" || clarifying}
                    className={cn("w-14 h-14 rounded-full flex items-center justify-center transition-all",
                      isListening ? "bg-red-500 hover:bg-red-400 text-white shadow-lg shadow-red-500/20"
                        : "bg-brand-600 hover:bg-brand-500 text-white shadow-lg shadow-brand-500/20",
                      "disabled:bg-bg-700 disabled:text-slate-600 disabled:shadow-none")}
                    title={isListening ? "Stop" : "Record"}>
                    {isListening ? <MicOff size={22} /> : <Mic size={22} />}
                  </button>
                  <button onClick={submitAnswer} disabled={submitting || !hasAnswer}
                    className={cn("h-12 px-6 rounded-full flex items-center gap-2 text-sm font-medium transition-all",
                      hasAnswer ? "bg-accent-500 hover:bg-accent-400 text-black shadow-lg shadow-accent-500/20" : "bg-bg-700 text-slate-600 cursor-not-allowed",
                      "disabled:opacity-50")}>
                    {submitting ? <><Loader2 size={14} className="animate-spin" /> Scoring…</> : <><Send size={14} /> Submit</>}
                  </button>
                  <button onClick={() => { setTextMode(true); stopListening(); setAgentState("idle"); }}
                    className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1"><Keyboard size={14} /> Type</button>
                </>
              ) : speechSupported && (
                <button onClick={() => setTextMode(false)}
                  className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1"><Volume2 size={14} /> Voice</button>
              )}
            </div>
          </div>

          {/* Transcript / text */}
          <div className="mt-6">
            {textMode ? (
              <div>
                <textarea value={textInput} onChange={e => setTextInput(e.target.value)} placeholder="Type your answer…" rows={4} disabled={submitting}
                  className="w-full p-4 rounded-xl bg-bg-900 border border-bg-700 focus:border-brand-500/50 focus:ring-1 focus:ring-brand-500/20 focus:outline-none text-sm text-slate-200 placeholder:text-slate-600 resize-none disabled:opacity-60"
                  autoFocus onKeyDown={e => { if (e.key === "Enter" && e.ctrlKey && hasAnswer) submitAnswer(); }} />
                <div className="mt-3 flex items-center justify-between">
                  <span className="text-[10px] text-slate-600">Ctrl+Enter to submit</span>
                  <button onClick={submitAnswer} disabled={submitting || !hasAnswer}
                    className={cn("px-5 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2 transition-all",
                      "bg-brand-600 hover:bg-brand-500 text-white disabled:bg-bg-700 disabled:text-slate-600 disabled:cursor-not-allowed")}>
                    {submitting ? <><Loader2 size={14} className="animate-spin" /> Scoring…</> : <><Send size={14} /> Submit</>}
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-bg-900 border border-bg-700 min-h-[80px]">
                {transcript || interimTranscript ? (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs text-slate-500 uppercase tracking-widest">Your answer</p>
                      <button onClick={() => { setTranscript(""); setInterimTranscript(""); finalCountRef.current = 0; if (!isListening) startListening(); }}
                        className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1"><RotateCcw size={10} /> Clear</button>
                    </div>
                    <p className="text-sm text-slate-300 leading-relaxed">
                      {transcript}{interimTranscript && <span className="text-slate-500 italic"> {interimTranscript}</span>}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-slate-600 text-center py-2">
                    {isListening ? "Speak your answer… take your time"
                      : agentState === "speaking" ? "Listen to the question, then respond"
                        : "Tap the mic to start speaking"}
                  </p>
                )}
              </div>
            )}
          </div>
        </div>

        <aside className="hidden lg:block">
          <BloomInsights currentSkill={currentQuestion.skill} progress={progress} />
        </aside>
      </div>
    </main>
  );
} 