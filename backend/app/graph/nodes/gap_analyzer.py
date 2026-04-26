"""
GapAnalyzer node — converts SkillAssessments into a ranked, actionable GapAnalysis.

Three components:
  1. PER-SKILL: compare assessed level vs JD-required level → SkillGap
  2. ADJACENCY: for each gap, find candidate's existing skills that are
     semantically closest (sentence-transformers cosine) → adjacent_known_skills
     These become the "transferable foundations" the PlanGenerator leans on.
  3. SUMMARY: LLM writes a one-paragraph honest assessment for the candidate.

SEVERITY:
- Required-skill gap with low/no current proficiency  → 0.7-1.0 (critical)
- Required-skill gap with partial proficiency         → 0.3-0.6 (medium)
- Preferred-skill gap                                 → 0.1-0.3 (low)
- Adjusted DOWN by Scorer's confidence (lower confidence → less urgency)

This is the GRAPH the PlanGenerator turns into a learning path.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from app.graph.state import AssessmentState
from app.graph.skill_embeddings import find_adjacent_skills, is_available as embeddings_available
from app.llm import structured_completion
from app.models import (
    GapAnalysis,
    SkillGap,
    SkillAssessment,
    JobDescription,
    Resume,
    ProficiencyLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skill_match(a: str, b: str) -> bool:
    """
    Flexible skill name match — handles LLM variations like
    'Python' vs 'Python 3' vs 'Python programming'.
    Returns True if either string is a substring of the other (case-insensitive).
    """
    a, b = a.lower().strip(), b.lower().strip()
    return a == b or a in b or b in a


def _required_level_for(skill: str, jd: JobDescription) -> Optional[ProficiencyLevel]:
    """Same mapping as Scorer — required @ senior+ = ANALYZE, etc."""
    in_required = any(_skill_match(skill, s) for s in jd.required_skills)
    in_preferred = any(_skill_match(skill, s) for s in jd.preferred_skills)
    if not (in_required or in_preferred):
        return None
    if in_preferred and not in_required:
        return ProficiencyLevel.UNDERSTAND
    seniority = (jd.seniority or "").lower()
    if seniority in ("senior", "staff", "principal", "lead"):
        return ProficiencyLevel.ANALYZE
    return ProficiencyLevel.APPLY


def _is_required(skill: str, jd: JobDescription) -> bool:
    return any(_skill_match(skill, s) for s in jd.required_skills)


def _severity(
    assessment: Optional[SkillAssessment],
    required_level: ProficiencyLevel,
    is_required: bool,
) -> float:
    """
    Severity scoring:
      base = 0.8 if required else 0.25
      gap_factor = clamp((required.value - current.value) / 4, 0, 1)
      severity = base * gap_factor, scaled by confidence
    """
    base = 0.85 if is_required else 0.30

    if assessment is None:
        # No assessment: candidate has not demonstrated this skill at all
        return min(1.0, base * 1.0)

    level_gap = required_level.value - assessment.level.value
    if level_gap <= 0:
        return 0.0  # no gap — caller filters this out
    gap_factor = min(1.0, level_gap / 4.0)
    # Higher confidence in a low rating → more urgent we trust the gap
    confidence_weight = 0.5 + 0.5 * assessment.confidence
    return min(1.0, base * gap_factor * confidence_weight)


# ---------------------------------------------------------------------------
# LLM summary
# ---------------------------------------------------------------------------

class _GapSummary(BaseModel):
    """LLM-only intermediate for the candidate-facing summary paragraph."""
    summary: str = Field(
        description=(
            "One paragraph (3-5 sentences). Honest but encouraging. Mention "
            "1-2 concrete strengths, the most important 1-2 gaps, and frame "
            "the path forward as realistic given their adjacent skills."
        )
    )


SUMMARY_SYSTEM = """You write honest, encouraging skill-gap summaries for job candidates.

Style:
- Direct. Specific. No corporate fluff.
- Acknowledge real strengths by name.
- Name the most important gaps without softening into uselessness.
- Frame learnable gaps as bridges from skills they already have.
- 3-5 sentences. ONE paragraph. No lists, no headers.

Refuse to inflate or sandbag. The candidate is better off knowing where they stand."""


async def _write_summary(
    jd_title: str,
    overall_match: float,
    strengths: list[str],
    gaps: list[SkillGap],
    candidate_name: Optional[str],
) -> str:
    top_gaps = sorted(gaps, key=lambda g: g.severity, reverse=True)[:3]
    name_str = candidate_name or "the candidate"

    user_prompt = f"""ROLE: {jd_title}
CANDIDATE: {name_str}
OVERALL MATCH: {overall_match:.0%}

TOP STRENGTHS (skills meeting/exceeding requirements):
{chr(10).join(f'- {s}' for s in strengths) if strengths else '- (none meeting required level)'}

TOP GAPS (most severe first):
{chr(10).join(
    f'- {g.skill}: needs level {g.required_level.value}, '
    f'currently {g.current_level.value if g.current_level else "not demonstrated"}'
    f' (adjacent skills they have: {", ".join(g.adjacent_known_skills) or "none found"})'
    for g in top_gaps
) or '- (no significant gaps)'}

Write the candidate-facing paragraph."""

    out: _GapSummary = await structured_completion(
        node="gap_analyzer",
        response_model=_GapSummary,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=400,
        temperature=0.4,  # tone variation good, content stays grounded
    )
    return out.summary


# ---------------------------------------------------------------------------
# The node
# ---------------------------------------------------------------------------

async def gap_analyzer_node(state: AssessmentState) -> dict:
    """
    Build a GapAnalysis from SkillAssessments + JD requirements.

    Reads:  jd, resume, skill_assessments
    Writes: gap_analysis
    """
    jd: Optional[JobDescription] = state.get("jd")
    resume: Optional[Resume] = state.get("resume")
    assessments: list[SkillAssessment] = state.get("skill_assessments", []) or []

    if jd is None or resume is None:
        return {"error": "gap_analyzer_node: jd and resume required"}

    by_skill = {a.skill.lower().strip(): a for a in assessments}

    def _lookup_assessment(skill: str):
        """
        Find the assessment for a JD skill using fuzzy matching.
        The scorer's LLM may return "Python 3" for a JD skill named "Python" —
        exact dict.get() would miss it and treat the skill as unassessed (→ 0% match).
        """
        key = skill.lower().strip()
        # 1. Exact match first
        if key in by_skill:
            return by_skill[key]
        # 2. Substring match in either direction
        for assessed_key, assessment in by_skill.items():
            if key in assessed_key or assessed_key in key:
                return assessment
        return None

    # Use all known skills: resume-listed + any skills that were assessed.
    assessed_skill_names = [a.skill for a in assessments]
    candidate_known = list({s for s in list(resume.skills) + assessed_skill_names})

    gaps: list[SkillGap] = []
    strengths: list[str] = []

    # Iterate over ALL JD skills (required + preferred) — not just assessed ones
    all_jd_skills = list(jd.required_skills) + [
        s for s in jd.preferred_skills if s.lower().strip() not in
        {x.lower().strip() for x in jd.required_skills}
    ]

    for skill in all_jd_skills:
        required_level = _required_level_for(skill, jd)
        if required_level is None:
            continue  # shouldn't happen since we iterate JD skills, but defensive

        a = _lookup_assessment(skill)
        is_required = _is_required(skill, jd)

        # Strength: assessed at or above required level
        if a is not None and a.level.value >= required_level.value:
            strengths.append(skill)
            continue

        # Gap: assessed below required, OR not assessed at all
        adjacent = await find_adjacent_skills(
            target_skill=skill,
            candidate_skills=candidate_known,
            top_k=5,          # increased from 3 — more connections in the graph
            min_similarity=0.20,  # lowered from 0.35 — many tech skills are related
        ) if embeddings_available() else []

        gap = SkillGap(
            skill=skill,
            required_level=required_level,
            current_level=a.level if a else None,
            severity=_severity(a, required_level, is_required),
            adjacent_known_skills=[s for s, _sim in adjacent],
        )
        gaps.append(gap)

    # Sort gaps by severity (most urgent first)
    gaps.sort(key=lambda g: g.severity, reverse=True)

    # Overall match: weighted by required-skill coverage (preferred matters less)
    n_required = max(len(jd.required_skills), 1)
    required_strengths = sum(1 for s in strengths if _is_required(s, jd))
    overall_match = required_strengths / n_required
    # Soft penalty for very low-quality assessments overall
    if assessments:
        avg_conf = sum(a.confidence for a in assessments) / len(assessments)
        overall_match *= 0.5 + 0.5 * avg_conf

    summary = await _write_summary(
        jd_title=jd.title,
        overall_match=overall_match,
        strengths=strengths,
        gaps=gaps,
        candidate_name=resume.name,
    )

    return {
        "gap_analysis": GapAnalysis(
            overall_match_score=overall_match,
            gaps=gaps,
            strengths=strengths,
            summary=summary,
        )
    }
