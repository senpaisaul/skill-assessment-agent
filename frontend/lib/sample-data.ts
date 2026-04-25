// Sample data used by the "Load sample" button. Tuned to produce a realistic
// demo: candidate has strong AI/Python background but is missing Kubernetes
// (the natural senior-role gap that surfaces the IRT loop and adjacency logic).

export const SAMPLE_RESUME = `Abhay Sengar
sengarabhay03@gmail.com | Bhopal, India
github.com/senpaisaul | linkedin.com/in/abhaysengar2109

EDUCATION
B.Tech Computer Science Engineering, VIT Bhopal University (2022-2026)

EXPERIENCE
AI Engineer Intern, WorkElate (Feb-Mar 2026)
- Built production email intent classification system: Python, FastAPI,
  LangChain LCEL 3-step chain, Gmail OAuth2 integration.
- Implemented daily task digest service with APScheduler, GPT-4o summaries
  over a MongoDB boards/cards schema.

AI/ML Intern, Smart Bridge x Google Cloud (Nov 2025 - Jan 2026)
- Vertex AI pipelines for tabular forecasting; deployed via GCP Cloud Run.

PROJECTS
UniQuant — Generative AI financial forecasting platform
- Amazon Chronos T5-Small + GJR-GARCH(1,1,1) + 4-state HMM regime detection
- FastAPI + Next.js 14, regime-conditional conformal calibration

SparsaOS — Live 3-agent GPT-4o CRM
- LangGraph supervisor + asyncio orchestration + SSE streaming
- Render + Vercel + Supabase, sparsaos.vercel.app

Voice AI Agent for Wise customer support
- Deepgram nova-3 STT + LangChain + GPT-4o-mini + ElevenLabs turbo v2.5 TTS
- Twilio Media Streams (WebSocket v2) for real-time call routing

HackerCup Multi-Agent DSA Solver
- 6-agent LangGraph system. Meta HackerCup 2025 AI Track Global Finalist.

SKILLS
Python · FastAPI · LangChain · LangGraph · LangSmith · Pydantic · Instructor
RAG · Vector databases (Chroma, FAISS) · OpenAI · Anthropic · GPT-4o · Claude
Next.js · React · TypeScript · TailwindCSS
Docker · Git · GCP Vertex AI · Render · Vercel · Supabase
PostgreSQL · MongoDB · Redis
Async Python · Multi-agent orchestration · Production ML
`;

export const SAMPLE_JD = `Senior AI Engineer — Platform Team

We're hiring a Senior AI Engineer to design and operate our agentic systems
platform. You'll own the architecture for multi-agent workflows running in
production for our enterprise customers.

What you'll do:
- Design and build LangGraph-based multi-agent systems
- Operate them at scale on Kubernetes — including custom operators, HPA tuning,
  observability stack
- Build robust RAG pipelines with vector databases
- Mentor mid-level engineers on agentic system design
- Work closely with product to define new agent capabilities

Required skills:
- 5+ years of Python in production
- LangGraph or equivalent agent orchestration framework (CrewAI, AutoGen)
- Kubernetes — ability to author Helm charts, debug pod scheduling, write CRDs
- PostgreSQL — schema design, query optimization, connection pooling
- Strong async Python / FastAPI experience
- RAG systems with production vector databases

Preferred:
- Experience with LangSmith / Langfuse for agent observability
- GraphQL APIs
- Prior experience leading technical projects
`;
