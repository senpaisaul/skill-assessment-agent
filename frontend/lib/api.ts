import type {
  StartAssessmentResponse,
  RespondResponse,
  AssessmentResultResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { const err = await res.json(); if (err?.detail) detail = err.detail; } catch { }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { const err = await res.json(); if (err?.detail) detail = err.detail; } catch { }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export async function startAssessment(args: {
  resume_text: string;
  jd_text: string;
  user_id?: string | null;
}): Promise<StartAssessmentResponse> {
  return postJson<StartAssessmentResponse>("/api/assess/start", {
    resume_text: args.resume_text,
    jd_text: args.jd_text,
    user_id: args.user_id ?? null,
  });
}

export async function startAssessmentWithUpload(args: {
  resumeFile: File;
  jd_text: string;
  user_id?: string | null;
}): Promise<StartAssessmentResponse> {
  const form = new FormData();
  form.append("resume", args.resumeFile);
  form.append("jd_text", args.jd_text);
  if (args.user_id) form.append("user_id", args.user_id);
  const res = await fetch(`${BASE}/api/assess/start-upload`, { method: "POST", body: form });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try { const err = await res.json(); if (err?.detail) detail = err.detail; } catch { }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<StartAssessmentResponse>;
}

export async function respondToQuestion(args: {
  session_id: string;
  response: string;
}): Promise<RespondResponse> {
  return postJson<RespondResponse>("/api/assess/respond", args);
}

export async function getResult(sessionId: string): Promise<AssessmentResultResponse> {
  return getJson<AssessmentResultResponse>(`/api/assess/result/${sessionId}`);
}

export async function checkReady(): Promise<{ ready: boolean; checks: Record<string, unknown> }> {
  return getJson("/api/ready");
}

/** TTS via backend ElevenLabs proxy. Returns audio blob or null (→ browser fallback). */
export async function textToSpeech(text: string): Promise<Blob | null> {
  try {
    const res = await fetch(`${BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (res.status === 204) return null;
    if (!res.ok) return null;
    return await res.blob();
  } catch {
    return null;
  }
}

/** Ask the agent to rephrase the current question. No scoring, no state change. */
export async function clarifyQuestion(args: {
  session_id: string;
  original_question: string;
  skill: string;
  bloom_level: number;
  candidate_message: string;
}): Promise<{ rephrased_question: string; context: string }> {
  return postJson("/api/assess/clarify", args);
}