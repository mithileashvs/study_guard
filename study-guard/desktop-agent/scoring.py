"""
Study Health Score

A simple, explainable productivity metric from 0-100, NOT a medical or
scientifically validated measurement. It exists to give you one number
to glance at after a session, built from five weighted components:

    Focus              35%
    Posture            25%
    Break discipline   15%
    Presence           15%
    Distractions       10%

Each component is its own 0-100 sub-score computed from simple ratios
(see the functions below) so every number on the dashboard can be
traced back to a plain formula -- nothing here is a black box.
"""

import csv
import os
from config import LOG_FILE, BREAK_INTERVAL

WEIGHTS = {
    "focus": 0.35,
    "posture": 0.25,
    "break_discipline": 0.15,
    "presence": 0.15,
    "distractions": 0.10,
}


def _clamp(value, low=0, high=100):
    return max(low, min(high, value))


def read_events(session_id: str = None):
    """
    Reads session_log.csv and returns the list of event rows.
    If session_id is given, only rows for that session are returned;
    otherwise all rows are returned (across every past session).
    """
    if not os.path.isfile(LOG_FILE):
        return []
    with open(LOG_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if session_id:
        rows = [r for r in rows if r.get("session_id") == session_id]
    return rows


def latest_session_id(rows):
    """Returns the session_id of the most recent SESSION_START event."""
    starts = [r for r in rows if r["event"] == "SESSION_START"]
    if not starts:
        return None
    return starts[-1]["session_id"]


def compute_totals(rows):
    """
    Walks a session's events and derives the raw numbers the score is
    built from. This re-derives totals from logged events rather than
    trusting in-memory state, so the dashboard stays correct even if
    it's run after the fact, in a separate process from main.py.
    """
    # "SLOUCH"/category=="SLOUCHING" is the old (pre-bugfix) event name,
    # kept for older session_log.csv rows. "POSTURE_WARNING" is current.
    slouch_events = sum(
        1 for r in rows
        if (r["event"] == "SLOUCH" and r["category"] == "SLOUCHING")
        or (r["event"] == "POSTURE_WARNING" and r["category"] == "SLOUCHING")
    )
    # "DISTRACTION" is the old (pre-Day-1) event name, kept here so
    # scores computed from older session_log.csv rows still work.
    # "DISTRACTION_STARTED" is the current one -- one per confirmed
    # distraction episode, not one per poll.
    distraction_events = sum(1 for r in rows if r["event"] in ("DISTRACTION", "DISTRACTION_STARTED"))
    away_events = [r for r in rows if r["event"] == "RETURNED"]
    away_seconds = sum(float(r["duration"] or 0) for r in away_events)
    breaks_taken = sum(1 for r in rows if r["event"] == "BREAK_START")

    start_rows = [r for r in rows if r["event"] == "SESSION_START"]
    end_rows = [r for r in rows if r["event"] == "SESSION_END"]
    session_seconds = float(end_rows[-1]["duration"]) if end_rows and end_rows[-1]["duration"] else None

    return {
        "slouch_events": slouch_events,
        "distraction_events": distraction_events,
        "away_seconds": away_seconds,
        "breaks_taken": breaks_taken,
        "session_seconds": session_seconds,
        "has_start": bool(start_rows),
        "has_end": bool(end_rows),
    }


def compute_health_score(totals: dict) -> dict:
    """
    Turns raw totals into the five 0-100 component scores and the
    final weighted Study Health Score. Every formula here is
    intentionally simple (linear penalties) so it's easy to explain
    and defend in a presentation.
    """
    session_seconds = totals["session_seconds"] or 1  # avoid div-by-zero

    # Presence: penalize time spent away relative to total session length.
    presence = 100 - (totals["away_seconds"] / session_seconds * 100)
    presence = _clamp(presence)

    # Posture: -8 points per full slouch event.
    posture = 100 - (totals["slouch_events"] * 8)
    posture = _clamp(posture)

    # Distractions: -12 points per sustained distraction event.
    distractions = 100 - (totals["distraction_events"] * 12)
    distractions = _clamp(distractions)

    # Focus: a blend of presence and staying off distractions, since we
    # don't track a separate raw "focus seconds" in the log -- this
    # keeps the score derivable purely from logged events.
    focus = _clamp((presence * 0.5) + (distractions * 0.5))

    # Break discipline: did the user take roughly the breaks a session
    # of this length should have? One break expected per BREAK_INTERVAL.
    expected_breaks = max(1, int(session_seconds // BREAK_INTERVAL))
    break_discipline = _clamp((totals["breaks_taken"] / expected_breaks) * 100)

    overall = (
        focus * WEIGHTS["focus"]
        + posture * WEIGHTS["posture"]
        + break_discipline * WEIGHTS["break_discipline"]
        + presence * WEIGHTS["presence"]
        + distractions * WEIGHTS["distractions"]
    )

    return {
        "overall": round(overall),
        "focus": round(focus),
        "posture": round(posture),
        "break_discipline": round(break_discipline),
        "presence": round(presence),
        "distractions": round(distractions),
    }


def compute_live_totals(rows, elapsed_seconds: float) -> dict:
    """
    Same idea as compute_totals(), but for a session that's still in
    progress -- there's no SESSION_END row yet, so `elapsed_seconds`
    (time since SESSION_START, e.g. from live_status.py) is used as
    session_seconds instead. Used by the live dashboard so the Study
    Health card doesn't have to wait for the session to end.
    """
    totals = compute_totals(rows)
    totals["session_seconds"] = max(elapsed_seconds, 1)
    return totals
