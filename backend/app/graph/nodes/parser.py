"""
Parser node — raw resume + JD text → typed Resume + JobDescription.

Uses Instructor's response_model coercion so output is *guaranteed* valid —
no string parsing, no JSON failures in the demo.

Outputs into AssessmentState:
- resume: Resume
- jd: JobDescription
- skills_to_assess: list[str]  ← ordered list driving the Interviewer loop
"""

from __future__ import annotations

from app.graph.state import AssessmentState
from app.llm import structured_completion
from app.models import Resume, JobDescription


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

RESUME_PARSE_SYSTEM = """You are a precise resume parser.

Extract structured information from the candidate's resume. Be faithful — do
NOT invent skills, experience, or projects that aren't in the source text.

For the `skills` field: include EVERY skill that is explicitly named or that
the candidate clearly demonstrated through described work. Normalize obvious
variants (e.g. "React.js" → "React") but do not over-aggregate (keep "PyTorch"
and "TensorFlow" separate, for example).

For each WorkExperience: extract the skills_used list from the role description
itself, not from elsewhere in the resume.

If a field is not present in the resume, leave it null/empty rather than
guessing."""

JD_PARSE_SYSTEM = """You are a precise job description parser.

Extract structured information from the job description.

`required_skills`: skills the JD explicitly marks as required, must-have, or
essential. Be conservative — when in doubt, prefer required.

`preferred_skills`: nice-to-have, bonus, plus, or "experience with X is a
plus" phrasing.

`seniority`: infer from years-of-experience requirements and role title.
Map to one of: 'junior' (0-2 yrs), 'mid' (2-5 yrs), 'senior' (5-8 yrs),
'staff' (8+ yrs). Leave null only if truly unclear.

Do NOT invent requirements that aren't in the source text."""


# ---------------------------------------------------------------------------
# Skill ordering — drives the Interviewer's question sequence
# ---------------------------------------------------------------------------

def _order_skills_to_assess(jd: JobDescription, resume: Resume) -> list[str]:
    """
    Order required + preferred skills so the Interviewer probes the most
    important ones first.

    Strategy:
    1. Required skills the candidate ALSO claims on their resume → assess first
       (highest signal: candidate said yes, JD needs yes — verify)
    2. Required skills the candidate did NOT claim → assess second
       (gap exploration: maybe they have it without naming it)
    3. Preferred skills → assess last (only if time/turns allow)

    Deduplicates case-insensitively while preserving order.
    """
    resume_skills_lower = {s.lower().strip() for s in resume.skills}

    claimed_required = [s for s in jd.required_skills if s.lower().strip() in resume_skills_lower]
    unclaimed_required = [s for s in jd.required_skills if s.lower().strip() not in resume_skills_lower]
    preferred = list(jd.preferred_skills)

    # Dedup while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for s in claimed_required + unclaimed_required + preferred:
        key = s.lower().strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(s)
    return ordered


# ---------------------------------------------------------------------------
# The node
# ---------------------------------------------------------------------------

async def parser_node(state: AssessmentState) -> dict:
    """
    Parse resume + JD into typed objects, set up skills_to_assess.

    Reads:  state.resume_text, state.jd_text
    Writes: state.resume, state.jd, state.skills_to_assess, state.current_skill_index
    """
    resume_text = state.get("resume_text", "")
    jd_text = state.get("jd_text", "")

    if not resume_text.strip() or not jd_text.strip():
        return {"error": "parser_node: resume_text and jd_text are both required"}

    # Parse in parallel? For Stage 2 we go sequential for clarity;
    # easy to asyncio.gather() if it shows up in a profile.
    resume = await structured_completion(
        node="parser",
        response_model=Resume,
        messages=[
            {"role": "system", "content": RESUME_PARSE_SYSTEM},
            {"role": "user", "content": resume_text},
        ],
        max_tokens=4096,
        temperature=0.0,  # deterministic for parsing
    )
    # Keep raw text for later evidence quoting in the Scorer
    resume.raw_text = resume_text

    jd = await structured_completion(
        node="parser",
        response_model=JobDescription,
        messages=[
            {"role": "system", "content": JD_PARSE_SYSTEM},
            {"role": "user", "content": jd_text},
        ],
        max_tokens=2048,
        temperature=0.0,
    )
    jd.raw_text = jd_text

    skills_to_assess = _order_skills_to_assess(jd, resume)

    return {
        "resume": resume,
        "jd": jd,
        "skills_to_assess": skills_to_assess,
        "current_skill_index": 0,
        "interview_turns": [],  # initialize for the operator.add reducer
        "irt_state": {
            "theta": {},
            "n_questions": {},
            "response_history": {},
        },
        "interview_complete": False,
    }
