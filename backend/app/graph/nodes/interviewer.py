"""
Interviewer node — IRT-driven adaptive question loop with HITL pause.

This is the heart of the assessment. Per skill, it:

  1. Picks the next question's Bloom level via IRT max-information selection
  2. Generates a Bloom-targeted question (Instructor-typed)
  3. PAUSES the graph via interrupt() to await the candidate's response
  4. Resumes when /api/assess/respond is called with their answer
  5. Scores the response (continuous [0,1])
  6. Updates the IRT theta for this skill
  7. Decides: ask another question on this skill (low confidence?
     min_questions not yet reached?) OR advance to the next skill
  8. When all skills are sufficiently probed, sets interview_complete=True
     and routes back to the Supervisor → Scorer

Loop termination per skill:
  - Hard cap: settings.max_questions_per_skill
  - Soft stop: confidence >= settings.irt_confidence_threshold AND
               n_questions >= settings.min_questions_per_skill

State writes:
  - interview_turns:  appended via operator.add reducer
  - irt_state:        replaced with updated theta/n_questions/history
  - current_skill_index: incremented when advancing
  - interview_complete: True when all skills done

DEMO MAGIC:
The IRT state in `irt_state.theta` and the per-skill ability estimates are
exposed by the API and can be drawn live in the frontend as a converging
ability curve. This is the headline visual for the demo.
"""

from __future__ import annotations

from langgraph.types import interrupt

from app.config import settings
from app.graph.state import AssessmentState, IRTState
from app.graph.irt import (
    bloom_to_difficulty,
    update_theta,
    confidence_from_history,
    next_difficulty,
)
from app.graph.question_gen import generate_question, score_response
from app.models import (
    InterviewTurn,
    ProficiencyLevel,
)


def _initial_theta() -> float:
    """Start at 0 — no prior assumption about candidate's level."""
    return 0.0


def _should_advance_skill(skill: str, irt: IRTState) -> bool:
    """
    Decide whether we have enough signal on this skill to move on.

    Stop asking when EITHER:
      - n_questions >= max (hard cap), OR
      - n_questions >= min AND confidence >= threshold (soft stop)
    """
    n = irt.get("n_questions", {}).get(skill, 0)
    if n >= settings.max_questions_per_skill:
        return True
    if n < settings.min_questions_per_skill:
        return False

    history = irt.get("response_history", {}).get(skill, [])
    confidence = confidence_from_history(history)
    return confidence >= settings.irt_confidence_threshold


def _ensure_irt_state(state: AssessmentState) -> IRTState:
    """Defensive default — Parser populates this, but be safe."""
    return state.get("irt_state") or {
        "theta": {},
        "n_questions": {},
        "response_history": {},
    }


async def interviewer_node(state: AssessmentState) -> dict:
    """
    Run one IRT cycle: select → generate → interrupt → score → update.

    The Interviewer is invoked repeatedly by the Supervisor. Each invocation
    handles ONE question/answer pair. When `interview_complete` is set, the
    Supervisor routes onward to the Scorer.
    """
    skills = state.get("skills_to_assess", [])
    if not skills:
        return {"interview_complete": True}

    idx = state.get("current_skill_index", 0)
    if idx >= len(skills):
        return {"interview_complete": True}

    skill = skills[idx]
    irt = _ensure_irt_state(state)
    resume = state["resume"]
    jd = state["jd"]

    # --- 1. Pick next Bloom level via IRT ---
    theta = irt.get("theta", {}).get(skill, _initial_theta())
    history = irt.get("response_history", {}).get(skill, [])
    asked_b = [b for b, _ in history]
    target_level = next_difficulty(theta, asked_b)

    # --- 2. Generate the question ---
    asked_questions = [
        t.question.question
        for t in state.get("interview_turns", [])
        if t.question.skill.lower() == skill.lower()
    ]
    question = await generate_question(
        skill=skill,
        bloom_level=target_level,
        resume=resume,
        jd=jd,
        asked_questions=asked_questions,
    )

    # --- 3. PAUSE — wait for candidate's response via /api/assess/respond ---
    # interrupt() returns when the FastAPI endpoint resumes the graph with
    # Command(resume=<response_text>).
    response: str = interrupt({
        "skill": skill,
        "skill_index": idx,
        "skills_total": len(skills),
        "question": question.question,
        "bloom_level": target_level.value,
        "theta_before": theta,
    })

    # --- 4. Score the response ---
    scored = await score_response(question=question, response=response)

    # --- 5. Update IRT state for this skill ---
    b = bloom_to_difficulty(target_level)
    new_history = history + [(b, scored.score)]
    new_theta = update_theta(theta, new_history)

    new_irt: IRTState = {
        "theta": {**irt.get("theta", {}), skill: new_theta},
        "n_questions": {
            **irt.get("n_questions", {}),
            skill: irt.get("n_questions", {}).get(skill, 0) + 1,
        },
        "response_history": {
            **irt.get("response_history", {}),
            skill: new_history,
        },
    }

    # --- 6. Decide: probe this skill more, or advance? ---
    advance = _should_advance_skill(skill, new_irt)
    new_idx = idx + 1 if advance else idx
    interview_complete = new_idx >= len(skills)

    # --- 7. Build the turn record ---
    turn = InterviewTurn(question=question, response=response)

    return {
        "interview_turns": [turn],   # operator.add reducer appends
        "irt_state": new_irt,
        "current_skill_index": new_idx,
        "interview_complete": interview_complete,
    }
