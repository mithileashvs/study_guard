"""
Learning Roadmap <-> distraction-detection bridge (spec items 27/28).

main.py's distraction_monitor loop runs in the monitoring process;
the roadmap lives in the dashboard process. They already only ever
share state through files (live_state.json / session_log.csv), so
this follows the same pattern: read-only here, roadmap_store.py owns
all writes.

get_active_topic_keywords() returns the small set of words that make
opening a resource for the CURRENT roadmap topic look like the topic's
own name in a window title, so session_context.classify_window's
existing "does the title look study-related" check (which already
inspects session.study_keywords for content-dependent apps like
YouTube) naturally recognizes it -- without globally allow-listing the
whole site/app. This adds no new classification path, only a bit more
signal to the one that already exists.

Deliberately cheap: one JSON file read, no network, no AI call -- safe
to call every distraction-monitor poll (a few seconds apart), nowhere
near the camera/posture loop (spec item 29).
"""

from __future__ import annotations

import re

from config import ROADMAP_DISTRACTION_INTEGRATION_ENABLED

_STOPWORDS = {"the", "a", "an", "of", "for", "and", "to", "in", "on", "with"}


def _keywords_from_name(name: str) -> list:
    words = re.findall(r"[a-zA-Z0-9']+", name.lower())
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def get_active_topic_keywords() -> list:
    """Keywords for whichever topic is currently IN_PROGRESS /
    NEEDS_REVISION across the active roadmap, or [] if there is no
    active roadmap, no such topic, or the integration is disabled."""
    if not ROADMAP_DISTRACTION_INTEGRATION_ENABLED:
        return []
    try:
        import roadmap_store
        from roadmap_models import STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION

        roadmap = roadmap_store.get_active_roadmap()
        if not roadmap:
            return []
        keywords = []
        for t in roadmap.topics:
            if t.status in (STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION):
                keywords.extend(_keywords_from_name(t.name))
        return sorted(set(keywords))
    except Exception:
        # Never let a roadmap-file hiccup affect distraction detection.
        return []
