"""
Learning Roadmap -- resource search, ranking, and caching.

get_resources(topic, goal, level) returns a dict of real, categorized,
directly-openable links for a topic:

    {
        "tutorials": [Resource, ...],
        "videos":    [Resource, ...],
        "docs":      [Resource, ...],
        "practice":  [Resource, ...],
        "quizzes":   [Resource, ...],
        "projects":  [Resource, ...],
    }

This never dumps raw/unranked search results -- every entry is
categorized, and best_match() below picks the single top recommendation
(spec item 20).

INTEGRATION BOUNDARY -- swapping in a real web-search backend
---------------------------------------------------------------------
Right now this builds well-formed queries against known, reputable
platforms (official docs, YouTube, freeCodeCamp, etc.) deterministically
-- no network call, so it works offline and never blocks the UI/camera
loop (spec items 21/29). To use a real search API instead, only
_search_web() below needs to change:

    def _search_web(query, k=5):
        return call_my_search_backend(query, k=k)

Everything above it (categorization, ranking, caching) is unchanged.

Caching: results are stored on the Topic itself (topic.resources /
topic.resources_cached_at) and only regenerated after
RESOURCE_CACHE_TTL_DAYS, via roadmap_store.get_or_refresh_resources().
This module itself does no I/O -- roadmap_store owns persistence.
"""

from __future__ import annotations

import time
import urllib.parse

from roadmap_models import Resource

_OFFICIAL_DOCS = {
    "python": ("Python Official Docs", "https://docs.python.org/3/"),
    "numpy": ("NumPy Documentation", "https://numpy.org/doc/stable/"),
    "pandas": ("Pandas Documentation", "https://pandas.pydata.org/docs/"),
    "javascript": ("MDN JavaScript Docs", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    "html": ("MDN HTML Docs", "https://developer.mozilla.org/en-US/docs/Web/HTML"),
    "css": ("MDN CSS Docs", "https://developer.mozilla.org/en-US/docs/Web/CSS"),
    "react": ("React Documentation", "https://react.dev/learn"),
    "java": ("Java Documentation", "https://docs.oracle.com/en/java/"),
    "sql": ("PostgreSQL Documentation", "https://www.postgresql.org/docs/"),
}


def _q(text: str) -> str:
    return urllib.parse.quote_plus(text)


def _pick_doc(topic_name: str, goal: str):
    haystack = f"{topic_name} {goal}".lower()
    for key, (title, url) in _OFFICIAL_DOCS.items():
        if key in haystack:
            return title, url
    return None


def _search_web(query: str, k: int = 5):
    """Placeholder network seam -- see module docstring. Deliberately
    returns nothing extra beyond the deterministic links built below;
    callers must not depend on it returning results."""
    return []


def _difficulty_for_level(level: str) -> str:
    level = (level or "").strip().lower()
    if level in ("beginner", "new", "start", "starting"):
        return "beginner"
    if level in ("intermediate", "some experience"):
        return "intermediate"
    if level in ("advanced", "expert"):
        return "advanced"
    return "any"


def get_resources(topic_name: str, goal: str, level: str = "beginner") -> dict:
    """Builds a fresh categorized resource set for one topic. Pure
    function, no I/O -- safe to call from any thread/process."""
    difficulty = _difficulty_for_level(level)
    now = time.time()
    query_base = f"{topic_name} {goal}".strip()

    resources = {
        "tutorials": [
            Resource(
                title=f"{topic_name} -- guided tutorial",
                url=f"https://www.freecodecamp.org/news/search/?query={_q(query_base)}",
                type="tutorial",
                source="freeCodeCamp",
                difficulty=difficulty,
                relevance=0.85,
                quality=0.8,
                last_checked=now,
            ),
            Resource(
                title=f"{topic_name} -- W3Schools reference",
                url=f"https://www.google.com/search?q=site:w3schools.com+{_q(topic_name)}",
                type="tutorial",
                source="W3Schools",
                difficulty="beginner",
                relevance=0.6,
                quality=0.65,
                last_checked=now,
            ),
        ],
        "videos": [
            Resource(
                title=f"{topic_name} explained (video)",
                url=f"https://www.youtube.com/results?search_query={_q(query_base + ' tutorial')}",
                type="video",
                source="YouTube",
                difficulty=difficulty,
                relevance=0.9,
                quality=0.7,
                last_checked=now,
            ),
        ],
        "docs": [],
        "practice": [
            Resource(
                title=f"{topic_name} -- practice problems",
                url=f"https://www.google.com/search?q={_q(topic_name + ' practice problems')}",
                type="practice",
                source="Web",
                difficulty=difficulty,
                relevance=0.7,
                quality=0.6,
                last_checked=now,
            ),
        ],
        "quizzes": [],
        "projects": [
            Resource(
                title=f"Mini project idea: {topic_name}",
                url=f"https://www.google.com/search?q={_q(topic_name + ' mini project idea')}",
                type="project",
                source="Web",
                difficulty="intermediate" if difficulty == "any" else difficulty,
                relevance=0.6,
                quality=0.6,
                last_checked=now,
            ),
        ],
    }

    doc = _pick_doc(topic_name, goal)
    if doc:
        title, url = doc
        resources["docs"].append(
            Resource(
                title=title,
                url=url,
                type="docs",
                source="Official documentation",
                difficulty="any",
                relevance=0.95,
                quality=0.95,
                last_checked=now,
            )
        )

    return resources


def best_match(resources: dict):
    """Spec item 20 -- a single top recommendation across all
    categories, ranked by relevance * quality."""
    best = None
    best_score = -1.0
    for items in resources.values():
        for r in items:
            score = r.relevance * r.quality
            if score > best_score:
                best_score = score
                best = r
    return best


def resource_domains(resources: dict) -> set:
    """Registrable domains referenced by a topic's resources -- used
    by the distraction-integration bridge to recognize when the
    user's active window matches a resource for their current topic."""
    domains = set()
    for items in resources.values():
        for r in items:
            try:
                netloc = urllib.parse.urlparse(r.url).netloc
                domains.add(netloc.replace("www.", ""))
            except Exception:
                continue
    return domains
