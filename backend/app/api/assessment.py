"""
Assessment endpoints.

/start        — accept resume text + JD text, kick off graph
/start-upload — accept resume file (PDF/DOCX/TXT) + JD text
/respond      — submit candidate answer, resume graph
/clarify      — rephrase current question (no scoring, no state change)
/result       — fetch final assessment + learning plan
"""

from __future__ import annotations

import io
import uuid
from typing import Optional, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from langgraph.types import Command

from app.models import LearningPlan, GapAnalysis, SkillAssessment, ProficiencyLevel
from app.graph import get_compiled_graph_async

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------

class StartAssessmentRequest(BaseModel):
    resume_text: str
    jd_text: str
    user_id: Optional[str] = None


class QuestionPayload(BaseModel):
    skill: str
    skill_index: int
    skills_total: int
    question: str
    bloom_level: int
    theta_before: float


class StartAssessmentResponse(BaseModel):
    session_id: str
    status: str
    next_question: Optional[QuestionPayload] = None
    message: Optional[str] = None


class RespondRequest(BaseModel):
    session_id: str
    response: str


class RespondResponse(BaseModel):
    session_id: str
    status: str
    next_question: Optional[QuestionPayload] = None
    interview_complete: bool = False


class ClarifyRequest(BaseModel):
    session_id: str
    original_question: str
    skill: str
    bloom_level: int
    candidate_message: str


class ClarifyResponse(BaseModel):
    rephrased_question: str
    context: str = ""


class AssessmentResultResponse(BaseModel):
    session_id: str
    skill_assessments: list[SkillAssessment]
    gap_analysis: Optional[GapAnalysis]
    learning_plan: Optional[LearningPlan]
    irt_thetas: dict[str, float] = {}


# ---------------------------------------------------------------------------
# File text extraction helpers
# ---------------------------------------------------------------------------

async def _extract_text_from_upload(file: UploadFile) -> str:
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        return _extract_pdf(content)
    elif filename.endswith(".docx"):
        return _extract_docx(content)
    elif filename.endswith(".txt") or filename.endswith(".md"):
        return content.decode("utf-8", errors="replace")
    else:
        try:
            return content.decode("utf-8", errors="replace")
        except Exception:
            raise HTTPException(400, f"Unsupported file type: {file.filename}. Use PDF, DOCX, or TXT.")


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() for page in reader.pages if page.extract_text()]
        result = "\n\n".join(pages).strip()
        if not result:
            raise HTTPException(400, "PDF appears to be empty or image-only.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to parse PDF: {e}")


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        result = "\n".join(paragraphs).strip()
        if not result:
            raise HTTPException(400, "DOCX appears to be empty.")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Failed to parse DOCX: {e}")


# ---------------------------------------------------------------------------
# Interrupt extraction helpers
# ---------------------------------------------------------------------------

def _extract_interrupt_from_result(graph_result: Any) -> Optional[dict]:
    if not isinstance(graph_result, dict):
        return None
    interrupts = graph_result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    return getattr(first, "value", None) or (first if isinstance(first, dict) else None)


async def _extract_interrupt_payload(graph, config, graph_result: Any) -> Optional[dict]:
    legacy = _extract_interrupt_from_result(graph_result)
    if legacy is not None:
        return legacy
    snapshot = await graph.aget_state(config)
    if snapshot and hasattr(snapshot, "tasks") and snapshot.tasks:
        for task in snapshot.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                first = task.interrupts[0]
                return getattr(first, "value", None) or (first if isinstance(first, dict) else None)
    return None


# ---------------------------------------------------------------------------
# Shared graph start logic
# ---------------------------------------------------------------------------

async def _run_start(resume_text: str, jd_text: str, user_id: Optional[str] = None) -> StartAssessmentResponse:
    if not resume_text.strip() or not jd_text.strip():
        raise HTTPException(400, "resume_text and jd_text are both required")

    session_id = str(uuid.uuid4())
    graph = await get_compiled_graph_async()

    config = {"configurable": {"thread_id": session_id, "user_id": user_id}}
    initial_state = {
        "resume_text": resume_text,
        "jd_text": jd_text,
        "session_id": session_id,
        "user_id": user_id,
        "messages": [],
    }

    try:
        result = await graph.ainvoke(initial_state, config)
    except Exception as e:
        raise HTTPException(500, f"Graph execution failed: {e}")

    interrupt_payload = await _extract_interrupt_payload(graph, config, result)
    if interrupt_payload:
        return StartAssessmentResponse(
            session_id=session_id,
            status="awaiting_response",
            next_question=QuestionPayload(**interrupt_payload),
        )

    return StartAssessmentResponse(
        session_id=session_id,
        status="complete",
        message="Graph completed without requiring questions.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartAssessmentResponse)
async def start_assessment(req: StartAssessmentRequest):
    return await _run_start(req.resume_text, req.jd_text, req.user_id)


@router.post("/start-upload", response_model=StartAssessmentResponse)
async def start_assessment_upload(
    resume: UploadFile = File(...),
    jd_text: str = Form(...),
    user_id: Optional[str] = Form(None),
):
    """Accept PDF/DOCX/TXT resume file + JD text."""
    resume_text = await _extract_text_from_upload(resume)
    return await _run_start(resume_text, jd_text, user_id)


@router.post("/respond", response_model=RespondResponse)
async def respond_to_question(req: RespondRequest):
    """Submit candidate's answer and resume the graph."""
    graph = await get_compiled_graph_async()
    config = {"configurable": {"thread_id": req.session_id}}

    try:
        result = await graph.ainvoke(Command(resume=req.response), config)
    except Exception as e:
        raise HTTPException(500, f"Graph resume failed: {e}")

    interrupt_payload = await _extract_interrupt_payload(graph, config, result)
    if interrupt_payload:
        return RespondResponse(
            session_id=req.session_id,
            status="awaiting_response",
            next_question=QuestionPayload(**interrupt_payload),
            interview_complete=False,
        )

    return RespondResponse(
        session_id=req.session_id,
        status="complete",
        interview_complete=True,
    )


@router.post("/clarify", response_model=ClarifyResponse)
async def clarify_question(req: ClarifyRequest):
    """
    Rephrase the current question based on candidate's clarification request.
    
    Does NOT advance IRT state or score anything — purely conversational.
    The candidate can ask for rephrasing, ask to relate to their experience,
    or ask for the question to be broken down.
    """
    graph = await get_compiled_graph_async()
    config = {"configurable": {"thread_id": req.session_id}}

    # Get current state to access resume
    snapshot = await graph.aget_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(404, f"Session {req.session_id} not found")

    resume = snapshot.values.get("resume")
    if resume is None:
        raise HTTPException(400, "Session has no parsed resume yet")

    from app.graph.question_gen import clarify_question as do_clarify

    try:
        bloom = ProficiencyLevel(req.bloom_level)
    except ValueError:
        bloom = ProficiencyLevel.APPLY

    result = await do_clarify(
        original_question=req.original_question,
        skill=req.skill,
        bloom_level=bloom,
        candidate_message=req.candidate_message,
        resume=resume,
    )

    return ClarifyResponse(
        rephrased_question=result.rephrased_question,
        context=result.context,
    )


@router.get("/result/{session_id}", response_model=AssessmentResultResponse)
async def get_result(session_id: str):
    """Fetch final assessment + learning plan."""
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