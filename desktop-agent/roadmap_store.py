"""
Learning Roadmap -- persistence + backend operations.

Single JSON file (config.ROADMAP_DATA_FILE), same atomic
write-to-tmp-then-os.replace pattern used everywhere else in this
project (see live_status.py). This is the ONE place that reads/writes
that file; roadmap_generator.py and roadmap_resources.py are pure
functions with no I/O, and dashboard.py only ever calls the functions
below.

Public operations (spec item 26):
    create_roadmap, get_roadmap, get_active_roadmap, list_roadmaps,
    update_topic_progress, start_study_session, end_study_session,
    get_next_topic, get_or_refresh_resources, generate_quiz,
    submit_quiz, delete_roadmap
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from config import ROADMAP_DATA_FILE, RESOURCE_CACHE_TTL_DAYS
from roadmap_models import (
    Roadmap, Topic, StudySessionRecord, QuizResult, _new_id,
    STATUS_LOCKED, STATUS_NOT_STARTED, STATUS_IN_PROGRESS,
    STATUS_NEEDS_REVISION, STATUS_COMPLETED, REVISION_QUIZ_THRESHOLD,
)
from roadmap_generator import generate_roadmap
import roadmap_resources


# ----------------------------------------------------------------------
# File I/O -- mirrors live_status.py's approach exactly (best-effort,
# atomic, never raises out into a caller that might be mid-UI-render
# or mid-detection-loop).
# ----------------------------------------------------------------------

def _load_raw() -> dict:
    if not os.path.isfile(ROADMAP_DATA_FILE):
        return {"roadmaps": {}, "active_roadmap_id": None}
    try:
        with open(ROADMAP_DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"roadmaps": {}, "active_roadmap_id": None}


def _save_raw(data: dict) -> bool:
    try:
        tmp_path = ROADMAP_DATA_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, ROADMAP_DATA_FILE)
        return True
    except Exception:
        return False


def _load_roadmaps() -> dict:
    raw = _load_raw()
    out = {}
    for rid, rdict in raw.get("roadmaps", {}).items():
        try:
            out[rid] = Roadmap.from_dict(rdict)
        except Exception:
            continue
    return out, raw.get("active_roadmap_id")


def _save_roadmaps(roadmaps: dict, active_roadmap_id: Optional[str]) -> bool:
    data = {
        "roadmaps": {rid: r.to_dict() for rid, r in roadmaps.items()},
        "active_roadmap_id": active_roadmap_id,
    }
    return _save_raw(data)


# ----------------------------------------------------------------------
# Status / locking rules
# ----------------------------------------------------------------------

def _recompute_locks(roadmap: Roadmap) -> None:
    """Applies the LOCKED rule (spec item 11): a topic is LOCKED if any
    prerequisite isn't COMPLETED, unless it already has real progress
    or is completed itself (never lock away work already done)."""
    for t in roadmap.topics:
        if t.status in (STATUS_COMPLETED, STATUS_IN_PROGRESS, STATUS_NEEDS_REVISION):
            continue
        prereqs_done = all(
            (roadmap.topic_by_id(pid) is None or roadmap.topic_by_id(pid).status == STATUS_COMPLETED)
            for pid in t.prerequisites
        )
        t.status = STATUS_NOT_STARTED if prereqs_done else STATUS_LOCKED


def _current_topic(roadmap: Roadmap) -> Optional[Topic]:
    """The single 'YOU ARE HERE' topic: prefer NEEDS_REVISION, then
    IN_PROGRESS, then the first unlocked NOT_STARTED topic in order."""
    for t in sorted(roadmap.topics, key=lambda x: x.order):
        if t.status == STATUS_NEEDS_REVISION:
            return t
    for t in sorted(roadmap.topics, key=lambda x: x.order):
        if t.status == STATUS_IN_PROGRESS:
            return t
    for t in sorted(roadmap.topics, key=lambda x: x.order):
        if t.status == STATUS_NOT_STARTED:
            return t
    return None


# ----------------------------------------------------------------------
# CRUD
# ----------------------------------------------------------------------

def create_roadmap(
    goal: str,
    current_level: str = "Beginner",
    target_level: str = "",
    deadline_days: int = 30,
    daily_minutes: int = 60,
    already_completed: Optional[list] = None,
    domain: str = "",
) -> Roadmap:
    topics = generate_roadmap(
        goal=goal,
        current_level=current_level,
        target_level=target_level,
        deadline_days=deadline_days,
        daily_minutes=daily_minutes,
        already_completed=already_completed,
    )
    roadmap = Roadmap(
        id=_new_id(),
        goal=goal.strip(),
        domain=domain or goal.strip(),
        current_level=current_level,
        target_level=target_level,
        deadline_days=deadline_days,
        daily_minutes=daily_minutes,
        created_at=time.time(),
        topics=topics,
    )
    _recompute_locks(roadmap)
    current = _current_topic(roadmap)
    if current and current.status == STATUS_NOT_STARTED:
        pass  # stays NOT_STARTED until the user actually starts it

    roadmaps, _active = _load_roadmaps()
    roadmaps[roadmap.id] = roadmap
    _save_roadmaps(roadmaps, roadmap.id)
    return roadmap


def get_roadmap(roadmap_id: str) -> Optional[Roadmap]:
    roadmaps, _ = _load_roadmaps()
    return roadmaps.get(roadmap_id)


def get_active_roadmap() -> Optional[Roadmap]:
    roadmaps, active_id = _load_roadmaps()
    if active_id and active_id in roadmaps:
        return roadmaps[active_id]
    return None


def list_roadmaps() -> list:
    roadmaps, _ = _load_roadmaps()
    return sorted(roadmaps.values(), key=lambda r: r.created_at, reverse=True)


def set_active_roadmap(roadmap_id: str) -> bool:
    roadmaps, _ = _load_roadmaps()
    if roadmap_id not in roadmaps:
        return False
    return _save_roadmaps(roadmaps, roadmap_id)


def delete_roadmap(roadmap_id: str) -> bool:
    roadmaps, active_id = _load_roadmaps()
    if roadmap_id in roadmaps:
        del roadmaps[roadmap_id]
        if active_id == roadmap_id:
            active_id = next(iter(roadmaps), None)
        return _save_roadmaps(roadmaps, active_id)
    return False


def _save_one(roadmap: Roadmap) -> bool:
    roadmaps, active_id = _load_roadmaps()
    roadmaps[roadmap.id] = roadmap
    if active_id is None:
        active_id = roadmap.id
    return _save_roadmaps(roadmaps, active_id)


# ----------------------------------------------------------------------
# Progress / study sessions (spec items 16/17)
# ----------------------------------------------------------------------

def start_study_session(roadmap_id: str, topic_id: str) -> Optional[Roadmap]:
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    topic = roadmap.topic_by_id(topic_id)
    if not topic or topic.status == STATUS_LOCKED:
        return None
    if topic.status == STATUS_NOT_STARTED:
        topic.status = STATUS_IN_PROGRESS
    topic.sessions.append(StudySessionRecord(started_at=time.time()))
    _save_one(roadmap)
    return roadmap


def end_study_session(roadmap_id: str, topic_id: str, progress_delta_pct: float = 0.0) -> Optional[Roadmap]:
    """Closes the most recent open session for the topic, adds its
    duration to time_spent_seconds, and (optionally) bumps progress.
    Real numbers only -- duration is measured wall-clock time, and
    progress is whatever the caller passed (dashboard computes this
    from user input / quiz results, never invented here)."""
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    topic = roadmap.topic_by_id(topic_id)
    if not topic:
        return None

    now = time.time()
    for s in reversed(topic.sessions):
        if s.ended_at is None:
            s.ended_at = now
            s.duration_seconds = max(0.0, now - s.started_at)
            topic.time_spent_seconds += s.duration_seconds
            break

    topic.last_studied = now
    if progress_delta_pct:
        topic.progress_pct = max(0.0, min(100.0, topic.progress_pct + progress_delta_pct))

    if topic.progress_pct >= 100.0 and topic.status != STATUS_NEEDS_REVISION:
        topic.status = STATUS_COMPLETED
        topic.progress_pct = 100.0
    elif topic.status == STATUS_NOT_STARTED:
        topic.status = STATUS_IN_PROGRESS

    _recompute_locks(roadmap)
    _save_one(roadmap)
    return roadmap


def update_topic_progress(roadmap_id: str, topic_id: str, progress_pct: float) -> Optional[Roadmap]:
    """Directly sets a topic's progress (e.g. a manual 'mark X% done'
    action), recomputing status/locks the same way end_study_session
    does. Kept separate from end_study_session because the two are
    triggered by different UI actions in spec items 16/17."""
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    topic = roadmap.topic_by_id(topic_id)
    if not topic or topic.status == STATUS_LOCKED:
        return None

    topic.progress_pct = max(0.0, min(100.0, progress_pct))
    if topic.progress_pct >= 100.0 and topic.status != STATUS_NEEDS_REVISION:
        topic.status = STATUS_COMPLETED
    elif topic.progress_pct > 0:
        topic.status = STATUS_IN_PROGRESS
    else:
        topic.status = STATUS_NOT_STARTED

    _recompute_locks(roadmap)
    _save_one(roadmap)
    return roadmap


def mark_reviewed(roadmap_id: str, topic_id: str) -> Optional[Roadmap]:
    """User has revised a NEEDS_REVISION topic -- moves it back to
    IN_PROGRESS so they can retake the quiz / keep studying it."""
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    topic = roadmap.topic_by_id(topic_id)
    if not topic:
        return None
    if topic.status == STATUS_NEEDS_REVISION:
        topic.status = STATUS_IN_PROGRESS
        topic.revision_count += 1
    _save_one(roadmap)
    return roadmap


# ----------------------------------------------------------------------
# Resources (spec items 18-21) -- caching lives here, network/lookup
# logic lives in roadmap_resources.py.
# ----------------------------------------------------------------------

def get_or_refresh_resources(roadmap_id: str, topic_id: str, force: bool = False) -> dict:
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return {}
    topic = roadmap.topic_by_id(topic_id)
    if not topic:
        return {}

    ttl_seconds = RESOURCE_CACHE_TTL_DAYS * 86400
    is_stale = (
        force
        or not topic.resources
        or not topic.resources_cached_at
        or (time.time() - topic.resources_cached_at) > ttl_seconds
    )
    if is_stale:
        try:
            fresh = roadmap_resources.get_resources(topic.name, roadmap.goal, roadmap.current_level)
            topic.resources = fresh
            topic.resources_cached_at = time.time()
            _save_one(roadmap)
        except Exception:
            # Never let a resource-lookup failure break the roadmap
            # (spec item 34) -- fall back to whatever was cached, or empty.
            pass
    return topic.resources


# ----------------------------------------------------------------------
# Quiz (spec item 24) + adaptive revision (spec items 12/22)
# ----------------------------------------------------------------------

def generate_quiz(roadmap_id: str, topic_id: str) -> list:
    """Small, extensible self-check quiz for a topic. See
    roadmap_generator.py's INTEGRATION BOUNDARY note for the same
    swap-in pattern applied to real LLM-generated questions."""
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return []
    topic = roadmap.topic_by_id(topic_id)
    if not topic:
        return []

    questions = [
        {
            "id": "q1",
            "prompt": f"How confident are you explaining the core idea of \u201c{topic.name}\u201d to someone else?",
            "options": ["Not at all", "A little", "Fairly confident", "Very confident"],
            "correct_index": 3,
        },
        {
            "id": "q2",
            "prompt": f"Have you applied \u201c{topic.name}\u201d in a real exercise or problem, not just read about it?",
            "options": ["No, only read/watched", "Tried once", "Practiced a few times", "Used it repeatedly"],
            "correct_index": 3,
        },
        {
            "id": "q3",
            "prompt": f"If given a new problem involving \u201c{topic.name}\u201d right now, how would you do?",
            "options": ["I'd be stuck", "I'd struggle a lot", "I'd manage with effort", "I'd handle it well"],
            "correct_index": 3,
        },
    ]
    topic.quiz = questions
    _save_one(roadmap)
    return questions


def submit_quiz(roadmap_id: str, topic_id: str, answers: dict) -> Optional[dict]:
    """answers: {question_id: selected_index}. Score is the fraction
    of answers matching the 'strong understanding' option -- simple
    and honest, not dressed up as more precise than it is."""
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    topic = roadmap.topic_by_id(topic_id)
    if not topic or not topic.quiz:
        return None

    total = len(topic.quiz)
    correct = 0
    for q in topic.quiz:
        selected = answers.get(q["id"])
        if selected is not None and selected == q["correct_index"]:
            correct += 1
    score_pct = round(100.0 * correct / total, 1) if total else 0.0
    strong = score_pct >= REVISION_QUIZ_THRESHOLD

    result = QuizResult(score_pct=score_pct, taken_at=time.time(), strong=strong)
    topic.quiz_results.append(result)

    if strong:
        # A weak-but-already-completed topic can graduate back out of
        # NEEDS_REVISION on a strong retake.
        if topic.status == STATUS_NEEDS_REVISION:
            topic.status = STATUS_COMPLETED
            topic.progress_pct = 100.0
    else:
        # Spec item 22: never silently push the user forward on a weak
        # score -- flip the topic (even a "completed" one) to
        # NEEDS_REVISION so the roadmap surfaces it.
        topic.status = STATUS_NEEDS_REVISION

    _recompute_locks(roadmap)
    _save_one(roadmap)

    return {"score_pct": score_pct, "strong": strong, "correct": correct, "total": total}


# ----------------------------------------------------------------------
# Next-step engine (spec item 23)
# ----------------------------------------------------------------------

def get_next_topic(roadmap_id: str) -> Optional[dict]:
    roadmap = get_roadmap(roadmap_id)
    if not roadmap:
        return None
    _recompute_locks(roadmap)

    for t in sorted(roadmap.topics, key=lambda x: x.order):
        if t.status == STATUS_NEEDS_REVISION:
            return {
                "topic": t,
                "reason": f"\u201c{t.name}\u201d needs revision before moving on -- your last quiz score was weak.",
            }
    for t in sorted(roadmap.topics, key=lambda x: x.order):
        if t.status == STATUS_IN_PROGRESS:
            return {
                "topic": t,
                "reason": f"You're partway through \u201c{t.name}\u201d -- finishing it keeps the roadmap moving.",
            }
    for t in sorted(roadmap.topics, key=lambda x: x.order):
        if t.status == STATUS_NOT_STARTED:
            unlocked_because = (
                "no prerequisites required" if not t.prerequisites
                else "its prerequisites are complete"
            )
            return {"topic": t, "reason": f"Next in sequence -- {unlocked_because}."}
    if roadmap.is_mastered():
        return {"topic": None, "reason": "Roadmap complete -- time for the capstone/mastery goal."}
    return None
