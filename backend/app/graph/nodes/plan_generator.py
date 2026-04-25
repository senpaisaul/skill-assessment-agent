"""
PlanGenerator node — MALPP three-agent pattern.

PIPELINE (per the playbook, MALPP arXiv:2601.17346):
  1. DIAGNOSE  — given GapAnalysis + adjacent skills, decide WHICH gaps to
                 address in the plan and WHICH ORDER (prerequisite-respecting,
                 leveraging adjacent skills as foundations)
  2. PLAN      — for each chosen gap, generate a LearningModule (target level,
                 prerequisites, rationale)
  3. REFLECT   — validate: does the plan cover all critical gaps? are
                 prerequisites internally consistent? are rationales tied to
                 the candidate's actual adjacent skills?
                 If issues found, loop back to PLAN with reflection feedback.
                 Hard cap: 2 reflection rounds.

After MALPP produces the structured modules, we attach REAL CURATED RESOURCES
from roadmap.sh / freeCodeCamp / YouTube / DEV.to and compute time estimates.

TIME ESTIMATION (per the playbook):
  estimated_hours = (Σ resource_minutes / 60) × difficulty_multiplier
  where difficulty_multiplier = 2.0 (beginner), 1.5 (intermediate), 1.0 (advanced)
  determined by gap.current_level vs gap.required_level.

Per-skill cap: top 4 resources to avoid overwhelming the candidate.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from app.graph.state import AssessmentState
from app.graph.resource_fetchers import fetch_all_resources
from app.llm import structured_completion
from app.models import (
    LearningPlan,
    LearningModule,
    LearningResource,
    GapAnalysis,
    SkillGap,
    Resume,
    JobDescription,
    ProficiencyLevel,
)


# ---------------------------------------------------------------------------
# MALPP intermediate schemas (LLM-side, not exposed publicly)
# ---------------------------------------------------------------------------

class _DiagnosisItem(BaseModel):
    skill: str
    target_level: ProficiencyLevel
    prerequisites: list[str] = Field(
        default_factory=list,
        description="Skills (in this plan or already known) that should come first.",
    )
    leveraged_adjacent_skills: list[str] = Field(
        default_factory=list,
        description="Subset of candidate's known skills that make this learnable.",
    )
    rationale: str


class _Diagnosis(BaseModel):
    """Output of step 1: ordered, prerequisite-aware diagnosis of which gaps to address."""
    suggested_order: list[str] = Field(
        description="Skill names in the recommended learning sequence."
    )
    items: list[_DiagnosisItem]


class _PlanReflection(BaseModel):
    """Output of step 3: did the plan pass validation, or does it need a redo?"""
    is_valid: bool
    issues: list[str] = Field(
        default_factory=list,
        description="Specific issues if not valid — fed back to the planner.",
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="How confident the reflector is in the plan as-is.",
    )


# ---------------------------------------------------------------------------
# Step 1: DIAGNOSE
# ---------------------------------------------------------------------------

DIAGNOSE_SYSTEM = """You are a senior learning architect.

Given a candidate's gap analysis and their already-known skills, decide:
  1. WHICH gaps to include in the learning plan (prioritize required + high severity)
  2. WHAT ORDER to learn them in (respect prerequisites, leverage adjacent skills)
  3. WHAT TARGET LEVEL each module aims for (usually = required_level from the gap)

CONSTRAINTS:
- Skip gaps with severity < 0.2 (they're not worth a candidate's time).
- For each gap, identify which of the candidate's KNOWN skills make it
  learnable — these go in `leveraged_adjacent_skills`. Only use skills the
  candidate ACTUALLY HAS (don't invent).
- Order: foundational/prerequisite skills FIRST, then dependent ones. If two
  gaps are independent, order by severity (most critical first).
- Be REALISTIC: a candidate can't learn 8 things at once. If there are >5
  gaps, focus on the top 5 by severity + required-status.

The candidate is a real person with limited time. Be honest about ordering."""


async def _diagnose(
    gap_analysis: GapAnalysis,
    resume: Resume,
    jd: JobDescription,
    feedback: Optional[str] = None,
) -> _Diagnosis:
    """Step 1 of MALPP: decide which gaps and in what order."""
    gaps_block = "\n".join(
        f"- {g.skill}: required={g.required_level.name}, "
        f"current={g.current_level.name if g.current_level else 'NOT_DEMONSTRATED'}, "
        f"severity={g.severity:.2f}, "
        f"adjacent_known={g.adjacent_known_skills or 'none'}"
        for g in gap_analysis.gaps
    ) or "(no gaps)"

    feedback_block = (
        f"\n\nREFLECTION FEEDBACK FROM PREVIOUS ATTEMPT — fix these issues:\n{feedback}"
        if feedback else ""
    )

    user_prompt = f"""TARGET ROLE: {jd.title} ({jd.seniority or 'unspecified'})

CANDIDATE'S KNOWN SKILLS (use only these for prerequisites/adjacencies):
{', '.join(resume.skills) or '(none)'}

GAPS (severity-ranked):
{gaps_block}{feedback_block}

Produce the diagnosis."""

    return await structured_completion(
        node="plan_generator",
        response_model=_Diagnosis,
        messages=[
            {"role": "system", "content": DIAGNOSE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2048,
        temperature=0.2,
    )


# ---------------------------------------------------------------------------
# Step 3: REFLECT
# ---------------------------------------------------------------------------

REFLECT_SYSTEM = """You are a critical reviewer of personalized learning plans.

You will be shown a candidate's gaps, their known skills, and a draft learning plan.

CHECK FOR THESE PROBLEMS (in order of importance):
  1. Critical gaps missing (any required-skill gap with severity > 0.5 that ISN'T in the plan)
  2. Prerequisites that don't exist (a module says 'requires X' but X is neither in
     the candidate's known skills nor an earlier module in the plan)
  3. Order violations (a dependent skill placed BEFORE its prerequisite)
  4. Hallucinated leveraged skills (claims candidate knows X when they don't)
  5. Target level lower than required level (under-shooting the JD)

If the plan is GOOD ENOUGH, set is_valid=true with empty issues. Don't nitpick.
If issues exist, list them as ACTIONABLE strings the planner can fix on retry."""


async def _reflect(
    diagnosis: _Diagnosis,
    gap_analysis: GapAnalysis,
    resume: Resume,
) -> _PlanReflection:
    """Step 3 of MALPP: validate the plan, return issues if any."""
    plan_block = "\n".join(
        f"- {item.skill} (target={item.target_level.name}, "
        f"prereqs={item.prerequisites}, "
        f"leverages={item.leveraged_adjacent_skills})"
        for item in diagnosis.items
    ) or "(empty plan)"

    critical_gaps = [g.skill for g in gap_analysis.gaps if g.severity > 0.5]

    user_prompt = f"""CANDIDATE'S KNOWN SKILLS:
{', '.join(resume.skills) or '(none)'}

CRITICAL GAPS (severity > 0.5) — these MUST be in the plan:
{', '.join(critical_gaps) or '(none)'}

DRAFT PLAN (in order):
{plan_block}

SUGGESTED LEARNING ORDER:
{' → '.join(diagnosis.suggested_order)}

Validate this plan."""

    return await structured_completion(
        node="plan_generator",
        response_model=_PlanReflection,
        messages=[
            {"role": "system", "content": REFLECT_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=600,
        temperature=0.1,
    )


# ---------------------------------------------------------------------------
# Step 2/4: PLAN with reflection loop
# ---------------------------------------------------------------------------

_MAX_REFLECTION_ROUNDS = 2


async def _diagnose_with_reflection(
    gap_analysis: GapAnalysis,
    resume: Resume,
    jd: JobDescription,
) -> _Diagnosis:
    """Run Diagnose → Reflect → (Re-Diagnose with feedback)* loop, max 2 retries."""
    diagnosis = await _diagnose(gap_analysis, resume, jd)

    for round_idx in range(_MAX_REFLECTION_ROUNDS):
        reflection = await _reflect(diagnosis, gap_analysis, resume)
        if reflection.is_valid:
            break
        feedback = "\n".join(f"  • {issue}" for issue in reflection.issues)
        diagnosis = await _diagnose(gap_analysis, resume, jd, feedback=feedback)

    return diagnosis


# ---------------------------------------------------------------------------
# Time estimation
# ---------------------------------------------------------------------------

def _difficulty_multiplier(gap: Optional[SkillGap]) -> float:
    """
    Beginner (no current proficiency)        → 2.0×
    Intermediate (current ≤ 2 levels short)  → 1.5×
    Advanced (current ≥ required - 1)        → 1.0×
    """
    if gap is None or gap.current_level is None:
        return 2.0
    level_gap = gap.required_level.value - gap.current_level.value
    if level_gap >= 3:
        return 2.0
    if level_gap >= 2:
        return 1.5
    return 1.0


def _estimate_hours(
    resources: list[LearningResource],
    multiplier: float,
) -> tuple[float, float]:
    """
    Σ resource_minutes / 60, multiplied by difficulty.
    Returns (min_hours, max_hours) where max = min × 1.5 to account for
    practice/projects beyond just consuming resources.
    """
    base_hours = sum(r.estimated_minutes for r in resources) / 60.0
    min_h = round(base_hours * multiplier, 1)
    max_h = round(min_h * 1.5, 1)
    # Floor at 4 hours minimum so trivial plans don't lie about being 30 minutes
    return max(4.0, min_h), max(6.0, max_h)


# ---------------------------------------------------------------------------
# The node
# ---------------------------------------------------------------------------

async def plan_generator_node(state: AssessmentState) -> dict:
    """
    Build the final LearningPlan from GapAnalysis using MALPP + curated resources.

    Reads:  jd, resume, gap_analysis
    Writes: learning_plan
    """
    jd: Optional[JobDescription] = state.get("jd")
    resume: Optional[Resume] = state.get("resume")
    gap_analysis: Optional[GapAnalysis] = state.get("gap_analysis")

    if jd is None or resume is None or gap_analysis is None:
        return {"error": "plan_generator_node: jd, resume, gap_analysis required"}

    # Edge case: no gaps at all — congratulate the candidate, return empty plan
    if not gap_analysis.gaps:
        return {
            "learning_plan": LearningPlan(
                candidate_name=resume.name,
                target_role=jd.title,
                total_hours_min=0.0,
                total_hours_max=0.0,
                modules=[],
                suggested_order=[],
                summary=(
                    f"You're already a strong fit for this {jd.title} role — "
                    "no skill gaps were identified that would be worth a learning plan. "
                    "Focus your prep on company-specific context and projects in the JD."
                ),
            )
        }

    # --- 1+3. Diagnose with reflection ---
    diagnosis = await _diagnose_with_reflection(gap_analysis, resume, jd)

    # --- 2. Build LearningModules with real resources ---
    gaps_by_skill = {g.skill.lower().strip(): g for g in gap_analysis.gaps}
    modules: list[LearningModule] = []

    for item in diagnosis.items:
        gap = gaps_by_skill.get(item.skill.lower().strip())
        resources = await fetch_all_resources(item.skill, max_per_source=2)
        # Cap at 4 resources — quality over quantity
        resources = resources[:4]
        # Guarantee at least one resource (roadmap.sh fallback always succeeds)
        if not resources:
            from app.graph.resource_fetchers import fetch_roadmap_sh
            resources = fetch_roadmap_sh(item.skill)

        multiplier = _difficulty_multiplier(gap)
        hours_min, hours_max = _estimate_hours(resources, multiplier)

        modules.append(LearningModule(
            skill=item.skill,
            target_level=item.target_level,
            estimated_hours_min=hours_min,
            estimated_hours_max=hours_max,
            prerequisites=item.prerequisites,
            resources=resources,
            rationale=item.rationale,
        ))

    # --- Aggregate totals + summary ---
    total_min = round(sum(m.estimated_hours_min for m in modules), 1)
    total_max = round(sum(m.estimated_hours_max for m in modules), 1)

    summary = (
        f"{len(modules)}-module learning plan for the {jd.title} role. "
        f"Estimated {total_min:.0f}-{total_max:.0f} hours total. "
        f"Plan respects prerequisite ordering and leverages your existing "
        f"{', '.join(resume.skills[:3])}{'...' if len(resume.skills) > 3 else ''} "
        f"as foundations."
    )

    plan = LearningPlan(
        candidate_name=resume.name,
        target_role=jd.title,
        total_hours_min=total_min,
        total_hours_max=total_max,
        modules=modules,
        suggested_order=diagnosis.suggested_order,
        summary=summary,
    )

    return {"learning_plan": plan}
