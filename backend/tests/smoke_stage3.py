"""
Stage 3 smoke test — full IRT loop with mocked LLM calls.

Validates:
- Interviewer pauses via interrupt() and emits the first question
- /respond-style Command(resume=...) cycle works for multiple turns
- IRT theta updates after each scored response
- Skill advancement triggers after min_questions OR confidence threshold
- After all skills are probed, graph progresses to Scorer/Gap/Plan and ends
- Final state has interview_turns, irt_state.theta populated for every skill

No API key needed — Parser, generate_question, score_response are all mocked.
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
# Tighter limits for the smoke test so it finishes in seconds
os.environ["MIN_QUESTIONS_PER_SKILL"] = "1"
os.environ["MAX_QUESTIONS_PER_SKILL"] = "2"
os.environ["IRT_CONFIDENCE_THRESHOLD"] = "0.99"  # never satisfied → hits max_questions


# ---------------------------------------------------------------------------
# Mock the Parser (no LLM call needed)
# ---------------------------------------------------------------------------

from app.models import (
    Resume, JobDescription, WorkExperience,
    InterviewQuestion, QuestionType, ProficiencyLevel,
)


async def fake_parser_node(state):
    return {
        "resume": Resume(
            name="Test Candidate",
            skills=["Python", "FastAPI"],
            experience=[WorkExperience(
                company="Acme", role="Engineer",
                duration_months=12, description="Built things.",
                skills_used=["Python"],
            )],
            raw_text=state["resume_text"],
        ),
        "jd": JobDescription(
            title="AI Engineer",
            seniority="mid",
            required_skills=["Python", "LangGraph"],  # 2 skills × 2 max questions = 4 turns
            preferred_skills=[],
            raw_text=state["jd_text"],
        ),
        "skills_to_assess": ["Python", "LangGraph"],
        "current_skill_index": 0,
        "interview_turns": [],
        "irt_state": {"theta": {}, "n_questions": {}, "response_history": {}},
        "interview_complete": False,
    }


# ---------------------------------------------------------------------------
# Mock the question_gen LLM calls
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class FakeResponseScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    keyword_hits: list[str] = []
    strengths: str = "Good answer."
    weaknesses: str = "Could go deeper."
    quote_for_evidence: str = ""


_call_count = {"gen": 0, "score": 0}


async def fake_generate_question(skill, bloom_level, resume, jd, asked_questions):
    _call_count["gen"] += 1
    return InterviewQuestion(
        skill=skill,
        question=f"[mock-Q{_call_count['gen']}] Explain {skill} at level {bloom_level.value}.",
        question_type=QuestionType.CONCEPTUAL,
        bloom_level=bloom_level,
        expected_keywords=["concept-A", "concept-B"],
    )


async def fake_score_response(question, response):
    _call_count["score"] += 1
    # Simulate decent answers — score=0.7 each turn
    return FakeResponseScore(
        score=0.7,
        keyword_hits=["concept-A"],
        strengths="Hit the key concept.",
        weaknesses="Missed concept-B.",
        quote_for_evidence=response[:80],
    )


# ---------------------------------------------------------------------------
# Patch BEFORE importing builder
# ---------------------------------------------------------------------------

import app.graph.nodes.parser as parser_mod
parser_mod.parser_node = fake_parser_node

import app.graph.nodes as nodes_pkg
nodes_pkg.parser_node = fake_parser_node


# Stub the downstream nodes too — they're now real (Stages 4+5) and would
# otherwise hit OpenAI when the interview completes. Stage 3 is only validating
# the IRT loop, not the full pipeline.
async def fake_scorer_node(state):
    from app.models import SkillAssessment, ProficiencyLevel
    skills = state.get("skills_to_assess", [])
    return {
        "skill_assessments": [
            SkillAssessment(
                skill=s, level=ProficiencyLevel.UNDERSTAND, confidence=0.5,
                evidence=["(stage-3 stub)"], reasoning="(stage-3 stub)",
            )
            for s in skills
        ]
    }


async def fake_gap_analyzer_node(state):
    from app.models import GapAnalysis
    return {"gap_analysis": GapAnalysis(
        overall_match_score=0.0, gaps=[], strengths=[], summary="(stage-3 stub)",
    )}


async def fake_plan_generator_node(state):
    from app.models import LearningPlan
    return {"learning_plan": LearningPlan(
        candidate_name=None, target_role=state["jd"].title,
        total_hours_min=0, total_hours_max=0,
        modules=[], suggested_order=[], summary="(stage-3 stub)",
    )}


import app.graph.nodes.scorer as scorer_mod
scorer_mod.scorer_node = fake_scorer_node
nodes_pkg.scorer_node = fake_scorer_node

import app.graph.nodes.gap_analyzer as gap_mod
gap_mod.gap_analyzer_node = fake_gap_analyzer_node
nodes_pkg.gap_analyzer_node = fake_gap_analyzer_node

import app.graph.nodes.plan_generator as plan_mod
plan_mod.plan_generator_node = fake_plan_generator_node
nodes_pkg.plan_generator_node = fake_plan_generator_node

# Patch question_gen at the module level — the Interviewer imports these by name
import app.graph.question_gen as qg
qg.generate_question = fake_generate_question
qg.score_response = fake_score_response

# Re-import the Interviewer so it picks up the patched functions in its closure
# (Interviewer does `from app.graph.question_gen import generate_question, score_response`)
import importlib
import app.graph.nodes.interviewer as interviewer_mod
importlib.reload(interviewer_mod)
nodes_pkg.interviewer_node = interviewer_mod.interviewer_node

from app.graph.builder import get_compiled_graph_async, shutdown_graph
from langgraph.types import Command


def _interrupt_payload(result):
    if not isinstance(result, dict):
        return None
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    return getattr(first, "value", None) or (first if isinstance(first, dict) else None)


async def main() -> int:
    print("=" * 70)
    print("STAGE 3 SMOKE TEST — IRT loop with interrupt/resume")
    print("=" * 70)

    graph = await get_compiled_graph_async()
    print("\n[1] Graph compiled ✓")

    session_id = "smoke-stage3-001"
    config = {"configurable": {"thread_id": session_id}}

    # --- Start the graph; expect first interrupt with first question ---
    print("\n[2] Starting graph — expect interrupt with Q1...")
    result = await graph.ainvoke({
        "resume_text": "(mock)",
        "jd_text": "(mock)",
        "session_id": session_id,
        "messages": [],
    }, config)

    payload = _interrupt_payload(result)
    assert payload is not None, f"Expected interrupt; got result keys: {list(result.keys())}"
    print(f"    ✓ First question received:")
    print(f"        skill={payload['skill']}  bloom={payload['bloom_level']}  "
          f"theta_before={payload['theta_before']:+.2f}")
    print(f"        Q: {payload['question']}")

    # --- Resume with a fake answer; expect either next Q or completion ---
    turn_count = 0
    seen_skills: set[str] = set()
    while True:
        turn_count += 1
        result = await graph.ainvoke(
            Command(resume=f"My answer to turn {turn_count}: I think it's a great tool."),
            config,
        )
        payload = _interrupt_payload(result)
        if payload is None:
            print(f"\n[3] Turn {turn_count} resumed → no more interrupts (interview complete)")
            break

        seen_skills.add(payload["skill"])
        print(f"    ✓ Turn {turn_count} → next Q on '{payload['skill']}' "
              f"(bloom={payload['bloom_level']}, theta_before={payload['theta_before']:+.2f})")
        if turn_count > 10:
            raise AssertionError("Loop didn't terminate after 10 turns!")

    # --- Validate final state ---
    print("\n[4] Validating final state:")
    snapshot = await graph.aget_state(config)
    final = snapshot.values

    turns = final.get("interview_turns", [])
    print(f"    ✓ interview_turns: {len(turns)}")
    assert len(turns) >= 2, f"Expected >=2 turns (1 per skill min), got {len(turns)}"

    irt = final.get("irt_state") or {}
    thetas = irt.get("theta", {})
    print(f"    ✓ irt_state.theta: {dict((k, round(v, 2)) for k, v in thetas.items())}")
    assert "Python" in thetas and "LangGraph" in thetas, "Both skills should have theta estimates"

    n_q = irt.get("n_questions", {})
    print(f"    ✓ irt_state.n_questions: {n_q}")
    assert n_q.get("Python", 0) >= 1
    assert n_q.get("LangGraph", 0) >= 1

    assert final.get("interview_complete") is True, "interview_complete should be True"
    print("    ✓ interview_complete=True")

    # Stage 2 stubs for Scorer/Gap/Plan should still produce output
    assessments = final.get("skill_assessments", [])
    print(f"    ✓ skill_assessments: {len(assessments)} (Stage 2 stubs)")

    print(f"\n[5] Mock LLM call counts: gen={_call_count['gen']}, score={_call_count['score']}")
    # gen is called every time Interviewer is entered (LangGraph re-runs the node
    # body up to interrupt() on resume), score is called only after a successful
    # resume — so gen >= score by ~2x is expected.
    assert _call_count["score"] >= 4, f"Expected ≥4 scored responses, got {_call_count['score']}"
    assert _call_count["gen"] >= _call_count["score"], "gen runs at least as often as score"

    print("\n" + "=" * 70)
    print("✅ STAGE 3 SMOKE TEST PASSED")
    print("=" * 70)

    await shutdown_graph()
    os.unlink(tmp_db.name)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
