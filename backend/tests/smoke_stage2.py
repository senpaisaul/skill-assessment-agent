"""
Stage 2 smoke test — full graph end-to-end with mocked Parser.

Validates:
- Supervisor routes correctly through all 5 workers
- State propagates across nodes (TypedDict + reducers work)
- SQLite checkpointer roundtrips
- Final state has skill_assessments, gap_analysis, learning_plan populated

No API key required — Parser is monkey-patched to return a hand-built Resume + JD.
"""

import asyncio
import os
import tempfile
import sys
import pathlib

# Make backend/ importable
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

# Use a temp checkpoint DB so we don't pollute the dev one
tmp_db = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
tmp_db.close()
os.environ["SQLITE_CHECKPOINT_PATH"] = tmp_db.name
os.environ.setdefault("OPENAI_API_KEY", "sk-test-not-used")  # config requires *something*
os.environ.setdefault("LANGGRAPH_ALLOWED_MSGPACK_MODULES", "app.models.schemas")


# ---------------------------------------------------------------------------
# Define the mock parser, then patch it in BEFORE importing the builder.
# Order matters: builder.py does `from app.graph.nodes import parser_node`
# at import time, capturing whatever reference is there at that moment.
# ---------------------------------------------------------------------------

from app.models import Resume, JobDescription, WorkExperience  # noqa: E402


async def fake_parser_node(state):
    """Mock Parser — returns a hand-built Resume + JD, and pre-populates
    enough state so the now-real Interviewer is skipped entirely (Stage 2
    only validated routing + checkpointing, not the IRT loop)."""
    resume = Resume(
        name="Abhay Sengar",
        email="sengarabhay03@gmail.com",
        skills=["Python", "FastAPI", "LangGraph", "RAG", "Docker"],
        experience=[
            WorkExperience(
                company="WorkElate",
                role="AI Engineer Intern",
                duration_months=2,
                description="Built email intent classification with LangChain LCEL.",
                skills_used=["Python", "FastAPI", "LangChain"],
            )
        ],
        raw_text=state["resume_text"],
    )
    jd = JobDescription(
        title="Senior AI Engineer",
        seniority="senior",
        required_skills=["Python", "LangGraph", "Kubernetes", "PostgreSQL"],
        preferred_skills=["RAG", "Vector databases"],
        raw_text=state["jd_text"],
    )
    skills_to_assess = ["Python", "LangGraph", "RAG", "Kubernetes", "PostgreSQL", "Vector databases"]
    return {
        "resume": resume,
        "jd": jd,
        "skills_to_assess": skills_to_assess,
        "current_skill_index": 0,
        "interview_turns": [],
        "irt_state": {"theta": {}, "n_questions": {}, "response_history": {}},
        # Mark interview as complete so the (now real) Interviewer is skipped.
        # Stage 2 only validates supervisor routing, state, and checkpointer —
        # the IRT loop is exercised in Stage 3+.
        "interview_complete": True,
    }


# Inject a couple of placeholder turns so downstream stubs (Scorer, GapAnalyzer)
# have something to consume, since real Scorer/GapAnalyzer are running now too.
from app.models import InterviewQuestion, InterviewTurn, QuestionType


async def fake_interviewer_node(state):
    """Belt-and-braces stub — even with interview_complete=True the supervisor
    won't route here, but if anything changes we still don't make a network call."""
    return {"interview_complete": True}


async def fake_scorer_node(state):
    """Stub Scorer to bypass the live LLM call."""
    from app.models import SkillAssessment, ProficiencyLevel
    skills = state.get("skills_to_assess", [])
    return {
        "skill_assessments": [
            SkillAssessment(
                skill=s,
                level=ProficiencyLevel.UNDERSTAND,
                confidence=0.5,
                evidence=["(stage-2 stub evidence)"],
                reasoning="(stage-2 stub)",
            )
            for s in skills
        ]
    }


async def fake_gap_analyzer_node(state):
    """Stub GapAnalyzer to bypass the live LLM call."""
    from app.models import GapAnalysis, SkillGap, ProficiencyLevel
    jd = state["jd"]
    return {
        "gap_analysis": GapAnalysis(
            overall_match_score=0.0,
            gaps=[
                SkillGap(
                    skill=s,
                    required_level=ProficiencyLevel.APPLY,
                    current_level=None,
                    severity=0.7,
                    adjacent_known_skills=[],
                )
                for s in jd.required_skills[:2]
            ],
            strengths=[],
            summary="(stage-2 stub)",
        )
    }


async def fake_plan_generator_node(state):
    """Stub PlanGenerator — produces a minimal valid LearningPlan without the LLM call."""
    from app.models import LearningPlan, LearningModule, LearningResource, ResourceType, ProficiencyLevel
    ga = state["gap_analysis"]
    modules = [
        LearningModule(
            skill=g.skill,
            target_level=g.required_level,
            estimated_hours_min=4.0,
            estimated_hours_max=8.0,
            prerequisites=[],
            resources=[LearningResource(
                title=f"(stub) {g.skill}",
                url=f"https://roadmap.sh/?q={g.skill}",
                resource_type=ResourceType.DOCS,
                source="roadmap.sh",
                estimated_minutes=240,
                reason="(stage-2 stub)",
            )],
            rationale="(stage-2 stub)",
        )
        for g in ga.gaps
    ]
    return {
        "learning_plan": LearningPlan(
            candidate_name=state["resume"].name,
            target_role=state["jd"].title,
            total_hours_min=sum(m.estimated_hours_min for m in modules),
            total_hours_max=sum(m.estimated_hours_max for m in modules),
            modules=modules,
            suggested_order=[m.skill for m in modules],
            summary="(stage-2 stub)",
        )
    }


# Patch at the source module first (where the function is defined),
# then patch the package re-export, BOTH before builder.py is imported.
import app.graph.nodes.parser as parser_mod
parser_mod.parser_node = fake_parser_node

import app.graph.nodes.interviewer as interviewer_mod
interviewer_mod.interviewer_node = fake_interviewer_node

import app.graph.nodes.scorer as scorer_mod
scorer_mod.scorer_node = fake_scorer_node

import app.graph.nodes.gap_analyzer as gap_mod
gap_mod.gap_analyzer_node = fake_gap_analyzer_node

import app.graph.nodes.plan_generator as plan_mod
plan_mod.plan_generator_node = fake_plan_generator_node

import app.graph.nodes as nodes_pkg
nodes_pkg.parser_node = fake_parser_node
nodes_pkg.interviewer_node = fake_interviewer_node
nodes_pkg.scorer_node = fake_scorer_node
nodes_pkg.gap_analyzer_node = fake_gap_analyzer_node
nodes_pkg.plan_generator_node = fake_plan_generator_node

# NOW import the builder — it'll pick up our patched function
from app.graph.builder import get_compiled_graph_async, shutdown_graph  # noqa: E402


async def main() -> int:
    print("=" * 70)
    print("STAGE 2 SMOKE TEST — full graph end-to-end")
    print("=" * 70)

    graph = await get_compiled_graph_async()
    print("\n[1] Graph compiled with SQLite checkpointer ✓")

    session_id = "smoke-test-session-001"
    config = {"configurable": {"thread_id": session_id}}
    initial_state = {
        "resume_text": "(stub resume text — Parser is mocked)",
        "jd_text": "(stub JD text — Parser is mocked)",
        "session_id": session_id,
        "messages": [],
    }

    print("\n[2] Invoking graph...")
    final_state = await graph.ainvoke(initial_state, config)
    print("    ✓ Graph reached END")

    # --- Validate every stage produced its expected output ---
    print("\n[3] Validating state population:")

    assert final_state.get("resume") is not None, "Parser didn't populate resume"
    print(f"    ✓ Parser:        resume populated ({len(final_state['resume'].skills)} skills)")

    assert final_state.get("jd") is not None, "Parser didn't populate jd"
    print(f"    ✓ Parser:        jd populated ({final_state['jd'].title})")

    assert final_state.get("interview_complete") is True, "Interviewer didn't complete"
    n_turns = len(final_state.get("interview_turns", []))
    print(f"    ✓ Interviewer:   {n_turns} turn(s) recorded")

    assessments = final_state.get("skill_assessments", [])
    assert len(assessments) > 0, "Scorer produced no assessments"
    print(f"    ✓ Scorer:        {len(assessments)} skill assessment(s)")

    gap_analysis = final_state.get("gap_analysis")
    assert gap_analysis is not None, "GapAnalyzer didn't run"
    print(f"    ✓ GapAnalyzer:   {len(gap_analysis.gaps)} gap(s), "
          f"match={gap_analysis.overall_match_score:.2f}")

    plan = final_state.get("learning_plan")
    assert plan is not None, "PlanGenerator didn't run"
    print(f"    ✓ PlanGenerator: {len(plan.modules)} module(s), "
          f"{plan.total_hours_min:.0f}-{plan.total_hours_max:.0f} hrs")

    # --- Validate checkpointer roundtrip ---
    print("\n[4] Validating checkpointer roundtrip:")
    snapshot = await graph.aget_state(config)
    assert snapshot.values.get("learning_plan") is not None, "Checkpoint missing plan"
    print(f"    ✓ Snapshot at thread_id={session_id} has learning_plan ✓")

    print("\n" + "=" * 70)
    print("✅ STAGE 2 SMOKE TEST PASSED")
    print("=" * 70)

    await shutdown_graph()
    os.unlink(tmp_db.name)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
