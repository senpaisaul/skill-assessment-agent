# Demo video script — 3-5 minute walkthrough

**Target length:** 4 minutes
**Target audience:** Hackathon judges
**Format:** Screen recording with voiceover
**Tooling:** OBS or Loom for capture; QuickTime trim if needed

---

## Pre-record checklist

- [ ] Backend running at `localhost:8000` (`uvicorn app.main:app --reload`)
- [ ] Frontend running at `localhost:3000` (`npm run dev`)
- [ ] `.env` has `OPENAI_API_KEY` set
- [ ] **`LANGSMITH_TRACING=true`** (so the trace link is mentioned + grabbable)
- [ ] Browser at `localhost:3000`, dev tools closed, screen at 1440×900 minimum
- [ ] Mic test, no AC noise
- [ ] Sample `01_senior_ai_engineer` ready to load via the button

---

## Beat-by-beat script

### 0:00–0:25 — Hook + the problem

> *[Landing page on screen]*
>
> "A resume tells you what someone *claims* to know. It doesn't tell you what they actually know. This is a conversational skill assessment agent that takes a job description and a candidate's resume, and finds out — in five to ten minutes of dialogue — what they really know, where the gaps are, and what they should learn next."

*Cursor lingers on the three differentiator cards: IRT, ESCO graph, evidence-required scoring.*

### 0:25–0:50 — Architecture in 25 seconds

> *[Cursor hovers over the differentiator cards, then scrolls to the bottom footer]*
>
> "Under the hood it's a LangGraph supervisor over five workers — Parser, Interviewer, Scorer, GapAnalyzer, PlanGenerator. The Interviewer uses Item Response Theory to pick question difficulty adaptively. Skill matching is grounded in sentence-transformers embeddings. Every proficiency rating ships with quoted evidence and a confidence number. No black boxes."

### 0:50–1:05 — Starting the demo

> *[Click "Load sample resume + JD"; both textareas populate]*
>
> "I'll demo it on my own resume against a senior AI engineer role at a platform team."

*Briefly scroll the JD to show "Required: Kubernetes" — sets up the gap reveal later.*

> "Click *Start assessment*."

*Click the button. Loading spinner.*

### 1:05–2:40 — The IRT loop in action

> *[First question appears: usually Python at L3 / Apply]*
>
> "First question is on Python at Bloom level 3 — Apply. The right-hand sidebar shows my running ability estimate, theta — currently zero, no prior."

*Type a confident, specific answer:*

> *"I built a FastAPI service for a CRM platform that handled three concurrent agent pipelines using asyncio.gather, with a global semaphore to bound LLM concurrency at 10."*

*Submit. Watch the sidebar update — theta jumps to ~+0.5, level rises.*

> "Theta jumps to about plus-zero-point-five. The next question on Python comes back at Bloom level 4 — Analyze. The system saw a strong answer and made the next one harder."

*Answer one more Python question well, then the loop advances to LangGraph.*

> "After two questions, confidence threshold met, advances to LangGraph."

*Show two LangGraph turns, similar pattern.*

> *[Now reach Kubernetes]*
>
> "Kubernetes question at L3. I'm going to be honest — I've used Docker but not Kubernetes."

*Type:* "I've heard of pods and services but I haven't actually deployed anything to a cluster."

*Submit. Theta drops; next K8s question downshifts to L2 — the system caught the lower proficiency and is asking an easier follow-up to confirm.*

> "Notice the next Kubernetes question came back at level 2, not level 3. The IRT loop saw a weak answer and adapted *down* — exactly what an experienced human interviewer does."

### 2:40–3:30 — The results page

*[Interview completes; redirect to /result page]*

> "Once the interview is done — five workers run in sequence: Scorer fuses the IRT data with each turn, picks evidence quotes, and assigns confidence. GapAnalyzer ranks the gaps by severity and finds adjacent already-known skills. PlanGenerator runs the MALPP three-agent pattern — diagnose, reflect, retry — to produce a prerequisite-ordered learning plan."

*Scroll to overall match score (e.g. ~45%) and the candidate-facing summary paragraph.*

> "Overall match: 45%. The summary is honest — 'strong on Python and LangGraph, but the Kubernetes gap is the critical blocker for a senior platform role'."

*Scroll to the **skill graph**.*

> "The graph shows my strengths on the left feeding into my gaps on the right via adjacency edges. Docker and Linux are *adjacent* to Kubernetes — those are the foundations the learning plan will leverage."

*Scroll to **per-skill assessments**.*

> "Each skill rated on Bloom 1-5 with mandatory evidence quotes. Click to expand."

*Expand one — show the actual quotes from earlier in the interview.*

> "Note the confidence numbers — 87% for Python, 65% for Kubernetes. We're more confident about strengths than the gap because we have more signal on it."

*Scroll to **learning plan**.*

> "Personalised plan, modules ordered by prerequisite. Kubernetes first — the critical gap — with curated resources from roadmap.sh and freeCodeCamp, time-estimated using a difficulty multiplier. Twenty to forty hours."

*Click an external link to show it actually points to a real resource (roadmap.sh).*

### 3:30–4:00 — Closing

> "What makes this different: IRT-driven adaptive questioning that's *visible* — judges can watch the difficulty track the candidate's ability live. Embedding-based adjacency that recommends *transferable* foundations. Evidence-required scoring with no black-box ratings. And the entire graph is traceable in LangSmith — every node's input and output captured for debugging or auditing."

*[Optional: switch to LangSmith trace link, scroll the trace tree briefly]*

> "Repo is at github.com/senpaisaul/skill-assessment-agent — backend is FastAPI plus LangGraph, frontend is Next.js plus ReactFlow. Both check out and run with one command each. Thanks for watching."

---

## What to leave on the cutting-room floor

- The Mem0 cross-session memory layer — it's wired in but irrelevant to a single demo session. Mention only if asked.
- LangSmith deep-dives — show the trace tree existence, not its details.
- The MALPP reflection retry — too inside-baseball for a 4-minute video. The smoke test in `tests/smoke_stage5.py` proves it works for anyone reading the code.
- Voice mode (Stage 8) — only mention if you got it working; otherwise it's noise.

## If something breaks live

If the LLM call fails or returns garbage: **don't redo the take from scratch.** Cut to the smoke test output (`python tests/smoke_stage4.py` produces a clean, terminal-only validation) and narrate over that. Sample output is in the repo at `samples/*.json` for reference.
