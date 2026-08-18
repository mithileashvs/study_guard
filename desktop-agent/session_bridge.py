"""
Session control bridge -- lets the web frontend (Live Session page,
via api_server.py) start/pause/resume/end the actual monitoring
session that used to only be startable by running `python main.py` in
a terminal and answering its input() prompts.

Follows the exact same pattern already used throughout this project
for cross-thread/cross-file coordination (live_status.py,
runtime_settings.py, roadmap_store.py): a small JSON file, atomic
overwrite-in-place, best-effort I/O that never raises into a caller on
a hot path. Here the "file" is actually just an in-memory, lock-
protected object, because -- unlike settings/roadmap data, which
survive process restarts -- session control commands only ever make
sense while the ONE long-lived Study Guard process (started by
launcher.py) is alive; there is nothing to persist across a restart.

Ownership:
  - api_server.py (Flask routes, in a daemon thread inside the main
    process) is the only WRITER -- it calls request_start() /
    request_pause() / request_resume() / request_end() in response to
    the Live Session page's actions, and reads current state via
    get_state() to answer GET /api/session/status.
  - main.py's SessionSupervisor is the only actual state-machine
    owner and the only thing that starts/stops the monitor threads --
    it polls this bridge's pending-command queue and drives its own
    session lifecycle from it. This module holds no monitoring logic
    of its own, exactly like runtime_settings.py holds no distraction-
    classification logic of its own.
"""

from __future__ import annotations

import threading
import time

# ---------------------------------------------------------------------
# Commands the web UI can request. The supervisor consumes these from
# a small FIFO queue (usually 0-1 items -- the UI only ever issues one
# action at a time) rather than a single "latest command" slot, so a
# quick double-click can't silently drop the first click's action.
# ---------------------------------------------------------------------
CMD_START = "start"
CMD_PAUSE = "pause"
CMD_RESUME = "resume"
CMD_END = "end"

# Supervisor-reported phases, mirrored to the frontend via
# /api/session/status so LiveSession.jsx can render the right screen
# (idle / calibrating / active / paused / complete) without needing to
# separately infer it from posture/timer state.
PHASE_IDLE = "IDLE"
PHASE_CALIBRATING = "CALIBRATING"
PHASE_ACTIVE = "ACTIVE"
PHASE_PAUSED = "PAUSED"
PHASE_COMPLETE = "COMPLETE"

_lock = threading.Lock()
_command_queue: list[dict] = []

# The supervisor's own last-published snapshot -- written by
# main.SessionSupervisor, read by api_server.py. Deliberately separate
# from the command queue above: commands flow web -> supervisor,
# status flows supervisor -> web, and neither side ever reaches into
# the other's half.
_state = {
    "phase": PHASE_IDLE,
    "duration_seconds": None,
    "remaining_seconds": None,
    "calibration_progress": 0.0,
    "session_id": None,
    "subject": None,
    "study_mode": None,
    "last_summary": None,  # populated on completion: {duration_seconds, focus_seconds, ...}
    "error": None,
    "updated_at": time.time(),
}


def request_start(duration_seconds: int, subject: str = None, mode: str = None,
                   allowed_apps: list = None, extra_keywords: list = None) -> None:
    """Queued by the Live Session page's "START SESSION" action (after
    duration selection). No-ops if a session is already active/paused
    -- the supervisor is the source of truth for whether a start is
    actually valid right now; this just queues the request."""
    with _lock:
        _command_queue.append({
            "cmd": CMD_START,
            "duration_seconds": duration_seconds,
            "subject": subject,
            "mode": mode,
            "allowed_apps": allowed_apps,
            "extra_keywords": extra_keywords,
        })


def request_pause() -> None:
    with _lock:
        _command_queue.append({"cmd": CMD_PAUSE})


def request_resume() -> None:
    with _lock:
        _command_queue.append({"cmd": CMD_RESUME})


def request_end() -> None:
    with _lock:
        _command_queue.append({"cmd": CMD_END})


def pop_commands() -> list:
    """Called once per supervisor loop tick -- drains and returns every
    command queued since the last call, oldest first."""
    with _lock:
        if not _command_queue:
            return []
        drained = list(_command_queue)
        _command_queue.clear()
        return drained


def publish_state(**fields) -> None:
    """Supervisor-only: overwrites the published state with the given
    fields plus a fresh updated_at timestamp. Any field not passed
    keeps its previous value, so the supervisor only needs to pass
    what actually changed this tick."""
    with _lock:
        _state.update(fields)
        _state["updated_at"] = time.time()


def get_state() -> dict:
    """Read-only snapshot for api_server.py. Returns a shallow copy so
    callers can't accidentally mutate the shared dict."""
    with _lock:
        return dict(_state)


def reset_for_tests() -> None:
    """Test-only helper: clears queued commands and resets published
    state back to idle. Never called from application code."""
    with _lock:
        _command_queue.clear()
        _state.update({
            "phase": PHASE_IDLE,
            "duration_seconds": None,
            "remaining_seconds": None,
            "calibration_progress": 0.0,
            "session_id": None,
            "subject": None,
            "study_mode": None,
            "last_summary": None,
            "error": None,
            "updated_at": time.time(),
        })
