"""
Supervisor node — deterministic state-machine router.

DESIGN DECISION: The pipeline is FIXED (JD→Parse→Interview→Score→Gap→Plan).
A deterministic supervisor is more reliable, cheaper, and demos cleaner than
an LLM-routed one. We inspect state and pick the next node.

Returns a routing decision via the `route` field in state, which is then used
by `route_from_supervisor` (in graph/builder.py) as a conditional edge.

The downside of LLM-routed supervisors — that they sometimes loop, sometimes
skip nodes — is a real demo risk we don't need on a 2-day timeline.
"""

from __future__ import annotations

from app.graph.state import AssessmentState


# Sentinel routing values
ROUTE_PARSER = "parser"
ROUTE_INTERVIEWER = "interviewer"
ROUTE_SCORER = "scorer"
ROUTE_GAP_ANALYZER = "gap_analyzer"
ROUTE_PLAN_GENERATOR = "plan_generator"
ROUTE_FINISH = "FINISH"


async def supervisor_node(state: AssessmentState) -> dict:
    """
    Inspect state and decide which worker runs next.

    Decision tree (in order — first match wins):
      1. error set            → FINISH (don't keep looping on a broken state)
      2. no resume/jd parsed  → parser
      3. interview not done   → interviewer
      4. no skill_assessments → scorer
      5. no gap_analysis      → gap_analyzer
      6. no learning_plan     → plan_generator
      7. else                 → FINISH
    """
    if state.get("error"):
        return {"route": ROUTE_FINISH}

    # Sentinel: node hasn't run yet ⇔ key absent OR explicitly None.
    # We deliberately do NOT use truthiness here — an empty list is a valid
    # "we ran and produced nothing" output (e.g. graph fast-path tests, or
    # a candidate with no JD-listed skills to assess).
    if state.get("resume") is None or state.get("jd") is None:
        return {"route": ROUTE_PARSER}

    if not state.get("interview_complete", False):
        return {"route": ROUTE_INTERVIEWER}

    if "skill_assessments" not in state or state.get("skill_assessments") is None:
        return {"route": ROUTE_SCORER}

    if state.get("gap_analysis") is None:
        return {"route": ROUTE_GAP_ANALYZER}

    if state.get("learning_plan") is None:
        return {"route": ROUTE_PLAN_GENERATOR}

    return {"route": ROUTE_FINISH}


def route_from_supervisor(state: AssessmentState) -> str:
    """
    Conditional edge function — reads `route` from state and returns the
    next node name (or END sentinel).
    """
    route = state.get("route", ROUTE_FINISH)
    if route == ROUTE_FINISH:
        from langgraph.graph import END
        return END
    return route
