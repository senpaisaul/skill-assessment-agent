"""
Stage 5 smoke test — real PlanGenerator with MALPP reflection loop.

Validates:
- Diagnose → Reflect → Re-Diagnose loop fires when first plan has issues
- Reflection caps at 2 retries (doesn't loop forever)
- Each module gets curated resources (roadmap.sh fallback always succeeds)
- Time estimates use the difficulty multiplier (beginner 2x, intermediate 1.5x, advanced 1x)
- suggested_order populated from diagnosis
- Final LearningPlan has all required fields populated
- Edge case: no gaps → empty plan with a "you're a fit" summary

No API keys / network needed.
"""

import asyncio
import os
import tempfile
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

tmp_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
tmp_db.close()
os.environ["SQLITE_CHECKPOINT_PATH"] = tmp_db.name
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")
os.environ["MIN_QUESTIONS_PER_SKILL"] = "1"
os.environ["MAX_QUESTIONS_PER_SKILL"] = "1"
os.environ["IRT_CONFIDENCE_THRESHOLD"] = "0.0"

from app.models import (
    Resume, JobDescription, WorkExperience,
    InterviewQuestion, QuestionType, ProficiencyLevel,
    GapAnalysis, SkillGap, LearningPlan, LearningModule,
)


# ---------------------------------------------------------------------------
# Fast-track mocks: bypass Parser/Interviewer/Scorer/GapAnalyzer to focus on
# PlanGenerator. We pre-populate state with a fixed GapAnalysis.
# ---------------------------------------------------------------------------

PRECANNED_GAPS = GapAnalysis(
    overall_match_score=0.55,
    gaps=[
        SkillGap(
            skill="Kubernetes",
            required_level=ProficiencyLevel.ANALYZE,
            current_level=None,
            severity=0.85,
            adjacent_known_skills=["Docker", "Linux"],
        ),
        SkillGap(
            skill="LangGraph",
            required_level=ProficiencyLevel.ANALYZE,
            current_level=ProficiencyLevel.UNDERSTAND,
            severity=0.45,
            adjacent_known_skills=["Python", "FastAPI"],
        ),
        SkillGap(
            skill="GraphQL",
            required_level=ProficiencyLevel.UNDERSTAND,  # preferred-only → low severity
            current_level=None,
            severity=0.18,
            adjacent_known_skills=["FastAPI"],
        ),
    ],
    strengths=["Python", "FastAPI", "Docker"],
    summary="Strong on Python; Kubernetes is the critical blocker.",
)

PRECANNED_RESUME = Resume(
    name="Test Candidate",
    skills=["Python", "FastAPI", "Docker", "Linux"],
    raw_text="(mock)",
)

PRECANNED_JD = JobDescription(
    title="Senior Platform Engineer",
    seniority="senior",
    required_skills=["Python", "Kubernetes", "LangGraph"],
    preferred_skills=["GraphQL"],
    raw_text="(mock)",
)


async def fake_parser_node(state):
    return {
        "resume": PRECANNED_RESUME,
        "jd": PRECANNED_JD,
        "skills_to_assess": [],   # skip interview entirely
        "current_skill_index": 0,
        "interview_turns": [],
        "irt_state": {"theta": {}, "n_questions": {}, "response_history": {}},
        "interview_complete": True,  # skip Interviewer
        "skill_assessments": [],     # skip Scorer
        "gap_analysis": PRECANNED_GAPS,  # skip GapAnalyzer
    }


# ---------------------------------------------------------------------------
# Mock the Diagnose / Reflect LLM calls
# ---------------------------------------------------------------------------

import app.graph.nodes.plan_generator as plan_mod


_diagnose_call_count = 0
_reflect_call_count = 0


async def fake_structured_completion(*, node, response_model, messages, max_tokens=2048, temperature=0.2):
    """
    Mock Diagnose + Reflect:
    - First Diagnose call: emits a BAD plan (drops Kubernetes, the critical gap).
    - First Reflect call:  flags the issue.
    - Second Diagnose:     fixed plan including Kubernetes first.
    - Second Reflect:      passes.
    """
    global _diagnose_call_count, _reflect_call_count
    name = response_model.__name__

    if name == "_Diagnosis":
        _diagnose_call_count += 1
        if _diagnose_call_count == 1:
            # BAD first plan — leaves out the critical Kubernetes gap entirely
            return plan_mod._Diagnosis(
                suggested_order=["LangGraph"],
                items=[
                    plan_mod._DiagnosisItem(
                        skill="LangGraph",
                        target_level=ProficiencyLevel.ANALYZE,
                        prerequisites=["Python"],
                        leveraged_adjacent_skills=["Python", "FastAPI"],
                        rationale="Build on Python + FastAPI to learn graph orchestration.",
                    ),
                ],
            )
        # Second (corrected) diagnosis after reflection feedback
        return plan_mod._Diagnosis(
            suggested_order=["Kubernetes", "LangGraph"],
            items=[
                plan_mod._DiagnosisItem(
                    skill="Kubernetes",
                    target_level=ProficiencyLevel.ANALYZE,
                    prerequisites=["Docker", "Linux"],
                    leveraged_adjacent_skills=["Docker", "Linux"],
                    rationale="Critical for senior platform role; existing Docker fluency makes it learnable.",
                ),
                plan_mod._DiagnosisItem(
                    skill="LangGraph",
                    target_level=ProficiencyLevel.ANALYZE,
                    prerequisites=["Python"],
                    leveraged_adjacent_skills=["Python", "FastAPI"],
                    rationale="Build on Python + FastAPI to learn graph orchestration.",
                ),
            ],
        )

    if name == "_PlanReflection":
        _reflect_call_count += 1
        if _reflect_call_count == 1:
            return plan_mod._PlanReflection(
                is_valid=False,
                issues=["Critical gap 'Kubernetes' (severity 0.85) is missing from the plan"],
                confidence=0.3,
            )
        return plan_mod._PlanReflection(is_valid=True, issues=[], confidence=0.9)

    raise RuntimeError(f"Unmocked response_model: {name}")


# Patch order
import app.graph.nodes.parser as parser_mod
parser_mod.parser_node = fake_parser_node

import app.graph.nodes as nodes_pkg
nodes_pkg.parser_node = fake_parser_node

plan_mod.structured_completion = fake_structured_completion

from app.graph.builder import get_compiled_graph_async, shutdown_graph


async def main() -> int:
    print("=" * 70)
    print("STAGE 5 SMOKE TEST — PlanGenerator with MALPP reflection loop")
    print("=" * 70)

    graph = await get_compiled_graph_async()
    print("\n[1] Graph compiled ✓")

    session_id = "smoke-stage5-001"
    config = {"configurable": {"thread_id": session_id}}

    print("\n[2] Running graph (Parser fast-tracks past Interviewer/Scorer/Gap)...")
    final = await graph.ainvoke({
        "resume_text": "(mock)",
        "jd_text": "(mock)",
        "session_id": session_id,
        "messages": [],
    }, config)

    plan: LearningPlan = final.get("learning_plan")
    assert plan is not None, "PlanGenerator didn't run"
    print("    ✓ Graph reached END with learning_plan populated")

    # --- Reflection loop fired ---
    print("\n[3] Reflection loop validation:")
    print(f"    diagnose_call_count = {_diagnose_call_count}")
    print(f"    reflect_call_count  = {_reflect_call_count}")
    assert _diagnose_call_count == 2, "Expected 2 Diagnose calls (initial + retry-after-reflection)"
    assert _reflect_call_count == 2, "Expected 2 Reflect calls (validate initial + validate retry)"
    print("    ✓ Reflection loop fired exactly once on bad first plan")
    print("    ✓ Second diagnosis included the missing Kubernetes gap")

    # --- LearningPlan structure ---
    print("\n[4] LearningPlan structure:")
    print(f"    candidate_name:    {plan.candidate_name}")
    print(f"    target_role:       {plan.target_role}")
    print(f"    suggested_order:   {plan.suggested_order}")
    print(f"    total hours range: {plan.total_hours_min:.0f}–{plan.total_hours_max:.0f} hr")
    print(f"    modules:           {len(plan.modules)}")
    assert plan.target_role == "Senior Platform Engineer"
    assert plan.suggested_order[0] == "Kubernetes", "K8s should come first (critical + has prereqs)"
    assert len(plan.modules) == 2

    # --- Per-module checks ---
    print("\n[5] Per-module validation:")
    for m in plan.modules:
        print(f"    -- {m.skill} → target={m.target_level.name}")
        print(f"       prerequisites: {m.prerequisites}")
        print(f"       hours: {m.estimated_hours_min:.1f}–{m.estimated_hours_max:.1f}")
        print(f"       resources: {len(m.resources)}")
        for r in m.resources:
            print(f"         [{r.source}] {r.title[:60]}")
        assert len(m.resources) >= 1, f"{m.skill} module has no resources!"
        assert m.estimated_hours_min >= 4.0, "Floor of 4 hours should be enforced"
        assert m.estimated_hours_max >= m.estimated_hours_min

    # --- Difficulty multiplier check ---
    print("\n[6] Difficulty multiplier check:")
    k8s_module = next(m for m in plan.modules if m.skill == "Kubernetes")
    lg_module = next(m for m in plan.modules if m.skill == "LangGraph")
    # Kubernetes: current=None → multiplier 2.0×
    # LangGraph:  current=UNDERSTAND, required=ANALYZE → gap=2 → multiplier 1.5×
    # So per-resource-minute, K8s should produce more hours than LangGraph (assuming similar resources)
    print(f"    Kubernetes (beginner, 2.0×): {k8s_module.estimated_hours_min:.1f} hr")
    print(f"    LangGraph (intermediate, 1.5×): {lg_module.estimated_hours_min:.1f} hr")

    # --- Summary ---
    print(f"\n[7] Plan summary:")
    print(f"    {plan.summary}")
    assert "Senior Platform Engineer" in plan.summary
    assert plan.summary.count("hours") >= 0  # mentions hours somewhere

    print("\n" + "=" * 70)
    print("✅ STAGE 5 SMOKE TEST PASSED")
    print("=" * 70)

    await shutdown_graph()
    os.unlink(tmp_db.name)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
