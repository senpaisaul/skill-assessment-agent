"""
LangGraph shared state for the skill-assessment graph.

This is the single source of truth that flows through Supervisor → Parser →
Interviewer → Scorer → GapAnalyzer → PlanGenerator. Every node reads from and
writes to this state.

Design notes:
- TypedDict (not Pydantic) because LangGraph requires it for reducer annotations.
- `messages` uses `add_messages` reducer for the conversation history.
- `interview_turns` uses `operator.add` reducer so each new turn appends rather
  than overwrites — critical for the multi-turn Interviewer loop.
- `irt_state` tracks the adaptive questioning loop's running ability estimate.
- `route` is what the Supervisor sets to dispatch to the next worker.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.models import (
    Resume,
    JobDescription,
    InterviewTurn,
    SkillAssessment,
    GapAnalysis,
    LearningPlan,
)


# ---------------------------------------------------------------------------
# IRT (Item Response Theory) running state for adaptive questioning
# ---------------------------------------------------------------------------

class IRTState(TypedDict, total=False):
    """
    Per-skill ability estimate for the IRT-driven adaptive question loop.

    Implements a lightweight 1PL/Rasch model:
        P(correct | theta, b) = sigmoid(theta - b)
    where theta is candidate ability and b is question difficulty (Bloom level).

    After each answer, theta is updated via simple gradient ascent on log-likelihood.
    Next question is selected with b ≈ theta_hat (max info point).
    """
    theta: dict[str, float]                # skill -> running ability estimate
    n_questions: dict[str, int]            # skill -> count of questions asked
    response_history: dict[str, list[tuple[float, int]]]  # skill -> [(b, score_0_to_1), ...]


# ---------------------------------------------------------------------------
# Routing — the Supervisor's verdict on what runs next
# ---------------------------------------------------------------------------

# Valid Supervisor routing decisions. The Supervisor is a structured-output
# LLM call that returns one of these strings.
NodeRoute = str  # Literal["parser", "interviewer", "scorer", "gap_analyzer", "plan_generator", "FINISH"]


# ---------------------------------------------------------------------------
# The shared state
# ---------------------------------------------------------------------------

class AssessmentState(TypedDict, total=False):
    """
    Single source of truth for the assessment graph.

    `total=False` means every key is optional — nodes only populate what they
    own, and downstream nodes check existence before reading.
    """

    # --- Inputs (set once at graph entry) ---
    resume_text: str                       # raw resume text (PDF/DOCX already extracted)
    jd_text: str                           # raw JD text
    session_id: str                        # for checkpointer thread_id
    user_id: Optional[str]                 # for Mem0 cross-session memory

    # --- Conversation history (assistant-ui binds to this) ---
    messages: Annotated[list[AnyMessage], add_messages]

    # --- Parser output ---
    resume: Optional[Resume]
    jd: Optional[JobDescription]

    # --- Interviewer running state ---
    skills_to_assess: list[str]            # required+preferred skills from JD, ordered
    current_skill_index: int               # which skill we're currently probing
    interview_turns: Annotated[list[InterviewTurn], operator.add]
    irt_state: IRTState
    interview_complete: bool               # set True when all skills sufficiently probed

    # --- Scorer output ---
    skill_assessments: list[SkillAssessment]

    # --- GapAnalyzer output ---
    gap_analysis: Optional[GapAnalysis]

    # --- PlanGenerator output ---
    learning_plan: Optional[LearningPlan]

    # --- Supervisor routing ---
    route: NodeRoute                       # which node runs next
    error: Optional[str]                   # surfaced to the frontend if a node fails
