"""
FastAPI entrypoint for the skill-assessment agent.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, configure_langsmith
from app.api.assessment import router as assessment_router
from app.api.health import router as health_router
from app.api.tts import router as tts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_langsmith()
    yield
    from app.graph import shutdown_graph
    await shutdown_graph()


app = FastAPI(
    title="Skill Assessment Agent",
    description=(
        "Conversational skill assessment + personalised learning plan agent. "
        "LangGraph supervisor over 5 workers."
    ),
    version="0.2.0",
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
app.include_router(tts_router, prefix="/api", tags=["tts"])


@app.get("/")
async def root():
    return {"name": "Skill Assessment Agent", "version": "0.2.0", "docs": "/docs"}