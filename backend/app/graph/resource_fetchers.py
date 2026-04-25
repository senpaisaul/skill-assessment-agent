"""
Resource fetchers for the PlanGenerator.

Four free, no-friction sources cover virtually all needs (per the playbook):

  1. roadmap.sh         — structured roadmap JSON, 240k stars, no auth
  2. YouTube Data API   — videos with duration + viewCount, requires API key
  3. freeCodeCamp       — open curriculum with explicit time estimates
  4. DEV.to             — articles with reading_time_minutes, no auth

ALL fetchers:
- Are async (httpx)
- Return list[LearningResource]
- Gracefully return [] on ANY failure (network, auth, parsing)
- Respect a hard timeout to keep the PlanGenerator snappy

Skipped intentionally per the playbook:
- Coursera / edX (no free public catalog APIs)
- LinkedIn Learning, Udemy (paid only)
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional
import httpx

from app.models import LearningResource, ResourceType


_TIMEOUT_SECONDS = 5.0
_USER_AGENT = "skill-assessment-agent/0.1 (+hackathon submission)"


# ---------------------------------------------------------------------------
# YouTube Data API v3
# ---------------------------------------------------------------------------

async def fetch_youtube(query: str, max_results: int = 3) -> list[LearningResource]:
    """
    Search YouTube for educational videos on `query`.

    Requires YOUTUBE_API_KEY env var. Returns [] if missing — PlanGenerator
    falls back to other sources without complaint.

    Filters to videoDuration=medium (4-20 min) and orderBy=relevance.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return []

    params = {
        "key": api_key,
        "part": "snippet",
        "q": f"{query} tutorial",
        "type": "video",
        "videoDuration": "medium",
        "order": "relevance",
        "maxResults": max_results,
        "safeSearch": "strict",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            r = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                headers={"User-Agent": _USER_AGENT},
            )
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, ValueError):
        return []

    out: list[LearningResource] = []
    for item in data.get("items", []):
        vid = item.get("id", {}).get("videoId")
        snip = item.get("snippet", {})
        if not vid:
            continue
        out.append(LearningResource(
            title=snip.get("title", "(untitled)"),
            url=f"https://www.youtube.com/watch?v={vid}",
            resource_type=ResourceType.VIDEO,
            source=f"YouTube — {snip.get('channelTitle', 'unknown channel')}",
            estimated_minutes=12,  # videoDuration=medium ≈ 4-20 min
            reason=f"Video introduction to {query}",
        ))
    return out


# ---------------------------------------------------------------------------
# DEV.to — free, no auth, returns reading_time_minutes
# ---------------------------------------------------------------------------

async def fetch_devto(query: str, max_results: int = 3) -> list[LearningResource]:
    """Search DEV.to articles. Free, no auth, returns reading_time_minutes per article."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            r = await client.get(
                "https://dev.to/api/articles",
                params={"tag": query.lower().replace(" ", "").replace("-", ""), "per_page": max_results, "top": "30"},
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            )
            r.raise_for_status()
            articles = r.json()
    except (httpx.HTTPError, ValueError):
        return []

    out: list[LearningResource] = []
    for art in articles[:max_results]:
        if not isinstance(art, dict):
            continue
        out.append(LearningResource(
            title=art.get("title", "(untitled)"),
            url=art.get("url", ""),
            resource_type=ResourceType.ARTICLE,
            source=f"DEV.to — {art.get('user', {}).get('name', 'unknown author')}",
            estimated_minutes=int(art.get("reading_time_minutes") or 5),
            reason=f"Community article on {query}",
        ))
    return [r for r in out if r.url]


# ---------------------------------------------------------------------------
# roadmap.sh — always-available curated roadmap
#
# The roadmap.sh GitHub repo has structured JSON for 50+ developer roadmaps.
# Their public site also accepts ?q=<term> deep links. For the hackathon we
# return a deterministic deep link as a guaranteed-available resource — no
# network call required, so this NEVER fails.
# ---------------------------------------------------------------------------

def fetch_roadmap_sh(query: str) -> list[LearningResource]:
    """
    Always-available roadmap.sh deep link.

    Synchronous — no network call. Acts as a guaranteed fallback so every
    skill in the plan has at least one resource even if all API-backed
    fetchers fail.
    """
    slug = query.lower().strip().replace(" ", "-")
    return [LearningResource(
        title=f"roadmap.sh — {query}",
        url=f"https://roadmap.sh/?q={query.replace(' ', '+')}",
        resource_type=ResourceType.DOCS,
        source="roadmap.sh",
        estimated_minutes=180,  # ~3hr to walk a roadmap is typical
        reason=f"Structured learning roadmap for {query} with checkpoints and prerequisites",
    )]


# ---------------------------------------------------------------------------
# freeCodeCamp — open curriculum
#
# freeCodeCamp publishes their curriculum at github.com/freeCodeCamp/freeCodeCamp
# but there's no live JSON API. We hardcode the small set of certifications
# that have explicit time estimates and link to the relevant section. This is
# fast (no network), comprehensive enough, and matches what every modern LMS
# does for a curated path.
# ---------------------------------------------------------------------------

# Map common skill keywords → freeCodeCamp certification + estimated hours
_FCC_CATALOG = {
    # cert_url, hours, slug-of-relevant-curriculum
    "python":              ("https://www.freecodecamp.org/learn/scientific-computing-with-python/",                 300, "Scientific Computing with Python"),
    "javascript":          ("https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/",        300, "JavaScript Algorithms and Data Structures"),
    "react":               ("https://www.freecodecamp.org/learn/front-end-development-libraries/",                  300, "Front End Development Libraries"),
    "node":                ("https://www.freecodecamp.org/learn/back-end-development-and-apis/",                    300, "Back End Development and APIs"),
    "node.js":             ("https://www.freecodecamp.org/learn/back-end-development-and-apis/",                    300, "Back End Development and APIs"),
    "html":                ("https://www.freecodecamp.org/learn/responsive-web-design/",                            300, "Responsive Web Design"),
    "css":                 ("https://www.freecodecamp.org/learn/responsive-web-design/",                            300, "Responsive Web Design"),
    "data analysis":       ("https://www.freecodecamp.org/learn/data-analysis-with-python/",                        300, "Data Analysis with Python"),
    "machine learning":    ("https://www.freecodecamp.org/learn/machine-learning-with-python/",                     300, "Machine Learning with Python"),
    "sql":                 ("https://www.freecodecamp.org/learn/relational-database/",                              300, "Relational Database"),
    "postgresql":          ("https://www.freecodecamp.org/learn/relational-database/",                              300, "Relational Database"),
    "linux":               ("https://www.freecodecamp.org/learn/relational-database/",                              300, "Relational Database (covers Linux/Bash)"),
    "bash":                ("https://www.freecodecamp.org/learn/relational-database/",                              300, "Relational Database (covers Bash)"),
}


def fetch_freecodecamp(query: str) -> list[LearningResource]:
    """Hardcoded freeCodeCamp catalog match. No network call."""
    q_lower = query.lower().strip()
    # Try exact match first, then substring
    entry = _FCC_CATALOG.get(q_lower)
    if entry is None:
        for key, val in _FCC_CATALOG.items():
            if key in q_lower or q_lower in key:
                entry = val
                break
    if entry is None:
        return []

    url, hours, slug = entry
    return [LearningResource(
        title=f"freeCodeCamp — {slug}",
        url=url,
        resource_type=ResourceType.COURSE,
        source="freeCodeCamp",
        estimated_minutes=hours * 60,
        reason=f"Free, hands-on certification covering {query}",
    )]


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

async def fetch_all_resources(query: str, max_per_source: int = 2) -> list[LearningResource]:
    """
    Run every fetcher in parallel and combine results.

    Order in the returned list is intentional: roadmap.sh first (always
    available + structured), then freeCodeCamp (hands-on), then YouTube
    (video), then DEV.to (articles). PlanGenerator can re-order or trim
    further if needed.
    """
    # Synchronous (no network) fetchers — instant
    rmsh = fetch_roadmap_sh(query)
    fcc = fetch_freecodecamp(query)

    # Async fetchers — run in parallel
    results = await asyncio.gather(
        fetch_youtube(query, max_results=max_per_source),
        fetch_devto(query, max_results=max_per_source),
        return_exceptions=True,
    )
    yt = results[0] if isinstance(results[0], list) else []
    devto = results[1] if isinstance(results[1], list) else []

    return rmsh + fcc + yt + devto
