"""
FastAPI entrypoint for the skill-assessment agent.

Exposes:
- POST /api/assess/start     — accept resume + JD, kick off the graph, return session_id
- POST /api/assess/respond   — submit a candidate answer to the current question
- GET  /api/assess/stream    — SSE stream of node events (assistant-ui binds here)
- GET  /api/assess/result    — fetch final assessment + learning plan
- GET  /api/health           — liveness check

The graph itself is wired in graph/builder.py (Stage 2+).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, configure_langsmith
from app.api.assessment import router as assessment_router
from app.api.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: activate LangSmith if configured. Shutdown: close graph checkpointer."""
    # NOTE(stage-7 polish): LangGraph emits deprecation warnings on checkpoint
    # restore for our Pydantic types. Future versions support
    # LANGGRAPH_ALLOWED_MSGPACK_MODULES; current version does not. Functional
    # but noisy. Either upgrade LangGraph or register types explicitly via
    # the serde API in Stage 7.
    configure_langsmith()
    yield
    from app.graph import shutdown_graph
    await shutdown_graph()


app = FastAPI(
    title="Skill Assessment Agent",
    description=(
        "Conversational skill assessment + personalised learning plan agent. "
        "LangGraph supervisor over 5 workers: Parser, Interviewer (IRT-driven), "
        "Scorer, GapAnalyzer, PlanGenerator."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(assessment_router, prefix="/api/assess", tags=["assessment"])


@app.get("/")
async def root():
    return {
        "name": "Skill Assessment Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }
