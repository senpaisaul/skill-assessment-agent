"""
LangGraph builder — wires Supervisor + 5 workers and compiles with checkpointer.

Topology:
    START → supervisor → (parser | interviewer | scorer | gap_analyzer | plan_generator | END)
                  ▲                       │
                  │                       │
                  └───────────────────────┘   each worker returns to supervisor

The supervisor is the only node with conditional edges. Workers always loop
back to supervisor, which inspects state and dispatches the next worker (or
END).

Checkpointer: SQLite-backed MemorySaver, keyed by thread_id = session_id.
This means:
- A session survives an app restart.
- Multi-turn `interrupt()` in the Interviewer (Stage 3) works correctly.
- We can replay/inspect any session via LangSmith or the checkpointer API.
"""

from __future__ import annotations

from functools import lru_cache
from langgraph.graph import StateGraph, START

from app.config import settings
from app.graph.state import AssessmentState
from app.graph import nodes as _nodes  # import the module, not the names
from app.graph.nodes import (
    route_from_supervisor,
    ROUTE_PARSER,
    ROUTE_INTERVIEWER,
    ROUTE_SCORER,
    ROUTE_GAP_ANALYZER,
    ROUTE_PLAN_GENERATOR,
)


def _build_graph() -> StateGraph:
    """Construct the StateGraph (uncompiled).

    Note: we resolve node functions via the `_nodes` module reference (not
    direct imports) so tests can monkey-patch e.g. `_nodes.parser_node`
    before compilation and have the patched function picked up here.
    """
    g = StateGraph(AssessmentState)

    # Add all nodes — resolved through the package so patches are honored
    g.add_node("supervisor", _nodes.supervisor_node)
    g.add_node("parser", _nodes.parser_node)
    g.add_node("interviewer", _nodes.interviewer_node)
    g.add_node("scorer", _nodes.scorer_node)
    g.add_node("gap_analyzer", _nodes.gap_analyzer_node)
    g.add_node("plan_generator", _nodes.plan_generator_node)

    # START → supervisor (always)
    g.add_edge(START, "supervisor")

    # supervisor → conditional dispatch via `route` field
    g.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            ROUTE_PARSER: "parser",
            ROUTE_INTERVIEWER: "interviewer",
            ROUTE_SCORER: "scorer",
            ROUTE_GAP_ANALYZER: "gap_analyzer",
            ROUTE_PLAN_GENERATOR: "plan_generator",
            "__end__": "__end__",  # END sentinel from route_from_supervisor
        },
    )

    # Every worker loops back to supervisor
    for worker in ("parser", "interviewer", "scorer", "gap_analyzer", "plan_generator"):
        g.add_edge(worker, "supervisor")

    return g


@lru_cache(maxsize=1)
def get_checkpointer():
    """SQLite-backed checkpointer. Lazy + cached so we open the file once."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    return AsyncSqliteSaver.from_conn_string(settings.sqlite_checkpoint_path)


@lru_cache(maxsize=1)
def get_compiled_graph():
    """
    Compile the graph with the SQLite checkpointer.

    Cached so the entire app shares one compiled graph instance.

    NOTE: Stage 3 will add `interrupt_before=["interviewer"]` (or use
    `interrupt()` inside the node) so the candidate's response is awaited via
    HITL pause/resume, not synchronous waiting.
    """
    graph = _build_graph()
    checkpointer_cm = get_checkpointer()
    # AsyncSqliteSaver.from_conn_string returns an async context manager;
    # we need to enter it for the actual saver object.
    # We do this lazily — see get_compiled_graph_async below for production use.
    raise NotImplementedError(
        "Use get_compiled_graph_async() — AsyncSqliteSaver requires async context."
    )


# ---------------------------------------------------------------------------
# Async-friendly compilation (recommended for FastAPI integration)
# ---------------------------------------------------------------------------

_compiled_graph_cache: dict = {}
_checkpointer_ctx = None  # holds the AsyncSqliteSaver context manager
_checkpointer_obj = None  # the entered saver instance


async def get_compiled_graph_async():
    """
    Async compilation entry point. Lazily enters the checkpointer's async
    context the first time it's called and reuses the saver thereafter.
    """
    global _checkpointer_ctx, _checkpointer_obj

    if "graph" in _compiled_graph_cache:
        return _compiled_graph_cache["graph"]

    if _checkpointer_obj is None:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(
            settings.sqlite_checkpoint_path
        )
        _checkpointer_obj = await _checkpointer_ctx.__aenter__()

    graph = _build_graph()
    compiled = graph.compile(checkpointer=_checkpointer_obj)
    _compiled_graph_cache["graph"] = compiled
    return compiled


async def shutdown_graph():
    """Cleanly close the checkpointer on app shutdown."""
    global _checkpointer_ctx, _checkpointer_obj
    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
        _checkpointer_ctx = None
        _checkpointer_obj = None
        _compiled_graph_cache.clear()
