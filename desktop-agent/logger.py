"""
Appends timestamped events to a CSV so you can build a history of
your study sessions -- how much you got distracted, how often you
slouched, how long your sessions ran. dashboard.py reads this file.

Privacy note: only classified, minimal data is ever written here.
No webcam frames, no screenshots, and no raw window titles -- just
event names, a coarse category (e.g. "Youtube"), and durations.
"""

import csv
import os
import uuid
from datetime import datetime
from config import LOG_FILE

# category/value are optional depending on event type -- e.g. a
# DISTRACTION event carries category="Youtube", a BREAK_START carries
# value=<planned duration in seconds>.
_FIELDNAMES = ["timestamp", "session_id", "event", "category", "duration", "value"]


def new_session_id() -> str:
    """Generates a short unique ID to group all events from one session."""
    return uuid.uuid4().hex[:8]


def log_event(session_id: str, event: str, category: str = "", duration: str = "", value: str = ""):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": session_id,
            "event": event,
            "category": category,
            "duration": duration,
            "value": value,
        })
