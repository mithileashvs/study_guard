"""
Study Guard -- standalone cloud backend entry point.

This is a THIN WRAPPER, not a second copy of the API. Study Guard's
API/business logic (api_server.py, roadmap_store.py, scoring.py,
runtime_settings.py, session_bridge.py, live_status.py, ai_coach.py,
config.py, logger.py, and their small dependents) already have no
hard dependency on Windows, a webcam, or a GUI (verified by
inspection -- see the root README's "Architecture" section). Rather
than maintaining a duplicate copy of that code here (which would drift
out of sync with the desktop agent), this file adds ../desktop-agent
to the import path and imports api_server's Flask `app` object
directly, so both deployments always run the exact same code.

What's DIFFERENT about running this way, vs. embedded in main.py on
the desktop:
  - No monitor threads exist in this process, so live_state.json /
    live_frame.jpg never get written here -- /api/status will always
    report {"running": false}, /api/status/frame will always 404, and
    /api/session/* will always report phase "IDLE". That's correct,
    not broken: those features need the desktop agent's actual webcam
    and window-tracking loops, which only exist on the user's PC.
  - Everything that doesn't need local hardware still works normally:
    Roadmap (create/track/quiz), Settings, session History/Analytics
    from any session_log.csv this deployment accumulates on its own,
    and the AI Coach's local rule engine.
  - DATA_DIR (see config.py) should be set to a writable, persistent
    path on whatever host runs this -- see backend/README section in
    the root README for platform-specific notes (e.g. Render's
    persistent disks).

Local run:
    cd backend
    pip install -r requirements.txt
    DATA_DIR=./data python app.py

Production (e.g. Render): gunicorn is used instead, see ./Procfile.
"""

from __future__ import annotations

import os
import sys

_DESKTOP_AGENT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "desktop-agent")
sys.path.insert(0, os.path.abspath(_DESKTOP_AGENT_DIR))

import api_server  # noqa: E402  (import after sys.path setup, intentionally)

# Exposed for gunicorn ("gunicorn app:app") and any other WSGI runner.
app = api_server.app

if __name__ == "__main__":
    api_server.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8000)),
    )
