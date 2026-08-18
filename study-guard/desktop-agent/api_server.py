"""
Study Guard -- local HTTP API layer.

Bridges the new HTML/CSS/JS (React) frontend to the existing Python
backend. This module owns NO detection logic of its own -- it only
reads/writes the same small local files the rest of the project
already uses (live_state.json, live_frame.jpg, session_log.csv,
roadmap_data.json, runtime_settings.json), exactly the same way
dashboard.py (the old, now-removed UI) used to.

Runs in its own daemon thread inside the SAME process as main.py's
monitors, started from main() in main.py. This means:
  - ONE webcam capture (owned entirely by posture_monitor in main.py;
    this module only ever reads the frame file that loop already
    writes -- see live_status.write_frame).
  - ONE process, so Ctrl+C / normal shutdown in main.py takes the API
    down with it; nothing extra to start or stop separately.

Every route is read-only against the monitoring/detection logic
itself; the only "writes" exposed are settings (runtime_settings.py)
and roadmap CRUD (roadmap_store.py), both of which already have their
own safe, file-based, atomic persistence and were designed to be
called from a separate process (that's exactly how dashboard.py used
them before).
"""

from __future__ import annotations

import json
import os
import time

from flask import Flask, Response, jsonify, request, send_from_directory

import live_status
import roadmap_store
import runtime_settings
import session_bridge
import ai_coach
import scoring
from config import (
    DEFAULT_ALLOWED_APPS,
    STUDY_KEYWORDS,
    COMPANION_ENABLED,
    BREAK_INTERVAL,
)

# Built frontend (npm run build output). The frontend now lives in a
# single shared location, ../frontend (sibling of this desktop-agent/
# directory) -- the same source Vercel builds/hosts, and what
# launcher.py builds locally for the desktop agent to serve directly.
# If it doesn't exist yet (e.g. running api_server.py alone without
# building, or a cloud deployment that only exposes the JSON API),
# the API still works -- only static-file serving is skipped.
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")


# ---------------------------------------------------------------------
# CORS -- manual, tiny, no extra dependency (flask-cors not required).
#
# Two situations this needs to cover:
#   1. Desktop agent, local use (default): frontend and API are same
#      origin (served together) or the frontend is Vercel-hosted but
#      talking to 127.0.0.1 -- loopback-only, so a permissive CORS
#      policy here doesn't expose anything that wasn't already only
#      reachable from this machine.
#   2. Cloud deployment (backend/, e.g. Render): API and frontend are
#      different origins on the public internet, so CORS must be
#      restricted to the actual deployed frontend origin(s).
#
# Set FRONTEND_URL to a comma-separated list of allowed origins (e.g.
# "https://study-guard.vercel.app") to restrict; left unset, this
# defaults to "*" (today's desktop-only behavior, unchanged).
# ---------------------------------------------------------------------
_FRONTEND_URL_ENV = os.environ.get("FRONTEND_URL", "*").strip()
_ALLOWED_ORIGINS = [o.strip() for o in _FRONTEND_URL_ENV.split(",") if o.strip()]


@app.after_request
def _add_cors_headers(resp):
    if _ALLOWED_ORIGINS == ["*"] or not _ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    else:
        origin = request.headers.get("Origin")
        if origin in _ALLOWED_ORIGINS:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/api/<path:_ignored>", methods=["OPTIONS"])
def _cors_preflight(_ignored):
    return "", 204


# ---------------------------------------------------------------------
# Helpers shared by several routes
# ---------------------------------------------------------------------

def _current_session_rows():
    """Rows for whichever session_id is currently live (from
    live_state.json), or [] if Study Guard's monitor isn't running."""
    status = live_status.read_status()
    if not status:
        return [], None
    session_id = status.get("session_id")
    return scoring.read_events(session_id), session_id


def _cat_intervened_this_session(session_id) -> bool:
    if not session_id:
        return False
    rows, _ = _current_session_rows()
    return any(r.get("event") == "INTERVENTION_TRIGGERED" for r in rows)


# ---------------------------------------------------------------------
# Live status -- the core "what's happening right now" endpoint that
# Overview / LiveSession / the Live Focus Monitor card all poll.
# ---------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    status = live_status.read_status()
    if not status:
        return jsonify({
            "running": False,
            "posture": "UNKNOWN",
            "presence": "AWAY",
            "distraction": False,
            "session_time": 0,
            "subject": None,
            "study_mode": None,
            "calibrated": False,
        })

    elapsed = time.time() - status.get("start_time", time.time())
    presence = status.get("presence_state", "PRESENT")

    # Never show a posture reading while the user is AWAY -- the
    # backend's own posture tracker reports AWAY/UNKNOWN in that case,
    # but this is asserted here too so the frontend can never end up
    # displaying a stale/incorrect "GOOD" during an away period, per
    # the "don't override backend values, but don't show something
    # backend didn't actually assert either" rule.
    posture = status.get("posture_state", "UNKNOWN")
    if presence == "AWAY":
        posture = "UNKNOWN"

    return jsonify({
        "running": True,
        "session_id": status.get("session_id"),
        "posture": posture,
        "presence": presence,
        "distraction": bool(status.get("distraction_active", False)),
        "current_activity": status.get("current_app_label", ""),
        "session_time": round(elapsed),
        "focus_seconds": status.get("focus_seconds", 0),
        "distraction_seconds": status.get("distraction_seconds", 0),
        "away_seconds": status.get("away_seconds", 0),
        "break_seconds": status.get("break_seconds", 0),
        "slouch_events": status.get("slouch_events", 0),
        "distraction_events": status.get("distraction_events", 0),
        "on_break": bool(status.get("on_break", False)),
        "calibrated": bool(status.get("calibrated", False)),
        "paused": bool(status.get("paused", False)),
        "subject": status.get("subject"),
        "study_mode": status.get("study_mode"),
        "updated_at": status.get("updated_at"),
    })


@app.route("/api/status/frame")
def api_status_frame():
    """Latest webcam frame as a JPEG, written by the SAME capture loop
    posture_monitor already owns in main.py -- this route never opens
    the camera itself, it only serves the file live_status.write_frame
    already produced. 404 (not a broken image) when there's no current
    frame, e.g. monitor not running or webcam unavailable."""
    if not os.path.isfile(live_status.FRAME_FILE):
        return jsonify({"error": "no_frame_available"}), 404
    try:
        with open(live_status.FRAME_FILE, "rb") as f:
            data = f.read()
    except Exception:
        return jsonify({"error": "no_frame_available"}), 404
    resp = Response(data, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------------------------------------------------------------------
# Session control -- the Live Session page's start/pause/resume/end
# actions. This does NOT run any detection itself: it only queues a
# command for main.SessionSupervisor (running in the main thread of
# this same process) via session_bridge, and reads back whatever
# SessionSupervisor has published there. There is exactly one
# supervisor and one session_bridge for the whole process, so this
# stays the single source of truth for session lifecycle -- no second
# session-state system.
# ---------------------------------------------------------------------

# Sensible bounds for a custom duration -- generous enough for any
# real study session, tight enough to reject obvious typos (e.g. "500"
# meant as minutes but read as seconds).
_MIN_SESSION_MINUTES = 1
_MAX_SESSION_MINUTES = 6 * 60


@app.route("/api/session/status")
def api_session_status():
    return jsonify(session_bridge.get_state())


@app.route("/api/session/start", methods=["POST"])
def api_session_start():
    print("[SESSION] Start session requested")
    body = request.get_json(silent=True) or {}
    current = session_bridge.get_state()
    if current["phase"] not in (session_bridge.PHASE_IDLE, session_bridge.PHASE_COMPLETE):
        return jsonify({"error": "session_already_active"}), 409

    try:
        minutes = float(body.get("duration_minutes"))
    except (TypeError, ValueError):
        return jsonify({"error": "duration_minutes is required"}), 400
    if not (_MIN_SESSION_MINUTES <= minutes <= _MAX_SESSION_MINUTES):
        return jsonify({"error": "invalid_duration"}), 400

    session_bridge.request_start(
        duration_seconds=round(minutes * 60),
        subject=body.get("subject"),
        mode=body.get("mode"),
        allowed_apps=body.get("allowed_apps"),
        extra_keywords=body.get("extra_keywords"),
    )
    return jsonify({"ok": True})


@app.route("/api/session/pause", methods=["POST"])
def api_session_pause():
    current = session_bridge.get_state()
    if current["phase"] != session_bridge.PHASE_ACTIVE:
        return jsonify({"error": "no_active_session"}), 409
    session_bridge.request_pause()
    return jsonify({"ok": True})


@app.route("/api/session/resume", methods=["POST"])
def api_session_resume():
    current = session_bridge.get_state()
    if current["phase"] != session_bridge.PHASE_PAUSED:
        return jsonify({"error": "not_paused"}), 409
    session_bridge.request_resume()
    return jsonify({"ok": True})


@app.route("/api/session/end", methods=["POST"])
def api_session_end():
    current = session_bridge.get_state()
    if current["phase"] not in (session_bridge.PHASE_ACTIVE, session_bridge.PHASE_PAUSED,
                                 session_bridge.PHASE_CALIBRATING):
        return jsonify({"error": "no_active_session"}), 409
    session_bridge.request_end()
    return jsonify({"ok": True})


@app.route("/api/session/acknowledge", methods=["POST"])
def api_session_acknowledge():
    """Called when the user clicks "START NEW SESSION" on the
    completion screen -- clears last_summary/phase back to IDLE so the
    Live Session page returns to its starting state instead of showing
    the previous session's completion screen forever."""
    current = session_bridge.get_state()
    if current["phase"] == session_bridge.PHASE_COMPLETE:
        session_bridge.publish_state(
            phase=session_bridge.PHASE_IDLE,
            duration_seconds=None,
            remaining_seconds=None,
            calibration_progress=0.0,
            session_id=None,
            last_summary=None,
            error=None,
        )
    return jsonify({"ok": True})


@app.route("/api/session/readiness")
def api_session_readiness():
    """Best-effort camera-availability probe for the Live Session
    page's "Camera Ready" indicator, shown before any session (and
    thus before main.py's own webcam capture loop) exists. Opens and
    immediately releases the camera -- never held open, so it can't
    conflict with a session's own capture once one starts."""
    camera_ready = False
    try:
        import cv2
        from config import CAMERA_INDEX
        cap = cv2.VideoCapture(CAMERA_INDEX)
        camera_ready = cap.isOpened()
        cap.release()
    except Exception:
        camera_ready = False
    return jsonify({
        "camera_ready": camera_ready,
        "posture_ready": True,      # posture_tracker has no separate readiness precondition
        "focus_monitor_ready": True,  # window_tracker has no separate readiness precondition
    })


# ---------------------------------------------------------------------
# Session health score -- same computation dashboard.py used to call.
# ---------------------------------------------------------------------

@app.route("/api/session/score")
def api_session_score():
    rows, session_id = _current_session_rows()
    status = live_status.read_status()
    if not session_id or not status:
        return jsonify({"available": False})
    elapsed = time.time() - status.get("start_time", time.time())
    totals = scoring.compute_live_totals(rows, elapsed)
    score = scoring.compute_health_score(totals)
    return jsonify({"available": True, "score": score})


# ---------------------------------------------------------------------
# Current-session timeline & recent alerts -- both derived from the
# current session's rows in session_log.csv, real events only (no
# invented segments/alerts). Used by Overview's Today's Timeline and
# Recent Alerts cards.
# ---------------------------------------------------------------------

@app.route("/api/session/timeline")
def api_session_timeline():
    rows, session_id = _current_session_rows()
    status = live_status.read_status()
    if not session_id or not status:
        return jsonify({"available": False, "segments": [], "legend": []})

    start_time = status.get("start_time", time.time())
    now = time.time()

    # Reconstruct focus/distraction/away/break segments in wall-clock
    # order from the event log's own transition events -- the same
    # source of truth scoring.py uses, just kept as an ordered
    # timeline instead of totals.
    from datetime import datetime

    def _ts(row):
        try:
            return datetime.fromisoformat(row["timestamp"]).timestamp()
        except Exception:
            return start_time

    transitions = []  # (time, bucket)
    for r in rows:
        event = r.get("event")
        if event in ("DISTRACTION_STARTED", "DISTRACTION"):
            transitions.append((_ts(r), "distraction"))
        elif event in ("FOCUS_RECOVERED", "DISTRACTION_ENDED"):
            transitions.append((_ts(r), "focus"))
        elif event == "BREAK_START":
            transitions.append((_ts(r), "break"))
        elif event == "BREAK_END":
            transitions.append((_ts(r), "focus"))
        elif event == "RETURNED":
            transitions.append((_ts(r), "focus"))
        elif event.endswith("AWAY") or event == "PRESENCE_AWAY":
            transitions.append((_ts(r), "away"))

    transitions.sort(key=lambda t: t[0])

    segments = []
    cursor = start_time
    bucket = "focus"
    for ts, new_bucket in transitions:
        if ts > cursor:
            segments.append({"type": bucket, "duration_seconds": ts - cursor})
        cursor = ts
        bucket = new_bucket
    if now > cursor:
        segments.append({"type": bucket, "duration_seconds": now - cursor})

    total = sum(s["duration_seconds"] for s in segments) or 1
    for s in segments:
        s["width_percent"] = round(100 * s["duration_seconds"] / total, 2)

    legend_totals = {}
    for s in segments:
        legend_totals[s["type"]] = legend_totals.get(s["type"], 0) + s["duration_seconds"]

    return jsonify({
        "available": True,
        "started_at": start_time,
        "segments": segments,
        "legend": [{"type": k, "duration_seconds": v} for k, v in legend_totals.items()],
    })


@app.route("/api/session/alerts")
def api_session_alerts():
    rows, session_id = _current_session_rows()
    if not session_id:
        return jsonify({"alerts": []})

    alert_events = {
        "DISTRACTION_STARTED": "distraction",
        "DISTRACTION": "distraction",
        "POSTURE_WARNING": "posture",
        "SLOUCH": "posture",
        "BREAK_START": "break",
    }

    alerts = []
    for r in rows:
        kind = alert_events.get(r.get("event"))
        if not kind:
            continue
        category = r.get("category") or ""
        title = {
            "distraction": f"{category} Distraction" if category else "Distraction Detected",
            "posture": "Poor Posture Detected",
            "break": "Break Started",
        }[kind]
        alerts.append({
            "id": f"{r.get('timestamp')}-{r.get('event')}",
            "type": kind,
            "title": title,
            "time": r.get("timestamp"),
        })

    alerts.sort(key=lambda a: a["time"] or "", reverse=True)
    return jsonify({"alerts": alerts[:10]})


# ---------------------------------------------------------------------
# Session history -- past sessions derived from session_log.csv.
# ---------------------------------------------------------------------

@app.route("/api/sessions/history")
def api_sessions_history():
    all_rows = scoring.read_events()
    by_session = {}
    for r in all_rows:
        by_session.setdefault(r.get("session_id"), []).append(r)

    sessions = []
    for session_id, rows in by_session.items():
        start_row = next((r for r in rows if r.get("event") == "SESSION_START"), None)
        end_row = next((r for r in rows if r.get("event") == "SESSION_END"), None)
        if not start_row:
            continue
        totals = scoring.compute_totals(rows)
        duration = float(end_row["duration"]) if end_row and end_row.get("duration") else None
        score = scoring.compute_health_score(totals) if duration else None
        sessions.append({
            "session_id": session_id,
            "subject": start_row.get("category") or "General Study",
            "mode": start_row.get("value") or "",
            "started_at": start_row.get("timestamp"),
            "duration_seconds": duration,
            "completed": end_row is not None,
            "score": score,
        })

    sessions.sort(key=lambda s: s["started_at"] or "", reverse=True)
    return jsonify({"sessions": sessions})


# ---------------------------------------------------------------------
# Analytics -- simple day-bucketed aggregation over session_log.csv.
# ---------------------------------------------------------------------

@app.route("/api/analytics/weekly")
def api_analytics_weekly():
    all_rows = scoring.read_events()
    by_session = {}
    for r in all_rows:
        by_session.setdefault(r.get("session_id"), []).append(r)

    from collections import defaultdict
    from datetime import datetime

    by_day = defaultdict(lambda: {"focus_seconds": 0.0, "distraction_seconds": 0.0, "session_seconds": 0.0})

    for session_id, rows in by_session.items():
        start_row = next((r for r in rows if r.get("event") == "SESSION_START"), None)
        end_row = next((r for r in rows if r.get("event") == "SESSION_END"), None)
        if not start_row or not end_row or not end_row.get("duration"):
            continue
        try:
            day = datetime.fromisoformat(start_row["timestamp"]).strftime("%a")
        except Exception:
            continue
        totals = scoring.compute_totals(rows)
        duration = float(end_row["duration"])
        distraction_events = totals["distraction_events"]
        # Approximate focused/distraction split for the day the same
        # way scoring.py does when a raw "focus seconds" total isn't
        # separately logged -- see compute_health_score's own comment.
        away = totals["away_seconds"]
        bucket = by_day[day]
        bucket["session_seconds"] += duration
        bucket["distraction_seconds"] += min(duration, distraction_events * 60)
        bucket["focus_seconds"] += max(0.0, duration - away - min(duration, distraction_events * 60))

    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    result = []
    for day in order:
        b = by_day.get(day)
        if not b or b["session_seconds"] <= 0:
            result.append({"day": day, "focused": 0, "distraction": 0, "hours": 0})
            continue
        focused_pct = round(100 * b["focus_seconds"] / b["session_seconds"])
        distraction_pct = round(100 * b["distraction_seconds"] / b["session_seconds"])
        result.append({
            "day": day,
            "focused": focused_pct,
            "distraction": distraction_pct,
            "hours": round(b["session_seconds"] / 3600, 1),
        })
    return jsonify({"days": result})


# ---------------------------------------------------------------------
# Settings -- Allowed Sites/Apps & Allowed Keywords (STEP 9 / STEP 10).
# Persisted via runtime_settings.py; picked up by main.py's
# distraction_monitor loop on its next poll (see _sync_runtime_settings
# in main.py). Also returns the session's built-in defaults so the
# frontend can show what's allowed even before the user adds anything.
# ---------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
def api_settings_get():
    overrides = runtime_settings.get_settings()
    status = live_status.read_status()
    return jsonify({
        "allowed_apps": overrides["allowed_apps"] or list(DEFAULT_ALLOWED_APPS),
        "study_keywords": overrides["study_keywords"],
        "default_study_keywords": STUDY_KEYWORDS,
        "companion_enabled": COMPANION_ENABLED,
        "break_interval_seconds": BREAK_INTERVAL,
        "monitor_running": status is not None,
    })


@app.route("/api/settings/allowed-apps", methods=["POST"])
def api_settings_allowed_apps():
    body = request.get_json(silent=True) or {}
    apps = body.get("allowed_apps")
    if not isinstance(apps, list):
        return jsonify({"error": "allowed_apps must be a list"}), 400
    result = runtime_settings.set_allowed_apps(apps)
    return jsonify(result)


@app.route("/api/settings/keywords", methods=["POST"])
def api_settings_keywords():
    body = request.get_json(silent=True) or {}
    keywords = body.get("study_keywords")
    if not isinstance(keywords, list):
        return jsonify({"error": "study_keywords must be a list"}), 400
    result = runtime_settings.set_study_keywords(keywords)
    return jsonify(result)


# ---------------------------------------------------------------------
# AI Coach -- reuses ai_coach.py's existing local rule engine. No
# second AI system; if ai_coach.reply_to() is later swapped for a real
# LLM backend (see that file's own INTEGRATION BOUNDARY note), this
# route needs no changes -- any API key involved stays server-side.
# ---------------------------------------------------------------------

@app.route("/api/coach/message", methods=["POST"])
def api_coach_message():
    body = request.get_json(silent=True) or {}
    action_key = body.get("action_key")
    user_text = body.get("text", "")

    status = live_status.read_status()
    running = status is not None
    rows, session_id = _current_session_rows()

    score = None
    elapsed = None
    if running and status:
        elapsed = time.time() - status.get("start_time", time.time())
        totals = scoring.compute_live_totals(rows, elapsed)
        score = scoring.compute_health_score(totals)

    context = ai_coach.build_context(
        running=running,
        posture_state=(status or {}).get("posture_state", "UNKNOWN"),
        presence_state=(status or {}).get("presence_state", "AWAY"),
        distraction_active=bool((status or {}).get("distraction_active", False)),
        distraction_events=(status or {}).get("distraction_events", 0),
        slouch_events=(status or {}).get("slouch_events", 0),
        elapsed_seconds=elapsed,
        cat_intervened=_cat_intervened_this_session(session_id),
        subject=(status or {}).get("subject") or "",
        study_mode=(status or {}).get("study_mode") or "",
        break_interval_seconds=BREAK_INTERVAL,
        score=score,
    )

    reply = ai_coach.reply_to(user_text, context, action_key=action_key)
    return jsonify({"reply": reply})


@app.route("/api/coach/greeting")
def api_coach_greeting():
    status = live_status.read_status()
    running = status is not None
    rows, session_id = _current_session_rows()
    context = ai_coach.build_context(
        running=running,
        posture_state=(status or {}).get("posture_state", "UNKNOWN"),
        presence_state=(status or {}).get("presence_state", "AWAY"),
        distraction_active=bool((status or {}).get("distraction_active", False)),
        distraction_events=(status or {}).get("distraction_events", 0),
        slouch_events=(status or {}).get("slouch_events", 0),
        elapsed_seconds=(time.time() - status["start_time"]) if status else None,
        cat_intervened=_cat_intervened_this_session(session_id),
        subject=(status or {}).get("subject") or "",
        study_mode=(status or {}).get("study_mode") or "",
        break_interval_seconds=BREAK_INTERVAL,
        score=None,
    )
    return jsonify({"greeting": ai_coach.greeting_message(context)})


# ---------------------------------------------------------------------
# Roadmap -- thin wrapper around roadmap_store.py (already a complete,
# UI-independent module -- see that file's own docstring). No roadmap
# logic lives here, only (de)serialization.
# ---------------------------------------------------------------------

@app.route("/api/roadmap/active")
def api_roadmap_active():
    roadmap = roadmap_store.get_active_roadmap()
    if not roadmap:
        return jsonify({"roadmap": None})
    return jsonify({"roadmap": roadmap.to_dict()})


@app.route("/api/roadmap/list")
def api_roadmap_list():
    roadmaps = roadmap_store.list_roadmaps()
    return jsonify({"roadmaps": [r.to_dict() for r in roadmaps]})


@app.route("/api/roadmap/create", methods=["POST"])
def api_roadmap_create():
    body = request.get_json(silent=True) or {}
    goal = (body.get("goal") or "").strip()
    if not goal:
        return jsonify({"error": "goal is required"}), 400
    roadmap = roadmap_store.create_roadmap(
        goal=goal,
        current_level=body.get("current_level", "Beginner"),
        target_level=body.get("target_level", ""),
        deadline_days=int(body.get("deadline_days", 30)),
        daily_minutes=int(body.get("daily_minutes", 60)),
        already_completed=body.get("already_completed"),
        domain=body.get("domain", ""),
    )
    return jsonify({"roadmap": roadmap.to_dict()})


@app.route("/api/roadmap/<roadmap_id>/topic/<topic_id>/start", methods=["POST"])
def api_roadmap_topic_start(roadmap_id, topic_id):
    roadmap = roadmap_store.start_study_session(roadmap_id, topic_id)
    if not roadmap:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"roadmap": roadmap.to_dict()})


@app.route("/api/roadmap/<roadmap_id>/topic/<topic_id>/end", methods=["POST"])
def api_roadmap_topic_end(roadmap_id, topic_id):
    body = request.get_json(silent=True) or {}
    roadmap = roadmap_store.end_study_session(
        roadmap_id, topic_id, progress_delta_pct=float(body.get("progress_delta_pct", 0.0))
    )
    if not roadmap:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"roadmap": roadmap.to_dict()})


@app.route("/api/roadmap/<roadmap_id>/topic/<topic_id>/progress", methods=["POST"])
def api_roadmap_topic_progress(roadmap_id, topic_id):
    body = request.get_json(silent=True) or {}
    roadmap = roadmap_store.update_topic_progress(
        roadmap_id, topic_id, progress_pct=float(body.get("progress_pct", 0.0))
    )
    if not roadmap:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"roadmap": roadmap.to_dict()})


@app.route("/api/roadmap/<roadmap_id>/topic/<topic_id>/resources")
def api_roadmap_topic_resources(roadmap_id, topic_id):
    force = request.args.get("force") == "1"
    resources = roadmap_store.get_or_refresh_resources(roadmap_id, topic_id, force=force)
    return jsonify({
        "resources": {cat: [r.to_dict() for r in items] for cat, items in resources.items()}
    })


@app.route("/api/roadmap/<roadmap_id>/topic/<topic_id>/quiz", methods=["GET", "POST"])
def api_roadmap_topic_quiz(roadmap_id, topic_id):
    if request.method == "GET":
        questions = roadmap_store.generate_quiz(roadmap_id, topic_id)
        return jsonify({"quiz": questions})
    body = request.get_json(silent=True) or {}
    result = roadmap_store.submit_quiz(roadmap_id, topic_id, body.get("answers", {}))
    if result is None:
        return jsonify({"error": "not_found"}), 404
    return jsonify(result)


@app.route("/api/roadmap/<roadmap_id>/set-active", methods=["POST"])
def api_roadmap_set_active(roadmap_id):
    ok = roadmap_store.set_active_roadmap(roadmap_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True})


@app.route("/api/roadmap/<roadmap_id>", methods=["DELETE"])
def api_roadmap_delete(roadmap_id):
    ok = roadmap_store.delete_roadmap(roadmap_id)
    if not ok:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------------
# Static frontend -- serves the built React app (npm run build output)
# so the whole thing is reachable from ONE server/port. Falls back to
# index.html for any non-API path so React Router's client-side routes
# (e.g. /roadmap, /settings) work on a hard refresh, not just via
# in-app navigation.
# ---------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path.startswith("api/"):
        return jsonify({"error": "not_found"}), 404
    full_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(full_path):
        return send_from_directory(FRONTEND_DIST, path)
    index_path = os.path.join(FRONTEND_DIST, "index.html")
    if not os.path.isfile(index_path):
        return (
            "Study Guard frontend is not built yet. Run 'npm run build' "
            "inside the frontend/ folder, or start it separately with "
            "'npm run dev' during development.",
            503,
        )
    return send_from_directory(FRONTEND_DIST, "index.html")


def run(host: str = "127.0.0.1", port: int = 8000):
    """Entry point called from main.py in a daemon thread. use_reloader
    is always off -- the reloader spawns a second process, which would
    mean a second copy of this whole module (and, transitively, a
    second attempt to read state) running alongside main.py's actual
    monitors; not appropriate for a thread embedded in another app."""
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    # Allows running the API alone against whatever state files already
    # exist on disk (e.g. for frontend development against a previous
    # session's data) without needing the webcam/monitors running.
    # Also what backend/app.py's local `python app.py` fallback uses --
    # HOST/PORT are read from the environment so this behaves the same
    # way under a cloud host (Render sets PORT) as it does locally.
    run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 8000)),
    )
