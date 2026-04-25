"""Liveness + readiness checks."""

from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness — is the app running?"""
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    """
    Readiness — are required external dependencies configured?
    Does NOT make outbound calls; just confirms env is set up.
    """
    checks = {
        "openai_configured": bool(settings.openai_api_key),
        "anthropic_configured": bool(settings.anthropic_api_key),
        "llm_provider": settings.llm_provider,
        "langsmith_enabled": settings.langsmith_tracing,
        "mem0_enabled": settings.mem0_enabled,
    }
    has_llm = checks["openai_configured"] or checks["anthropic_configured"]
    return {"ready": has_llm, "checks": checks}
