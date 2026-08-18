"""
Runtime settings bridge -- lets the web frontend (via api_server.py,
a separate thread in this same process) change the running session's
allowed sites/apps and extra study keywords without restarting
Study Guard.

Follows the exact same pattern as live_status.py / roadmap_store.py:
one small JSON file, atomic overwrite-in-place, best-effort I/O that
never raises into a caller on the monitoring hot path.

Ownership:
  - api_server.py is the only writer (settings changes come from the
    Settings page).
  - main.py's distraction_monitor loop is the only reader -- it polls
    this file once per WINDOW_CHECK_INTERVAL (the same cadence it
    already uses for roadmap_bridge.get_active_topic_keywords()) and
    folds any change into the live StudySession object in place, the
    same additive/idempotent way sync_roadmap_keywords() already
    works. This never touches DEFAULT_ALLOWED_APPS or config.py --
    only the in-memory session for the session currently running.
"""

from __future__ import annotations

import json
import os

from config import data_path

SETTINGS_FILE = data_path("runtime_settings.json")


def _load_raw() -> dict:
    if not os.path.isfile(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_raw(data: dict) -> bool:
    try:
        tmp_path = SETTINGS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp_path, SETTINGS_FILE)
        return True
    except Exception:
        return False


def get_settings() -> dict:
    """Returns {"allowed_apps": [...], "study_keywords": [...]} using
    empty lists for anything not yet set (nothing has been overridden
    from the frontend yet, so the session's own defaults still hold)."""
    raw = _load_raw()
    return {
        "allowed_apps": raw.get("allowed_apps", []),
        "study_keywords": raw.get("study_keywords", []),
    }


def set_allowed_apps(apps: list) -> dict:
    raw = _load_raw()
    raw["allowed_apps"] = [a.strip() for a in apps if a and a.strip()]
    _save_raw(raw)
    return get_settings()


def set_study_keywords(keywords: list) -> dict:
    raw = _load_raw()
    raw["study_keywords"] = [k.strip() for k in keywords if k and k.strip()]
    _save_raw(raw)
    return get_settings()
