"""
Skill embedding store — sentence-transformers + Chroma.

Used by GapAnalyzer to find the candidate's already-known skills that are
semantically closest to each gap (the "adjacent skills" that make a gap
learnable).

DESIGN:
- mpnet-base-v2 (sentence-transformers/all-mpnet-base-v2) — small, fast, strong
  on technical text per the playbook
- Chroma in-memory by default (no persistence overhead during a session);
  persistent client is opt-in via the existing CHROMA_PERSIST_DIR setting
- Embeddings computed on first use, cached per skill string
- Module-level singletons so the model loads once

ESCO INTEGRATION (deferred to Stage 7):
The Tabiya ESCO mirror has ~13.5k skill labels with descriptions. When loaded,
we'd populate `_skill_collection` with all of ESCO at startup so adjacency
lookup is global, not just within the candidate's own skill list. For now,
adjacency is computed against the candidate's resume skills only — which
already gives high-quality "transferable foundations" suggestions for free.

GRACEFUL DEGRADATION:
If sentence-transformers isn't installed (e.g. lightweight deploy), all
adjacency calls return empty lists. GapAnalyzer handles that case fine.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Optional

# Prevent module-import-time failure if optional deps aren't installed
try:
    from sentence_transformers import SentenceTransformer
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False


_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
_model: Optional[object] = None
_lock = asyncio.Lock()


def is_available() -> bool:
    return _ST_AVAILABLE


async def _get_model():
    """Lazy singleton — load model on first use."""
    global _model
    if _model is not None:
        return _model
    async with _lock:
        if _model is not None:
            return _model
        # Run the synchronous model load in a thread so we don't block the loop.
        # Use asyncio.to_thread so any long-running download doesn't freeze FastAPI.
        loop = asyncio.get_event_loop()
        _model = await loop.run_in_executor(None, SentenceTransformer, _MODEL_NAME)
    return _model


@lru_cache(maxsize=2048)
def _norm_skill(s: str) -> str:
    return s.lower().strip()


async def embed_skills(skills: list[str]) -> dict[str, list[float]]:
    """Return {skill: vector} for all skills. Cached by string.

    Any failure during model load or embedding computation degrades silently
    to an empty dict — callers (e.g. find_adjacent_skills) treat this as
    "no adjacency available" and the GapAnalyzer falls back to an empty
    adjacent_known_skills list rather than failing the whole graph.
    """
    if not _ST_AVAILABLE or not skills:
        return {}

    deduped = list({_norm_skill(s): s for s in skills if s.strip()}.values())
    if not deduped:
        return {}

    try:
        model = await _get_model()
        loop = asyncio.get_event_loop()
        vecs = await loop.run_in_executor(
            None, lambda: model.encode(deduped, normalize_embeddings=True).tolist()
        )
        return dict(zip(deduped, vecs))
    except Exception:
        # Network failure, OOM, model corruption, etc. — degrade to no adjacency.
        # The GapAnalyzer handles this by populating adjacent_known_skills=[].
        return {}


def cosine(a: list[float], b: list[float]) -> float:
    """Vectors are pre-normalized so dot product == cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


async def find_adjacent_skills(
    target_skill: str,
    candidate_skills: list[str],
    top_k: int = 3,
    min_similarity: float = 0.3,
) -> list[tuple[str, float]]:
    """
    For a gap (target_skill), return the candidate's most semantically-similar
    already-known skills. These are the "transferable foundations" the learning
    plan should leverage.

    Returns: list of (skill, similarity) sorted desc, capped at top_k, filtered
             by min_similarity.
    """
    if not _ST_AVAILABLE or not candidate_skills:
        return []

    embeds = await embed_skills([target_skill] + candidate_skills)
    target_vec = embeds.get(target_skill)
    if target_vec is None:
        return []

    scored: list[tuple[str, float]] = []
    target_lower = _norm_skill(target_skill)
    for skill in candidate_skills:
        if _norm_skill(skill) == target_lower:
            continue  # don't recommend the gap as its own neighbor
        vec = embeds.get(skill)
        if vec is None:
            continue
        sim = cosine(target_vec, vec)
        if sim >= min_similarity:
            scored.append((skill, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
