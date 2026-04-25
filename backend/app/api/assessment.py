"""
Assessment endpoints.

Stage 3: /start runs the graph until the first interrupt() (i.e., the first
question is ready) and returns it. /respond resumes the graph with the
candidate's answer, runs until the next interrupt() (or END), and returns
either the next question or the final result.
"""

from __future__ import annotations

import uuid
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from langgraph.types import Command

from app.models import LearningPlan, GapAnalysis, SkillAssessment
from app.graph import get_compiled_graph_async

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------

class StartAssessmentRequest(BaseModel):
    resume_text: str
    jd_text: str
    user_id: Optional[str] = None  # for Mem0 cross-session memory


class QuestionPayload(BaseModel):
    """What the frontend needs to render the next question + IRT progress bar."""
    skill: str
    skill_index: int
    skills_total: int
    question: str
    bloom_level: int
    theta_before: float


class StartAssessmentResponse(BaseModel):
    session_id: str
    status: str  # 'awaiting_response' | 'complete' | 'error'
    next_question: Optional[QuestionPayload] = None
    message: Optional[str] = None


class RespondRequest(BaseModel):
    session_id: str
    response: str


class RespondResponse(BaseModel):
    session_id: str
    status: str  # 'awaiting_response' | 'complete'
    next_question: Optional[QuestionPayload] = None
    interview_complete: bool = False


class AssessmentResultResponse(BaseModel):
    session_id: str
    skill_assessments: list[SkillAssessment]
    gap_analysis: Optional[GapAnalysis]
    learning_plan: Optional[LearningPlan]
    irt_thetas: dict[str, float] = {}  # for the demo's ability-curve viz


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_interrupt_payload(graph_result: Any) -> Optional[dict]:
    """
    LangGraph signals an interrupt by including a `__interrupt__` key in the
    result dict (or via state.tasks.interrupts in newer versions). Pull out
    the payload we passed to interrupt() in the Interviewer.
    """
    if not isinstance(graph_result, dict):
        return None
    interrupts = graph_result.get("__interrupt__")
    if not interrupts:
        return None
    # interrupts is a tuple/list of Interrupt objects; first one is our pause
    first = interrupts[0]
    # Interrupt object: .value is the dict we passed in
    return getattr(first, "value", None) or (first if isinstance(first, dict) else None)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartAssessmentResponse)
async def start_assessment(req: StartAssessmentRequest):
    """
    Kick off an assessment session.

    Runs Parser, then runs the Interviewer until its first interrupt() —
    returns the first question payload to the candidate. Frontend calls
    /respond next with the candidate's answer.
    """
    if not req.resume_text.strip() or not req.jd_text.strip():
        raise HTTPException(400, "resume_text and jd_text are both required")

    session_id = str(uuid.uuid4())
    graph = await get_compiled_graph_async()

    config = {
        "configurable": {
            "thread_id": session_id,
            "user_id": req.user_id,
        }
    }
    initial_state = {
        "resume_text": req.resume_text,
        "jd_text": req.jd_text,
        "session_id": session_id,
        "user_id": req.user_id,
        "messages": [],
    }

    try:
        result = await graph.ainvoke(initial_state, config)
    except Exception as e:
        raise HTTPException(500, f"Graph execution failed: {e}")

    interrupt_payload = _extract_interrupt_payload(result)
    if interrupt_payload:
        return StartAssessmentResponse(
            session_id=session_id,
            status="awaiting_response",
            next_question=QuestionPayload(**interrupt_payload),
        )

    # No interrupt → graph reached END (e.g., empty skills_to_assess)
    return StartAssessmentResponse(
        session_id=session_id,
        status="complete",
        message="Graph completed without requiring questions.",
    )


@router.post("/start-upload", response_model=StartAssessmentResponse)
async def start_assessment_upload(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
    user_id: Optional[str] = Form(None),
):
    """Same as /start but accepts a resume file (PDF/DOCX/TXT). Stage 3 stub."""
    raise HTTPException(501, "File upload extraction lands in Stage 6")


@router.post("/respond", response_model=RespondResponse)
async def respond_to_question(req: RespondRequest):
    """
    Submit candidate's answer. Resumes the LangGraph interrupt with
    Command(resume=<response>). Returns either the next question or
    interview_complete=True (after which the caller should poll /result).
    """
    graph = await get_compiled_graph_async()
    config = {"configurable": {"thread_id": req.session_id}}

    try:
        result = await graph.ainvoke(Command(resume=req.response), config)
    except Exception as e:
        raise HTTPException(500, f"Graph resume failed: {e}")

    interrupt_payload = _extract_interrupt_payload(result)
    if interrupt_payload:
        return RespondResponse(
            session_id=req.session_id,
            status="awaiting_response",
            next_question=QuestionPayload(**interrupt_payload),
            interview_complete=False,
        )

    # No interrupt → interview is done; Scorer/GapAnalyzer/PlanGenerator have run
    return RespondResponse(
        session_id=req.session_id,
        status="complete",
        interview_complete=True,
    )


@router.get("/result/{session_id}", response_model=AssessmentResultResponse)
async def get_result(session_id: str):
    """
    Fetch final assessment + learning plan for a completed session.
    Reads final state from the LangGraph checkpointer using session_id as thread_id.
    """
    graph = await get_compiled_graph_async()
    config = {"configurable": {"thread_id": session_id}}

    snapshot = await graph.aget_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(404, f"Session {session_id} not found")

    values = snapshot.values
    irt = values.get("irt_state") or {}
    return AssessmentResultResponse(
        session_id=session_id,
        skill_assessments=values.get("skill_assessments", []),
        gap_analysis=values.get("gap_analysis"),
        learning_plan=values.get("learning_plan"),
        irt_thetas=irt.get("theta", {}),
    )


@router.get("/stream/{session_id}")
async def stream_events(session_id: str):
    """SSE stream of node events. Wired in Stage 6 alongside the frontend."""
    raise HTTPException(501, "SSE streaming wired in Stage 6")
