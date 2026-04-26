"""
Typed configuration loaded from environment variables / .env file.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM provider keys ---
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # --- Model assignments per node ---
    parser_model: str = "gpt-4o-mini"
    scorer_model: str = "gpt-4o-mini"
    supervisor_model: str = "gpt-4o-mini"
    interviewer_model: str = "gpt-4o"
    plan_generator_model: str = "gpt-4o"
    gap_analyzer_model: str = "gpt-4o-mini"

    # --- Provider preference ---
    llm_provider: Literal["openai", "anthropic"] = "openai"

    # --- ElevenLabs TTS (optional — frontend falls back to browser TTS) ---
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: str = "9BWtsMINqrJLrRacOk9x"  # Aria — empathetic, conversational

    # --- Memory layer (Mem0) — optional ---
    mem0_enabled: bool = False
    mem0_api_key: Optional[str] = None

    # --- Observability ---
    langsmith_tracing: bool = False
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "skill-assessment-agent"

    # --- App ---
    app_env: Literal["dev", "prod"] = "dev"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:3001"]
    )

    # --- Interview tuning (IRT loop) ---
    min_questions_per_skill: int = 2      # ask at least 2 per skill before soft-stop
    max_questions_per_skill: int = 3      # hard cap — 3 questions per skill max
    irt_confidence_threshold: float = 0.55  # soft-stop sooner once we have a reasonable signal

    # --- Storage paths ---
    chroma_persist_dir: str = "./chroma_data"
    sqlite_checkpoint_path: str = "./checkpoints.sqlite"


settings = Settings()


def configure_langsmith() -> None:
    """One-line LangSmith activation. Called once at app startup."""
    if settings.langsmith_tracing and settings.langsmith_api_key:
        import os
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project