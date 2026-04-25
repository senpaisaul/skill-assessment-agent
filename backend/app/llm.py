"""
LLM client factory — Instructor-wrapped clients for guaranteed structured output.

Why Instructor: every node returns typed Pydantic objects, no JSON parse failures
during a live demo. Instructor handles retry-on-validation-failure automatically.

Single source of truth for model assignment — no node hardcodes a model name.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
import instructor
from pydantic import BaseModel

from app.config import settings


NodeName = Literal[
    "parser",
    "supervisor",
    "interviewer",
    "scorer",
    "gap_analyzer",
    "plan_generator",
]


def _model_for(node: NodeName) -> str:
    """Map node name → configured model identifier."""
    return {
        "parser": settings.parser_model,
        "supervisor": settings.supervisor_model,
        "interviewer": settings.interviewer_model,
        "scorer": settings.scorer_model,
        "gap_analyzer": settings.gap_analyzer_model,
        "plan_generator": settings.plan_generator_model,
    }[node]


@lru_cache(maxsize=1)
def _openai_client():
    from openai import AsyncOpenAI
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Either configure it in .env or switch "
            "LLM_PROVIDER=anthropic."
        )
    return instructor.from_openai(AsyncOpenAI(api_key=settings.openai_api_key))


@lru_cache(maxsize=1)
def _anthropic_client():
    from anthropic import AsyncAnthropic
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Either configure it in .env or switch "
            "LLM_PROVIDER=openai."
        )
    return instructor.from_anthropic(AsyncAnthropic(api_key=settings.anthropic_api_key))


def get_client():
    """Return an Instructor-wrapped async client for the configured provider."""
    if settings.llm_provider == "openai":
        return _openai_client()
    return _anthropic_client()


async def structured_completion(
    *,
    node: NodeName,
    response_model: type[BaseModel],
    messages: list[dict],
    max_tokens: int = 2048,
    temperature: float = 0.2,
):
    """
    Run a structured-output completion for a given node.

    Args:
        node: which node is calling — drives model selection
        response_model: Pydantic class to coerce the response into
        messages: chat-format list of {"role", "content"} dicts
        max_tokens: completion cap
        temperature: 0.2 default — low for structured tasks, override for creative ones

    Returns:
        Validated instance of response_model.
    """
    client = get_client()
    model = _model_for(node)

    # Anthropic requires max_tokens; OpenAI doesn't but it's cheap insurance.
    kwargs = {
        "model": model,
        "messages": messages,
        "response_model": response_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    return await client.chat.completions.create(**kwargs)
