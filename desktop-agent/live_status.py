"""
Live status file -- a tiny bridge between the running monitor
(main.py) and the dashboard (dashboard.py), which run as two separate
processes and only ever shared data through session_log.csv before.

session_log.csv is an append-only *event* log (state transitions),
which is exactly right for history but awkward for "what's happening
right now" -- you'd have to replay the whole log to know the current
posture/presence/distraction state. This file adds a single small
JSON snapshot, overwritten in place every poll, purely for that
"right now" view. It changes no detection logic and adds no new
dependency.

Privacy note: same rule as logger.py -- the raw active window title
is reduced to a short label before it's written here, and this file
lives only on disk locally (see .gitignore), never uploaded anywhere.
"""

import json
import os
import time

from config import data_path

STATUS_FILE = data_path("live_state.json")

# Latest webcam frame, written by the SAME posture-tracking loop in
# main.py that already owns the one cv2.VideoCapture for this process
# -- no second capture, no second thread. This is purely an extra
# "save the frame I already have" step on a loop that already reads
# one frame every POSTURE_CHECK_INTERVAL seconds for posture/presence
# detection, so it adds no additional webcam reads and no extra image
# processing. The dashboard (a separate Streamlit process) only ever
# reads this file; it never touches the webcam.
FRAME_FILE = data_path("live_frame.jpg")

# How stale (seconds) the status file can be before the dashboard
# should treat the monitor as no longer running. A couple of missed
# polls shouldn't flip this, so it's a few times the slowest poll
# interval used in main.py.
STALE_AFTER = 12


def write_status(**fields):
    """
    Overwrites the status file with the given fields plus a fresh
    "updated_at" timestamp. Best-effort: a failed write here should
    never interrupt monitoring, so errors are swallowed.
    """
    fields["updated_at"] = time.time()
    try:
        tmp_path = STATUS_FILE + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(fields, f)
        os.replace(tmp_path, STATUS_FILE)  # atomic on POSIX and Windows
    except Exception:
        pass


def read_status():
    """
    Returns the latest status dict, or None if the file doesn't exist,
    is unreadable, or is stale (monitor likely isn't running anymore).
    """
    if not os.path.isfile(STATUS_FILE):
        return None
    try:
        with open(STATUS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if time.time() - data.get("updated_at", 0) > STALE_AFTER:
        return None
    return data


def is_running() -> bool:
    return read_status() is not None


def clear_status():
    """Removes the status file on clean shutdown, so the dashboard
    immediately reflects "monitoring offline" instead of waiting out
    STALE_AFTER. Best-effort, same as write_status."""
    try:
        if os.path.isfile(STATUS_FILE):
            os.remove(STATUS_FILE)
    except Exception:
        pass


def write_frame(frame, quality: int = 70) -> None:
    """
    JPEG-encodes an already-captured frame and atomically overwrites
    FRAME_FILE with it, for the dashboard to read as a static image.

    Deliberately dumb: it does not open the camera (the caller already
    did that), does not run any detection, and does not keep a history
    -- just "here is the most recent frame", same one-file-overwritten-
    in-place approach as write_status(). Best-effort, same as
    write_status(): a failed write here should never interrupt
    monitoring.

    Imported lazily-friendly: cv2 is only needed by callers that
    already depend on it (main.py), so it's imported here rather than
    at module load time, keeping this module importable (e.g. by the
    dashboard) without requiring opencv.
    """
    try:
        import cv2

        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            return
        tmp_path = FRAME_FILE + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(buf.tobytes())
        os.replace(tmp_path, FRAME_FILE)  # atomic on POSIX and Windows
    except Exception:
        pass


def clear_frame() -> None:
    """Removes the frame file on clean shutdown / camera loss, so the
    dashboard doesn't keep showing a stale freeze-frame as if it were
    still live. Best-effort, same as clear_status()."""
    try:
        if os.path.isfile(FRAME_FILE):
            os.remove(FRAME_FILE)
    except Exception:
        pass
